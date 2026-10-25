"""Export a locally built Docker image and its checksum without pushing a registry."""

import gzip
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from release.build import checksum, target_name  # noqa: E402


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python release/export_image.py IMAGE")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    output = ROOT / "dist" / f"majsoul-hook-{version}-{target_name()}-docker.tar.gz"
    output.parent.mkdir(parents=True, exist_ok=True)
    with subprocess.Popen(["docker", "save", sys.argv[1]], stdout=subprocess.PIPE) as process:
        with gzip.open(output, "wb", compresslevel=6) as packed:
            shutil.copyfileobj(process.stdout, packed)
        if process.wait() != 0:
            output.unlink(missing_ok=True)
            raise RuntimeError("docker save failed")
    checksum(output)
    print(output)


if __name__ == "__main__":
    main()
