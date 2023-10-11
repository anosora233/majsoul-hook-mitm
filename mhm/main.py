import asyncio
import os

from mitmproxy.tools.dump import DumpMaster
from mitmproxy import options
from .config import settings
from .addons import addons


async def start_proxy():
    mode = [
        f"socks5@{settings['socks5_port']}",
        f"upstream:{settings['upstream_proxy']}"
        if settings["upstream_proxy"]
        else "regular",
    ]
    opts = options.Options(
        listen_port=settings["listen_port"],
        http2=False,
        mode=mode,
    )
    master = DumpMaster(
        opts,
        with_termlog=True,
        with_dumper=settings["dumper"],
    )

    master.addons.add(*addons)
    await master.run()
    return master


async def start_inject():
    cmd = [
        os.path.join("utils", "proxinject", "proxinjector-cli"),
        "--name",
        "*mahjongsoul*",
        "--set-proxy",
        f"127.0.0.1:{settings['socks5_port']}",
    ]

    await (
        await asyncio.subprocess.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    ).communicate()

    await asyncio.sleep(0.5)

    asyncio.create_task(start_inject())


def main():
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(start_proxy())
        loop.create_task(start_inject())
        loop.run_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
