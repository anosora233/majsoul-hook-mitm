import base64

import pytest

from majsoul_hook.protocol import ConnectionDecoder, ProtocolError, decode_action

from .conftest import packet


def test_request_response_and_isolation(schema):
    a, b = ConnectionDecoder(schema), ConnectionDecoder(schema)
    request = packet(schema, 2, ".lq.Lobby.test", b"\x08\x07", 65535)
    assert a.decode(request, from_client=True).data == {"value": 7}
    response = packet(schema, 3, payload=b"\x08\x09", request_id=65535)
    assert b.decode(response, from_client=False).status == "orphan_response"
    assert a.decode(response, from_client=False).data == {"value": "9"}
    assert not a.pending


def test_same_ids_in_opposite_directions(schema):
    decoder = ConnectionDecoder(schema)
    for direction in (True, False):
        decoder.decode(packet(schema, 2, ".lq.Lobby.test", request_id=0), from_client=direction)
    for direction in (True, False):
        assert decoder.decode(packet(schema, 3), from_client=direction).name == ".lq.Lobby.test"
    assert not decoder.pending


def test_eviction_expiry_reuse_and_cleanup(schema):
    now = [0]
    decoder = ConnectionDecoder(schema, max_pending=1, timeout=10, clock=lambda: now[0])
    request = packet(schema, 2, ".lq.Lobby.test")
    decoder.decode(request, from_client=True)
    assert decoder.decode(request, from_client=True).warnings
    decoder.decode(packet(schema, 2, ".lq.Lobby.test", request_id=1), from_client=True)
    assert list(decoder.pending) == [(True, 1)]
    now[0] = 10
    assert (
        decoder.decode(packet(schema, 3, request_id=1), from_client=False).status
        == "orphan_response"
    )
    decoder.decode(request, from_client=True)
    decoder.clear()
    assert not decoder.pending


def test_unknown_schema_retains_payload_and_correlation(schema):
    decoder = ConnectionDecoder(schema)
    result = decoder.decode(packet(schema, 2, ".lq.Future.call", b"abc"), from_client=True)
    assert result.status == "unknown_schema"
    assert base64.b64decode(result.payload_base64) == b"abc"
    result = decoder.decode(packet(schema, 3), from_client=False)
    assert result.name == ".lq.Future.call"


@pytest.mark.parametrize("content", [b"", b"\x02", b"\x03\x01", b"\xff", b"\x01\xff"])
def test_malformed_frames(schema, content):
    with pytest.raises(ProtocolError):
        ConnectionDecoder(schema).decode(content, from_client=True)


def test_malformed_payload_and_size_limit(schema):
    decoder = ConnectionDecoder(schema)
    with pytest.raises(ProtocolError):
        decoder.decode(packet(schema, 2, ".lq.Lobby.test", b"\xff"), from_client=True)
    with pytest.raises(ProtocolError):
        ConnectionDecoder(schema, max_frame=3).decode(b"\x01abcd", from_client=False)


def test_action_notification_and_restore(schema):
    decoder = ConnectionDecoder(schema)
    action = schema.message_class("ActionPrototype")(
        name="ActionDeal", data=decode_action(b"\x08\x2a")
    )
    result = decoder.decode(
        packet(schema, 1, ".lq.ActionPrototype", action.SerializeToString()), from_client=False
    )
    assert result.data["data"] == {"value": 42}
    decoder.decode(packet(schema, 2, ".lq.FastTest.syncGame"), from_client=True)
    response = schema.message_class("ResSync")()
    response.game_restore.actions.add(name="ActionDeal", data=b"\x08\x07")
    result = decoder.decode(
        packet(schema, 3, payload=response.SerializeToString()), from_client=False
    )
    assert result.data["game_restore"]["actions"][0]["data"] == {"value": 7}


def test_unknown_action_keeps_raw(schema):
    action = schema.message_class("ActionPrototype")(name="Future", data=b"abc")
    result = ConnectionDecoder(schema).decode(
        packet(schema, 1, ".lq.ActionPrototype", action.SerializeToString()), from_client=False
    )
    assert result.warnings
    assert result.data["data"] == "YWJj"
