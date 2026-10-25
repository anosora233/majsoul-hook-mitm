"""Shared defaults, input validation, and atomic local configuration writes."""

from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_BASE_URL = "https://game.maj-soul.com/assetbundles/DXT/"
INDEX = "bundle_info_so.majset"


def capture_process(value: str) -> str:
    process = value.strip()
    if not process or process.startswith(("!", ":")) or any(c in process for c in ",\r\n"):
        raise ValueError("--process must select one process name or PID")
    return process


def normalize_base_url(base_url: str) -> str:
    base_url = base_url.strip().rstrip("/") + "/"
    if urlsplit(base_url).scheme != "https":
        raise ValueError("Resource base URL must use HTTPS")
    return base_url


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)
