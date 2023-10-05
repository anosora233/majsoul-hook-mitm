from mitmproxy import http

from .proto.liqi import LQPROTO, MsgType, manipulate
from .config import settings, logger, entrance


def player(flow: http.HTTPFlow) -> dict:
    handlers = []
    if settings["enable_skins"]:
        from .plugin.skin import SkinHandler

        handlers.append(SkinHandler())
    if settings["enable_aider"]:
        from .plugin.aider import AiderHandler

        handlers.append(AiderHandler())
    if settings["enable_chest"]:
        from .plugin.chest import ChestHandler

        handlers.append(ChestHandler())

    return {"flows": [flow], "handlers": handlers}


def log(flow: http.HTTPFlow, parsed: dict) -> None:
    logger.info(
        f"[i][gold1]{parsed['type'].name}[/gold1] [cyan3]{parsed['method']}[/cyan3] {parsed['id']} at {flow.id[:13]}[/i]"
    )

    if parsed["type"] == MsgType.Req:
        logger.debug(f"--> {parsed['data']}")
    else:
        logger.debug(f"<-- {parsed['data']}")


class WebSocketAddon:
    def __init__(self) -> None:
        self.proto = LQPROTO()
        self.players = {}

    def invoke(self, flow: http.HTTPFlow, parsed: dict):
        msg_type = parsed["type"]
        method_bef = parsed["method"]

        for player in self.players.values():
            manipulated = 0

            if flow in player["flows"]:
                for handler in player["handlers"]:
                    if method_bef in handler.methods(msg_type):
                        manipulated += handler.handle(flow, parsed)

            if manipulated:
                manipulate(flow, parsed)

    def websocket_message(self, flow: http.HTTPFlow):
        # make type checker happy
        assert flow.websocket is not None
        # get the latest message
        message = flow.websocket.messages[-1]

        try:
            parsed = self.proto.parse(flow)
        except:
            logger.warning(f"[i][red]Unsupported[/red] message at {flow.id[:13]}[/i]")
            logger.debug(__import__("traceback").format_exc())

            return

        log(flow=flow, parsed=parsed)

        data = parsed["data"]
        method = parsed["method"]
        msg_type = parsed["type"]

        # identify game websocket
        if msg_type == MsgType.Res and method in entrance:
            if (account_id := data["account_id"]) == 0:
                return
            elif account_id in self.players:
                self.players[account_id]["flows"].append(flow)
            else:
                self.players[account_id] = player(flow)

        elif msg_type == MsgType.Req and method == ".lq.FastTest.authGame":
            assert (account_id := data["account_id"]) in self.players
            self.players[account_id]["flows"].append(flow)

        # invoke methods to modify websockt message
        self.invoke(flow, parsed)

    def websocket_start(self, flow: http.HTTPFlow):
        logger.info(f"[i][green]Connected[/green] {flow.id[:13]}[/i]")

    def websocket_end(self, flow: http.HTTPFlow):
        logger.info(f"[i][blue]Disconnected[/blue] {flow.id[:13]}[/i]")

        # clear flow and player
        logouts = []
        for account, player in self.players.items():
            if flow in player["flows"]:
                player["flows"].remove(flow)

                if not player["flows"]:
                    logouts.append(account)

        for account in logouts:
            self.players.pop(account)


addons = [WebSocketAddon()]
