import base64

import pytest
from mitmproxy import websocket
from mitmproxy.test import tflow

from majsoul_hook.addon import CaptureAddon

from .conftest import packet
from .test_cosmetics import login


@pytest.mark.parametrize("raw", [None, b"\xff"])
def test_read_only_snapshot_and_broken_observer(schema, raw):
    raw = packet(schema, 2, ".lq.Lobby.test", b"\x08\x03") if raw is None else raw
    events = []
    addon = CaptureAddon(schema, event_sink=events.append)
    flow = tflow.twebsocketflow(messages=False)
    message = websocket.WebSocketMessage(2, True, raw)
    flow.websocket.messages.append(message)
    before = message.get_state()
    addon.websocket_message(flow)
    assert message.get_state() == before
    event = events[0]
    assert event["wire_before"] == event["wire_after"] == base64.b64encode(raw).decode()
    assert event["action"] == ("error" if raw == b"\xff" else "pass")
    assert event["before"] == event["after"]
    addon.event_sink = lambda _: (_ for _ in ()).throw(OSError("closed inspector"))
    addon.websocket_message(flow)
    assert message.get_state() == before


def test_modified_intercepted_and_synthetic_contents(cosmetics, monkeypatch):
    events, sent = [], []
    addon = CaptureAddon(cosmetics.schema, cosmetics=cosmetics, event_sink=events.append)
    monkeypatch.setattr(addon, "_inject", lambda flow, content: sent.append(content))
    flow = tflow.twebsocketflow(messages=False)

    def send(kind, name, data):
        content = cosmetics.codec.packet(kind, name, data, 7)
        message = websocket.WebSocketMessage(2, kind == 2, content)
        flow.websocket.messages.append(message)
        addon.websocket_message(flow)
        return message

    send(2, ".lq.Lobby.login", {})
    send(3, ".lq.Lobby.login", {"account_id": 42, "account": {"account_id": 42}})
    modified = events[-1]
    assert modified["action"] == "modified"
    assert "avatar_id" not in modified["before"]["account"]
    assert modified["after"]["account"]["avatar_id"] == 400001
    assert modified["wire_before"] != modified["wire_after"]
    events.clear()
    message = send(2, ".lq.Lobby.useTitle", {"title": 1})
    assert message.dropped
    assert events[0]["action"] == "intercepted" and events[0]["before"] == {"title": 1}
    assert events[0]["after"] is None and events[0]["wire_after"] is None
    assert events[1]["action"] == "local" and events[1]["synthetic"]
    assert [base64.b64decode(e["wire_after"]) for e in events[1:]] == sent
    assert events[1]["request_id"] == 7
    count = len(events)
    injected = websocket.WebSocketMessage(2, False, sent[0], injected=True)
    flow.websocket.messages.append(injected)
    addon.websocket_message(flow)
    assert len(events) == count


def test_failed_local_request_shows_error_response(cosmetics, monkeypatch):
    login(cosmetics)
    events = []
    addon = CaptureAddon(cosmetics.schema, cosmetics=cosmetics, event_sink=events.append)
    monkeypatch.setattr(addon, "_inject", lambda *args: None)
    monkeypatch.setattr(cosmetics, "apply", lambda *a, **kw: (_ for _ in ()).throw(ValueError()))
    raw = cosmetics.codec.packet(2, ".lq.Lobby.useTitle", {"title": 1}, 8)
    flow = tflow.twebsocketflow(messages=False)
    flow.websocket.messages.append(websocket.WebSocketMessage(2, True, raw))
    addon.websocket_message(flow)
    assert events[0]["action"] == "error" and not events[0]["retained"]
    assert events[0]["injections"] == 1
    assert events[1]["action"] == "local" and events[1]["after"]["error"]["code"] == 1
