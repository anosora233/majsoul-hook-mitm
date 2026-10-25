"""Bounded inspector storage and subprocess management, independent of Tk."""

import hashlib
import json
import os
import subprocess
import sys
import threading
from collections import OrderedDict, deque
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

from google.protobuf.message import DecodeError

from .config import DEFAULT_BASE_URL, INDEX, normalize_base_url
from .gui_i18n import N_
from .schema import Schema

ACTION_LABELS = {
    "pass": N_("Pass"),
    "modified": N_("Modified"),
    "intercepted": N_("Intercepted"),
    "local": N_("Injected"),
    "error": N_("Error"),
}


def local_resource_status(path: Path) -> dict:
    if not path.is_file():
        return {"exists": False, "path": str(path), "base_url": DEFAULT_BASE_URL}
    document = json.loads(path.read_text(encoding="utf-8"))
    try:
        Schema.from_document(document)
    except (DecodeError, TypeError) as exc:
        raise ValueError(f"Invalid protocol resource: {exc}") from exc
    cfg = document.get("cosmetics") or {}
    return {
        "exists": True,
        "path": str(path),
        "version": document.get("resource_version") or document.get("bundle_sha256", {}).get(INDEX),
        "generated_at": document.get("generated_at")
        or datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
        "base_url": document.get("base_url", DEFAULT_BASE_URL),
        "methods": sum(len(methods) for methods in document["service"].values()),
        "cosmetics": bool(cfg),
        "characters": len(cfg.get("characters", [])),
        "skins": len(cfg.get("skins", [])),
        "titles": len(cfg.get("titles", [])),
    }


def check_resources(path: Path, base_url: str) -> dict:
    status = local_resource_status(path)
    base_url = normalize_base_url(base_url)
    request = Request(base_url + INDEX, headers={"Cache-Control": "no-cache"})
    with urlopen(request, timeout=60) as response:
        remote = hashlib.sha256(response.read()).hexdigest()
    status["remote_version"] = remote
    status["checked_url"] = base_url
    status["update_available"] = (
        not status["exists"]
        or status.get("version") != remote
        or status["base_url"].rstrip("/") + "/" != base_url
    )
    return status


class MessageHistory:
    def __init__(self, max_items=2000, max_bytes=64 * 1024 * 1024):
        self.max_items, self.max_bytes = max_items, max_bytes
        self.items: OrderedDict[str, tuple[dict, int]] = OrderedDict()
        self.size = 0
        self.sequence = 0

    def append(self, record: dict) -> tuple[str, list[str]]:
        self.sequence += 1
        key = str(self.sequence)
        size = len(json.dumps(record, ensure_ascii=False).encode("utf-8"))
        self.items[key] = (record, size)
        self.size += size
        removed = []
        # Keep an oversized single message inspectable, evicting older history.
        while len(self.items) > 1 and (
            len(self.items) > self.max_items or self.size > self.max_bytes
        ):
            old, (_, weight) = self.items.popitem(last=False)
            self.size -= weight
            removed.append(old)
        return key, removed

    def clear(self):
        self.items.clear()
        self.size = 0


class EventInbox:
    """Never let an overwhelmed UI block the proxy pipe or grow without limit."""

    def __init__(self, max_items=500, max_bytes=32 * 1024 * 1024):
        self.max_items, self.max_bytes = max_items, max_bytes
        self.events = deque()
        self.message_count = 0
        self.lock = threading.Lock()
        self.size = 0
        self.dropped = 0

    def put(self, event: dict, size: int = 0):
        with self.lock:
            self.events.append((event, size))
            if event.get("event") == "message":
                self.message_count += 1
                self.size += size
                while self.message_count > 1 and (
                    self.message_count > self.max_items or self.size > self.max_bytes
                ):
                    for index, (item, weight) in enumerate(self.events):
                        if item.get("event") == "message":
                            del self.events[index]
                            self.size -= weight
                            self.message_count -= 1
                            self.dropped += 1
                            break
            else:
                # Logs are expendable; lifecycle/result events are not.
                if len(self.events) - self.message_count > 500:
                    for index, (item, _) in enumerate(self.events):
                        if item.get("event") == "log":
                            del self.events[index]
                            break

    def drain(self, limit=100) -> list[dict]:
        with self.lock:
            events = []
            while self.events and len(events) < limit:
                item, size = self.events.popleft()
                if item.get("event") == "message":
                    self.size -= size
                    self.message_count -= 1
                events.append(item)
            return events


def worker_command(task: str) -> list[str]:
    executable = Path(sys.executable)
    if getattr(sys, "frozen", False):
        suffix = ".exe" if executable.suffix.lower() == ".exe" else ""
        return [str(executable.with_name("majsoul-hook" + suffix)), "--gui-worker", task]
    if executable.name.lower() == "pythonw.exe":
        executable = executable.with_name("python.exe")
    return [str(executable), "-u", "-m", "majsoul_hook.gui_worker", task]


class BackendProcess:
    def __init__(self):
        self.inbox = EventInbox()
        self.process = None
        self.task = None
        self._lock = threading.Lock()

    @property
    def running(self):
        # Stay busy until the GUI consumes finished and acknowledges it.
        return self.task is not None

    def start(self, task: str, config: dict):
        if self.running:
            raise RuntimeError("A backend task is already running")
        process = subprocess.Popen(
            worker_command(task),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.process, self.task = process, task
        try:
            process.stdin.write(json.dumps(config, ensure_ascii=False) + "\n")
            process.stdin.flush()
        except Exception:
            process.kill()
            process.wait()
            self._close_pipes(process)
            self.process, self.task = None, None
            raise

        def read_output():
            for line in process.stdout:
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise ValueError()
                except ValueError:
                    event = {"event": "log", "text": line[:4096].rstrip()}
                self.inbox.put(event, len(line.encode("utf-8")))

        def read_errors():
            for line in process.stderr:
                self.inbox.put({"event": "log", "text": line[:4096].rstrip()})

        readers = [threading.Thread(target=fn, daemon=True) for fn in (read_output, read_errors)]
        for thread in readers:
            thread.start()

        def wait():
            code = process.wait()
            for thread in readers:
                thread.join()
            try:
                self._close_pipes(process)
            finally:
                self.inbox.put({"event": "finished", "task": task, "code": code})

        threading.Thread(target=wait, daemon=True).start()

    @staticmethod
    def _close_pipes(process):
        for stream in (process.stdin, process.stdout, process.stderr):
            try:
                stream.close()
            except OSError, ValueError:
                # Closing stdin may flush buffered commands after the worker exits.
                pass

    def acknowledge_finished(self):
        self.process, self.task = None, None

    def stop(self, timeout=15):
        process = self.process
        if process is None or process.poll() is not None:
            return
        with self._lock:
            try:
                process.stdin.write('{"command":"stop"}\n')
                process.stdin.flush()
            except OSError, ValueError:
                pass

        def force_stop():
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.inbox.put({"event": "log", "text": "Stop timed out; terminating the worker."})
                try:
                    process.terminate()
                except OSError:
                    pass

        threading.Thread(target=force_stop, daemon=True).start()
