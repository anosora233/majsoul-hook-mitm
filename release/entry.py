"""Frozen entry point for the console and private GUI worker."""

import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    # Frozen Python ignores PYTHONIOENCODING; the private worker protocol is UTF-8.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if stream is not None:
            stream.reconfigure(encoding="utf-8", errors="replace")
    if sys.argv[1:2] == ["--gui-worker"]:
        if len(sys.argv) != 3:
            raise SystemExit("Expected --gui-worker TASK")
        from majsoul_hook.gui_worker import main

        main(sys.argv[2])
    else:
        from majsoul_hook.cli import main

        main()
