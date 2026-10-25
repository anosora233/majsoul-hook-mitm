"""Read-only dependency checks for source and packaged installations."""

import sys
from importlib import import_module
from importlib.metadata import version
from pathlib import Path

from .app_paths import default_path
from .gui_i18n import translate


def check_runtime() -> dict:
    import certifi
    import mitmproxy_rs
    import UnityPy
    from google.protobuf.descriptor_pb2 import FileDescriptorProto
    from lupa.lua51 import LuaRuntime

    # Exercise native modules without opening sockets or installing certificates.
    import_module("UnityPy.UnityPyBoost")
    # Import the actual capture stack, including mitmproxy's eager addon imports.
    # This detects over-aggressive packaging exclusions without starting a proxy.
    import_module("majsoul_hook.runtime")
    if LuaRuntime(register_eval=False, register_builtins=False).eval("1 + 1") != 2:
        raise ValueError("Lua runtime check failed")
    descriptor = FileDescriptorProto(name="diagnostic.proto")
    if FileDescriptorProto.FromString(descriptor.SerializeToString()).name != descriptor.name:
        raise ValueError("Protobuf runtime check failed")
    if not Path(certifi.where()).is_file():
        raise FileNotFoundError("Bundled TLS CA certificates are missing")
    native_files = []
    if sys.platform == "win32":
        import mitmproxy_windows

        directory = mitmproxy_windows.executable_path().parent
        for name in ("windows-redirector.exe", "WinDivert.dll", "WinDivert64.sys"):
            if not (directory / name).is_file():
                raise FileNotFoundError(directory / name)
            native_files.append(name)
    elif sys.platform == "linux":
        import mitmproxy_linux

        executable = mitmproxy_linux.executable_path()
        if not executable.is_file():
            raise FileNotFoundError(executable)
        native_files.append(executable.name)
    elif sys.platform == "darwin":
        import mitmproxy_macos

        archive = Path(mitmproxy_macos.__file__).parent / "Mitmproxy Redirector.app.tar"
        if not archive.is_file():
            raise FileNotFoundError(archive)
        native_files.append(archive.name)
    return {
        "ok": True,
        "frozen": bool(getattr(sys, "frozen", False)),
        "data_directory": str(default_path("data").resolve()),
        "dependencies": {
            name: version(name)
            for name in ("mitmproxy", "protobuf", "UnityPy", "lupa", "mitmproxy-rs")
        },
        "unity": UnityPy.__version__,
        "native_proxy": mitmproxy_rs.__name__,
        "native_files": native_files,
        "translations": {
            language: translate(language, "Start capture") for language in ("ja", "zh")
        },
    }
