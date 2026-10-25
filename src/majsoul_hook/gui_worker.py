"""Private JSONL worker protocol. Capture lives on this process's main thread."""

import asyncio
import json
import logging
import sys
import threading
from contextlib import redirect_stdout
from pathlib import Path

from .config import capture_process
from .cosmetics import Cosmetics
from .gui_backend import check_resources, local_resource_status
from .resources import update_resources
from .runtime import run_capture
from .schema import Schema


def main(task=None):
    transport = sys.stdout
    lock = threading.Lock()

    def emit(event):
        with lock:
            transport.write(json.dumps(event, ensure_ascii=False) + "\n")
            transport.flush()

    try:
        config = json.loads(sys.stdin.readline())
        task = task if task is not None else sys.argv[1]
        # mitmproxy/UnityPy output belongs on stderr, never in the event channel.
        with redirect_stdout(sys.stderr):
            if task == "capture":
                stop = threading.Event()

                def controls():
                    try:
                        for line in sys.stdin:
                            if json.loads(line).get("command") == "stop":
                                break
                    finally:
                        # A vanished GUI closes stdin; do not leave capture orphaned.
                        stop.set()

                threading.Thread(target=controls, daemon=True).start()
                process = capture_process(config["process"])
                schema = Schema.load(Path(config["schema"]))
                cosmetics = None
                if config.get("cosmetics"):
                    cosmetics = Cosmetics.from_schema(schema, Path(config["state"]))
                asyncio.run(
                    run_capture(
                        process,
                        schema,
                        cosmetics=cosmetics,
                        event_sink=emit,
                        stop_event=stop,
                        confdir=Path(config["confdir"]) if config.get("confdir") else None,
                    )
                )
            elif task == "check":
                emit(
                    {
                        "event": "resources",
                        "status": check_resources(Path(config["schema"]), config["base_url"]),
                    }
                )
            elif task == "update":
                logging.basicConfig(level=logging.INFO)
                update_resources(
                    Path(config["schema"]),
                    Path(config["cache"]),
                    base_url=config["base_url"],
                    include_cosmetics=True,
                    offline=config.get("offline", False),
                )
                emit(
                    {"event": "resources", "status": local_resource_status(Path(config["schema"]))}
                )
            else:
                raise ValueError("Unknown worker task")
    except Exception as exc:
        emit({"event": "error", "message": str(exc), "error_type": type(exc).__name__})
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
