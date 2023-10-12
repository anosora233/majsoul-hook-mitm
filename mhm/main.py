import asyncio
import os

from mitmproxy.tools.dump import DumpMaster
from mitmproxy import options
from .config import settings
from .addons import addons


async def start_proxy():
    if not settings["mode"]:
        return

    opts = options.Options(
        mode=settings["mode"],
        http2=False,
    )
    master = DumpMaster(
        opts,
        with_termlog=settings["with_termlog"],
        with_dumper=settings["with_dumper"],
    )

    master.addons.add(*addons)
    await master.run()
    return master


async def start_inject():
    if not settings["proxinject_proxy"]:
        return

    cmd = [
        os.path.join("utils", "proxinject", "proxinjector-cli"),
        "--name",
        "*mahjongsoul*",
        "--set-proxy",
        settings["proxinject_proxy"],
    ]

    await (
        await asyncio.subprocess.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    ).communicate()

    await asyncio.sleep(0.8)

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
