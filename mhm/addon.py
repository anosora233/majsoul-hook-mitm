from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from mitmproxy import ctx, http, websocket
from mitmproxy.addons import view
from rich.traceback import Traceback

from .protocol import GameMessage, GameMessageType, compose, parse
from .tui import app

_LOGIN_INFO_MESSAGES = [
    (GameMessageType.Response, ".lq.Lobby.login"),
    (GameMessageType.Response, ".lq.Lobby.emailLogin"),
    (GameMessageType.Response, ".lq.Lobby.oauth2Login"),
]

_MATCH_INFO_MESSAGES = [
    (GameMessageType.Request, ".lq.FastTest.authGame"),
]

ChannelType = Literal["LoBBY", "MaTCH"]
# O: ORIGINAL, I: INJECTED, M: MODIFIED, D: DROPPED
# NOTE: The status `to modify` is unnecessary, as message are dropped directly if fails
MessageStatus = Literal["O", "I", "M", "D"]
# HACK: Define Message status's colors
StatusColor: dict[MessageStatus, str] = {
    "O": "grey85",
    "I": "cyan1",  # NOTE: This indicates that this message is injected
    "M": "magenta3",  # SECURITY: Whether the modification can be viewed by the server?
    "D": "orange3",  # SECURITY: Dropping will result in non-sequential request msg idx
}


def inject(flow: http.HTTPFlow, content: bytes):
    ctx.master.commands.call("inject.websocket", flow, True, content, False)


def broadcast(
    flows: Sequence[http.HTTPFlow],
    content: bytes,
    channel: ChannelType,
    members: list[int],
) -> None:
    for f in flows:
        if f.live and f.marked in members:
            if f.metadata.get(ChannelType) == channel:
                inject(f, content)


class GameAddon(view.View):
    def __init__(self, methods) -> None:
        super().__init__()
        # HACK: `methods` refers to the
        # `run(mp: `MessageProcessor`)` method of `Hook` instances.
        self.methods = methods

    def websocket_start(self, flow: http.HTTPFlow):
        app.add_note(" ".join(["[i][green]Connected", flow.id[:8]]))

    def websocket_end(self, flow: http.HTTPFlow):
        app.add_note(" ".join(["[i][blue]Disconnected", flow.id[:8]]))

    def websocket_message(self, flow: http.HTTPFlow):
        # NOTE: make type checker happy
        assert flow.websocket is not None

        try:
            # NOTE: Flows are no longer saved into a dictionary
            wss_msg = flow.websocket.messages[-1]
            gam_msg = parse(flow.id, wss_msg.content)
            mp = MessageProcessor(flow=flow, wss_msg=wss_msg, gam_msg=gam_msg)
        except Exception as e:
            app.add_note(f"[i][red]{repr(e)} @ {flow.id[:8]}")
            return

        # HACK: Temporarily mark the LoBBY message
        if mp.key in _LOGIN_INFO_MESSAGES:
            channel: ChannelType = "LoBBY"
            account_id = gam_msg.data.get("account_id")
            flow.marked = account_id
            flow.metadata[ChannelType] = channel
        # HACK: Temporarily mark the MaTCH message
        elif mp.key in _MATCH_INFO_MESSAGES:
            channel: ChannelType = "MaTCH"
            account_id = gam_msg.data.get("account_id")
            flow.marked = account_id
            flow.metadata[ChannelType] = channel

        # NOTE: Previous `log` method
        def _pure(mp: MessageProcessor, tag: int | str):
            subname = f"[{mp.data['name']}]" if mp.name == ".lq.ActionPrototype" else ""
            idx = mp.idx if mp.idx else ""
            status = mp.status
            text = (
                f"[i][{StatusColor[status]}]{status}[/{StatusColor[status]}]"
                f" [grey50]{tag:<9}[/grey50]"
                f" [cyan2]{mp.kind.name:<8}[/cyan2]"
                f" [gold1]{mp.name}[/gold1]"
                f" [cyan3]{idx}[/cyan3]"
                f"[gold3]{subname}[/gold3]"
            )
            return text, mp.data

        # NOTE: Messages are only modified once the account_id is determined
        if not mp.member:
            app.add_message(*_pure(flow.id[:8], mp))
            return

        try:
            for fn in self.methods:
                fn(mp)
            mp.apply()
        except Exception:
            app.add_note(Traceback())
            mp.drop()  # NOTE: Discard the message if fails
        finally:
            app.add_message(*_pure(mp, mp.member))


@dataclass
class MessageProcessor:
    flow: http.HTTPFlow

    wss_msg: websocket.WebSocketMessage

    gam_msg: GameMessage

    modified: bool = False

    @property
    def status(self) -> MessageStatus:
        if self.wss_msg.dropped:
            return "D"
        elif self.wss_msg.injected:
            return "I"
        elif self.modified:
            return "M"
        else:
            return "O"

    @property  # NOTE: Flow internal `NotifyRoomPlayer***` message sequence id
    def sequence(self) -> int:  # HACK
        self.flow.metadata["sequence"] += 1
        return self.flow.metadata["sequence"]

    @sequence.setter  # NOTE: Call when creating or joining a room
    def sequence(self, value: int):  # HACK: Regularly the value should be zero
        self.flow.metadata["sequence"] = value

    @property
    def data(self) -> dict:
        return self.gam_msg.data

    @data.setter
    def data(self, value: dict):
        self.gam_msg.data = value

    @property
    def name(self) -> str:
        return self.gam_msg.name

    @property
    def kind(self) -> GameMessageType:
        return self.gam_msg.kind

    @property
    def idx(self) -> int:
        return self.gam_msg.idx

    @property
    def key(self) -> tuple[GameMessageType, str]:
        return self.kind, self.name

    @property  # NOTE: the alias of account_id
    def member(self) -> int:
        return self.flow.marked

    def amend(self):
        # NOTE: After calling `amend`, method `apply` should be called.
        self.modified = True

    def drop(self):
        # NOTE: Now the 'dropped' status is determined by the original websocket message
        self.wss_msg.drop()

    def apply(self):
        # NOTE: It's best to `compose(message)` after all hooks are completed
        if self.modified:
            self.wss_msg.content = compose(self.gam_msg)

    def request(self, data: dict, id: int):
        # SECURITY: Currently uncertain about the security of injecting into the server
        # TODO: It can provide the foundation for automation implementation
        raise NotImplementedError

    def response(self, data: dict | None = None):
        if not data:
            data = {}

        # NOTE: Discard the request sent to the server
        self.drop()

        response = GameMessage(
            data=data,
            idx=self.gam_msg.idx,
            name=self.gam_msg.name,
            kind=GameMessageType.Response,
        )

        inject(self.flow, compose(response))

    def notify(self, name: str, data: dict):
        notify = GameMessage(
            idx=0,
            name=name,
            data=data,
            kind=GameMessageType.Notify,
        )

        inject(self.flow, compose(notify))

    def broadcast(
        self,
        name: str,
        data: dict,
        channel: ChannelType,
        members: list[int],
    ):
        notify = GameMessage(
            idx=0,
            name=name,
            data=data,
            kind=GameMessageType.Notify,
        )

        broadcast(
            ctx.master.commands.call("view.flows.resolve", "@marked"),
            compose(notify),
            channel,
            members,
        )  # HACK: Marked flow includes non-live flows
