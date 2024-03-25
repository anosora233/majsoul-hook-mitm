import random

from mhm.addon import MessageProcessor
from mhm.hook import Hook
from mhm.protocol import GameMessageType
from mhm.resource import ResourceManager


def rewards(mapChest: dict, count: int, id: int):
    rewards = []
    # HACK: This lottery algorithm lacks a reward for the worst result
    if id not in mapChest:
        id = -999
    for _i in range(0, count):
        aRandom, bRandom = random.random(), random.random()
        for (aPb, aPool), (bPb, bPool) in mapChest[id]:
            if aRandom < aPb:
                rewards.append(random.choice(bPool if bRandom < bPb else aPool))
                break
    return [{"reward": {"id": id, "count": 1}} for id in rewards]


def chest(mapChest: dict, count: int, id: int):
    return {
        "results": rewards(mapChest, count, id),
        "total_open_count": count,
    }


class EstHook(Hook):
    def __init__(self, resger: ResourceManager) -> None:
        super().__init__()

        aChars = [m["charid"] for m in resger.character_rows]
        nViews = sorted(set(range(305001, 305056)).difference({305043, 305047}))
        gGifts = sorted(range(303012, 303090, 10))
        bGifts = sorted(range(303013, 303090, 10))
        # TODO: Should attempt to read the game chest info from `lqc.lqbin`
        self.mapChest = {
            1005: [
                [(0.05, aChars), (0.2, [200076])],
                [(0.2, nViews), (0, [])],
                [(1, gGifts), (0.0625, bGifts)],
            ],
            -999: [
                [(0.05, aChars), (0, [])],
                [(0.2, nViews), (0, [])],
                [(1, gGifts), (0.0625, bGifts)],
            ],
        }

        @self.bind(GameMessageType.Response, ".lq.Lobby.login")
        @self.bind(GameMessageType.Response, ".lq.Lobby.emailLogin")
        @self.bind(GameMessageType.Response, ".lq.Lobby.oauth2Login")
        @self.bind(GameMessageType.Response, ".lq.Lobby.fetchAccountInfo")
        def _(mp: MessageProcessor):
            mp.data["account"]["platform_diamond"] = [{"id": 100001, "count": 66666}]
            mp.amend()

        @self.bind(GameMessageType.Request, ".lq.Lobby.openChest")
        def _(mp: MessageProcessor):
            data = chest(self.mapChest, mp.data["count"], mp.data["chest_id"])
            mp.response(data)
