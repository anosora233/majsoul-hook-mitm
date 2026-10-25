"""Build and smoke-test native desktop bundles on Windows, macOS, and Linux."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def target_name():
    systems = {"win32": "windows", "darwin": "macos", "linux": "linux"}
    architectures = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}
    system = systems.get(sys.platform)
    architecture = architectures.get(platform.machine().lower())
    if not system or not architecture or (system == "windows" and architecture != "x64"):
        raise ValueError("Supported native targets: Windows x64, macOS/Linux x64 and arm64")
    return f"{system}-{architecture}"


def checksum(path):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    path.with_name(path.name + ".sha256").write_text(f"{digest}  {path.name}\n", encoding="ascii")
    return digest


def validate_bundle(bundle, output):
    if not bundle.exists():
        return
    if bundle.is_symlink() or bundle.resolve().parent != output:
        raise ValueError("Refusing to replace a redirected bundle directory")
    public = {
        "_internal",
        "majsoul-hook.exe",
        "majsoul-hook-gui.exe",
        "majsoul-hook",
        "majsoul-hook-gui",
        "LICENSE",
        "PYTHON-LICENSE.txt",
        "README.md",
        "README.ja.md",
        "README.zh-CN.md",
        "docs",
    }
    if bundle.suffix == ".app" or any(path.name not in public for path in bundle.iterdir()):
        raise ValueError(
            "Existing bundle may contain local data; choose a fresh --output directory"
        )


def python_license():
    for candidate in (
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sysconfig.get_path("stdlib")) / "LICENSE.txt",
        Path(sys.base_prefix) / "share/licenses/python/LICENSE",
    ):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Cannot locate the Python runtime license")


def archive_bundle(bundle, output, version, target):
    name = f"majsoul-hook-{version}-{target}-portable"
    if target.startswith("windows-"):
        archive = output / f"{name}.zip"
        with zipfile.ZipFile(
            archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as zipped:
            for path in sorted(bundle.rglob("*")):
                if path.is_file():
                    zipped.write(path, path.relative_to(output))
    else:
        archive = output / f"{name}.tar.gz"
        # tar preserves executable permissions and macOS bundle symlinks.
        with tarfile.open(archive, "w:gz", dereference=False) as packed:
            packed.add(bundle, arcname=bundle.name)
    checksum(archive)
    return archive


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--resource-cache", type=Path)
    parser.add_argument(
        "--installer", action="store_true", help="Also build the Windows EXE installer"
    )
    args = parser.parse_args(argv)
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/tags/v") and ref.removeprefix("refs/tags/v") != version:
        parser.error("The Git tag must match the project version")
    try:
        target = target_name()
    except ValueError as exc:
        parser.error(str(exc))
    if args.installer and sys.platform != "win32":
        parser.error("The EXE installer is only built on Windows")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    bundle = output / ("Majsoul Hook.app" if sys.platform == "darwin" else "majsoul-hook")
    validate_bundle(bundle, output)
    if sys.platform == "darwin":
        validate_bundle(output / "majsoul-hook", output)
    work = ROOT / "build" / target
    if not work.resolve().is_relative_to(ROOT):
        raise ValueError("Build work directory must stay inside the repository")
    work.mkdir(parents=True, exist_ok=True)
    license_file = python_license()
    log = work / "pyinstaller.log"
    with log.open("w", encoding="utf-8") as stream:
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "PyInstaller",
                "--noconfirm",
                "--clean",
                "--distpath",
                str(output),
                "--workpath",
                str(work / "pyinstaller"),
                str(ROOT / "release/app.spec"),
            ],
            cwd=ROOT,
            stdout=stream,
            stderr=subprocess.STDOUT,
            env={**os.environ, "MAJSOUL_PYTHON_LICENSE": str(license_file)},
        )
    if process.returncode:
        print(log.read_text(encoding="utf-8")[-12000:], file=sys.stderr)
        raise SystemExit(process.returncode)
    if sys.platform != "darwin":
        for name in ("LICENSE", "README.md", "README.ja.md", "README.zh-CN.md"):
            shutil.copy2(ROOT / name, bundle / name)
        shutil.copy2(license_file, bundle / "PYTHON-LICENSE.txt")
        shutil.copytree(ROOT / "docs", bundle / "docs", dirs_exist_ok=True)
    from release.smoke import smoke

    report = smoke(bundle, args.resource_cache)
    (output / "smoke.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    archive = archive_bundle(bundle, output, version, target)
    components = {}
    for path in bundle.rglob("*"):
        if path.is_file() and not path.is_symlink():
            relative = path.relative_to(bundle)
            if relative.parts[0] == "Contents" and len(relative.parts) > 2:
                component = relative.parts[2]
            else:
                component = (
                    relative.parts[1] if relative.parts[0] == "_internal" else relative.parts[0]
                )
            components[component] = components.get(component, 0) + path.stat().st_size
    sizes = {
        "bundle_bytes": sum(components.values()),
        "archive_bytes": archive.stat().st_size,
        "components": dict(sorted(components.items(), key=lambda item: -item[1])),
    }
    (output / "size.json").write_text(json.dumps(sizes, indent=2) + "\n", encoding="utf-8")
    artifacts = [archive]
    if args.installer:
        from release.windows_installer import build_installer

        artifacts.append(build_installer(bundle, output, version))
    print(
        json.dumps(
            {
                "target": target,
                "bundle": str(bundle),
                "artifacts": list(map(str, artifacts)),
                "bundle_bytes": sizes["bundle_bytes"],
                "archive_bytes": sizes["archive_bytes"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
