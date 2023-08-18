from mitmproxy.websocket import WebSocketMessage
from typing import Dict, List, Any, Type, Tuple
from json import load, dump
from os.path import exists
from os import mkdir
from random import choice
from liqi import Handler, MsgType


class SkinHandler(Handler):
    fake_pool: Dict[int, Type["SkinHandler"]] = {}

    available_frame = {
        305510,
        305529,
        305537,
        305542,
        305545,
        305551,
        305552,
        305554,
    } | set(range(305520, 305524))

    removed_items = set(range(305501, 305556)).difference(available_frame) | {
        305214,
        305314,
        305526,
        305725,
    }

    removed_title = {
        600017,
        600024,
        600025,
        600029,
        600030,
        600041,
        600043,
        600044,
    }

    def __init__(self) -> None:
        self.profile_path: str = "profile"
        self.profile: str = "error.json"

        if not exists(self.profile_path):
            mkdir(self.profile_path)

        self.max_charid: int = load(open("version.json", "r"))["max_charid"]

        self.title: int = 0
        self.account_id: int = 101000000
        self.avatar_id: int = 400101
        self.character_id: int = 200001
        self.loading_image: List[int] = []
        self.commonviews: Dict[str, Any] = {"views": [{}] * 10, "use": 0}
        self.characters: Dict[str, Any] = {}

        self.origin_char: Tuple[int, int] = (200001, 400101)
        self.last_charid: int = 200001

    def save(self) -> None:
        dump(
            {
                "title": self.title,
                "loading_image": self.loading_image,
                "characters": self.characters,
                "commonviews": self.commonviews,
            },
            open(self.profile, "w"),
        )

    def read(self) -> None:
        profile_data = load(open(self.profile, "r"))

        if str("title") in profile_data:
            self.title = profile_data["title"]
        if str("loading_image") in profile_data:
            self.loading_image = profile_data["loading_image"]
        if str("commonviews") in profile_data:
            self.commonviews = profile_data["commonviews"]
        if str("characters") in profile_data:
            self.characters = profile_data["characters"]
            self.character_id = self.characters["main_character_id"]
            self.avatar_id = self.get_character(self.character_id)["skin"]
            self.update_characters()
        else:
            self.init_characters()

    def get_character(self, charid: int) -> Dict:
        for char in self.characters["characters"]:
            if char["charid"] == charid:
                return char

    def get_views(self) -> Dict:
        views = self.commonviews["views"][self.commonviews["use"]]["values"].copy()
        for slot in views:
            if slot["type"]:
                slot["item_id"] = choice(slot["item_id_list"])
                slot["type"], slot["item_id_list"] = 0, []
        return views

    def init_commonviews(self) -> None:
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
        for charid in range(200001, self.max_charid):
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

    def update_characters(self) -> None:
        if len(self.characters["characters"]) == self.max_charid - 200001:
            return

        for charid in range(
            len(self.characters["characters"]) + 200001, self.max_charid
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

    def methods(self, type: MsgType) -> List:
        if type == MsgType.Notify:
            return [
                ".lq.NotifyRoomPlayerUpdate",
                ".lq.NotifyGameFinishRewardV2",
                ".lq.NotifyAccountUpdate",
            ]
        elif type == MsgType.Req:
            return [
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
            ]
        elif type == MsgType.Res:
            return [
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
                # 登录
                ".lq.Lobby.oauth2Login",
                ".lq.Lobby.login",
            ]

    def handle(self, flow_msg: WebSocketMessage, parse_obj: Dict) -> bool:
        type = parse_obj["type"]
        data = parse_obj["data"]
        method = parse_obj["method"]

        # NOTIFY
        if type == MsgType.Notify:
            if method == ".lq.NotifyRoomPlayerUpdate":
                # 房间中添加、减少玩家时修改立绘、头衔
                for player in data["player_list"]:
                    if player["account_id"] in self.fake_pool:
                        object: SkinHandler = self.fake_pool[player["account_id"]]
                        player["title"] = object.title
                        player["avatar_id"] = object.avatar_id
            elif method == ".lq.NotifyGameFinishRewardV2":
                # 终局结算时，不播放羁绊动画
                data["main_character"] = {"exp": 1, "add": 0, "level": 5}
            elif method == ".lq.NotifyAccountUpdate":
                # 修改角色皮肤时
                if str("character") in data["update"]:
                    for character in data["update"]["character"]["characters"]:
                        character.update(self.get_character(self.last_charid))
        # REQUEST
        elif type == MsgType.Req:
            if method == ".lq.Lobby.changeMainCharacter":
                # 修改主角色时存储，并替换原数据
                self.character_id = data["character_id"]
                self.characters["main_character_id"] = self.character_id
                self.avatar_id = self.get_character(self.character_id)["skin"]
                self.save()

                data["character_id"], _ = self.origin_char
            elif method == ".lq.Lobby.changeCharacterSkin":
                # 修改角色皮肤时存储，并替换原数据
                self.get_character(data["character_id"])["skin"] = data["skin"]
                self.avatar_id = self.get_character(self.character_id)["skin"]
                self.last_charid = data["character_id"]
                self.save()

                data["character_id"], data["skin"] = self.origin_char
            elif method == ".lq.Lobby.updateCharacterSort":
                # 修改星标角色时存储，并替换原数据
                self.characters["character_sort"] = data["sort"]
                self.save()

                data["sort"] = [self.origin_char[0]]
            elif method == ".lq.Lobby.saveCommonViews":
                # 修改装扮时存储，并替换原数据
                self.commonviews["views"][data["save_index"]]["values"] = data["views"]
                self.save()

                data.update({"views": [], "save_index": 9, "is_use": 0})
            elif method == ".lq.Lobby.useCommonView":
                # 选择装扮时存储，并替换原数据
                self.commonviews["use"] = data["index"]
                self.save()

                data["index"] = 0
            elif method == ".lq.Lobby.useTitle":
                # 选择头衔时存储，并替换原数据
                self.title = data["title"]
                self.save()

                data["title"] = 0
            elif method == ".lq.Lobby.setLoadingImage":
                # 选择加载图时存储，并替换原数据
                self.loading_image = data["images"]
                self.save()

                data["images"] = []
        # RESPONSE
        elif type == MsgType.Res:
            if method in [".lq.Lobby.oauth2Login", ".lq.Lobby.login"]:
                # 创建本地数据
                self.account_id = data["account_id"]
                self.profile = f"{self.profile_path}/{self.account_id}.json"

                if exists(self.profile):
                    self.read()
                else:
                    # 生成数据信息
                    self.init_commonviews()
                    self.init_characters()

                    avatar_id = data["account"]["avatar_id"]
                    character_id = (int)((self.avatar_id - 400000) / 100 + 200000)
                    self.origin_char = (character_id, avatar_id)
                    self.save()
                # 修改立绘、头衔、加载图
                data["account"]["avatar_id"] = self.avatar_id
                data["account"]["title"] = self.title
                data["account"]["loading_image"] = self.loading_image

                self.fake_pool[self.account_id] = self
            elif method == ".lq.Lobby.fetchCharacterInfo":
                # 全角色数据替换
                data.update(self.characters)
            elif method == ".lq.FastTest.authGame":
                # 进入对局时
                for player in data["players"]:
                    # 替换头像，角色、头衔
                    if player["account_id"] in self.fake_pool:
                        object: SkinHandler = self.fake_pool[player["account_id"]]
                        player["title"] = object.title
                        player["avatar_id"] = object.avatar_id
                        player["character"] = object.get_character(object.character_id)
                        player["views"] = object.get_views()
                    # 其他玩家报菜名，对机器人无效
                    else:
                        player["character"]["level"] = 5
                        player["character"]["exp"] = 1
                        player["character"]["is_upgraded"] = True
            elif method == ".lq.Lobby.fetchAccountInfo":
                # 修改状态面板立绘、头衔
                if data["account"]["account_id"] in self.fake_pool:
                    object: SkinHandler = self.fake_pool[data["account"]["account_id"]]
                    data["account"]["avatar_id"] = object.avatar_id
                    data["account"]["title"] = object.title
            elif method == ".lq.Lobby.fetchAllCommonViews":
                # 装扮本地数据替换
                data.update(self.commonviews)
            elif method == ".lq.Lobby.fetchBagInfo":
                # 添加全部装扮
                items = []
                for i in range(305001, 309000):
                    if i not in self.removed_items:
                        items.append({"item_id": i, "stack": 1})
                data["bag"]["items"].extend(items)
            elif method == ".lq.Lobby.fetchTitleList":
                # 添加部分有效头衔
                title_list = []
                for i in range(600047, 600001, -1):
                    if i not in self.removed_title:
                        title_list.append(i)
                data["title_list"] = title_list
            elif method in [
                ".lq.Lobby.joinRoom",
                ".lq.Lobby.fetchRoom",
                ".lq.Lobby.createRoom",
            ]:
                # 在加入、获取、创建房间时修改己方头衔、立绘、角色
                if str("room") in data:
                    for person in data["room"]["persons"]:
                        if person["account_id"] in self.fake_pool:
                            object: SkinHandler = self.fake_pool[person["account_id"]]
                            person["title"] = object.title
                            person["avatar_id"] = object.avatar_id
                            person["character"] = object.get_character(
                                object.character_id
                            )

        return super().handle(flow_msg, parse_obj)
