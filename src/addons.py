from typing import Dict
from mitmproxy import http
from liqi import LQPROTO, MsgType
from os.path import exists
from mitmproxy.websocket import WebSocketMessage

from rich.logging import RichHandler
from rich import print

import os
import json
import logging

logging.basicConfig(
    level=logging.root.getEffectiveLevel(),
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)


def init_version():
    import requests
    import random

    rand_var_a: int = random.randint(0, 1e9)
    rand_var_b: int = random.randint(0, 1e9)

    ver_url = f"https://game.maj-soul.com/1/version.json?randv={rand_var_a}{rand_var_b}"
    response = requests.get(ver_url, proxies={"https": settings["upstream_proxy"]})
    response.raise_for_status()
    ver_data = response.json()

    server = settings.get("server")
    if not server or server["version"] != ver_data["version"]:
        res_url = f"https://game.maj-soul.com/1/resversion{ver_data['version']}.json"
        response = requests.get(res_url, proxies={"https": settings["upstream_proxy"]})
        response.raise_for_status()
        res_data = response.json()

        max_charid = 200070
        while str(f"extendRes/emo/e{max_charid}/0.png") in res_data["res"]:
            max_charid += 1

        settings["server"] = {"version": ver_data["version"], "max_charid": max_charid}


def init_player(login_id: str) -> Dict:
    handlers = []
    if settings["enable_skins"]:
        handlers.append(__import__("skin").SkinHandler())
    if settings["enable_aider"]:
        handlers.append(__import__("aider").AiderHandler())
    return {"conn_ids": [login_id], "handlers": handlers}


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
                        modify = handler.handle(flow_msg=flow_msg, parse_obj=parse_obj)

                        if modify:
                            logger.info("---->> Modified Websocket Message <<----")
                            logger.info(parse_obj)

    def terminate_conn(self, conn_id: str):
        for player in self.players.values():
            if conn_id in player["conn_ids"]:
                player["conn_ids"].remove(conn_id)

    def websocket_message(self, flow: http.HTTPFlow):
        assert flow.websocket is not None
        message = flow.websocket.messages[-1]

        try:
            parse_obj = self.proto.parse(message)
        except:
            logger.warning("---->> Unsupported Websocket Message <<----")
            logger.warning(__import__("traceback").format_exc())

            return

        if message.from_client:
            logger.debug(f"[{flow.client_conn.id[:13]}] -->> {parse_obj}")
        else:
            logger.debug(f"[{flow.client_conn.id[:13]}] <<-- {parse_obj}")

        if (
            parse_obj["method"] in {".lq.Lobby.oauth2Login", ".lq.Lobby.login"}
            and parse_obj["type"] == MsgType.Res
        ):
            account_id = parse_obj["data"]["account_id"]

            if account_id == 0:
                return
            elif account_id in self.players:
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
            logger.debug(f"[{account_id}] : {value['conn_ids']}")

        self.invoke(flow.client_conn.id, flow_msg=message, parse_obj=parse_obj)

    def websocket_error(self, flow: http.HTTPFlow):
        self.terminate_conn(flow.client_conn.id)

    def websocket_end(self, flow: http.HTTPFlow):
        self.terminate_conn(flow.client_conn.id)


settings = {
    "dumper": False,
    "log_level": "info",
    "listen_port": 23410,
    "enable_skins": False,
    "enable_aider": False,
    "upstream_proxy": None,
    "pure_python_protobuf": False,
}

if not exists("settings.json"):
    json.dump(settings, open("settings.json", "w"), indent=2)
    print("---->> Initialize Configuration <<----\n", json.dumps(settings, indent=2))
    input("Press Enter to exit ... ")
    raise SystemExit

settings.update(json.load(open("settings.json", "r")))

if settings["enable_skins"]:
    init_version()
if settings["pure_python_protobuf"]:
    os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

json.dump(settings, open("settings.json", "w"), indent=2)
print("---->> Load Configuration <<----\n", json.dumps(settings, indent=2))

addons = [WebSocketAddon()]
logger = logging.getLogger(__name__)
logger.setLevel(settings["log_level"].upper())
