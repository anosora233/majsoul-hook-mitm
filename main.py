from os import system
from _thread import start_new_thread
from time import sleep
from win32gui import GetWindowText, GetWindowRect, SetWindowPos, EnumWindows
from win32con import HWND_TOPMOST
from json import load
from mitmproxy.tools.main import mitmdump
from os import _exit
from atexit import register

import winreg


ARGS = ["-p", "23410", "-s", "src/addons.py"]
SETTINGS = load(open("bin/settings.json", "r"))
UPSTREAM_PROXY = SETTINGS["UPSTREAM_PROXY"]

if len(UPSTREAM_PROXY):
    ARGS.extend(["-m", f"upstream:{UPSTREAM_PROXY}"])

WindowsTitle = "Console · 🀄"


def top_alacritty(hwnd, mouse) -> None:
    if WindowsTitle in GetWindowText(hwnd):
        rect = GetWindowRect(hwnd)
        SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            rect[0],
            rect[1],
            rect[2] - rect[0],
            rect[3] - rect[1],
            0,
        )


REGISTRY = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
KEY = winreg.OpenKey(
    REGISTRY,
    r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
    0,
    winreg.KEY_ALL_ACCESS,
)

try:
    PROXY, __ = winreg.QueryValueEx(KEY, "ProxyServer")
    ENABLE, __ = winreg.QueryValueEx(KEY, "ProxyEnable")
except Exception:
    PROXY = ""
    ENABLE = 0

winreg.SetValueEx(KEY, "ProxyServer", 0, winreg.REG_SZ, "127.0.0.1:23410")
winreg.SetValueEx(KEY, "ProxyEnable", 0, winreg.REG_DWORD, 1)


def reset_proxy() -> None:
    winreg.SetValueEx(KEY, "ProxyServer", 0, winreg.REG_SZ, PROXY)
    winreg.SetValueEx(KEY, "ProxyEnable", 0, winreg.REG_DWORD, ENABLE)

    print("RESET SYSTEM PROXY DONE")


def run(id: str) -> None:
    system("bin\\alacritty.exe --config-file bin\\alacritty.yml")

    reset_proxy(), _exit(0)


if __name__ == "__main__":
    register(reset_proxy)
    start_new_thread(run, (WindowsTitle,))

    sleep(0.5)

    EnumWindows(top_alacritty, None)
    mitmdump(args=ARGS)
