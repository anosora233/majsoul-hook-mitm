from typing import Dict, List
from json import load, dump
from os.path import exists
from os import mkdir

SKIN_METHODS = {
    "notify": [
        ".lq.NotifyRoomPlayerUpdate",
        ".lq.NotifyGameFinishRewardV2",
        ".lq.NotifyAccountUpdate",
    ],
    "req": [
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
    ],
    "res": [
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
    ],
}


class FakeDataHandler:
    def __init__(self) -> None:
        self.profile_path = "profile"
        self.profile = "error.json"

        if not exists(self.profile_path):
            mkdir(self.profile_path)

        self.account_id = 101000000
        self.avatar_id = 400101
        self.character_id = 200001
        self.title = 0
        self.loading_image = []
        self.commonviews = {"views": [{}] * 10, "use": 0}
        self.characters = []

        self.fake_slot = False
        self.last_charid = 200001

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
        else:
            self.init_characters()

    def get_character(self, charid: int) -> Dict:
        for char in self.characters["characters"]:
            if char["charid"] == charid:
                return char

    def init_commonviews(self) -> None:
        for i in range(0, 10):
            self.commonviews["views"][i] = {
                "values": [{"slot": 8, "item_id": 0, "type": 0, "item_id_list": []}],
                "index": i,
            }

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
        for charid in range(200001, 200076):
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

    def fake_character(self):
        if self.fake_slot:
            self.fake_slot = False
            return 200001, 400101
        else:
            self.fake_slot = True
            return 200002, 400201

    def fake_views_data(self):
        return {
            "views": [{"slot": 8, "item_id": 0, "type": 0, "item_id_list": []}],
            "save_index": 9,
            "is_use": 0,
        }

    def skin_handle(self, method: str, data: Dict) -> Dict:
        # NOTIFY
        if method == ".lq.NotifyRoomPlayerUpdate":
            # 房间中添加、减少玩家时修改立绘
            for i in range(0, len(data["player_list"])):
                if data["player_list"][i]["account_id"] == self.account_id:
                    data["player_list"][i]["avatar_id"] = self.avatar_id
        elif method == ".lq.NotifyGameFinishRewardV2":
            # 终局结算时，不播放羁绊动画
            data["main_character"] = {"exp": 1, "add": 0, "level": 5}
        elif method == ".lq.NotifyAccountUpdate":
            # 修改角色皮肤时
            if "character" in data["update"]:
                for i in range(0, len(data["update"]["character"]["characters"])):
                    data["update"]["character"]["characters"][i] = self.get_character(
                        self.last_charid
                    )

        # REQUEST
        if method == ".lq.Lobby.changeMainCharacter":
            # 修改主角色时存储，并用一姬、二姐替代
            self.character_id = data["character_id"]
            self.characters["main_character_id"] = self.character_id
            self.avatar_id = self.get_character(self.character_id)["skin"]
            self.save()

            data["character_id"], _ = self.fake_character()
        elif method == ".lq.Lobby.changeCharacterSkin":
            # 修改角色皮肤时存储，并用一姬、二姐替代
            self.get_character(data["character_id"])["skin"] = data["skin"]
            self.avatar_id = self.get_character(self.character_id)["skin"]
            self.last_charid = data["character_id"]
            self.save()

            data["character_id"], data["skin"] = self.fake_character()
        elif method == ".lq.Lobby.updateCharacterSort":
            # 修改星标角色时存储，并用一姬、二姐替代
            self.characters["character_sort"] = data["sort"]
            self.save()

            data["sort"] = [self.fake_character()[0]]
        elif method == ".lq.Lobby.saveCommonViews":
            # 修改装扮时存储，并替换原数据
            self.commonviews["views"][data["save_index"]]["values"] = data["views"]
            self.save()

            data = self.fake_views_data()
        elif method == ".lq.Lobby.useCommonView":
            # 选择装扮时存储，并替换原数据
            self.commonviews["use"] = data["index"]
            self.save()

            data["index"] = 9
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
                self.avatar_id = data["account"]["avatar_id"]
                self.character_id = (int)((self.avatar_id - 400000) / 100 + 200000)

                self.characters["main_character_id"] = self.character_id
                self.get_character(self.character_id)["skin"] = self.avatar_id
                self.save()
            # 修改立绘、头衔、加载图
            data["account"]["avatar_id"] = self.avatar_id
            data["account"]["title"] = self.title
            data["account"]["loading_image"] = self.loading_image
        elif method == ".lq.Lobby.fetchCharacterInfo":
            # 全角色数据替换
            data = self.characters
        elif method == ".lq.FastTest.authGame":
            # 进入对局时
            for i in range(0, len(data["players"])):
                # 替换己方头像，角色
                if data["players"][i]["account_id"] == self.account_id:
                    data["players"][i]["avatar_id"] = self.avatar_id
                    data["players"][i]["character"] = self.get_character(
                        self.character_id
                    )
                    # 应用装扮
                    data["players"][i]["views"] = self.commonviews["views"][
                        self.commonviews["use"]
                    ]["values"]
                    # 应用头衔
                    data["players"][i]["title"] = self.title
                # 其他玩家报菜名，对机器人无效
                else:
                    data["players"][i]["character"]["level"] = 5
                    data["players"][i]["character"]["exp"] = 1
                    data["players"][i]["character"]["is_upgraded"] = True
        elif method == ".lq.Lobby.fetchAccountInfo":
            # 修改状态面板立绘、头衔
            if data["account"]["account_id"] == self.account_id:
                data["account"]["avatar_id"] = self.avatar_id
                data["account"]["title"] = self.title
        elif method == ".lq.Lobby.fetchAllCommonViews":
            # 装扮本地数据替换
            data = self.commonviews
        elif method == ".lq.Lobby.fetchBagInfo":
            # 添加全部装扮
            items = []
            removed_items = [
                305214,
                305314,
                305525,
                305526,
                305533,
                305539,
                305546,
                305501,
                305555,
            ]
            for i in range(305001, 308000):
                if i not in removed_items:
                    items.append({"item_id": i, "stack": 1})
            data["bag"]["items"].extend(items)
        elif method == ".lq.Lobby.fetchTitleList":
            # 添加部分有效头衔
            title_list = []
            removed_title = [
                600017,
                600024,
                600025,
                600029,
                600030,
                600041,
                600043,
                600044,
            ]
            for i in range(600047, 600001, -1):
                if i not in removed_title:
                    title_list.append(i)
            data["title_list"] = title_list
        elif method in [
            ".lq.Lobby.joinRoom",
            ".lq.Lobby.fetchRoom",
            ".lq.Lobby.createRoom",
        ]:
            # 在加入、获取、创建房间时修改己方头衔、立绘、角色
            for i in range(0, len(data["room"]["persons"])):
                if data["room"]["persons"][i]["account_id"] == self.account_id:
                    data["room"]["persons"][i]["title"] = self.title
                    data["room"]["persons"][i]["avatar_id"] = self.avatar_id
                    data["room"]["persons"][i]["character"] = self.get_character(
                        self.character_id
                    )

        return data
