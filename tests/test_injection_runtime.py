"""End-to-end local takeover through real mitmproxy sockets, without the game."""

import asyncio
import base64
import hashlib

from majsoul_hook.addon import CaptureAddon
from majsoul_hook.runtime import CaptureMaster
from majsoul_hook.schema import dictionary
from majsoul_hook.wire import Frame


async def read_frame(reader):
    opcode, size = await reader.readexactly(2)
    assert opcode == 0x82
    length = size & 127
    if length == 126:
        length = int.from_bytes(await reader.readexactly(2), "big")
    mask = await reader.readexactly(4) if size & 128 else None
    payload = await reader.readexactly(length)
    return bytes(v ^ mask[i % 4] for i, v in enumerate(payload)) if mask else payload


async def send_frame(writer, payload, *, masked=False):
    length = len(payload)
    size = bytes([length]) if length < 126 else b"\x7e" + length.to_bytes(2, "big")
    if masked:
        size = bytes([size[0] | 128]) + size[1:]
        mask = b"abcd"
        payload = mask + bytes(v ^ mask[i % 4] for i, v in enumerate(payload))
    writer.write(b"\x82" + size + payload)
    await writer.drain()


def test_local_rpc_never_reaches_server_and_notices_follow_response(cosmetics, tmp_path):
    async def check():
        schema, codec = cosmetics.schema, cosmetics.codec
        seen = []
        server_result = asyncio.get_running_loop().create_future()

        async def serve(reader, writer):
            try:
                headers = (await reader.readuntil(b"\r\n\r\n")).decode()
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
                for name, response in (
                    (".lq.Lobby.login", {"account_id": 42, "account": {"account_id": 42}}),
                    (".lq.Lobby.leaveRoom", {}),
                ):
                    packet = Frame.parse(schema, await read_frame(reader))
                    seen.append(packet.wrapper.name)
                    assert packet.wrapper.name == name
                    await send_frame(writer, codec.packet(3, name, response, packet.request_id))
                server_result.set_result(True)
            except Exception as exc:
                server_result.set_exception(exc)
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(serve, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        master = CaptureMaster(
            "unused", CaptureAddon(schema, cosmetics=cosmetics), confdir=tmp_path / "ca"
        )
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
            await send_frame(writer, codec.packet(2, ".lq.Lobby.login", {}, 0), masked=True)
            login = codec.read(Frame.parse(schema, await read_frame(reader)), ".lq.Lobby.login")
            assert login.account.avatar_id == 400001  # server sent no avatar
            await send_frame(
                writer,
                codec.packet(
                    2, ".lq.Lobby.changeCharacterSkin", {"character_id": 200007, "skin": 400002}, 1
                ),
                masked=True,
            )
            response = Frame.parse(schema, await read_frame(reader))
            notice = Frame.parse(schema, await read_frame(reader))
            assert response.kind == 3 and response.request_id == 1
            assert dictionary(codec.read(response, ".lq.Lobby.changeCharacterSkin")) == {}
            assert notice.wrapper.name == ".lq.NotifyAccountUpdate"
            account_update = codec.read(notice, notice.wrapper.name)
            assert account_update.update.character.characters[0].skin == 400002
            await send_frame(writer, codec.packet(2, ".lq.Lobby.leaveRoom", {}, 2), masked=True)
            assert Frame.parse(schema, await read_frame(reader)).request_id == 2
            assert await server_result
            assert seen == [".lq.Lobby.login", ".lq.Lobby.leaveRoom"]
            assert cosmetics.store.account(42)["skins"]["200007"] == 400002
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()
            master.shutdown()
            await task
            await master.done()
            server.close()
            await server.wait_closed()

    asyncio.run(asyncio.wait_for(check(), timeout=10))
