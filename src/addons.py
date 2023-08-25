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


class WebSocketAddon:
    def __init__(self) -> None:
        self.proto = LQPROTO()
        self.players = {}

    def invoke(self, conn_id: str, flow_msg: WebSocketMessage, parse_obj: Dict):
        msg_type = parse_obj["type"]
        method = parse_obj["method"]

        for player in self.players.values():
            if conn_id in player["conn_ids"]:
                modify = False
                for handler in player["handlers"]:
                    if method in handler.methods(msg_type):
                        modify = handler.handle(flow_msg=flow_msg, parse_obj=parse_obj)
                if modify:
                    logger.info(f"[i][red]Modified[/red] {conn_id}[/i]")
                    logger.info(parse_obj)

    def websocket_message(self, flow: http.HTTPFlow):
        # make type checker happy
        assert flow.websocket is not None
        # get the latest message
        message = flow.websocket.messages[-1]

        # parse websock message
        try:
            parse_obj = self.proto.parse(message)
        except:
            logger.warning("[red]Unsupported Message[/red]")
            logger.warning(__import__("traceback").format_exc())

            return

        msg_type = parse_obj["type"]
        method = parse_obj["method"]

        # debug
        logger.debug(f"[i][bold]Message Of[/bold] {flow.client_conn.id}[/i]")
        logger.debug(parse_obj)

        # identify game websocket
        if msg_type == MsgType.Res and method in {
            ".lq.Lobby.oauth2Login",
            ".lq.Lobby.login ",
        }:
            account_id = parse_obj["data"]["account_id"]
            if account_id == 0:
                return
            elif account_id in self.players:
                self.players[account_id]["conn_ids"].append(flow.client_conn.id)
            else:
                self.players[account_id] = init_player(flow.client_conn.id)
        elif msg_type == MsgType.Req and method == ".lq.FastTest.authGame":
            account_id = parse_obj["data"]["account_id"]
            assert account_id in self.players
            self.players[account_id]["conn_ids"].append(flow.client_conn.id)

        # client players
        # for account_id, value in self.players.items():
        #     logger.debug(f"[i][{account_id}] : {value['conn_ids']}[/i]")

        # invoke methods to modify websockt message
        self.invoke(flow.client_conn.id, flow_msg=message, parse_obj=parse_obj)

    def websocket_start(self, flow: http.HTTPFlow):
        logger.info(f"[i][green]Connected[/green] {flow.client_conn.id}[/i]")

    def websocket_end(self, flow: http.HTTPFlow):
        logger.info(f"[i][blue]Disconnected[/blue] {flow.client_conn.id}[/i]")

        # remove end connection ids
        for player in self.players.values():
            if flow.client_conn.id in player["conn_ids"]:
                player["conn_ids"].remove(flow.client_conn.id)


addons = [WebSocketAddon()]
