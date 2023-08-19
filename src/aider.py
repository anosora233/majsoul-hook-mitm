from mitmproxy.websocket import WebSocketMessage
from typing import Dict, Set
from os import system
from requests import post
from liqi import Handler, MsgType

from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
from socket import socket, AF_INET, SOCK_STREAM

disable_warnings(InsecureRequestWarning)


class AiderHandler(Handler):
    port: int = 23330
    actions: Set[str] = {
        "ActionNewRound",
        "ActionDealTile",
        "ActionAnGangAddGang",
        "ActionChiPengGang",
        "ActionNoTile",
        "ActionHule",
        "ActionBaBei",
        "ActionLiuJu",
        "ActionUnveilTile",
        "ActionHuleXueZhanMid",
        "ActionGangResult",
        "ActionRevealTile",
        "ActionChangeTile",
        "ActionSelectGap",
        "ActionLiqi",
        "ActionDiscardTile",
        "ActionHuleXueZhanEnd",
        "ActionNewCard",
        "ActionGangResultEnd",
    }

    def __init__(self) -> None:
        with socket(AF_INET, SOCK_STREAM) as s:
            s.settimeout(0.02)
            if s.connect_ex(("127.0.0.1", self.port)) != 0:
                cmd = f'start cmd /c "title Console · 🀄 && bin\\console.exe -majsoul -p {self.port}"'
                system(cmd)

        self.api = f"https://127.0.0.1:{self.port}"
        self.__class__.port += 1

    def methods(self, type: MsgType) -> Set[str]:
        if type == MsgType.Notify:
            return {
                ".lq.NotifyPlayerLoadGameReady",
                ".lq.ActionPrototype",
            }
        if type == MsgType.Req:
            return set()
        if type == MsgType.Res:
            return {
                ".lq.FastTest.authGame",
                ".lq.FastTest.syncGame",
                ".lq.Lobby.fetchFriendList",
                ".lq.Lobby.fetchGameRecordList",
                ".lq.Lobby.oauth2Login",
                ".lq.Lobby.login",
            }

    def handle(self, flow_msg: WebSocketMessage, parse_obj: Dict) -> bool:
        data = parse_obj["data"]
        method = parse_obj["method"]

        # Thanks to Avenshy
        if method == ".lq.ActionPrototype":
            if data["name"] not in self.actions:
                return False
            elif data["name"] == "ActionNewRound":
                data["data"]["md5"] = data["data"]["sha256"][:32]
            msg = data["data"]
        elif method == ".lq.FastTest.syncGame":
            for action in data["game_restore"]["actions"]:
                if action["name"] == "ActionNewRound":
                    action["data"]["md5"] = action["data"]["sha256"][:32]
            msg = {"sync_game_actions": data["game_restore"]["actions"]}
        else:
            msg = data

        post(self.api, json=msg, verify=False)

        return False
