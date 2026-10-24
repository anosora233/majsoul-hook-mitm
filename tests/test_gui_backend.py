import base64
import hashlib
import io
import json
import time

import pytest

from majsoul_hook.gui_backend import (
    BackendProcess,
    EventInbox,
    MessageHistory,
    check_resources,
    local_resource_status,
)
from majsoul_hook.resources import DEFAULT_BASE_URL, INDEX


@pytest.fixture
def resource_file(schema, tmp_path):
    path = tmp_path / "protocol.json"
    path.write_text(
        json.dumps(
            {
                "format": 1,
                "descriptor": base64.b64encode(
                    schema.pool.FindFileByName("test.proto").serialized_pb
                ).decode(),
                "service": {"Lobby": {"test": {"request": "Req", "response": "Res"}}},
                "base_url": DEFAULT_BASE_URL,
                "bundle_sha256": {INDEX: hashlib.sha256(b"index").hexdigest()},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_resource_fingerprints_and_missing_file(resource_file, monkeypatch):
    calls = []

    def fetch(request, timeout):
        calls.append((request.full_url, timeout))
        return io.BytesIO(b"index")

    monkeypatch.setattr("majsoul_hook.gui_backend.urlopen", fetch)
    original = resource_file.read_bytes()
    assert not check_resources(resource_file, DEFAULT_BASE_URL)["update_available"]
    assert check_resources(resource_file, "https://other.test/")["update_available"]
    missing = resource_file.with_name("missing.json")
    assert check_resources(missing, DEFAULT_BASE_URL)["update_available"]
    assert resource_file.read_bytes() == original and not missing.exists()
    assert calls[0] == (DEFAULT_BASE_URL + INDEX, 60)
    status = local_resource_status(resource_file)
    assert status["methods"] == 1 and not status["cosmetics"]
    with pytest.raises(ValueError, match="HTTPS"):
        check_resources(resource_file, "http://other.test/")


def test_history_count_bytes_and_large_message():
    history = MessageHistory(max_items=2, max_bytes=100)
    first, _ = history.append({"name": "a"})
    second, _ = history.append({"name": "b"})
    third, removed = history.append({"name": "c"})
    assert removed == [first] and list(history.items) == [second, third]
    large, removed = history.append({"body": "x" * 200})
    assert removed == [second, third] and list(history.items) == [large]
    history.clear()
    assert history.size == 0 and not history.items


def test_inbox_preserves_lifecycle_order_under_pressure():
    inbox = EventInbox(max_items=2, max_bytes=100)
    inbox.put({"event": "ready"})
    for number in range(4):
        inbox.put({"event": "message", "id": number}, 40)
    inbox.put({"event": "finished"})
    assert inbox.dropped == 2
    assert inbox.drain(1) == [{"event": "ready"}]
    assert [item.get("id") for item in inbox.drain()] == [2, 3, None]
    assert inbox.message_count == inbox.size == 0
    inbox.put({"event": "message"}, 200)
    assert len(inbox.drain()) == 1
    for _ in range(1000):
        inbox.put({"event": "log"})
    inbox.put({"event": "error"})
    inbox.put({"event": "finished"})
    events = inbox.drain(1000)
    assert len(events) <= 500 and [e["event"] for e in events[-2:]] == ["error", "finished"]


def test_worker_failure_can_be_acknowledged_and_restarted(tmp_path):
    backend = BackendProcess()
    config = {"process": "test-only", "schema": str(tmp_path / "缺失资源.json")}
    for _ in range(2):
        backend.start("capture", config)
        with pytest.raises(RuntimeError, match="already running"):
            backend.start("capture", config)
        events = []
        deadline = time.monotonic() + 20
        try:
            while time.monotonic() < deadline:
                events.extend(backend.inbox.drain())
                if any(item["event"] == "finished" for item in events):
                    break
                time.sleep(0.02)
            assert [item["event"] for item in events] == ["error", "finished"]
            assert "缺失资源.json" in events[0]["message"]
            assert events[-1]["code"] != 0
            assert backend.running and backend.process.poll() is not None
        finally:
            backend.stop(timeout=0)
        backend.acknowledge_finished()
        assert not backend.running
