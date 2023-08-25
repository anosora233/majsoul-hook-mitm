from mitmproxy.websocket import WebSocketMessage
from typing import Dict, Set, List

from liqi import Handler, MsgType
from random import random, randint, choice
from skin import SkinHandler


class ChestHandler(Handler):
    def __init__(self, up_characters: List[int] = [], up_views: List[int] = []) -> None:
        self.up_characters = up_characters
        self.up_views = up_views
        self.count = 10

    def methods(self, type: MsgType) -> Set[str]:
        if type == MsgType.Notify:
            return set()
        if type == MsgType.Req:
            return {
                ".lq.Lobby.openChest",
            }
        if type == MsgType.Res:
            return {
                ".lq.Lobby.openChest",
                ".lq.Lobby.oauth2Login",
                ".lq.Lobby.login",
            }

    def handle(self, flow_msg: WebSocketMessage, parse_obj: Dict) -> bool:
        type = parse_obj["type"]
        data = parse_obj["data"]
        method = parse_obj["method"]

        if method in [".lq.Lobby.oauth2Login", ".lq.Lobby.login"]:
            data["account"]["platform_diamond"][0] = {"id": 100001, "count": 99999}
        elif method == ".lq.Lobby.openChest":
            if type == MsgType.Req:
                self.count = data["count"]

                super().drop(parse_obj=parse_obj)
            elif type == MsgType.Res:
                results = []

                for i in range(0, self.count):
                    rand = random()

                    if rand <= 0.05:
                        if self.up_characters and random() <= 0.2:
                            id = choice(self.up_characters)
                        else:
                            id = randint(200003, SkinHandler.max_charid - 1)
                        results.append({"reward": {"id": id, "count": 1}})
                    elif rand <= 0.20:
                        if self.up_views and random() <= 0.49:
                            id = choice(self.up_views)
                        else:
                            id = randint(305001, 305056)
                        results.append({"reward": {"id": id, "count": 1}})
                    else:
                        results.append({"reward": {"id": 303995, "count": 1}})

                data.update(
                    {
                        "results": results,
                        "total_open_count": self.count,
                        "faith_count": 0,
                    }
                )

        return super().handle(flow_msg, parse_obj)
