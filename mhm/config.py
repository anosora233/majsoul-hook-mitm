from rich.console import Console
from rich.panel import Panel
from rich.json import JSON
from rich.logging import RichHandler
from os.path import exists
from os import environ
from json import load, dump


def fetch_maxid():
    import requests
    import random

    with console.status("[magenta]Fetch the latest server version") as status:
        rand_a: int = random.randint(0, 1e9)
        rand_b: int = random.randint(0, 1e9)

        ver_url = f"https://game.maj-soul.com/1/version.json?randv={rand_a}{rand_b}"
        response = requests.get(ver_url, proxies={"https": settings["upstream_proxy"]})
        response.raise_for_status()
        ver_data = response.json()

        server = settings.get("server")
        if server and server["version"] == ver_data["version"]:
            return

        res_url = f"https://game.maj-soul.com/1/resversion{ver_data['version']}.json"
        response = requests.get(res_url, proxies={"https": settings["upstream_proxy"]})
        response.raise_for_status()
        res_data = response.json()

        max_charid = 200070
        while str(f"extendRes/emo/e{max_charid}/0.png") in res_data["res"]:
            max_charid += 1

        settings["server"] = {"version": ver_data["version"], "max_charid": max_charid}


def init():
    # init settings.json
    if not exists("settings.json"):
        dump(settings, open("settings.json", "w"), indent=2)
        console.print(
            Panel.fit(JSON.from_data(data=settings), title="Initialize Configuration"),
        )
        console.input("Press [red]Enter[/red] to exit ... :smiley: ")
        raise SystemExit
    else:
        settings.update(load(open("settings.json", "r")))

    # apply settings
    if settings["enable_skins"]:
        fetch_maxid()
    if settings["pure_python_protobuf"]:
        environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

    # save settings.json
    dump(settings, open("settings.json", "w"), indent=2)
    console.print(
        Panel.fit(JSON.from_data(data=settings), title="Load Configuration"),
    )


settings = {
    "dumper": False,
    "log_level": "info",
    "listen_port": 23410,
    "socks5_port": 23412,
    "enable_skins": False,
    "enable_aider": False,
    "enable_chest": False,
    "upstream_proxy": None,
    "random_star_char": False,
    "pure_python_protobuf": False,
}

console = Console()

# init func
init()

# logger
import logging

logger = logging.getLogger(__name__)
logger.propagate = False
logger.setLevel(settings["log_level"].upper())
logger.addHandler(RichHandler(markup=True, rich_tracebacks=True))

# login methods
entrance = {
    ".lq.Lobby.oauth2Login",
    ".lq.Lobby.emailLogin",
    ".lq.Lobby.login",
}
