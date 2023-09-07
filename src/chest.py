from mitmproxy.websocket import WebSocketMessage
from typing import Dict, Set, List

from liqi import Handler, MsgType
from random import random, randint, choice
from skin import SkinHandler

DEFAULT_CHEST = [
    # CHARACTERS
    (0.05, list(range(200003, SkinHandler.MAX_CHARID - 1))),
    # VIEWS
    (0.2, list(set(range(305001, 305056)).difference({305047}))),
    # GIFTS
    (1, list(range(303012, 303090, 10))),
]

UP_GIFTS = (0.0625, list(range(303013, 303090, 10)))

CHEST_DFLT = [
    (0, []),
    (0, []),
    UP_GIFTS,
]

CHEST_1005 = [
    (0.2, [200076]),
    (0, []),
    UP_GIFTS,
]

CHESTS = {
    1005: CHEST_1005,
    -999: CHEST_DFLT,
}


class ChestHandler(Handler):
    def __init__(self) -> None:
        self.count: int = 10
        self.chest_id: int = -999

    @property
    def results(self):
        return [{"reward": {"id": id, "count": 1}} for id in self.rewards]

    @property
    def rewards(self):
        assert CHESTS[self.chest_id]
        assert self.count > 0

        rewards = []

        for i in range(0, self.count):
            random_a = random()
            random_b = random()

            for m in range(0, len(DEFAULT_CHEST)):
                prob_a, pool_a = DEFAULT_CHEST[m]
                if random_a < prob_a:
                    prob_b, pool_b = CHESTS[self.chest_id][m]
                    rewards.append(choice(pool_b if random_b < prob_b else pool_a))
                    break

        return rewards

    def methods(self, msg_type: MsgType) -> Set[str]:
        if msg_type == MsgType.Notify:
            return set()
        if msg_type == MsgType.Req:
            return {
                ".lq.Lobby.openChest",
            }
        if msg_type == MsgType.Res:
            return {
                ".lq.Lobby.fetchAccountInfo",
                ".lq.Lobby.oauth2Login",
                ".lq.Lobby.login",
                ".lq.Lobby.openChest",
            }

    def handle(self, flow_msg: WebSocketMessage, parse_obj: Dict) -> bool:
        msg_type = parse_obj["type"]
        data = parse_obj["data"]
        method = parse_obj["method"]

        if method in [
            ".lq.Lobby.oauth2Login",
            ".lq.Lobby.login",
            ".lq.Lobby.fetchAccountInfo",
        ]:
            if data["account"]["account_id"] in SkinHandler.POOL:
                data["account"]["platform_diamond"] = [{"id": 100001, "count": 66666}]
            else:
                return False

        elif method == ".lq.Lobby.openChest":
            if msg_type == MsgType.Res:
                data.update(
                    {
                        "results": self.results,
                        "total_open_count": self.count,
                    }
                )
            elif msg_type == MsgType.Req:
                self.count = data["count"]
                self.chest_id = data["chest_id"] if data["chest_id"] in CHESTS else -999

                super().drop(parse_obj=parse_obj)

        return super().handle(flow_msg, parse_obj)
