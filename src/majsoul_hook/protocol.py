"""One decoder per WebSocket connection. No packet serialization or mutation API."""

import base64
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from time import monotonic

from google.protobuf.message import DecodeError

from .schema import Schema, qualified
from .wire import MAX_FRAME_SIZE, Frame


class ProtocolError(ValueError):
    """A frame does not satisfy the Mahjong Soul protocol."""


@dataclass(frozen=True)
class DecodedMessage:
    kind: str
    request_id: int | None
    name: str | None
    data: dict | None
    status: str = "decoded"
    payload_base64: str | None = None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def decode_action(payload: bytes) -> bytes:
    keys = (0x84, 0x5E, 0x4E, 0x42, 0x39, 0xA2, 0x1F, 0x60, 0x1C)
    return bytes(
        value ^ (((23 ^ len(payload)) + 5 * i + keys[i % 9]) & 255)
        for i, value in enumerate(payload)
    )


class ConnectionDecoder:
    def __init__(
        self,
        schema: Schema,
        *,
        max_pending: int = 4096,
        timeout: float = 120,
        max_frame: int = MAX_FRAME_SIZE,
        clock=monotonic,
    ):
        if max_pending < 1 or timeout <= 0 or max_frame < 3:
            raise ValueError("Decoder limits must be positive")
        self.schema = schema
        self.max_pending, self.timeout, self.max_frame = max_pending, timeout, max_frame
        self.clock = clock
        self.pending: OrderedDict[tuple[bool, int], tuple[str, float]] = OrderedDict()

    def clear(self) -> None:
        self.pending.clear()

    def decode(self, content: bytes, *, from_client: bool) -> DecodedMessage:
        now = self.clock()
        while self.pending and now - next(iter(self.pending.values()))[1] >= self.timeout:
            self.pending.popitem(last=False)
        try:
            frame = Frame.parse(self.schema, content, max_size=self.max_frame)
        except DecodeError as exc:
            raise ProtocolError("Malformed Wrapper") from exc
        except ValueError as exc:
            raise ProtocolError(str(exc)) from exc
        kind, request_id, wrapper = frame.kind, frame.request_id, frame.wrapper
        name = wrapper.name or None
        payload = bytes(wrapper.data)
        warnings = []
        type_name = None
        if kind == 1:
            if not name:
                raise ProtocolError("Notification has no name")
            type_name = name
        elif kind == 2:
            if not name:
                raise ProtocolError("Request has no method name")
            key = (from_client, request_id)
            if key in self.pending:
                warnings.append("Request ID reused before response")
                del self.pending[key]
            self.pending[key] = (name, now)
            while len(self.pending) > self.max_pending:
                self.pending.popitem(last=False)
            pair = self.schema.methods.get(name)
            type_name = pair[0] if pair else None
        else:
            # Responses use the ID of a request sent in the opposite direction.
            previous = self.pending.pop((not from_client, request_id), None)
            if previous:
                name = previous[0]
                pair = self.schema.methods.get(name)
                type_name = pair[1] if pair else None
            else:
                return DecodedMessage(
                    "response",
                    request_id,
                    None,
                    None,
                    "orphan_response",
                    base64.b64encode(payload).decode(),
                )
        label = {1: "notify", 2: "request", 3: "response"}[kind]
        try:
            if type_name is None:
                raise KeyError(name)
            data = self.schema.decode(type_name, payload)
        except KeyError:
            return DecodedMessage(
                label,
                request_id,
                name,
                None,
                "unknown_schema",
                base64.b64encode(payload).decode(),
                warnings,
            )
        except DecodeError as exc:
            raise ProtocolError(f"Malformed payload for {name}") from exc
        if name == ".lq.ActionPrototype":
            self._action(data, encoded=True, warnings=warnings)
        if name in (".lq.FastTest.syncGame", ".lq.FastTest.enterGame"):
            for action in data.get("game_restore", {}).get("actions", []):
                self._action(action, encoded=False, warnings=warnings)
        return DecodedMessage(label, request_id, name, data, warnings=warnings)

    def _action(self, action: dict, *, encoded: bool, warnings: list[str]) -> None:
        if not action.get("name") or "data" not in action:
            return
        try:
            raw = base64.b64decode(action["data"], validate=True)
            if encoded:
                raw = decode_action(raw)
            action["data"] = self.schema.decode(qualified(action["name"]), raw)
        except (KeyError, ValueError, DecodeError):
            warnings.append(f"Cannot decode nested action {action['name']}")
