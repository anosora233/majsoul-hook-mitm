"""Mitmproxy events, optional cosmetic effects, client injection and diagnostics."""

import base64
import json
import logging
from collections.abc import Callable
from pathlib import Path
from time import time
from typing import TextIO

from mitmproxy import ctx, http

from .cosmetics import Cosmetics
from .protocol import ConnectionDecoder, ProtocolError
from .schema import Schema
from .wire import Codec, Frame, dictionary

logger = logging.getLogger(__name__)


class CaptureAddon:
    def __init__(
        self,
        schema: Schema,
        *,
        hosts: tuple[str, ...] = (),
        output: Path | None = None,
        verbose: bool = False,
        cosmetics: Cosmetics | None = None,
        event_sink: Callable[[dict], None] | None = None,
    ):
        self.schema = schema
        self.hosts = hosts
        self.output = output
        self.verbose = verbose
        self.cosmetics = cosmetics
        self.event_sink = event_sink
        self.codec = Codec(schema)
        self.connections: dict[str, ConnectionDecoder] = {}
        self.stream: TextIO | None = None

    def running(self) -> None:
        if self.output:
            self.output.parent.mkdir(parents=True, exist_ok=True)
            self.stream = self.output.open("a", encoding="utf-8")
        self._event({"event": "ready"})

    def _event(self, event: dict) -> None:
        if self.event_sink:
            try:
                self.event_sink(event)
            except Exception:
                logger.warning("Inspector event delivery failed")

    def _inspection(self, flow, message, record, original, injections) -> None:
        if not self.event_sink:
            return
        try:
            action = record["action"]
            shown_action = (
                "intercepted"
                if action == "local"
                else "error"
                if action.startswith("error_")
                else action
            )
            after = record.get("data")
            if message.content != original:
                after = dictionary(
                    self.codec.read(Frame.parse(self.schema, message.content), record["name"])
                )
            self._event(
                {
                    "event": "message",
                    **record,
                    "action": shown_action,
                    "source_action": action,
                    "retained": not message.dropped,
                    "before": record.get("data"),
                    "after": None if message.dropped else after,
                    "wire_before": base64.b64encode(original).decode(),
                    "wire_after": None
                    if message.dropped
                    else base64.b64encode(message.content).decode(),
                }
            )
            for content in injections:
                frame = Frame.parse(self.schema, content)
                name = frame.wrapper.name if frame.kind == 1 else record["name"]
                data = dictionary(self.codec.read(frame, name))
                self._event(
                    {
                        "event": "message",
                        "flow_id": flow.id,
                        "host": flow.request.host,
                        "timestamp": time(),
                        "direction": "server_to_client",
                        "kind": "notify" if frame.kind == 1 else "response",
                        "request_id": frame.request_id,
                        "name": name,
                        "data": data,
                        "status": "decoded",
                        "action": "local",
                        "retained": True,
                        "before": None,
                        "after": data,
                        "synthetic": True,
                        "wire_before": None,
                        "wire_after": base64.b64encode(content).decode(),
                    }
                )
        except Exception:
            logger.warning("Inspector snapshot unavailable")

    def _accepts(self, flow: http.HTTPFlow) -> bool:
        host = flow.request.host.lower().rstrip(".")
        return not self.hosts or any(
            host == suffix or host.endswith("." + suffix) for suffix in self.hosts
        )

    def websocket_start(self, flow: http.HTTPFlow) -> None:
        if self._accepts(flow):
            logger.info(
                "%s WebSocket connected host=%s port=%s scheme=%s client_tls=%s server_tls=%s",
                flow.id[:8],
                flow.request.host,
                flow.request.port,
                flow.request.scheme,
                flow.client_conn.tls,
                flow.server_conn.tls,
            )

    def websocket_message(self, flow: http.HTTPFlow) -> None:
        if not flow.websocket or not flow.websocket.messages or not self._accepts(flow):
            return
        message = flow.websocket.messages[-1]
        if message.is_text or message.injected:
            return
        original = message.content
        decoder = self.connections.get(flow.id)
        if decoder is None:
            decoder = self.connections[flow.id] = ConnectionDecoder(self.schema)
        frame, local = None, False
        if self.cosmetics:
            try:
                frame = Frame.parse(self.schema, message.content)
                local = self.cosmetics.is_local(frame, from_client=message.from_client)
            except Exception:
                # A malformed ordinary frame must not disrupt forwarding.
                frame = None
            if local:
                message.drop()
        try:
            decoded = decoder.decode(message.content, from_client=message.from_client)
        except ProtocolError as exc:
            injections = []
            if local:
                injections = self._local_error(flow, decoder, frame)
                logger.warning(
                    "%s local request decode failed; request remains blocked", flow.id[:8]
                )
            logger.debug("Skipped frame on %s: %s", flow.id[:8], exc)
            self._inspection(
                flow,
                message,
                {
                    "flow_id": flow.id,
                    "host": flow.request.host,
                    "timestamp": message.timestamp,
                    "direction": "client_to_server" if message.from_client else "server_to_client",
                    "kind": {1: "notify", 2: "request", 3: "response"}.get(
                        original[0] if original else 0, "unknown"
                    ),
                    "request_id": frame.request_id if frame else None,
                    "name": frame.wrapper.name if frame else None,
                    "data": None,
                    "status": "malformed",
                    "error": str(exc),
                    "action": "error_blocked" if local else "error_passthrough",
                },
                original,
                injections,
            )
            return
        action = "pass"
        injections = []
        if self.cosmetics and frame:
            try:
                if decoded.status != "decoded":
                    if local:
                        raise ValueError("Local method schema unavailable")
                else:
                    effect = self.cosmetics.apply(
                        flow.id, frame, decoded.name, from_client=message.from_client
                    )
                    if effect.local:
                        message.drop()
                        decoder.pending.pop((message.from_client, frame.request_id), None)
                    for content in effect.injections:
                        self._inject(flow, content)
                        injections.append(content)
                    if effect.content is not None:
                        message.content = effect.content
                    action = "local" if effect.local else "modified" if effect.content else "pass"
            except Exception as exc:
                if local:
                    injections += self._local_error(flow, decoder, frame)
                action = "error_blocked" if local else "error_passthrough"
                logger.warning(
                    "%s cosmetic processing failed (%s); %s",
                    flow.id[:8],
                    type(exc).__name__,
                    action,
                )
        record = {
            "flow_id": flow.id,
            "host": flow.request.host,
            "timestamp": message.timestamp,
            "direction": "client_to_server" if message.from_client else "server_to_client",
            **decoded.as_dict(),
            "action": action,
            "injections": len(injections),
        }
        logger.info(
            "%s %s %s %s id=%s [%s] %s",
            flow.id[:8],
            record["direction"],
            decoded.kind,
            decoded.name or "?",
            decoded.request_id,
            decoded.status,
            action,
        )
        self._inspection(flow, message, record, original, injections)
        if self.verbose:
            logger.info("%s", json.dumps(record, ensure_ascii=False))
        if self.stream:
            try:
                self.stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                self.stream.flush()
            except OSError:
                logger.exception("Capture output failed; disabling file output")
                self._close_output()

    @staticmethod
    def _inject(flow: http.HTTPFlow, content: bytes) -> None:
        # to_client=True; never send synthesized messages to the real server.
        ctx.master.commands.call("inject.websocket", flow, True, content, False)

    def _local_error(
        self, flow: http.HTTPFlow, decoder: ConnectionDecoder, frame: Frame
    ) -> list[bytes]:
        decoder.pending.pop((True, frame.request_id), None)
        try:
            content = self.cosmetics.codec.error_response(frame.wrapper.name, frame.request_id)
            self._inject(flow, content)
            return [content]
        except Exception as exc:
            logger.error(
                "%s local error response failed (%s); request remains blocked",
                flow.id[:8],
                type(exc).__name__,
            )
            return []

    def _close_output(self) -> None:
        stream, self.stream = self.stream, None
        if stream is not None:
            try:
                stream.close()
            except OSError:
                logger.exception("Could not close capture output")

    def websocket_end(self, flow: http.HTTPFlow) -> None:
        if self.cosmetics:
            self.cosmetics.close(flow.id)
        decoder = self.connections.pop(flow.id, None)
        if decoder:
            decoder.clear()

    def done(self) -> None:
        self.connections.clear()
        if self.cosmetics:
            self.cosmetics.sessions.clear()
            self.cosmetics.accounts.clear()
        self._close_output()
