# Compatibility entry point for older local build commands.
from pathlib import Path

exec((Path(SPECPATH) / "app.spec").read_text(encoding="utf-8"))
