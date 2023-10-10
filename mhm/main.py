async def start_proxy():
    from mitmproxy.tools.dump import DumpMaster
    from mitmproxy import options
    from .config import settings
    from .addons import addons

    mode = (
        [f"upstream:{settings['upstream_proxy']}"]
        if settings["upstream_proxy"]
        else ["regular"]
    )
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


def main():
    try:
        __import__("asyncio").run(start_proxy())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
