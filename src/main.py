from os import system
from _thread import start_new_thread
from mitmproxy.tools.main import mitmdump
from json import load

# import winreg


ARGS = ["-p", "23410", "-s", "src/addons.py"]
SETTINGS = load(open("conf/settings.json", "r"))
UPSTREAM_PROXY = SETTINGS["UPSTREAM_PROXY"]

if len(UPSTREAM_PROXY):
    ARGS.extend(["-m", f"upstream:{UPSTREAM_PROXY}"])

WindowsTitle = "Console · 🀄"

# REGISTRY = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
# KEY = winreg.OpenKey(
#     REGISTRY,
#     r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
#     0,
#     winreg.KEY_ALL_ACCESS,
# )

# try:
#     PROXY, __ = winreg.QueryValueEx(KEY, "ProxyServer")
#     ENABLE, __ = winreg.QueryValueEx(KEY, "ProxyEnable")
# except Exception:
#     PROXY = ""
#     ENABLE = 0

# winreg.SetValueEx(KEY, "ProxyServer", 0, winreg.REG_SZ, "127.0.0.1:23410")
# winreg.SetValueEx(KEY, "ProxyEnable", 0, winreg.REG_DWORD, 1)


# def reset_proxy() -> None:
#     winreg.SetValueEx(KEY, "ProxyServer", 0, winreg.REG_SZ, PROXY)
#     winreg.SetValueEx(KEY, "ProxyEnable", 0, winreg.REG_DWORD, ENABLE)

#     print("=======================")
#     print("RESET SYSTEM PROXY DONE")
#     print("=======================")


def run(id: str) -> None:
    system('start cmd /c "title Console · 🀄 && bin\\console.exe -majsoul"')


def main() -> None:
    start_new_thread(run, (WindowsTitle,))
    mitmdump(args=ARGS)


if __name__ == "__main__":
    main()
