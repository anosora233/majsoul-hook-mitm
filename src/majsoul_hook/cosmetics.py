"""Mirage-compatible local cosmetics, with account-scoped persistent settings."""

import json
import random
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic

from .resources import atomic_write
from .schema import Schema, dictionary
from .wire import Codec, Frame

LOCAL_METHODS = frozenset(
    {
        "fetchRandomCharacter",
        "setRandomCharacter",
        "fetchTitleList",
        "useTitle",
        "setLoadingImage",
        "changeMainCharacter",
        "changeCharacterSkin",
        "updateCharacterSort",
        "setHiddenCharacter",
        "useCommonView",
        "saveCommonViews",
        "addFinishedEnding",
    }
)
LOCAL_NAMES = frozenset(f".lq.Lobby.{method}" for method in LOCAL_METHODS)


class StateStore:
    def __init__(self, path: Path):
        self.path = path
        self.accounts = {}
        if path.exists():
            document = json.loads(path.read_text(encoding="utf-8"))
            if document.get("format") != 1 or not isinstance(document.get("accounts"), dict):
                raise ValueError("Invalid cosmetic state file")
            if any(not isinstance(value, dict) for value in document["accounts"].values()):
                raise ValueError("Invalid account settings")
            self.accounts = document["accounts"]

    def account(self, account: int) -> dict:
        if not account:
            raise ValueError("Cosmetic account is not identified")
        return self.accounts.setdefault(str(account), {})

    def save(self) -> None:
        atomic_write(
            self.path,
            (
                json.dumps({"format": 1, "accounts": self.accounts}, ensure_ascii=False, indent=2)
                + "\n"
            ).encode(),
        )


@dataclass
class AccountState:
    room: dict | None = None
    room_seq: int = 0
    choice: dict | None = None
    game_uuid: str | None = None
    game_choice: dict | None = None


@dataclass
class Session:
    account: int = 0
    seat: int = -1
    choice: dict | None = None
    game_uuid: str | None = None
    view_queries: OrderedDict[int, tuple[int, float]] = field(default_factory=OrderedDict)


@dataclass
class Effect:
    content: bytes | None = None
    injections: list[bytes] = field(default_factory=list)
    local: bool = False


class Cosmetics:
    @classmethod
    def from_schema(cls, schema: Schema, state_path: Path) -> "Cosmetics":
        if not schema.cosmetic_config:
            raise ValueError("Update resources with cosmetics enabled first")
        return cls(schema, schema.cosmetic_config, StateStore(state_path))

    def __init__(self, schema: Schema, cfg: dict, store: StateStore, *, rng=None, clock=monotonic):
        self.schema, self.cfg, self.store = schema, cfg, store
        self.codec = Codec(schema)
        self.rng = rng or random.Random()
        self.clock = clock
        self.characters = {int(i): int(skin) for i, skin in cfg["characters"]}
        self.skins = set(cfg["skins"])
        if not self.characters or not self.skins or not cfg.get("skin_owners"):
            raise ValueError("Missing cosmetic configuration; run resources --cosmetics")
        self.accounts: dict[int, AccountState] = {}
        self.sessions: dict[str, Session] = {}
        # Known-local methods must be encodable before enabling interception.
        for name in LOCAL_NAMES:
            schema.message_class(self.codec.type_name(2, name))
            self.codec.error_response(name, 0)
        self.codec.error_response(".lq.FastTest.broadcastInGame", 0)

    def close(self, flow_id: str) -> None:
        self.sessions.pop(flow_id, None)

    def _state(self, account: int) -> AccountState:
        state = self.accounts.setdefault(account, AccountState())
        # Keep the game choice across a gap where all sockets reconnect. Retain
        # only a bounded number of inactive accounts for a long-running process.
        active = {session.account for session in self.sessions.values()} | {account}
        for candidate in list(self.accounts):
            if len(self.accounts) <= 64:
                break
            if candidate not in active:
                del self.accounts[candidate]
        return state

    def is_local(self, frame: Frame, *, from_client: bool) -> bool:
        if not from_client or frame.kind != 2:
            return False
        if frame.wrapper.name in LOCAL_NAMES:
            return True
        if frame.wrapper.name == ".lq.FastTest.broadcastInGame":
            try:
                content = json.loads(self.codec.read(frame, frame.wrapper.name).content)
                return isinstance(content, dict) and type(content.get("emo_id")) is int
            except (ValueError, TypeError):
                return False
        return False

    def _valid_skin(self, character: int, skin: int) -> bool:
        return (
            character in self.characters
            and skin in self.skins
            and self.cfg["skin_owners"].get(str(skin)) == character
        )

    def _character(self, charid: int, settings: dict, choice: dict | None) -> dict:
        if charid not in self.characters:
            raise ValueError("Unknown character")
        skin = settings.get("skins", {}).get(str(charid), self.characters[charid])
        if choice and choice["character_id"] == charid:
            skin = choice["skin_id"]
        if not self._valid_skin(charid, skin):
            skin = self.characters[charid]
        return {
            "charid": charid,
            "skin": skin,
            "level": 5,
            "exp": 1,
            "is_upgraded": True,
            "rewarded_level": [1, 2, 3, 4, 5],
            "views": [],
            "extra_emoji": self.cfg["emojis"].get(str(charid), []),
        }

    def _main(self, settings: dict, choice: dict | None) -> int:
        default = 200007 if 200007 in self.characters else next(iter(self.characters))
        main = choice["character_id"] if choice else settings.get("main", default)
        return main if main in self.characters else default

    def _selected_views(self, settings: dict) -> list:
        return settings.get("views", {}).get(str(settings.get("use", 0)), {}).get("values", [])

    def _view_setting(self, settings: dict, index: int) -> dict:
        saved = settings.get("views", {}).get(str(index), {})
        return {
            "index": index,
            "values": deepcopy(saved.get("values", [])),
            "name": saved.get("name", ""),
        }

    def _all_views(self, settings: dict) -> dict:
        return {
            "use": settings.get("use", 0),
            "views": [self._view_setting(settings, i) for i in range(10)],
        }

    def _character_info(self, settings: dict, choice: dict | None) -> dict:
        return {
            "send_gift_count": 0,
            "send_gift_limit": 2,
            "skins": sorted(self.skins),
            "finished_endings": self.cfg["rewards"],
            "rewarded_endings": self.cfg["rewards"],
            "main_character_id": self._main(settings, choice),
            "character_sort": settings.get("sort", []),
            "hidden_characters": settings.get("hidden", []),
            "characters": [self._character(i, settings, choice) for i in self.characters],
        }

    def _sync_game_choice(
        self,
        account: int,
        state: AccountState,
        *,
        character: int,
        skin: int,
        change_main: bool = False,
    ) -> None:
        if not state.game_uuid:
            return
        if change_main:
            state.game_choice = {"character_id": character, "skin_id": skin}
        elif state.game_choice and state.game_choice["character_id"] == character:
            state.game_choice["skin_id"] = skin
        for session in self.sessions.values():
            if session.account != account or session.game_uuid != state.game_uuid:
                continue
            if change_main:
                session.choice = deepcopy(state.game_choice)
            elif session.choice and session.choice["character_id"] == character:
                session.choice["skin_id"] = skin

    def _views(self, settings: dict) -> list:
        return [
            {
                "slot": view.get("slot", 0),
                "type": 0,
                "item_id_list": [],
                "item_id": self.rng.choice(view["item_id_list"])
                if view.get("type")
                else view.get("item_id", 0),
            }
            for view in self._selected_views(settings)
        ]

    def _override(
        self, players: list, account: int, choice: dict | None, type_name: str = "PlayerGameView"
    ) -> None:
        fields = self.schema.message_class(type_name).DESCRIPTOR.fields_by_name
        settings = self.store.account(account)
        for player in players or []:
            if not player:
                continue
            if player.get("account_id") == account:
                character = self._character(self._main(settings, choice), settings, choice)
                views = self._views(settings)
                updates = {
                    "views": views,
                    "avatar_id": character["skin"],
                    "character": character,
                    "avatar_frame": next((v["item_id"] for v in views if v["slot"] == 5), 0),
                    "title": settings.get("title", 0),
                    "loading_image": settings.get("loading", []),
                }
                player.update({key: value for key, value in updates.items() if key in fields})
            elif player.get("character"):
                player["character"].update(level=5, exp=1, is_upgraded=True)

    def _select(self, state: AccountState, settings: dict) -> None:
        config = settings.get("random", {})
        pool = [
            entry
            for entry in config.get("pool", [])
            if self._valid_skin(entry["character_id"], entry["skin_id"])
        ]
        state.choice = deepcopy(self.rng.choice(pool)) if config.get("enabled") and pool else None

    def _next_seq(self, state: AccountState, message: dict) -> None:
        state.room_seq = max(message.get("seq", 0), state.room_seq + 1)
        message["seq"] = state.room_seq

    def _update_room(self, state: AccountState, message: dict, account: int) -> None:
        self._override(message.get("player_list", []), account, state.choice)
        state.room = (
            deepcopy(message)
            if any(p.get("account_id") == account for p in message.get("player_list", []))
            else None
        )
        if state.room is None:
            state.room_seq = 0

    @staticmethod
    def _clear_room(state: AccountState) -> None:
        state.room, state.room_seq, state.choice = None, 0, None

    def _random_notice(self, account: int, choice: dict) -> tuple[str, dict]:
        return "NotifyAccountUpdate", {
            "update": {
                "character": {
                    "characters": [
                        self._character(choice["character_id"], self.store.account(account), choice)
                    ]
                },
                "main_character": choice,
            }
        }

    def apply(self, flow_id: str, frame: Frame, name: str, *, from_client: bool) -> Effect:
        # Stage all state and wire output together. Failed encoding or persistence
        # must not leave settings changed for a response the client never received.
        before = deepcopy((self.store.accounts, self.accounts, self.sessions))
        try:
            original = self.codec.read(frame, name)
            data = dictionary(original)
            previous = deepcopy(data)
            session = self.sessions.setdefault(flow_id, Session())
            now = self.clock()
            while (
                session.view_queries and now - next(iter(session.view_queries.values()))[1] >= 120
            ):
                session.view_queries.popitem(last=False)
            notices = []
            local = self.is_local(frame, from_client=from_client)
            response = None
            if frame.kind == 2 and from_client:
                # A standalone slot response has no index; correlate it with
                # the original request, including out-of-order responses.
                session.view_queries.pop(frame.request_id, None)
                if name == ".lq.Lobby.fetchCommonViews" and 0 <= data.get("index", 0) < 10:
                    session.view_queries[frame.request_id] = (data.get("index", 0), now)
                    while len(session.view_queries) > 4096:
                        session.view_queries.popitem(last=False)
                if name == ".lq.FastTest.authGame":
                    session.account = data.get("account_id", 0)
                    session.game_uuid = data.get("game_uuid")
                    state = self._state(session.account)
                    session.choice = (
                        deepcopy(state.game_choice)
                        if (data.get("game_uuid") and data["game_uuid"] == state.game_uuid)
                        else None
                    )
                    session.seat = -1
                elif name == ".lq.FastTest.broadcastInGame":
                    try:
                        content = json.loads(data.get("content", ""))
                    except (ValueError, TypeError):
                        content = None
                    if isinstance(content, dict) and type(content.get("emo_id")) is int:
                        local, response = True, {}
                        if session.seat >= 0:
                            notices.append(
                                (
                                    "NotifyGameBroadcast",
                                    {"seat": session.seat, "content": data["content"]},
                                )
                            )
                elif local:
                    response, notices = self._local(name.rsplit(".", 1)[1], data, session)
            elif not from_client:
                if frame.kind == 3:
                    view_query = session.view_queries.pop(frame.request_id, None)
                    notices = self._response(
                        name, data, session, view_index=view_query[0] if view_query else None
                    )
                elif frame.kind == 1:
                    notices = self._notify(name.removeprefix(".lq."), data, session)
            injections = (
                [self.codec.packet(3, name, response or {}, frame.request_id)] if local else []
            )
            injections += [
                self.codec.packet(1, ".lq." + notice, payload) for notice, payload in notices
            ]
            content = self.codec.replace(frame, original, data) if data != previous else None
            if self.store.accounts != before[0]:
                self.store.save()
            return Effect(content, injections, local)
        except Exception:
            self.store.accounts, self.accounts, self.sessions = before
            raise

    def _local(self, method: str, data: dict, session: Session) -> tuple[dict, list]:
        settings = self.store.account(session.account)
        state = self._state(session.account)
        notices, response = [], {}
        if method == "fetchRandomCharacter":
            response = settings.get("random", {"enabled": False, "pool": []})
        elif method == "fetchTitleList":
            response = {"title_list": self.cfg["titles"]}
        elif method == "setRandomCharacter":
            pool = [
                {"character_id": entry.get("character_id", 0), "skin_id": entry.get("skin_id", 0)}
                for entry in data.get("pool", [])
            ]
            if (
                data.get("enabled")
                and not pool
                or any(not self._valid_skin(e["character_id"], e["skin_id"]) for e in pool)
            ):
                raise ValueError("Invalid random character pool")
            settings["random"] = {"enabled": data.get("enabled", False), "pool": pool}
        elif method == "useTitle":
            title = data.get("title", 0)
            if title and title not in self.cfg["titles"]:
                raise ValueError("Unknown title")
            settings["title"] = title
        elif method == "setLoadingImage":
            settings["loading"] = data.get("images", [])
        elif method == "changeMainCharacter":
            charid = data.get("character_id", 0)
            if charid not in self.characters:
                raise ValueError("Unknown character")
            settings["main"], state.choice = charid, None
            self._sync_game_choice(
                session.account,
                state,
                character=charid,
                skin=self._character(charid, settings, None)["skin"],
                change_main=True,
            )
        elif method == "changeCharacterSkin":
            charid, skin = data.get("character_id", 0), data.get("skin", 0)
            if not self._valid_skin(charid, skin):
                raise ValueError("Skin does not belong to character")
            settings.setdefault("skins", {})[str(charid)] = skin
            if state.choice and state.choice["character_id"] == charid:
                state.choice["skin_id"] = skin
            self._sync_game_choice(session.account, state, character=charid, skin=skin)
            notices.append(
                (
                    "NotifyAccountUpdate",
                    {
                        "update": {
                            "character": {
                                "characters": [self._character(charid, settings, state.choice)]
                            }
                        }
                    },
                )
            )
        elif method == "updateCharacterSort":
            settings["sort"] = data.get("sort", [])
        elif method == "setHiddenCharacter":
            settings["hidden"] = data.get("chara_list", [])
            response = {"hidden_characters": settings["hidden"]}
        elif method == "useCommonView":
            index = data.get("index", 0)
            if not 0 <= index < 10:
                raise ValueError("Invalid view index")
            settings["use"] = index
        elif method == "saveCommonViews":
            index = data.get("save_index", 0)
            views = data.get("views", [])
            if not 0 <= index < 10 or any(
                v.get("type") and not v.get("item_id_list") for v in views
            ):
                raise ValueError("Invalid common view")
            settings.setdefault("views", {})[str(index)] = {
                "values": views,
                "index": index,
                "name": data.get("name", self._view_setting(settings, index)["name"]),
            }
            if data.get("is_use"):
                settings["use"] = index
        # addFinishedEnding is intentionally a local acknowledgement, as in Mirage.
        if method in ("changeMainCharacter", "changeCharacterSkin") and state.room:
            self._override(state.room.get("player_list", []), session.account, state.choice)
            self._next_seq(state, state.room)
            notices.append(("NotifyRoomPlayerUpdate", deepcopy(state.room)))
        return response, notices

    def _response(
        self, name: str, data: dict, session: Session, *, view_index: int | None = None
    ) -> list:
        if data.get("error", {}).get("code"):
            return []
        if name in {f".lq.Lobby.{m}" for m in ("login", "emailLogin", "oauth2Login")}:
            account = data.get("account_id", 0)
            if account:
                if account != session.account:
                    session.view_queries.clear()
                session.account = account
        if not session.account:
            return []
        account = session.account
        settings = self.store.account(account)
        state = self._state(account)
        if name == ".lq.FastTest.authGame":
            session.seat = (
                data.get("seat_list", []).index(account)
                if account in data.get("seat_list", [])
                else -1
            )
            self._override(data.get("players", []), account, session.choice)
            return []
        if not name.startswith(".lq.Lobby."):
            return []
        method = name.rsplit(".", 1)[1]
        if method in ("login", "emailLogin", "oauth2Login", "fetchAccountInfo"):
            self._override([data.get("account")], account, state.choice, "Account")
        elif method == "fetchInfo":
            if "random" not in settings and data.get("random_character"):
                settings["random"] = deepcopy(data["random_character"])
                settings["random"].pop("error", None)
            data["random_character"] = deepcopy(
                settings.get("random", {"enabled": False, "pool": []})
            )
            data.setdefault("character_info", {}).update(
                self._character_info(settings, state.choice)
            )
            data.setdefault("all_common_views", {}).update(self._all_views(settings))
            data.setdefault("title_list", {})["title_list"] = self.cfg["titles"]
            bag = data.setdefault("bag_info", {}).setdefault("bag", {})
            existing = {item.get("item_id") for item in bag.get("items", [])}
            bag["items"] = [
                {"item_id": item, "stack": 1}
                for category in ("5", "8")
                for item in self.cfg["items"].get(category, [])
                if item not in existing
            ] + bag.get("items", [])
        elif method == "fetchCharacterInfo":
            data.update(self._character_info(settings, state.choice))
        elif method == "fetchAllCommonViews":
            data.update(self._all_views(settings))
        elif method == "fetchCommonViews" and view_index is not None:
            view = self._view_setting(settings, view_index)
            data.update(views=view["values"], name=view["name"])
        elif method in ("joinRoom", "fetchRoom", "createRoom"):
            room = data.get("room")
            if not room:
                self._clear_room(state)
                return []
            entering = method != "fetchRoom" or state.room is None
            if entering:
                state.room_seq = room.get("seq", 0)
                self._select(state, settings)
            room["seq"] = state.room_seq = max(room.get("seq", 0), state.room_seq)
            update = {
                "player_list": room.get("persons", []),
                **{
                    key: room[key]
                    for key in ("owner_id", "robot_count", "seq", "robots", "positions")
                    if key in room
                },
            }
            self._update_room(state, update, account)
            if entering and state.room and state.choice:
                return [self._random_notice(account, state.choice)]
        elif method == "leaveRoom":
            self._clear_room(state)
        elif method == "fetchGameRecord":
            self._override(
                data.get("head", {}).get("accounts", []),
                account,
                state.choice,
                "RecordGame.AccountInfo",
            )
        return []

    def _notify(self, name: str, data: dict, session: Session) -> list:
        if not session.account:
            return []
        state = self._state(session.account)
        settings = self.store.account(session.account)
        if name in ("NotifyRoomGameStart", "NotifyMatchGameStart"):
            uuid = data.get("game_uuid")
            if not uuid or uuid == state.game_uuid:
                return []
            if name == "NotifyMatchGameStart":
                self._select(state, settings)
            state.game_uuid, state.game_choice = uuid, deepcopy(state.choice)
            if name == "NotifyMatchGameStart" and state.choice:
                return [self._random_notice(session.account, state.choice)]
        elif name == "NotifyAccountUpdate":
            if "update" in data:
                data["update"].pop("character", None)
                if state.choice and "main_character" in data["update"]:
                    data["update"]["main_character"] = deepcopy(state.choice)
                else:
                    data["update"].pop("main_character", None)
        elif name == "NotifyRoomPlayerUpdate":
            self._next_seq(state, data)
            self._update_room(state, data, session.account)
        elif name in ("NotifyRoomPlayerReady", "NotifyRoomPlayerDressing"):
            self._next_seq(state, data)
        elif name == "NotifyRoomKickOut":
            self._clear_room(state)
        elif name == "NotifyGameFinishRewardV2" and data.get("main_character"):
            data["main_character"].update(exp=1, add=0, level=5)
        return []
