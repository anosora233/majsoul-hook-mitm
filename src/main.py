from os import environ
from os.path import exists
from json import load, dump


async def start_proxy():
    from addons import WebSocketAddon
    from mitmproxy.tools.dump import DumpMaster
    from mitmproxy import options

    mode = (
        [f"upstream:{SETTINGS['upstream_proxy']}"]
        if SETTINGS["upstream_proxy"]
        else ["regular"]
    )
    opts = options.Options(
        listen_port=SETTINGS["listen_port"],
        http2=False,
        mode=mode,
    )
    master = DumpMaster(
        opts,
        with_termlog=SETTINGS["termlog"],
        with_dumper=SETTINGS["dumper"],
    )

    master.addons.add(WebSocketAddon())
    await master.run()
    return master


def main():
    try:
        __import__("asyncio").run(start_proxy())
    except KeyboardInterrupt:
        pass


SETTINGS = {
    "pure_python_protobuf": False,
    "termlog": False,
    "dumper": True,
    "listen_port": 23410,
    "enable_skins": False,
    "enable_helper": False,
    "upstream_proxy": None,
}

if exists("settings.json"):
    SETTINGS.update(load(open("settings.json", "r")))
dump(SETTINGS, open("settings.json", "w"), indent=2)

if __name__ == "__main__":
    main()
