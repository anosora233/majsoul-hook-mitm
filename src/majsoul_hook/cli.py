"""Explicit resource preparation and local-only capture commands."""

import argparse
import asyncio
import json
import logging
from pathlib import Path

from .app_paths import default_confdir, default_path
from .config import DEFAULT_BASE_URL, capture_process
from .schema import Schema


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Mahjong Soul capture and local cosmetic overrides")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("gui", help="Open the Tkinter capture and message inspector")
    commands.add_parser("doctor", help="Check runtime dependencies without capturing traffic")
    resources = commands.add_parser(
        "resources", help="Build protocol resources from client bundles"
    )
    resources.add_argument("--output", type=Path, default=default_path("data/protocol.json"))
    resources.add_argument("--cache", type=Path, default=default_path(".cache/bundles"))
    resources.add_argument("--base-url", default=DEFAULT_BASE_URL)
    resources.add_argument("--offline", action="store_true")
    resources.add_argument(
        "--cosmetics", action="store_true", help="Include cosmetic configuration"
    )
    capture = commands.add_parser("capture", help="Capture a local process with mitmproxy")
    capture.add_argument(
        "--process", required=True, help="Process name or PID, e.g. chrome or 1234"
    )
    capture.add_argument("--schema", type=Path, default=default_path("data/protocol.json"))
    capture.add_argument(
        "--host", action="append", default=[], help="Host suffix to decode; repeatable"
    )
    capture.add_argument("--output", type=Path, help="Append full decoded messages as JSON Lines")
    capture.add_argument("--verbose", action="store_true", help="Log full decoded messages")
    capture.add_argument(
        "--confdir",
        type=Path,
        default=default_confdir(),
        help="CA directory; config.yaml/yml are not read",
    )
    capture.add_argument(
        "--cosmetics", action="store_true", help="Enable local cosmetic modifications"
    )
    capture.add_argument(
        "--state",
        type=Path,
        default=default_path("data/cosmetics-state.json"),
        help="Account-scoped local cosmetic settings",
    )
    return root


def main(argv: list[str] | None = None) -> None:
    root = parser()
    args = root.parse_args(argv)
    if args.command == "gui":
        from .gui import main as gui_main

        gui_main()
        return
    try:
        if args.command == "resources":
            logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
            from .resources import update_resources

            print(
                json.dumps(
                    update_resources(
                        args.output,
                        args.cache,
                        base_url=args.base_url,
                        offline=args.offline,
                        include_cosmetics=args.cosmetics,
                    ),
                    ensure_ascii=False,
                )
            )
        elif args.command == "doctor":
            from .diagnostics import check_runtime

            print(json.dumps(check_runtime(), ensure_ascii=False))
        else:
            from .runtime import run_capture

            process = capture_process(args.process)
            schema = Schema.load(args.schema)
            cosmetics = None
            if args.cosmetics:
                from .cosmetics import Cosmetics

                cosmetics = Cosmetics.from_schema(schema, args.state)
            asyncio.run(
                run_capture(
                    process,
                    schema,
                    hosts=tuple(h.lower().strip(".") for h in args.host),
                    output=args.output,
                    verbose=args.verbose,
                    confdir=args.confdir,
                    cosmetics=cosmetics,
                )
            )
    except (OSError, ValueError, KeyError, ImportError) as exc:
        root.exit(1, f"Error: {exc}\n")
    except KeyboardInterrupt, asyncio.CancelledError:
        pass
