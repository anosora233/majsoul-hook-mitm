"""Build a per-user Inno Setup EXE installer from a clean onedir bundle."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def find_iscc():
    if override := os.environ.get("ISCC"):
        path = Path(override)
        if path.is_file():
            return path
        raise FileNotFoundError(path)
    if path := shutil.which("iscc"):
        return Path(path)
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        for major in (7, 6):
            path = (
                Path(os.environ.get(variable, "C:/Program Files")) / f"Inno Setup {major}/ISCC.exe"
            )
            if path.is_file():
                return path
    raise FileNotFoundError("Missing Inno Setup compiler. Install Inno Setup or set ISCC")


def build_installer(bundle, output, version):
    from release.build import checksum, validate_bundle

    bundle, output = bundle.resolve(), output.resolve()
    validate_bundle(bundle, bundle.parent)
    compiler = find_iscc()
    work = (ROOT / "build/windows-x64").resolve()
    if not work.is_relative_to(ROOT):
        raise ValueError("Installer work directory must stay inside the repository")
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="installer-", dir=work) as temporary:
        staging = Path(temporary) / "payload"
        shutil.copytree(bundle, staging)
        (staging / "installed.json").write_text(
            json.dumps({"layout": "installed"}), encoding="utf-8"
        )
        command = [
            str(compiler),
            f"/DAppVersion={version}",
            f"/DSourceDir={staging}",
            f"/DOutputDir={output}",
            str(ROOT / "release/windows.iss"),
        ]
        log = work / "iscc.log"
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(log.read_text(encoding="utf-8", errors="replace")[-12000:])
        artifact = output / f"majsoul-hook-{version}-windows-x64-installer.exe"
        if not artifact.is_file():
            raise FileNotFoundError(artifact)
        checksum(artifact)
    return artifact
