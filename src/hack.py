from typing import Dict, List
from json import load, dump
from os.path import exists
from os import mkdir


class SkinHanlder:
    notify = [
        ".lq.NotifyRoomPlayerUpdate",
        ".lq.NotifyGameFinishRewardV2",
        ".lq.NotifyAccountUpdate",
    ]
    req = [
        ".lq.Lobby.changeMainCharacter",
        ".lq.Lobby.changeCharacterSkin",
        ".lq.Lobby.updateCharacterSort",
    ]
    res = [
        ".lq.Lobby.fetchCharacterInfo",
        ".lq.Lobby.createRoom",
        ".lq.FastTest.authGame",
        ".lq.Lobby.fetchRoom",
        ".lq.Lobby.joinRoom",
        ".lq.Lobby.oauth2Login",  # MAIN
        ".lq.Lobby.login",  # MAIN
        ".lq.Lobby.fetchAccountInfo",
        ".lq.Lobby.fetchBagInfo",
    ]

    def __init__(self) -> None:
        self.profile = "profile"

        self.account_id = 101000000
        self.avatar_id = 400101
        self.character_id = 200001

        self.fake_slot = False
        self.last_charid = 200001

        if exists(self.profile):
            self.read()

    def save(self) -> None:
        dump(
            self.characters,
            open(f"{self.profile}/characters.json", "w"),
        )

    def read(self) -> None:
        self.characters = load(open(f"{self.profile}/characters.json", "r"))
        self.character_id = self.characters["main_character_id"]
        self.avatar_id = self.get_character(self.character_id)["skin"]

    def get_character(self, charid: int) -> Dict:
        for char in self.characters["characters"]:
            if char["charid"] == charid:
                return char

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

    def handler(self, method: str, data: Dict) -> Dict:
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
            # 修改主角色时保存本地，并用一姬、二姐替代
            self.character_id = data["character_id"]
            self.characters["main_character_id"] = self.character_id
            self.avatar_id = self.get_character(self.character_id)["skin"]
            self.save()

            data["character_id"], _ = self.fake_character()
        elif method == ".lq.Lobby.changeCharacterSkin":
            # 修改角色皮肤时保存本地，并用一姬、二姐替代
            self.get_character(data["character_id"])["skin"] = data["skin"]
            self.avatar_id = self.get_character(self.character_id)["skin"]
            self.last_charid = data["character_id"]
            self.save()

            data["character_id"], data["skin"] = self.fake_character()
        elif method == ".lq.Lobby.updateCharacterSort":
            # 修改星标角色时保存本地，并用一姬、二姐替代
            self.characters["character_sort"] = data["sort"]
            self.save()

            data["sort"] = [self.fake_character()[0]]

        # RESPONSE
        if method in [".lq.Lobby.oauth2Login", ".lq.Lobby.login"]:
            # 创建本地数据
            if not exists(self.profile):
                mkdir(self.profile)

                self.init_characters()
                self.avatar_id = data["account"]["avatar_id"]
                self.character_id = (int)((self.avatar_id - 400000) / 100 + 200000)

                self.characters["main_character_id"] = self.character_id
                self.get_character(self.character_id)["skin"] = self.avatar_id

                self.save()
            # 登录时获取账户信息并保存，并修改初始大厅显示角色
            self.read()
            self.account_id = data["account_id"]
            data["account"]["avatar_id"] = self.avatar_id
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
                # 其他玩家报菜名，对机器人无效
                else:
                    data["players"][i]["character"]["level"] = 5
                    data["players"][i]["character"]["exp"] = 1
                    data["players"][i]["character"]["is_upgraded"] = True
        elif method == ".lq.Lobby.fetchAccountInfo":
            # 修改状态面板立绘
            if data["account"]["account_id"] == self.account_id:
                data["account"]["avatar_id"] = self.avatar_id
        elif method == ".lq.Lobby.fetchBagInfo":
            """ERROR ITEM
            305214
            305314
            """

            items = []
            error_items = [305214, 305314, 305525, 305526, 305533, 305539, 305546]
            for i in range(305001, 308000):
                if i not in error_items:
                    items.append({"item_id": i, "stack": 1})
            data["bag"]["items"] = items
        elif method in [
            ".lq.Lobby.joinRoom",
            ".lq.Lobby.fetchRoom",
            ".lq.Lobby.createRoom",
        ]:
            # 在加入、获取、创建房间时修改己方立绘、角色
            for i in range(0, len(data["room"]["persons"])):
                if data["room"]["persons"][i]["account_id"] == self.account_id:
                    data["room"]["persons"][i]["avatar_id"] = self.avatar_id
                    data["room"]["persons"][i]["character"] = self.get_character(
                        self.character_id
                    )

        return data
