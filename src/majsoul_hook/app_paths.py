"""Writable defaults for source runs, portable folders, and installed apps."""

import os
import sys
from pathlib import Path


def default_path(relative: str) -> Path:
    if directory := os.environ.get("MAJSOUL_HOOK_HOME"):
        return Path(directory).expanduser().resolve() / relative
    if getattr(sys, "frozen", False):
        directory = Path(sys.executable).resolve().parent
        mac_app = directory.name == "MacOS" and directory.parent.name == "Contents"
        if mac_app or (directory / "installed.json").is_file():
            if mac_app:
                directory = Path.home() / "Library/Application Support/majsoul-hook"
            elif getattr(sys, "platform", "") == "win32":
                directory = (
                    Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
                    / "majsoul-hook"
                )
            else:
                directory = (
                    Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
                    / "majsoul-hook"
                )
        return directory / relative
    return Path(relative)


def default_confdir() -> Path | None:
    return (
        default_path(".mitmproxy")
        if getattr(sys, "frozen", False) or os.environ.get("MAJSOUL_HOOK_HOME")
        else None
    )
