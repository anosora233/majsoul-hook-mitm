"""Run each GUI regression in a fresh interpreter to isolate Tcl/Tk state."""

import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests/test_gui.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    nodes = [
        line.strip()
        for line in collected.stdout.splitlines()
        if line.startswith("tests/test_gui.py::")
    ]
    if not nodes:
        raise RuntimeError(f"No GUI regressions collected: {collected.stdout}")
    work = (ROOT / "build/gui-tests").resolve()
    if not work.is_relative_to(ROOT):
        raise ValueError("GUI test work directory must stay inside the repository")
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as temporary:
        for index, node in enumerate(nodes):
            report = Path(temporary) / f"{index}.xml"
            subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-rs", f"--junitxml={report}", node],
                cwd=ROOT,
                check=True,
            )
            if ET.parse(report).find(".//skipped") is not None:
                raise RuntimeError(f"GUI test requires working Tk/display support: {node}")
    print(f"Validated {len(nodes)} GUI cases in separate interpreters")


if __name__ == "__main__":
    main()
