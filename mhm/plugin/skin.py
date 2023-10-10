from json import load, dump
from os.path import exists
from os import mkdir
from random import choice, randint
from mitmproxy import http

from mhm.addons import settings, entrance
from mhm.proto.liqi import Handler, MsgType


def _update(dict_a: dict, dict_b: dict, *exclude: str) -> None:
    for key, value in dict_b.items():
        if key not in exclude and key in dict_a:
            dict_a[key] = value


class SkinInfo:
    def __init__(self) -> None:
        # 可用头像框
        usable_frames = {305529, 305537, 305542, 305545, 305551, 305552} | set(
            range(305520, 305524)
        )

        useless_items = {305214, 305314, 305526, 305725} | set(
            range(305501, 305556)
        ).difference(usable_frames)

        useless_titles = {
            600030,
            600043,
            # 600017,
            # 600024,
            # 600025,
            # 600029,
            # 600041,
            # 600044,
        } | set(range(600057, 600064))

        # ============== #
        self.titles = list(set(range(600002, 600082)).difference(useless_titles))
        self.items = [
            {"item_id": i, "stack": 1}
            for i in set(range(305001, 309000)).difference(useless_items)
        ]

        self.path = "account"

        if not exists(self.path):
            mkdir(self.path)


class SkinHandler(Handler):
    MAX_CHARID: int = settings["server"]["max_charid"]

    RANDOM_STAR_CHAR: int = settings["random_star_char"]

    POOL: dict[int, type["SkinHandler"]] = dict()

    GAME_POOL: dict[str, dict[str, any]] = dict()

    INFO = SkinInfo()

    @property
    def views(self) -> dict[str, any]:
        return [
            {
                "type": 0,
                "slot": slot["slot"],
                "item_id_list": [],
                "item_id": choice(slot["item_id_list"])
                if slot["type"]
                else slot["item_id"],
            }
            for slot in self.commonviews["views"][self.commonviews["use"]]["values"]
        ]

    @property
    def avatar_frame(self) -> int:
        for slot in self.commonviews["views"][self.commonviews["use"]]["values"]:
            if slot["slot"] == 5:
                return slot["item_id"]
        return 0

    @property
    def random_star_character(self) -> dict[str, any]:
        return (
            self.get_character(choice(self.characters["character_sort"]))
            if self.characters["character_sort"]
            else self.character
        )

    @property
    def random_character(self) -> dict[str, any]:
        return self.get_character(randint(200001, self.MAX_CHARID - 1))

    @property
    def character(self) -> dict[str, any]:
        return self.get_character(self.characters["main_character_id"])

    @property
    def player(self) -> dict[str, any]:
        (
            player := {
                "views": self.views,
                "character": self.character,
                "avatar_frame": self.avatar_frame,
            }
        ).update(self.account)

        return player

    def __init__(self) -> None:
        self.profile: str = str()
        self.game_uuid: str = str()
        self.original_char: tuple[int, int] = (200001, 400101)

        self.characters: dict[str, any] = {}
        self.commonviews: dict[str, any] = {}

        # default account structure
        self.account: dict[str, any] = {
            "title": 0,
            "nickname": 0,
            "avatar_id": 0,
            "account_id": 0,
            "loading_image": 0,
        }

    def save(self) -> None:
        with open(self.profile, "w", encoding="utf-8") as file:
            dump(
                {
                    "account": self.account,
                    "characters": self.characters,
                    "commonviews": self.commonviews,
                },
                file,
                ensure_ascii=False,
            )

    def read(self) -> None:
        with open(self.profile, "r", encoding="utf-8") as file:
            conf = load(file)

            self.characters = conf.get("characters")
            self.commonviews = conf.get("commonviews")
            self.account.update(
                conf.get("account", {"avatar_id": self.character["skin"]})
            )

            self.update_characters()

    def get_character(self, charid: int) -> dict:
        assert 200000 < charid < self.MAX_CHARID
        return self.characters["characters"][charid - 200001]

    def init_commonviews(self) -> None:
        self.commonviews = {"views": [{}] * 10, "use": 0}
        for i in range(0, 10):
            self.commonviews["views"][i] = {"values": [], "index": i}

    def init_characters(self) -> None:
        self.characters = {
            "characters": [],
            "skins": [],
            "main_character_id": 200001,
            "send_gift_limit": 2,
            "character_sort": [],
            "finished_endings": [],
            "hidden_characters": [],
            "rewarded_endings": [],
            "send_gift_count": 0,
        }

        # 200001 一姬
        # 200002 二姐
        # ......
        # 200075
        for charid in range(200001, self.MAX_CHARID):
            skin = 400000 + (charid - 200000) * 100 + 1
            character = {
                "charid": charid,
                "level": 5,
                "exp": 1,
                "skin": skin,
                "extra_emoji": [],
                "is_upgraded": True,
                "rewarded_level": [],
                "views": [],
            }

            self.characters["characters"].append(character)
            for skin_id in range(skin, skin + 9):
                self.characters["skins"].append(skin_id)

        # 同步原角色皮肤
        self.characters["main_character_id"] = self.original_char[0]
        self.character["skin"] = self.original_char[1]

    def update_characters(self) -> None:
        if len(self.characters["characters"]) == self.MAX_CHARID - 200001:
            return

        for charid in range(
            len(self.characters["characters"]) + 200001, self.MAX_CHARID
        ):
            skin = 400000 + (charid - 200000) * 100 + 1
            character = {
                "charid": charid,
                "level": 5,
                "exp": 1,
                "skin": skin,
                "extra_emoji": [],
                "is_upgraded": True,
                "rewarded_level": [],
                "views": [],
            }

            self.characters["characters"].append(character)
            for skin_id in range(skin, skin + 9):
                self.characters["skins"].append(skin_id)

        self.save()

    def notify_skin(self, charid: int) -> dict:
        return {
            "type": MsgType.Notify,
            "method": ".lq.NotifyAccountUpdate",
            "data": {
                "update": {"character": {"characters": [self.get_character(charid)]}}
            },
        }

    def methods(self, msg_type: MsgType) -> set[str]:
        if msg_type == MsgType.Notify:
            return {
                ".lq.NotifyRoomPlayerUpdate",
                ".lq.NotifyGameFinishRewardV2",
            }
        elif msg_type == MsgType.Req:
            return {
                ".lq.FastTest.authGame",
                ".lq.Lobby.changeMainCharacter",
                ".lq.Lobby.changeCharacterSkin",
                ".lq.Lobby.updateCharacterSort",
                # 加载图
                ".lq.Lobby.setLoadingImage",
                # 头衔
                ".lq.Lobby.useTitle",
                # 装扮
                ".lq.Lobby.saveCommonViews",
                ".lq.Lobby.useCommonView",
            }
        elif msg_type == MsgType.Res:
            return {
                ".lq.FastTest.authGame",
                ".lq.Lobby.fetchAccountInfo",
                ".lq.Lobby.fetchCharacterInfo",
                ".lq.Lobby.createRoom",
                ".lq.Lobby.fetchRoom",
                ".lq.Lobby.joinRoom",
                # 头衔
                ".lq.Lobby.fetchTitleList",
                # 装扮
                ".lq.Lobby.fetchBagInfo",
                ".lq.Lobby.fetchAllCommonViews",
            } | entrance

    def handle(self, flow: http.HTTPFlow, parsed: dict) -> bool:
        data = parsed["data"]
        method = parsed["method"]
        msg_type = parsed["type"]

        # NOTIFY
        if msg_type == MsgType.Notify:
            if method == ".lq.NotifyRoomPlayerUpdate":
                # 房间中添加、减少玩家时修改立绘、头衔
                for player in data["player_list"]:
                    if player["account_id"] in SkinHandler.POOL:
                        object: SkinHandler = SkinHandler.POOL[player["account_id"]]
                        _update(player, object.account)
            elif method == ".lq.NotifyGameFinishRewardV2":
                # 终局结算时，不播放羁绊动画
                data["main_character"] = {"exp": 1, "add": 0, "level": 5}

        # REQUEST
        elif msg_type == MsgType.Req:
            if method == ".lq.FastTest.authGame":
                # 避免多人随机装扮不一致
                self.game_uuid = data["game_uuid"]
            elif method == ".lq.Lobby.changeMainCharacter":
                # 修改主角色时
                self.characters["main_character_id"] = data["character_id"]
                self.account["avatar_id"] = self.character["skin"]
                self.save()

                return super().inject(flow, parsed, {})
            elif method == ".lq.Lobby.changeCharacterSkin":
                # 修改角色皮肤时
                self.get_character(data["character_id"])["skin"] = data["skin"]
                self.account["avatar_id"] = self.character["skin"]
                self.save()

                inject_notify = self.notify_skin(data["character_id"])
                return super().inject(flow, parsed, {}, inject_notify)
            elif method == ".lq.Lobby.updateCharacterSort":
                # 修改星标角色时
                self.characters["character_sort"] = data["sort"]
                self.save()

                return super().inject(flow, parsed, {})
            elif method == ".lq.Lobby.saveCommonViews":
                # 修改装扮时
                self.commonviews["views"][data["save_index"]]["values"] = data["views"]
                self.save()

                return super().inject(flow, parsed, {})
            elif method == ".lq.Lobby.useCommonView":
                # 选择装扮时
                self.commonviews["use"] = data["index"]
                self.save()

                return super().inject(flow, parsed, {})
            elif method == ".lq.Lobby.useTitle":
                # 选择头衔时
                self.account["title"] = data["title"]
                self.save()

                return super().inject(flow, parsed, {})
            elif method == ".lq.Lobby.setLoadingImage":
                # 选择加载图时
                self.account["loading_image"] = data["images"]
                self.save()

                return super().inject(flow, parsed, {})

        # RESPONSE
        elif msg_type == MsgType.Res:
            if method in entrance:
                # 本地配置文件
                self.profile = f"{self.INFO.path}/{data['account_id']}.json"

                # 保存原角色、皮肤、昵称
                avatar_id = data["account"]["avatar_id"]
                character_id = (int)((avatar_id - 400000) / 100 + 200000)
                self.original_char = (character_id, avatar_id)

                # 保存原账户信息
                _update(self.account, data["account"])

                if exists(self.profile):
                    self.read()
                    _update(data["account"], self.account)
                else:
                    self.init_characters()
                    self.init_commonviews()
                    self.save()

                self.POOL[data["account_id"]] = self
            elif method == ".lq.FastTest.authGame":
                # 进入对局时
                if self.game_uuid in self.GAME_POOL:
                    data["players"] = self.GAME_POOL[self.game_uuid]
                else:
                    for player in data["players"]:
                        # 替换头像，角色、头衔
                        if player["account_id"] in self.POOL:
                            object: SkinHandler = self.POOL[player["account_id"]]
                            _update(player, object.player)

                            if self.RANDOM_STAR_CHAR:
                                random_char = object.random_star_character
                                player["character"] = random_char
                                player["avatar_id"] = random_char["skin"]
                        # 其他玩家报菜名，对机器人无效
                        else:
                            player["character"].update(
                                {"level": 5, "exp": 1, "is_upgraded": True}
                            )
                    self.GAME_POOL[self.game_uuid] = data["players"]
            elif method == ".lq.Lobby.fetchAccountInfo":
                # 修改状态面板立绘、头衔
                if data["account"]["account_id"] in self.POOL:
                    object: SkinHandler = self.POOL[data["account"]["account_id"]]
                    _update(data["account"], object.account, "loading_image")
                else:
                    return False
            elif method == ".lq.Lobby.fetchCharacterInfo":
                # 全角色数据替换
                data.update(self.characters)
            elif method == ".lq.Lobby.fetchAllCommonViews":
                # 装扮本地数据替换
                data.update(self.commonviews)
            elif method == ".lq.Lobby.fetchBagInfo":
                # 添加物品
                data["bag"]["items"].extend(self.INFO.items)
            elif method == ".lq.Lobby.fetchTitleList":
                # 添加头衔
                data["title_list"] = self.INFO.titles
            elif method in [
                ".lq.Lobby.joinRoom",
                ".lq.Lobby.fetchRoom",
                ".lq.Lobby.createRoom",
            ]:
                # 在加入、获取、创建房间时修改己方头衔、立绘、角色
                if str("room") not in data:
                    return False
                for person in data["room"]["persons"]:
                    if person["account_id"] in self.POOL:
                        object: SkinHandler = self.POOL[person["account_id"]]
                        _update(person, object.account)

        return True
