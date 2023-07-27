import json
import base64
import lq_pb2 as pb

from struct import unpack
from enum import Enum
from typing import List, Dict
from google.protobuf.json_format import MessageToDict, ParseDict

from mitmproxy.websocket import WebSocketMessage

""" 
    # msg_block Notify
    [{'id': 1, 'type': 'string','data': b'.lq.ActionPrototype'},
    {'id': 2, 'type': 'string','data': b'protobuf_bytes'}]
    # msg_block Req & Res
    [{'id': 1, 'type': 'string','data': b'.lq.FastTest.authGame'},
    {'id': 2, 'type': 'string','data': b'protobuf_bytes'}]
    # debug
    print(f"Before: {flow_msg.content}")
    print(f"After: {flow_msg.content}")
"""


class MsgType(Enum):
    Notify = 1
    Req = 2
    Res = 3


from rich import print

import hack


class LQPROTO:
    def __init__(self) -> None:
        self.tot = 0
        self.res_type = {}
        self.jsonProto = json.load(open("./src/lq.json", "r"))

        self.not_tasks = {}
        self.req_tasks = {}
        self.res_tasks = {}

    def bond(self, handler) -> None:
        for method in handler.notify:
            self.not_tasks[method] = handler.handler
        for method in handler.req:
            self.req_tasks[method] = handler.handler
        for method in handler.res:
            self.res_tasks[method] = handler.handler

    def parse(self, flow_msg: WebSocketMessage) -> Dict:
        buf = flow_msg.content
        from_client = flow_msg.from_client
        result = {}
        msg_type = MsgType(buf[0])

        if msg_type == MsgType.Notify:
            msg_block = fromProtobuf(buf[1:])
            method_name = msg_block[0]["data"].decode()
            _, lq, message_name = method_name.split(".")
            liqi_pb2_notify = getattr(pb, message_name)
            proto_obj = liqi_pb2_notify.FromString(msg_block[1]["data"])
            dict_obj = MessageToDict(
                proto_obj,
                preserving_proto_field_name=True,
                including_default_value_fields=True,
            )

            if method_name in self.not_tasks.keys():
                dict_obj = self.not_tasks[method_name](
                    method=method_name,
                    data=dict_obj,
                )
                proto_obj = ParseDict(
                    js_dict=dict_obj,
                    message=liqi_pb2_notify(),
                )

                msg_block[1]["data"] = proto_obj.SerializeToString()
                flow_msg.content = buf[:1] + toProtobuf(msg_block)

            if "data" in dict_obj:
                B = base64.b64decode(dict_obj["data"])
                action_proto_obj = getattr(pb, dict_obj["name"]).FromString(decode(B))
                action_dict_obj = MessageToDict(
                    action_proto_obj,
                    preserving_proto_field_name=True,
                    including_default_value_fields=True,
                )
                dict_obj["data"] = action_dict_obj

            msg_id = self.tot
        else:
            msg_id = unpack("<H", buf[1:3])[0]
            msg_block = fromProtobuf(buf[3:])
            if msg_type == MsgType.Req:
                assert msg_id < 1 << 16
                assert len(msg_block) == 2
                assert msg_id not in self.res_type
                method_name = msg_block[0]["data"].decode()
                _, lq, service, rpc = method_name.split(".")
                proto_domain = self.jsonProto["nested"][lq]["nested"][service][
                    "methods"
                ][rpc]
                liqi_pb2_req = getattr(pb, proto_domain["requestType"])
                proto_obj = liqi_pb2_req.FromString(msg_block[1]["data"])
                dict_obj = MessageToDict(
                    proto_obj,
                    preserving_proto_field_name=True,
                    including_default_value_fields=True,
                )

                if method_name in self.req_tasks.keys():
                    dict_obj = self.req_tasks[method_name](
                        method=method_name,
                        data=dict_obj,
                    )
                    proto_obj = ParseDict(
                        js_dict=dict_obj,
                        message=liqi_pb2_req(),
                    )

                    msg_block[1]["data"] = proto_obj.SerializeToString()
                    flow_msg.content = buf[:3] + toProtobuf(msg_block)

                self.res_type[msg_id] = (
                    method_name,
                    getattr(pb, proto_domain["responseType"]),
                )
            elif msg_type == MsgType.Res:
                assert len(msg_block[0]["data"]) == 0
                assert msg_id in self.res_type
                method_name, liqi_pb2_res = self.res_type.pop(msg_id)
                proto_obj = liqi_pb2_res.FromString(msg_block[1]["data"])
                dict_obj = MessageToDict(
                    proto_obj,
                    preserving_proto_field_name=True,
                    including_default_value_fields=True,
                )

                if method_name in self.res_tasks.keys():
                    dict_obj = self.res_tasks[method_name](
                        method=method_name,
                        data=dict_obj,
                    )
                    proto_obj = ParseDict(
                        js_dict=dict_obj,
                        message=liqi_pb2_res(),
                    )

                    msg_block[1]["data"] = proto_obj.SerializeToString()
                    flow_msg.content = buf[:3] + toProtobuf(msg_block)
        result = {
            "id": msg_id,
            "type": msg_type,
            "method": method_name,
            "data": dict_obj,
        }
        self.tot += 1
        return result


def fromProtobuf(buf) -> List[Dict]:
    p = 0
    result = []
    while p < len(buf):
        block_begin = p
        block_type = buf[p] & 7
        block_id = buf[p] >> 3
        p += 1
        if block_type == 0:
            block_type = "varint"
            data, p = parseVarint(buf, p)
        elif block_type == 2:
            block_type = "string"
            s_len, p = parseVarint(buf, p)
            data = buf[p : p + s_len]
            p += s_len
        else:
            raise Exception("unknow type:", block_type, " at", p)
        result.append(
            {"id": block_id, "type": block_type, "data": data, "begin": block_begin}
        )
    return result


def toProtobuf(data: List[Dict]) -> bytes:
    result = b""
    for d in data:
        if d["type"] == "varint":
            result += ((d["id"] << 3) + 0).to_bytes(length=1, byteorder="little")
            result += toVarint(d["data"])
        elif d["type"] == "string":
            result += ((d["id"] << 3) + 2).to_bytes(length=1, byteorder="little")
            result += toVarint(len(d["data"]))
            result += d["data"]
        else:
            raise NotImplementedError
    return result


def parseVarint(buf, p):
    data = 0
    base = 0
    while p < len(buf):
        data += (buf[p] & 127) << base
        base += 7
        p += 1
        if buf[p - 1] >> 7 == 0:
            break
    return (data, p)


def toVarint(x: int) -> bytes:
    data = 0
    base = 0
    length = 0
    if x == 0:
        return b"\x00"
    while x > 0:
        length += 1
        data += (x & 127) << base
        x >>= 7
        if x > 0:
            data += 1 << (base + 7)
        base += 8
    return data.to_bytes(length, "little")


def decode(data: bytes):
    keys = [0x84, 0x5E, 0x4E, 0x42, 0x39, 0xA2, 0x1F, 0x60, 0x1C]
    data = bytearray(data)
    k = len(keys)
    d = len(data)
    for i, j in enumerate(data):
        u = (23 ^ d) + 5 * i + keys[i % k] & 255
        data[i] ^= u
    return bytes(data)


"""
'buf': b'\x02+\x00\n\x13.lq.Lobby.loginBeat\x12"\n DF2vkXCnfeXp4WoGSBGNcJBufZiMN3UP',
'from_client': True,
'result': {
    'id': 43,
    'type': <MsgType.Req: 2>,
    'method': '.lq.Lobby.loginBeat',
    'data': {'contract': 'DF2vkXCnfeXp4WoGSBGNcJBufZiMN3UP'}
},
'msg_type': <MsgType.Req: 2>,
'msg_block': [
    {'id': 1, 'type': 'string', 'data': b'.lq.Lobby.loginBeat', 'begin': 0},
    {'id': 2, 'type': 'string', 'data': b'\n DF2vkXCnfeXp4WoGSBGNcJBufZiMN3UP', 'begin': 21}
]
"""
