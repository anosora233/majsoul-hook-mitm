from pathlib import Path
from types import SimpleNamespace

import pytest

from majsoul_hook import app_paths, gui_backend
from majsoul_hook.cli import parser


def test_source_defaults_keep_working_directory_semantics(monkeypatch):
    monkeypatch.setattr(app_paths, "sys", SimpleNamespace(frozen=False))
    assert app_paths.default_path("data/protocol.json") == Path("data/protocol.json")
    assert app_paths.default_confdir() is None


def test_frozen_defaults_are_beside_executable_not_working_directory(tmp_path, monkeypatch):
    home = tmp_path / "portable"
    monkeypatch.setattr(
        app_paths, "sys", SimpleNamespace(frozen=True, executable=str(home / "majsoul-hook.exe"))
    )
    monkeypatch.chdir(tmp_path)
    args = parser().parse_args(["capture", "--process", "test"])
    assert args.schema == home / "data/protocol.json"
    assert args.state == home / "data/cosmetics-state.json"
    assert args.confdir == home / ".mitmproxy"
    explicit = parser().parse_args(["capture", "--process", "test", "--schema", "custom.json"])
    assert explicit.schema == Path("custom.json")
    assert not home.exists()


@pytest.mark.parametrize("executable", ["python.exe", "pythonw.exe"])
def test_source_worker_uses_python_interpreter(tmp_path, monkeypatch, executable):
    monkeypatch.setattr(gui_backend, "sys", SimpleNamespace(executable=str(tmp_path / executable)))
    assert gui_backend.worker_command("check") == [
        str(tmp_path / "python.exe"),
        "-u",
        "-m",
        "majsoul_hook.gui_worker",
        "check",
    ]


def test_frozen_gui_uses_console_sibling_for_worker(tmp_path, monkeypatch):
    monkeypatch.setattr(
        gui_backend,
        "sys",
        SimpleNamespace(frozen=True, executable=str(tmp_path / "majsoul-hook-gui.exe")),
    )
    assert gui_backend.worker_command("update") == [
        str(tmp_path / "majsoul-hook.exe"),
        "--gui-worker",
        "update",
    ]


def test_mac_app_uses_user_storage_and_native_worker(tmp_path, monkeypatch):
    executable = tmp_path / "Majsoul Hook.app/Contents/MacOS/majsoul-hook-gui"
    monkeypatch.setattr(app_paths.Path, "home", lambda: tmp_path / "home")
    monkeypatch.setattr(app_paths, "sys", SimpleNamespace(frozen=True, executable=str(executable)))
    monkeypatch.setattr(
        gui_backend, "sys", SimpleNamespace(frozen=True, executable=str(executable))
    )
    assert (
        app_paths.default_path("data")
        == tmp_path / "home/Library/Application Support/majsoul-hook/data"
    )
    assert gui_backend.worker_command("check") == [
        str(executable.with_name("majsoul-hook")),
        "--gui-worker",
        "check",
    ]


def test_installed_windows_keeps_data_outside_program_files(tmp_path, monkeypatch):
    program = tmp_path / "program"
    program.mkdir()
    (program / "installed.json").write_text("{}")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user"))
    monkeypatch.setattr(
        app_paths,
        "sys",
        SimpleNamespace(
            platform="win32", frozen=True, executable=str(program / "majsoul-hook.exe")
        ),
    )
    assert app_paths.default_path("data") == tmp_path / "user/majsoul-hook/data"


def test_explicit_data_home_applies_to_source_and_frozen(tmp_path, monkeypatch):
    monkeypatch.setenv("MAJSOUL_HOOK_HOME", str(tmp_path / "storage"))
    for frozen in (False, True):
        monkeypatch.setattr(app_paths, "sys", SimpleNamespace(frozen=frozen))
        assert app_paths.default_confdir() == tmp_path / "storage/.mitmproxy"
