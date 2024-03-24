from mitmproxy import http

from . import console
from .config import config
from .hook import Hook
from .proto import MsgManager


def log(debug: bool, mger: MsgManager):
    match mger.m.status:
        case "Md" | "ToMd":
            head = "red"
        case "Dp":
            head = "green4"
        case "Og":
            head = "grey85"

    console.log(
        " ".join(
            [
                f"[{head}]{mger.m.status}[/{head}]",
                f"[grey50]{mger.tag}[/grey50]",
                f"[cyan2]{mger.m.type.name}[/cyan2]",
                f"[gold1]{mger.m.method}[/gold1]",
                f"[cyan3]{mger.m.id}[/cyan3]",
            ]
        )
    )

    if debug:
        console.log(f"-->> {mger.m.data}")


class WebSocketAddon:
    def __init__(self, hooks: list[Hook]):
        self.hooks = hooks
        self.debug = config.base.debug
        self.manager = MsgManager()

    def websocket_start(self, flow: http.HTTPFlow):
        console.log(" ".join(["[i][green]Connected", flow.id[:13]]))

    def websocket_end(self, flow: http.HTTPFlow):
        console.log(" ".join(["[i][blue]Disconnected", flow.id[:13]]))

    def websocket_message(self, flow: http.HTTPFlow):
        # make type checker happy
        assert flow.websocket is not None

        try:
            self.manager.parse(flow)
        except Exception:
            console.log(f"[red]Unsupported Message @ {flow.id[:13]}")

        if self.manager.member:
            for hook in self.hooks:
                try:
                    self.manager.apply(hook.apply)
                except Exception:
                    console.print_exception()

        log(self.debug, self.manager)
