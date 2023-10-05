import base64

from struct import unpack, pack
from enum import Enum
from google.protobuf.json_format import MessageToDict, ParseDict
from mitmproxy import http, ctx


from . import liqi_pb2 as pb

""" 
    # msg_block notify
    [   {'id': 1, 'type': 'string','data': b'.lq.ActionPrototype'},
        {'id': 2, 'type': 'string','data': b'protobuf_bytes'}       ]
    # msg_block request & response
    [   {'id': 1, 'type': 'string','data': b'.lq.FastTest.authGame'},
        {'id': 2, 'type': 'string','data': b'protobuf_bytes'}       ]
"""


class MsgType(Enum):
    Notify = 1
    Req = 2
    Res = 3


class Handler(object):
    def handle(self, flow: http.HTTPFlow, parsed: dict) -> bool:
        raise NotImplementedError

    def methods(self, msg_type: MsgType) -> set[str]:
        raise NotImplementedError

    def drop(self, *args) -> bool:
        raise NotImplementedError

    def inject(
        self, flow: http.HTTPFlow, parsed: dict, inject_data: dict, *notifys: dict
    ) -> bool:
        assert parsed["type"] is MsgType.Req

        flow.websocket.messages[-1].drop()
        inject_parsed = parsed.copy()
        inject_parsed["type"] = MsgType.Res
        inject_parsed["data"] = inject_data

        return inject(flow, inject_parsed, *notifys)


class LQPROTO:
    def __init__(self) -> None:
        self.tot = 0
        self.res_type = {}

    def parse(self, flow: http.HTTPFlow) -> dict:
        flow_msg = flow.websocket.messages[-1]
        buf = flow_msg.content
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

            if str("data") in dict_obj:
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
                method_desc = pb.DESCRIPTOR.services_by_name[service].methods_by_name[
                    rpc
                ]
                liqi_pb2_req = getattr(pb, method_desc.input_type.name)
                proto_obj = liqi_pb2_req.FromString(msg_block[1]["data"])
                dict_obj = MessageToDict(
                    proto_obj,
                    preserving_proto_field_name=True,
                    including_default_value_fields=True,
                )

                self.res_type[msg_id] = (
                    method_name,
                    getattr(pb, method_desc.output_type.name),
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

                if str("game_restore") in dict_obj:
                    for action in dict_obj["game_restore"]["actions"]:
                        b64 = base64.b64decode(action["data"])
                        action_proto_obj = getattr(pb, action["name"]).FromString(b64)
                        action_dict_obj = MessageToDict(
                            action_proto_obj,
                            preserving_proto_field_name=True,
                            including_default_value_fields=True,
                        )
                        action["data"] = action_dict_obj
        parsed = {
            "id": msg_id,
            "type": msg_type,
            "method": method_name,
            "data": dict_obj,
        }
        self.tot += 1
        return parsed


def compose(parsed) -> bytes:
    data = parsed["data"]
    msg_type = parsed["type"]
    method_name = parsed["method"]

    head = msg_type.value.to_bytes(length=1, byteorder="little")
    msg_block = [{"id": 1, "type": "string"}, {"id": 2, "type": "string"}]

    if msg_type == MsgType.Notify:
        if str("data") in data:
            """Not yet supported"""
            raise NotImplementedError

        _, lq, message_name = method_name.split(".")
        liqi_pb2_notify = getattr(pb, message_name)
        protod = ParseDict(js_dict=data, message=liqi_pb2_notify())
        msg_block[0]["data"] = method_name.encode()
        msg_block[1]["data"] = protod.SerializeToString()
        return head + toProtobuf(msg_block)

    else:
        msg_id = parsed["id"]
        if msg_type == MsgType.Req:
            _, lq, service, rpc = method_name.split(".")
            method_desc = pb.DESCRIPTOR.services_by_name[service].methods_by_name[rpc]
            liqi_pb2_req = getattr(pb, method_desc.input_type.name)
            protod = ParseDict(js_dict=data, message=liqi_pb2_req())
            msg_block[0]["data"] = method_name.encode()
            msg_block[1]["data"] = protod.SerializeToString()
            return head + pack("<H", msg_id) + toProtobuf(msg_block)

        elif msg_type == MsgType.Res:
            _, lq, service, rpc = method_name.split(".")
            method_desc = pb.DESCRIPTOR.services_by_name[service].methods_by_name[rpc]
            liqi_pb2_res = getattr(pb, method_desc.output_type.name)
            protod = ParseDict(js_dict=data, message=liqi_pb2_res())
            msg_block[0]["data"] = b""
            msg_block[1]["data"] = protod.SerializeToString()
            return head + pack("<H", msg_id) + toProtobuf(msg_block)


def manipulate(flow: http.HTTPFlow, parsed: dict) -> None:
    last_message = flow.websocket.messages[-1]
    last_message.content = compose(parsed=parsed)


def inject(flow: http.HTTPFlow, parsed: dict, *notifys: dict) -> bool:
    """inject.websocket flow to_client message is_text"""

    assert parsed["type"] is MsgType.Res
    ctx.master.commands.call("inject.websocket", flow, True, compose(parsed), False)

    for notify in notifys:
        assert notify["type"] is MsgType.Notify
        ctx.master.commands.call("inject.websocket", flow, True, compose(notify), False)

    return False


def fromProtobuf(buf) -> list[dict]:
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
            raise Exception("unknow type:", block_type, "at", p)
        result.append(
            {"id": block_id, "type": block_type, "data": data, "begin": block_begin}
        )
    return result


def toProtobuf(data: list[dict]) -> bytes:
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
    for i in range(len(data)):
        u = (23 ^ len(data)) + 5 * i + keys[i % len(keys)] & 255
        data[i] ^= u
    return bytes(data)
