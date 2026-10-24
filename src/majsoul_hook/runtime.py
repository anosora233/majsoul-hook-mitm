"""An isolated mitmproxy runtime with only forwarding and inspection addons."""

import asyncio
import logging
import signal
from collections.abc import Callable
from contextlib import contextmanager, suppress
from pathlib import Path
from threading import Event

from mitmproxy import options
from mitmproxy.addons import core, dns_resolver, errorcheck, next_layer, proxyserver, tlsconfig
from mitmproxy.master import Master

from .addon import CaptureAddon
from .cosmetics import Cosmetics
from .schema import Schema


class CaptureMaster(Master):
    def __init__(self, process: str, addon: CaptureAddon, *, confdir: Path | None = None):
        # Do not use tools.main.run or default_addons: they load user config and
        # register traffic modification, replay, recording and script features.
        opts = options.Options()
        if confdir is not None:
            opts.update(confdir=str(confdir.expanduser().resolve()))
        super().__init__(opts, with_termlog=True)
        self._closed = False
        self._errors = errorcheck.ErrorCheck()
        self.addons.add(
            core.Core(),
            proxyserver.Proxyserver(),
            next_layer.NextLayer(),
            tlsconfig.TlsConfig(),
            dns_resolver.DnsResolver(),
            self._errors,
            addon,
        )
        opts.update(mode=[f"local:{process}"])

    async def done(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            # Explicitly disable local interception, including on startup failure.
            await self.addons.get("proxyserver").servers.update([])
        finally:
            try:
                await super().done()
            finally:
                self._errors.finish()


@contextmanager
def shutdown_signals(master: CaptureMaster):
    """Use the portable signal API, including Windows, and restore caller handlers."""
    previous = {}
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, lambda *_: master.shutdown())
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


async def run_capture(
    process: str,
    schema: Schema,
    *,
    confdir: Path | None = None,
    hosts: tuple[str, ...] = (),
    output: Path | None = None,
    verbose: bool = False,
    cosmetics: Cosmetics | None = None,
    event_sink: Callable[[dict], None] | None = None,
    stop_event: Event | None = None,
) -> None:
    addon = CaptureAddon(
        schema,
        hosts=hosts,
        output=output,
        verbose=verbose,
        cosmetics=cosmetics,
        event_sink=event_sink,
    )
    root_logger = logging.getLogger()
    previous_level = root_logger.level
    root_logger.setLevel(logging.INFO)
    master = None
    monitor = None
    try:
        master = CaptureMaster(process, addon, confdir=confdir)
        if stop_event is not None:

            async def watch_stop():
                while not stop_event.is_set():
                    await asyncio.sleep(0.1)
                master.shutdown()

            monitor = asyncio.create_task(watch_stop())
        with shutdown_signals(master):
            await master.run()
    finally:
        try:
            if monitor:
                monitor.cancel()
                with suppress(asyncio.CancelledError):
                    await monitor
            # Master.run does not invoke done() if it fails during server setup.
            if master is not None:
                await master.done()
        finally:
            root_logger.setLevel(previous_level)
