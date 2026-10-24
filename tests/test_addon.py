import io
import json

import pytest
from mitmproxy import websocket
from mitmproxy.test import tflow

from majsoul_hook.addon import CaptureAddon

from .conftest import packet


@pytest.mark.parametrize("invalid", [False, True])
def test_read_only_and_cleanup(schema, tmp_path, invalid):
    output = tmp_path / "capture.jsonl"
    addon = CaptureAddon(schema, output=output)
    addon.running()
    flow = tflow.twebsocketflow(messages=False)
    raw = b"\xff" if invalid else packet(schema, 2, ".lq.Lobby.test", b"\x08\x03")
    message = websocket.WebSocketMessage(2, True, raw)
    flow.websocket.messages.append(message)
    before = message.get_state()
    message_count = len(flow.websocket.messages)
    addon.websocket_message(flow)
    assert message.get_state() == before
    assert not message.dropped and not message.injected
    assert len(flow.websocket.messages) == message_count
    if not invalid:
        record = json.loads(output.read_text())
        assert record["data"] == {"value": 3}
        assert record["flow_id"] == flow.id
    else:
        assert output.read_text() == ""
    addon.websocket_end(flow)
    assert not addon.connections
    addon.done()
    assert addon.stream is None


def test_host_filter_and_text_frames(schema):
    addon = CaptureAddon(schema, hosts=("maj-soul.com",))
    flow = tflow.twebsocketflow(messages=False)
    message = websocket.WebSocketMessage(2, True, packet(schema, 2, ".lq.Lobby.test"))
    flow.websocket.messages.append(message)
    for host in ("example.org", "evilmaj-soul.com", "maj-soul.com.attacker.test"):
        flow.request.host = host
        addon.websocket_message(flow)
        assert not addon.connections
    flow.request.host = "game.maj-soul.com"
    flow.websocket.messages[-1] = websocket.WebSocketMessage(1, True, b"hello")
    addon.websocket_message(flow)
    assert not addon.connections
    flow.websocket.messages[-1] = message
    addon.websocket_message(flow)
    assert flow.id in addon.connections


def test_output_failure_preserves_forwarding(schema):
    class BrokenOutput:
        closed = False

        def write(self, value):
            raise OSError("disk full")

        def close(self):
            self.closed = True

    addon = CaptureAddon(schema)
    broken = BrokenOutput()
    addon.stream = broken
    flow = tflow.twebsocketflow(messages=False)
    message = websocket.WebSocketMessage(2, True, packet(schema, 2, ".lq.Lobby.test"))
    flow.websocket.messages.append(message)
    before = message.get_state()
    addon.websocket_message(flow)
    assert message.get_state() == before
    assert broken.closed and addon.stream is None


@pytest.mark.parametrize("at_shutdown", [False, True])
def test_buffered_flush_and_close_failure(schema, at_shutdown, caplog):
    class FullDevice(io.RawIOBase):
        def writable(self):
            return True

        def write(self, content):
            raise OSError("disk full")

    # Reproduce the actual buffered-file behavior: flush and close both fail.
    stream = io.TextIOWrapper(io.BufferedWriter(FullDevice()), encoding="utf-8")
    addon = CaptureAddon(schema)
    addon.stream = stream
    flow = tflow.twebsocketflow()
    message = websocket.WebSocketMessage(2, True, packet(schema, 2, ".lq.Lobby.test"))
    flow.websocket.messages.append(message)
    before = message.get_state()
    if at_shutdown:
        stream.write("buffered output")
        addon.connections[flow.id] = object()
        addon.done()
        assert not addon.connections
    else:
        addon.websocket_message(flow)
        # A subsequent response must still be decoded without touching the closed stream.
        flow.websocket.messages.append(websocket.WebSocketMessage(2, False, packet(schema, 3)))
        addon.websocket_message(flow)
        assert not addon.connections[flow.id].pending
    assert message.get_state() == before
    assert "Could not close capture output" in caplog.text
    assert stream.closed and addon.stream is None
    addon.done()
