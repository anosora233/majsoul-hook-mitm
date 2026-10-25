"""Editable envelopes and descriptor-aware patches that retain unknown protobuf fields."""

from copy import deepcopy
from dataclasses import dataclass

from google.protobuf.json_format import ParseDict
from google.protobuf.message import Message

from .schema import Schema, dictionary

MAX_FRAME_SIZE = 16 * 1024 * 1024


def patch_message(message: Message, before: dict, after: dict) -> None:
    """Apply only changed fields to the original message, retaining untouched wire data.

    Repeated objects are matched by stable business identities, or by position when
    no identity exists. Removed objects/fields intentionally lose their contents.
    """
    for name in before.keys() | after.keys():
        if before.get(name) == after.get(name) and (name in before) == (name in after):
            continue
        field = message.DESCRIPTOR.fields_by_name[name]
        if name not in after:
            message.ClearField(name)
        elif field.message_type and not field.is_repeated:
            target = getattr(message, name)
            target.SetInParent()
            patch_message(target, before.get(name, {}), after[name])
        elif field.message_type and field.is_repeated:
            container = getattr(message, name)
            originals = [deepcopy(item) for item in container]
            old = [dictionary(item) for item in originals]
            identity = next(
                (
                    key
                    for key in (
                        "account_id",
                        "charid",
                        "item_id",
                        "id",
                        "slot",
                        "index",
                        "character_id",
                    )
                    if key in field.message_type.fields_by_name
                ),
                None,
            )
            message.ClearField(name)
            used = set()
            for index, row in enumerate(after[name]):
                match = (
                    next(
                        (
                            i
                            for i, prior in enumerate(old)
                            if i not in used and prior.get(identity) == row.get(identity)
                        ),
                        None,
                    )
                    if identity
                    else index
                    if index < len(old)
                    else None
                )
                target = getattr(message, name).add()
                prior = {}
                if match is not None:
                    used.add(match)
                    target.CopyFrom(originals[match])
                    prior = old[match]
                patch_message(target, prior, row)
        else:
            # Parse on a temporary instance for enum/bytes/int64 JSON conversion
            # and type checking, then replace only this known field.
            parsed = ParseDict({name: after[name]}, type(message)())
            message.ClearField(name)
            if field.is_repeated:
                getattr(message, name).extend(getattr(parsed, name))
            else:
                setattr(message, name, getattr(parsed, name))


@dataclass
class Frame:
    kind: int
    request_id: int | None
    wrapper: Message

    @classmethod
    def parse(cls, schema: Schema, content: bytes, *, max_size: int = MAX_FRAME_SIZE) -> Frame:
        if not content or content[0] not in (1, 2, 3) or len(content) > max_size:
            raise ValueError("Invalid frame kind or size")
        offset = 1 if content[0] == 1 else 3
        if len(content) < offset:
            raise ValueError("Truncated request ID")
        return cls(
            content[0],
            int.from_bytes(content[1:3], "little") if offset == 3 else None,
            schema.parse("Wrapper", content[offset:]),
        )

    def serialize(self) -> bytes:
        return (
            bytes([self.kind])
            + (self.request_id.to_bytes(2, "little") if self.request_id is not None else b"")
            + self.wrapper.SerializeToString()
        )


class Codec:
    def __init__(self, schema: Schema):
        self.schema = schema

    def type_name(self, kind: int, name: str) -> str:
        return name if kind == 1 else self.schema.methods[name][0 if kind == 2 else 1]

    def read(self, frame: Frame, name: str) -> Message:
        return self.schema.parse(self.type_name(frame.kind, name), frame.wrapper.data)

    def replace(self, frame: Frame, original: Message, after: dict) -> bytes:
        edited = deepcopy(original)
        patch_message(edited, dictionary(original), after)
        wrapper = deepcopy(frame.wrapper)
        wrapper.data = edited.SerializeToString()
        return Frame(frame.kind, frame.request_id, wrapper).serialize()

    def packet(self, kind: int, name: str, data: dict, request_id: int | None = None) -> bytes:
        payload = ParseDict(data, self.schema.message_class(self.type_name(kind, name))())
        wrapper = self.schema.message_class("Wrapper")(
            name=name if kind != 3 else "", data=payload.SerializeToString()
        )
        return Frame(kind, request_id, wrapper).serialize()

    def error_response(self, name: str, request_id: int) -> bytes:
        # Independent of the normal notification/response dictionary encoder.
        response = self.schema.message_class(self.type_name(3, name))()
        response.error.code = 1
        wrapper = self.schema.message_class("Wrapper")(data=response.SerializeToString())
        return Frame(3, request_id, wrapper).serialize()
