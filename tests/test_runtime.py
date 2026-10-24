import asyncio
import base64
import hashlib
import json
import logging
import signal
from threading import Event
from unittest.mock import AsyncMock

import pytest
from mitmproxy import optmanager
from mitmproxy.proxy.layers.http import HttpRequestHeadersHook
from mitmproxy.test import tflow

from majsoul_hook.addon import CaptureAddon
from majsoul_hook.runtime import CaptureMaster, run_capture

from .conftest import packet


def test_isolated_config_and_addon_set(schema, tmp_path, monkeypatch):
    # Both extensions and both default/custom locations must be ignored.
    home = tmp_path / "home"
    default = home / ".mitmproxy"
    custom = tmp_path / "custom"
    for directory in (default, custom):
        directory.mkdir(parents=True)
        for suffix in ("yaml", "yml"):
            (directory / f"config.{suffix}").write_text(
                'ssl_insecure: true\nmodify_headers: ["/x-review/modified"]\n'
                'scripts: ["missing-script.py"]\n',
                encoding="utf-8",
            )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    def unexpected_config(*args, **kwargs):
        pytest.fail("Capture attempted to load external configuration")

    monkeypatch.setattr(optmanager, "load_paths", unexpected_config)
    monkeypatch.setattr(optmanager, "load", unexpected_config)

    async def check():
        for confdir in (None, custom):
            master = CaptureMaster("1234", CaptureAddon(schema), confdir=confdir)
            try:
                assert set(master.addons.lookup) == {
                    "termlog",
                    "core",
                    "proxyserver",
                    "nextlayer",
                    "tlsconfig",
                    "dnsresolver",
                    "errorcheck",
                    "captureaddon",
                }
                assert master.options.mode == ["local:1234"]
                assert master.options.ssl_insecure is False
                assert "modify_headers" not in master.options
                if confdir:
                    assert master.options.confdir == str(custom.resolve())
                flow = tflow.tflow()
                flow.request.headers["x-review"] = "original"
                await master.addons.trigger_event(HttpRequestHeadersHook(flow))
                assert flow.request.headers["x-review"] == "original"
            finally:
                await master.done()

    asyncio.run(check())


def test_shutdown_signals_and_cleanup(schema, tmp_path, monkeypatch):
    instances = []
    original = CaptureMaster
    prior = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    root_level = logging.getLogger().level

    class Master(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            instances.append(self)
            self.addons.get("proxyserver").setup_servers = AsyncMock(return_value=True)
            self.stop_servers = AsyncMock(return_value=True)
            self.addons.get("proxyserver").servers.update = self.stop_servers
            master = self

            class Stop:
                def running(self):
                    signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
                    assert master.addons.get("captureaddon").stream is not None

            self.addons.add(Stop())

    monkeypatch.setattr("majsoul_hook.runtime.CaptureMaster", Master)
    asyncio.run(run_capture("1234", schema, confdir=tmp_path / "ca", output=tmp_path / "out.jsonl"))
    master = instances[0]
    master.stop_servers.assert_awaited_once_with([])
    assert master.addons.get("captureaddon").stream is None
    assert logging.getLogger().level == root_level
    assert all(signal.getsignal(s) == handler for s, handler in prior.items())


def test_gui_stop_event_cleans_proxy_and_emits_ready(schema, tmp_path, monkeypatch):
    stop = Event()
    events, instances = [], []
    original = CaptureMaster

    class Master(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            instances.append(self)
            self.addons.get("proxyserver").setup_servers = AsyncMock(return_value=True)
            self.stop_servers = AsyncMock(return_value=True)
            self.addons.get("proxyserver").servers.update = self.stop_servers

            class Stop:
                def running(self):
                    stop.set()

            self.addons.add(Stop())

    monkeypatch.setattr("majsoul_hook.runtime.CaptureMaster", Master)
    asyncio.run(
        asyncio.wait_for(
            run_capture(
                "test-only", schema, confdir=tmp_path, stop_event=stop, event_sink=events.append
            ),
            timeout=5,
        )
    )
    assert events == [{"event": "ready"}]
    instances[0].stop_servers.assert_awaited_once_with([])


@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
def test_startup_failure_always_cleans_up(schema, tmp_path, monkeypatch, failure):
    instances = []
    original = CaptureMaster

    class Master(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            instances.append(self)
            self.addons.get("proxyserver").setup_servers = AsyncMock(return_value=True)
            self.stop_servers = AsyncMock(return_value=True)
            self.addons.get("proxyserver").servers.update = self.stop_servers

        async def run(self):
            self.addons.get("captureaddon").running()
            raise failure()

    monkeypatch.setattr("majsoul_hook.runtime.CaptureMaster", Master)
    prior = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    with pytest.raises(failure):
        asyncio.run(run_capture("1234", schema, confdir=tmp_path, output=tmp_path / "out.jsonl"))
    instances[0].stop_servers.assert_awaited_once_with([])
    assert instances[0].addons.get("captureaddon").stream is None
    assert all(signal.getsignal(s) == handler for s, handler in prior.items())


def test_websocket_roundtrip_through_real_proxy(schema, tmp_path):
    async def check():
        loop = asyncio.get_running_loop()
        received = loop.create_future()
        request = packet(schema, 2, ".lq.Lobby.test", b"\x08\x07")
        response = packet(schema, 3, payload=b"\x08\x09")

        async def serve(reader, writer):
            try:
                headers = (await reader.readuntil(b"\r\n\r\n")).decode("ascii")
                key = next(
                    line.split(":", 1)[1].strip()
                    for line in headers.split("\r\n")
                    if line.lower().startswith("sec-websocket-key:")
                )
                accept = base64.b64encode(
                    hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
                )
                writer.write(
                    b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                    b"Connection: Upgrade\r\nSec-WebSocket-Accept: " + accept + b"\r\n\r\n"
                )
                await writer.drain()
                opcode, length = await reader.readexactly(2)
                assert opcode == 0x82 and length & 0x80
                mask = await reader.readexactly(4)
                data = await reader.readexactly(length & 0x7F)
                received.set_result(bytes(value ^ mask[i % 4] for i, value in enumerate(data)))
                writer.write(bytes([0x82, len(response)]) + response)
                await writer.drain()
                await reader.read()
            except Exception as exc:
                if not received.done():
                    received.set_exception(exc)
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(serve, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        output = tmp_path / "messages.jsonl"
        addon = CaptureAddon(schema, output=output)
        master = CaptureMaster("unused", addon, confdir=tmp_path / "ca")
        # Use an ordinary loopback listener to test real forwarding without local
        # interception, elevated privileges or a real game client in the test suite.
        master.options.update(mode=["regular@127.0.0.1:0"])
        ready = asyncio.Event()

        class Ready:
            def running(self):
                ready.set()

        master.addons.add(Ready())
        task = asyncio.create_task(master.run())
        writer = None
        try:
            await ready.wait()
            proxy_port = master.addons.get("proxyserver").listen_addrs()[0][1]
            reader, writer = await asyncio.open_connection("127.0.0.1", proxy_port)
            writer.write(
                (
                    f"GET http://127.0.0.1:{port}/ws HTTP/1.1\r\n"
                    f"Host: 127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                    "Sec-WebSocket-Version: 13\r\n"
                    "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n"
                ).encode()
            )
            await writer.drain()
            assert (await reader.readuntil(b"\r\n\r\n")).startswith(b"HTTP/1.1 101")
            mask = b"abcd"
            masked = bytes(value ^ mask[i % 4] for i, value in enumerate(request))
            writer.write(bytes([0x82, 0x80 | len(request)]) + mask + masked)
            await writer.drain()
            assert await received == request
            assert await reader.readexactly(2) == bytes([0x82, len(response)])
            assert await reader.readexactly(len(response)) == response
            records = [json.loads(line) for line in output.read_text().splitlines()]
            assert [record["data"] for record in records] == [{"value": 7}, {"value": "9"}]
            assert not addon.connections[records[0]["flow_id"]].pending
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()
            master.shutdown()
            await task
            await master.done()
            server.close()
            await server.wait_closed()
        assert addon.stream is None and not addon.connections
        assert not list(master.addons.get("proxyserver").servers)

    asyncio.run(asyncio.wait_for(check(), timeout=10))
