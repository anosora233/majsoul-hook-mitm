"""Load client-derived descriptors without generated Python modules or protoc."""

import base64
import json
from pathlib import Path

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message


def dictionary(message: Message) -> dict:
    return MessageToDict(message, preserving_proto_field_name=True)


def qualified(name: str) -> str:
    name = name.lstrip(".")
    return name if name.startswith("lq.") else f"lq.{name}"


class Schema:
    def __init__(self, descriptor: bytes, services: dict):
        self.cosmetic_config = None
        self.pool = descriptor_pool.DescriptorPool()
        definition = descriptor_pb2.FileDescriptorProto.FromString(descriptor)
        self.pool.Add(definition)
        self.methods = {
            f".lq.{service}.{method}": (qualified(pair["request"]), qualified(pair["response"]))
            for service, methods in services.items()
            for method, pair in methods.items()
        }
        self.message_class("lq.Wrapper")

    @classmethod
    def load(cls, path: Path) -> Schema:
        return cls.from_document(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def from_document(cls, document: dict) -> Schema:
        if not isinstance(document, dict) or document.get("format") != 1:
            raise ValueError("Unsupported protocol resource format; update resources")
        schema = cls(base64.b64decode(document["descriptor"], validate=True), document["service"])
        schema.cosmetic_config = document.get("cosmetics")
        return schema

    def message_class(self, name: str):
        return message_factory.GetMessageClass(self.pool.FindMessageTypeByName(qualified(name)))

    def parse(self, name: str, payload: bytes):
        return self.message_class(name).FromString(payload)

    def decode(self, name: str, payload: bytes) -> dict:
        return dictionary(self.parse(name, payload))
