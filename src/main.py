import os
from os.path import exists
from json import load, dump

if not exists("settings.json"):
    SETTINGS = {
        "listen_port": 80,
        "enable_helper": False,
        "enable_skins": False,
        "upstream_proxy": None,
        "pure_python_protobuf": False,
        # "upstream_proxy": "http://127.0.0.1:12345"
    }
    dump(SETTINGS, open("settings.json", "w"), indent=2)

SETTINGS = load(open("settings.json", "r"))
if SETTINGS["pure_python_protobuf"]:
    os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"


async def start_proxy():
    from addons import WebSocketAddon
    from mitmproxy.tools.dump import DumpMaster
    from mitmproxy import options
    mode = [f"upstream:{SETTINGS['upstream_proxy']}"] if SETTINGS["upstream_proxy"] else ["regular"]
    opts = options.Options(listen_host="0.0.0.0", listen_port=SETTINGS["listen_port"], http2=False, mode=mode)
    master = DumpMaster(
        opts,
        with_termlog=False,
        with_dumper=False,
    )
    master.addons.add(WebSocketAddon())
    await master.run()
    return master

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(start_proxy())
    except KeyboardInterrupt:
        pass
