from typing import Dict
from mitmproxy import http
from mitmproxy.websocket import WebSocketMessage

from liqi import LQPROTO, MsgType
from config import settings, logger


def init_player(login_id: str) -> Dict:
    handlers = []
    if settings["enable_skins"]:
        handlers.append(__import__("skin").SkinHandler())
    if settings["enable_aider"]:
        handlers.append(__import__("aider").AiderHandler())
    if settings["enable_chest"]:
        handlers.append(__import__("chest").ChestHandler())
    return {"conn_ids": [login_id], "handlers": handlers}


def log_parse(parse_obj: Dict, flow_id: str) -> None:
    logger.info(
        "[i][gold1]{}[/gold1] [cyan3]{}[/cyan3] {} at {}[/i]".format(
            parse_obj["type"].name,
            parse_obj["method"],
            parse_obj["id"],
            flow_id[:13],
        )
    )

    if parse_obj["type"] == MsgType.Req:
        logger.debug("--> {}".format(parse_obj["data"]))
    else:
        logger.debug("<-- {}".format(parse_obj["data"]))


def log_modify(parse_obj: Dict, flow_id: str, method_bef) -> None:
    logger.info(
        "[i][slate_blue1]Modify[/slate_blue1] [gold1]{}[/gold1] {} --> {} [/i]".format(
            parse_obj["type"].name,
            method_bef,
            parse_obj["method"],
        )
    )

    if parse_obj["type"] == MsgType.Req:
        logger.debug("--> {}".format(parse_obj["data"]))
    else:
        logger.debug("<-- {}".format(parse_obj["data"]))


class WebSocketAddon:
    def __init__(self) -> None:
        self.proto = LQPROTO()
        self.players = {}

    def invoke(self, conn_id: str, flow_msg: WebSocketMessage, parse_obj: Dict):
        msg_type = parse_obj["type"]
        method_bef = parse_obj["method"]

        for player in self.players.values():
            modify = False

            if conn_id in player["conn_ids"]:
                for handler in player["handlers"]:
                    if method_bef in handler.methods(msg_type):
                        modify = handler.handle(flow_msg=flow_msg, parse_obj=parse_obj)

            if modify:
                log_modify(parse_obj, conn_id, method_bef)

    def websocket_message(self, flow: http.HTTPFlow):
        # make type checker happy
        assert flow.websocket is not None
        # get the latest message
        message = flow.websocket.messages[-1]

        # parse websocket message
        try:
            parse_obj = self.proto.parse(message)
        except:
            logger.warning(f"[i][red]Unsupported[/red] message at {flow.id[:13]}[/i]")
            logger.debug(__import__("traceback").format_exc())

            return

        msg_type = parse_obj["type"]
        method = parse_obj["method"]

        log_parse(parse_obj=parse_obj, flow_id=flow.id)

        # identify game websocket
        if msg_type == MsgType.Res and method in {
            ".lq.Lobby.oauth2Login",
            ".lq.Lobby.login",
        }:
            if (account_id := parse_obj["data"]["account_id"]) == 0:
                return
            elif account_id in self.players:
                self.players[account_id]["conn_ids"].append(flow.id)
            else:
                self.players[account_id] = init_player(flow.id)
        elif msg_type == MsgType.Req and method == ".lq.FastTest.authGame":
            assert (account_id := parse_obj["data"]["account_id"]) in self.players
            self.players[account_id]["conn_ids"].append(flow.id)

        # list players
        for account_id, value in self.players.items():
            logger.debug(f"{account_id} --> {value['conn_ids']}")

        # invoke methods to modify websockt message
        self.invoke(flow.id, flow_msg=message, parse_obj=parse_obj)

    def websocket_start(self, flow: http.HTTPFlow):
        logger.info(f"[i][green]Connected[/green] {flow.id[:13]}[/i]")

    def websocket_end(self, flow: http.HTTPFlow):
        logger.info(f"[i][blue]Disconnected[/blue] {flow.id[:13]}[/i]")

        end_accounts = []
        # clear end conn ids
        for account, player in self.players.items():
            if flow.id in player.get("conn_ids"):
                player.get("conn_ids").remove(flow.id)

                if not player.get("conn_ids"):
                    end_accounts.append(account)

        # clear player
        for account in end_accounts:
            self.players.pop(account)


addons = [WebSocketAddon()]
