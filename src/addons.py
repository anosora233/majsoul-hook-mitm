import json
import logging
import requests
import mitmproxy.http

import lq
import lq_pb2 as pb
import hack

from typing import Dict, List
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
from google.protobuf.json_format import MessageToDict
from base64 import b64decode

# 禁用 urllib3 的安全警告
disable_warnings(InsecureRequestWarning)

SEND_METHOD = [
    ".lq.Lobby.oauth2Login",
    ".lq.Lobby.fetchFriendList",
    ".lq.FastTest.authGame",
    ".lq.NotifyPlayerLoadGameReady",
    ".lq.ActionPrototype",
    ".lq.Lobby.fetchGameRecordList",
    ".lq.FastTest.syncGame",
    ".lq.Lobby.login",
]  # 需要发送给小助手的方法（METHOD）
SEND_ACTION = [
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
]  # 需要发送给小助手的动作（ACTION）
SOUL_SNIS = [
    "maj-soul.com",
    "maj-soul.net",
    "mahjongsoul.com",
    "yo-star.com",
]

# 导入配置
API_URL = "https://localhost:12121/"  # 小助手的地址
SETTINGS = json.load(open("settings.json", "r"))
logging.warning(f"Settings: {SETTINGS}")

# 初始化
LQPROTO = lq.LQPROTO()
if SETTINGS["enable_skins"]:
    skin_handler = hack.SkinHanlder()
    LQPROTO.bond(skin_handler)


# 排除无效 WebSocket 消息
# 不适用于 Steam 端
def check_sni(server_sni: str) -> bool:
    for sni in SOUL_SNIS:
        if sni in server_sni:
            return True
    return False


class WebSocketAddon:
    def websocket_message(self, flow: mitmproxy.http.HTTPFlow):
        # 在捕获到 WebSocket 消息时触发
        assert flow.websocket is not None  # 类型检查
        message = flow.websocket.messages[-1]

        # 解析 PROTO 消息
        result = LQPROTO.parse(message)

        if message.from_client:
            logging.info(f"-->> Cilent -->>: {result}")
        else:
            logging.warning(f"<<-- Server <<--: {result}")

            if SETTINGS["enable_helper"]:
                post_helper(result=result)


def post_helper(result: Dict) -> None:
    # 兼容小助手
    if result["method"] in SEND_METHOD:
        if result["method"] == ".lq.ActionPrototype":
            if result["data"]["name"] in SEND_ACTION:
                data = result["data"]["data"]
                if result["data"]["name"] == "ActionNewRound":
                    # 雀魂弃用了 md5 改用 sha256，但没有该字段会导致小助手无法解析牌局，也不能留空
                    # 所以干脆发一个假的，反正也用不到
                    data["md5"] = data["sha256"][:32]
            else:
                return
        elif result["method"] == ".lq.FastTest.syncGame":  # 重新进入对局时
            actions = []
            for item in result["data"]["game_restore"]["actions"]:
                if item["data"] == "":
                    actions.append({"name": item["name"], "data": {}})
                else:
                    b64 = b64decode(item["data"])
                    action_proto_obj = getattr(pb, item["name"]).FromString(b64)
                    action_dict_obj = MessageToDict(
                        action_proto_obj,
                        preserving_proto_field_name=True,
                        including_default_value_fields=True,
                    )
                    if item["name"] == "ActionNewRound":
                        # 这里也是假的 md5，理由同上
                        action_dict_obj["md5"] = action_dict_obj["sha256"][:32]
                    actions.append({"name": item["name"], "data": action_dict_obj})
            data = {"sync_game_actions": actions}
        else:
            data = result["data"]

        logging.info(f"已发送：{data}")
        requests.post(API_URL, json=data, verify=False)
        if "liqi" in data.keys():  # 补发立直消息
            logging.warning(f'已发送：{data["liqi"]}')
            requests.info(API_URL, json=data["liqi"], verify=False)


addons = [WebSocketAddon()]
