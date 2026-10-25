"""Exercise a relocated native bundle without interception or trust changes."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def smoke(bundle: Path, resource_cache: Path | None = None) -> dict:
    bundle = bundle.resolve()
    work = (ROOT / "build/smoke").resolve()
    if not work.is_relative_to(ROOT):
        raise ValueError("Smoke directory must stay inside the build directory")
    work.mkdir(parents=True, exist_ok=True)
    env = {
        name: value
        for name, value in os.environ.items()
        if name
        not in {
            "PYTHONPATH",
            "PYTHONHOME",
            "TCL_LIBRARY",
            "TK_LIBRARY",
            "MAJSOUL_HOOK_HOME",
        }
    }
    env["PYTHONIOENCODING"] = "utf-8"
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    with tempfile.TemporaryDirectory(prefix="portable-测试-", dir=work) as temporary:
        location = Path(temporary).resolve()
        if not location.is_relative_to(work):
            raise ValueError("Unexpected temporary smoke directory")
        relocated = location / ("Majsoul Hook.app" if bundle.suffix == ".app" else "portable app")
        shutil.copytree(bundle, relocated, symlinks=True)
        home = location / "home"
        home.mkdir()
        env.update(HOME=str(home), USERPROFILE=str(home), LOCALAPPDATA=str(home / "Local"))
        unrelated = location / "unrelated working directory"
        unrelated.mkdir()
        mac_app = relocated.suffix == ".app"
        directory = relocated / "Contents/MacOS" if mac_app else relocated
        suffix = ".exe" if sys.platform == "win32" else ""
        console = directory / ("majsoul-hook" + suffix)
        gui = directory / ("majsoul-hook-gui" + suffix)

        def run(arguments, *, content=None, expected=0, executable=console):
            result = subprocess.run(
                [str(executable), *arguments],
                input=content,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                cwd=unrelated,
                env=env,
                timeout=120,
                creationflags=flags,
            )
            if result.returncode != expected:
                raise RuntimeError(
                    f"{arguments}: exit {result.returncode}\n{result.stdout}\n{result.stderr}"
                )
            return result

        def check_gui():
            if sys.platform == "win32":
                from release.smoke_windows import gui_smoke

                gui_smoke(gui, unrelated, env)
            else:
                run(["--smoke-test"], executable=gui)

        run(["--help"])
        report = json.loads(run(["doctor"]).stdout)
        expected_data = (
            (home / "Library/Application Support/majsoul-hook/data")
            if mac_app
            else relocated / "data"
        )
        if not report["frozen"] or Path(report["data_directory"]) != expected_data:
            raise RuntimeError(f"Incorrect runtime paths: {report}")
        result = run(
            ["--gui-worker", "capture"],
            content=json.dumps(
                {
                    "process": "unused-smoke-selector",
                    "schema": str(location / "missing.json"),
                }
            )
            + "\n",
            expected=1,
        )
        event = json.loads(result.stdout)
        if event.get("event") != "error" or event.get("error_type") != "FileNotFoundError":
            raise RuntimeError(f"Worker transport failed: {event}")
        run(["resources", "--base-url", "http://invalid.test/"], expected=1)
        check_gui()
        if sys.platform == "win32":
            marker = relocated / "installed.json"
            marker.write_text("{}", encoding="utf-8")
            installed = json.loads(run(["doctor"]).stdout)
            if Path(installed["data_directory"]) != home / "Local/majsoul-hook/data":
                raise RuntimeError(f"Incorrect installer data paths: {installed}")
            check_gui()
            marker.unlink()
            report["installed_layout"] = True
        if resource_cache is not None:
            result = run(
                ["--gui-worker", "update"],
                content=json.dumps(
                    {
                        "schema": str(expected_data / "protocol.json"),
                        "cache": str(resource_cache.resolve()),
                        "base_url": "https://game.maj-soul.com/assetbundles/DXT/",
                        "offline": True,
                    }
                )
                + "\n",
            )
            event = json.loads(result.stdout)
            if event.get("event") != "resources" or not event["status"]["cosmetics"]:
                raise RuntimeError(f"Offline resource extraction failed: {event}")
            report["offline_resource_methods"] = event["status"]["methods"]
            check_gui()
            report["gui_with_resources"] = True
        report.update(gui_start_and_close=True, worker_transport=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--resource-cache", type=Path)
    args = parser.parse_args()
    report = smoke(args.bundle, args.resource_cache)
    (args.bundle.parent / "smoke.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
