import struct
from dataclasses import asdict, dataclass
from enum import Enum

from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.message import Message
from google.protobuf.message_factory import GetMessageClass

from .proto import liqi_pb2

_MESSAGE_TYPE_MAP: dict[str, type[Message]] = {}
for sdesc in liqi_pb2.DESCRIPTOR.services_by_name.values():
    for mdesc in sdesc.methods:
        _MESSAGE_TYPE_MAP["." + mdesc.full_name] = (
            GetMessageClass(mdesc.input_type),
            GetMessageClass(mdesc.output_type),
        )
for tdesc in liqi_pb2.DESCRIPTOR.message_types_by_name.values():
    _MESSAGE_TYPE_MAP["." + tdesc.full_name] = GetMessageClass(tdesc)


class GameMessageType(Enum):
    """Message Types for Game Messages"""

    Notify = 1
    Request = 2
    Response = 3

    def to_bytes(self) -> bytes:
        return self.value.to_bytes(1, "little")


@dataclass
class GameMessage:
    """A message in a game with attributes like idx, name, data, kind, and base."""

    idx: int
    name: str
    data: dict

    kind: GameMessageType
    base: Message | None = None

    def asdict(self) -> dict:
        return asdict(self)


# TODO: Refactor this section using Object-Oriented Programming (OOP) principles.
# Ensure that each HTTP flow possesses its own message queue for improved encapsulation and modularity  # noqa: E501
_names_by_flow_idx: dict[tuple[str, int], str] = {}


def parse(id4flow: str, content: bytes) -> GameMessage:
    kind = GameMessageType(content[0])

    match kind:
        case GameMessageType.Notify:
            idx = 0
            name, data = unwrap(content[1:])

            parser = _MESSAGE_TYPE_MAP[name]()

        case GameMessageType.Request:
            idx = struct.unpack("<H", content[1:3])[0]
            key = (id4flow, idx)
            name, data = unwrap(content[3:])

            _names_by_flow_idx[key] = name
            parser = _MESSAGE_TYPE_MAP[name][0]()
        case GameMessageType.Response:
            idx = struct.unpack("<H", content[1:3])[0]
            key = (id4flow, idx)
            name, data = unwrap(content[3:])

            name = _names_by_flow_idx.pop(key)
            parser = _MESSAGE_TYPE_MAP[name][1]()

    parser.ParseFromString(data)

    data = MessageToDict(
        parser,
        including_default_value_fields=True,
        preserving_proto_field_name=True,
    )

    return GameMessage(idx=idx, name=name, data=data, base=parser, kind=kind)


def compose(message: GameMessage) -> bytes:
    # Using the original parser(`base`) is essential to prevent
    # the loss of unsupported protobuf fields.
    if not message.base:
        match message.kind:
            case GameMessageType.Notify:
                message.base = _MESSAGE_TYPE_MAP[message.name]()
            case GameMessageType.Request:
                message.base = _MESSAGE_TYPE_MAP[message.name][0]()
            case GameMessageType.Response:
                message.base = _MESSAGE_TYPE_MAP[message.name][1]()

    name = "" if message.kind == GameMessageType.Response else message.name

    data = ParseDict(
        js_dict=message.data,
        message=message.base,
    ).SerializeToString()

    buffer = wrap(name, data)

    match message.kind:
        case GameMessageType.Notify:
            return message.kind.to_bytes() + buffer
        case GameMessageType.Request | GameMessageType.Response:
            return message.kind.to_bytes() + struct.pack("<H", message.idx) + buffer


def unwrap(buffer: bytes) -> tuple[str, bytes]:
    wrapper: Message = liqi_pb2.Wrapper()  # type: ignore[attr-defined]
    wrapper.ParseFromString(buffer)
    return wrapper.name, wrapper.data


def wrap(name: str, data: bytes) -> bytes:
    wrapper: Message = liqi_pb2.Wrapper()
    wrapper.name, wrapper.data = name, data
    return wrapper.SerializeToString()
