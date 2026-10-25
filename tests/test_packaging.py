import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from release import build, windows_installer


def test_gui_import_does_not_load_worker_dependencies():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import majsoul_hook.gui; "
            "blocked = {'majsoul_hook.cli', 'majsoul_hook.resources', "
            "'majsoul_hook.runtime', 'UnityPy', 'mitmproxy', 'lupa'}; "
            "assert not blocked.intersection(sys.modules), blocked.intersection(sys.modules)",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_build_refuses_to_replace_portable_user_data(tmp_path, monkeypatch):
    bundle = tmp_path / "majsoul-hook"
    data = bundle / "data" / "cosmetics-state.json"
    data.parent.mkdir(parents=True)
    data.write_text('{"synthetic": true}', encoding="utf-8")
    monkeypatch.setattr(build, "sys", SimpleNamespace(platform="win32", executable=sys.executable))
    monkeypatch.setattr(build.platform, "machine", lambda: "AMD64")
    with pytest.raises(ValueError, match="local data"):
        build.main(["--output", str(tmp_path)])
    assert data.read_text(encoding="utf-8") == '{"synthetic": true}'


def test_build_rejects_unsupported_target_before_building(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "sys", SimpleNamespace(platform="freebsd"))
    with pytest.raises(SystemExit) as error:
        build.main(["--output", str(tmp_path / "output")])
    assert error.value.code == 2
    assert not (tmp_path / "output").exists()


def test_exe_installer_stages_installed_marker_without_changing_portable_bundle(
    tmp_path, monkeypatch
):
    bundle = tmp_path / "majsoul-hook"
    bundle.mkdir()
    (bundle / "majsoul-hook-gui.exe").write_bytes(b"synthetic")
    output = tmp_path / "output"
    monkeypatch.setattr(windows_installer, "ROOT", tmp_path)
    monkeypatch.setattr(windows_installer, "find_iscc", lambda: Path("ISCC.exe"))

    def compile_package(command, **kwargs):
        staging = Path(
            next(arg.split("=", 1)[1] for arg in command if arg.startswith("/DSourceDir="))
        )
        assert (staging / "installed.json").is_file()
        assert not (staging / "data").exists()
        (output / "majsoul-hook-0.1.0-windows-x64-installer.exe").write_bytes(b"synthetic")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(windows_installer.subprocess, "run", compile_package)
    artifact = windows_installer.build_installer(bundle, output, "0.1.0")
    assert artifact.with_name(artifact.name + ".sha256").is_file()
    assert not (bundle / "installed.json").exists()


@pytest.mark.parametrize(
    ("system", "machine", "target"),
    [
        ("win32", "AMD64", "windows-x64"),
        ("darwin", "arm64", "macos-arm64"),
        ("darwin", "x86_64", "macos-x64"),
        ("linux", "aarch64", "linux-arm64"),
        ("linux", "x86_64", "linux-x64"),
    ],
)
def test_native_build_targets(monkeypatch, system, machine, target):
    monkeypatch.setattr(build, "sys", SimpleNamespace(platform=system))
    monkeypatch.setattr(build.platform, "machine", lambda: machine)
    assert build.target_name() == target


def test_unix_archive_preserves_executable_mode_and_symlink(tmp_path):
    import stat
    import tarfile

    bundle = tmp_path / "Majsoul Hook.app"
    binary = bundle / "Contents/MacOS/majsoul-hook"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"synthetic")
    binary.chmod(0o755)
    link = binary.with_name("worker-link")
    try:
        link.symlink_to(binary.name)
    except OSError:
        pytest.skip("Creating symlinks requires privileges on this Windows host")
    archive = build.archive_bundle(bundle, tmp_path, "0.1.0", "macos-arm64")
    with tarfile.open(archive) as packed:
        assert packed.getmember("Majsoul Hook.app/Contents/MacOS/worker-link").issym()
        mode = packed.getmember("Majsoul Hook.app/Contents/MacOS/majsoul-hook").mode
        assert mode == stat.S_IMODE(binary.stat().st_mode)
        if sys.platform != "win32":
            assert mode & 0o111
    assert archive.with_name(archive.name + ".sha256").is_file()
