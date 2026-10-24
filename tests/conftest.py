import pytest
from google.protobuf import descriptor_pb2

from majsoul_hook.schema import Schema

pytest_plugins = ("tests.cosmetic_fixtures",)


@pytest.fixture
def schema():
    file = descriptor_pb2.FileDescriptorProto(name="test.proto", package="lq", syntax="proto2")
    definitions = {
        "Wrapper": [("name", 1, 9, None), ("data", 2, 12, None)],
        "Req": [("value", 1, 5, None)],
        "Res": [("value", 1, 3, None)],
        "ActionPrototype": [("name", 2, 9, None), ("data", 3, 12, None)],
        "ActionDeal": [("value", 1, 5, None)],
        "Restore": [("actions", 1, 11, ".lq.ActionPrototype")],
        "ResSync": [("game_restore", 1, 11, ".lq.Restore")],
    }
    for name, fields in definitions.items():
        message = file.message_type.add(name=name)
        for field_name, number, type_id, reference in fields:
            field = message.field.add(
                name=field_name,
                number=number,
                type=type_id,
                label=3 if field_name == "actions" else 1,
            )
            if reference:
                field.type_name = reference
    return Schema(
        file.SerializeToString(),
        {
            "Lobby": {"test": {"request": "Req", "response": "Res"}},
            "FastTest": {"syncGame": {"request": "Req", "response": "ResSync"}},
        },
    )


def packet(schema, kind, name="", payload=b"", request_id=0):
    wrapper = schema.message_class("Wrapper")(name=name, data=payload).SerializeToString()
    return bytes([kind]) + (request_id.to_bytes(2, "little") if kind != 1 else b"") + wrapper
