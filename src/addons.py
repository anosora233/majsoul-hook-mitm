import json
import logging
import requests
import mitmproxy.http
import richi
import pb2 as pb

from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
from google.protobuf.json_format import MessageToDict
from base64 import b64decode

# 导入配置
SETTINGS = json.load(open("conf/settings.json", "r"))

SEND_METHOD = SETTINGS["SEND_METHOD"]  # 需要发送给小助手的方法（method）
SEND_ACTION = SETTINGS["SEND_ACTION"]  # '.lq.ActionPrototype'中，需要发送给小助手的动作（action）
API_URL = SETTINGS["API_URL"]  # 小助手的地址
UPSTREAM_PROXY = SETTINGS["UPSTREAM_PROXY"]

logging.info(
    f"""
    已载入配置：\n
    SEND_METHOD: {SEND_METHOD}\n
    SEND_ACTION: {SEND_ACTION}\n
    API_URL: {API_URL}
    UPSTREAM_PROXY: {UPSTREAM_PROXY}
    """
)

richi_proto = richi.RichiProto()
# 禁用 urllib3 的安全警告
disable_warnings(InsecureRequestWarning)


class WebSocketAddon:
    def websocket_message(self, flow: mitmproxy.http.HTTPFlow):
        # 在捕获到 WebSocket 消息时触发
        assert flow.websocket is not None  # 让类型检查器满意
        message = flow.websocket.messages[-1]
        # 排除无效 WebSocket 消息
        if message.content[0] not in [1, 2, 3]:
            return
        # 解析 proto 消息
        result = richi_proto.parse(message)
        if not message.from_client:
            logging.info(f"接收到：{result}")
        if result["method"] in SEND_METHOD and not message.from_client:
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
            logging.warn(f"已发送：{data}")
            requests.post(API_URL, json=data, verify=False)
            if "liqi" in data.keys():  # 补发立直消息
                logging.warn(f'已发送：{data["liqi"]}')
                requests.post(API_URL, json=data["liqi"], verify=False)


addons = [WebSocketAddon()]
