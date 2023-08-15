from typing import Dict, Any
from mitmproxy import http, ctx
from liqi import LQPROTO, MsgType
from os.path import exists
from mitmproxy.websocket import WebSocketMessage

import os
import json


def obtain_max_charid():
    import requests
    import random

    rand_var_a: int = random.randint(0, 1e9)
    rand_var_b: int = random.randint(0, 1e9)

    ver_url = f"https://game.maj-soul.com/1/version.json?randv={rand_var_a}{rand_var_b}"
    response = requests.get(ver_url, proxies={"https": SETTINGS["upstream_proxy"]})
    response.raise_for_status()
    ver_data = response.json()

    if exists("version.json"):
        res_data = json.load(open("version.json", "r"))
        if res_data["version"] == ver_data["version"]:
            return

    res_url = f"https://game.maj-soul.com/1/resversion{ver_data['version']}.json"
    response = requests.get(res_url, proxies={"https": SETTINGS["upstream_proxy"]})
    response.raise_for_status()
    res_data = response.json()

    max_charid = 200070
    while str(f"extendRes/emo/e{max_charid}/0.png") in res_data["res"]:
        max_charid += 1

    json.dump(
        {
            "version": ver_data["version"],
            "max_charid": max_charid,
        },
        open("version.json", "w"),
        indent=2,
    )


def init_player(login_id: str) -> Dict:
    handlers = []

    if SETTINGS["enable_skins"]:
        handlers.append(__import__("skin").SkinHandler())
    if SETTINGS["enable_helper"]:
        pass

    return {
        "conn_ids": [login_id],
        "handlers": handlers,
    }


class WebSocketAddon:
    def __init__(self) -> None:
        self.proto = LQPROTO()
        self.players = {}

    def invoke(self, conn_id: str, flow_msg: WebSocketMessage, parse_obj: Dict):
        type = parse_obj["type"]
        method = parse_obj["method"]

        for player in self.players.values():
            if conn_id in player["conn_ids"]:
                for handler in player["handlers"]:
                    if method in handler.methods(type):
                        handler.handle(flow_msg=flow_msg, parse_obj=parse_obj)

    def terminate_conn(self, conn_id: str):
        for player in self.players.values():
            if conn_id in player["conn_ids"]:
                player["conn_ids"].remove(conn_id)

    def websocket_message(self, flow: http.HTTPFlow):
        assert flow.websocket is not None
        message = flow.websocket.messages[-1]
        parse_obj = self.proto.parse(message)

        if (
            parse_obj["method"] in [".lq.Lobby.oauth2Login", ".lq.Lobby.login"]
            and parse_obj["type"] == MsgType.Res
        ):
            account_id = parse_obj["data"]["account_id"]

            if account_id in self.players:
                self.players[account_id]["conn_ids"].append(flow.client_conn.id)
            else:
                self.players[account_id] = init_player(flow.client_conn.id)

        elif (
            parse_obj["method"] == ".lq.FastTest.authGame"
            and parse_obj["type"] == MsgType.Req
        ):
            account_id = parse_obj["data"]["account_id"]
            assert account_id in self.players
            self.players[account_id]["conn_ids"].append(flow.client_conn.id)

        for account_id, value in self.players.items():
            ctx.log.warn(f"{account_id}: {value['conn_ids']}")

        self.invoke(flow.client_conn.id, flow_msg=message, parse_obj=parse_obj)

        if message.from_client:
            ctx.log.warn(f"[{flow.client_conn.id[:13]}]-->>: {parse_obj}")
        else:
            ctx.log.warn(f"[{flow.client_conn.id[:13]}]<<--: {parse_obj}")

    def websocket_error(self, flow: http.HTTPFlow):
        self.terminate_conn(flow.client_conn.id)

    def websocket_end(self, flow: http.HTTPFlow):
        self.terminate_conn(flow.client_conn.id)


SETTINGS: Dict[str, Any] = json.load(open("settings.json", "r"))

if SETTINGS["enable_skins"]:
    obtain_max_charid()
if SETTINGS["pure_python_protobuf"]:
    os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

addons = [WebSocketAddon()]
