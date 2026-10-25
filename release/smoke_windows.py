"""Exercise a relocated Windows bundle without capturing traffic or changing trust."""

import ctypes
import subprocess
import time
from ctypes import wintypes
from pathlib import Path


def gui_smoke(executable: Path, cwd: Path, env: dict):
    process = subprocess.Popen(
        [str(executable)], cwd=cwd, env=env, creationflags=subprocess.CREATE_NO_WINDOW
    )
    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    handles = []

    @callback_type
    def visit(handle, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        name = ctypes.create_unicode_buffer(128)
        user32.GetClassNameW(handle, name, len(name))
        if (
            pid.value == process.pid
            and user32.IsWindowVisible(handle)
            and name.value == "TkTopLevel"
        ):
            handles.append(handle)
        return True

    try:
        deadline = time.monotonic() + 25
        while not handles and time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"GUI exited before opening a window: {process.returncode}")
            user32.EnumWindows(visit, 0)
            time.sleep(0.1)
        if not handles:
            raise RuntimeError("No visible Tk GUI window appeared")
        # Close only the test process's own root through its normal shutdown handler.
        user32.PostMessageW(handles[0], 0x0010, 0, 0)
        if process.wait(timeout=15) != 0:
            raise RuntimeError(f"GUI shutdown failed: {process.returncode}")
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    from smoke import main

    main()
