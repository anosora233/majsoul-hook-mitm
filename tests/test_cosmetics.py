from copy import deepcopy

import pytest
from mitmproxy import websocket
from mitmproxy.test import tflow

from majsoul_hook.addon import CaptureAddon
from majsoul_hook.cosmetics import StateStore
from majsoul_hook.wire import Frame, dictionary


def apply(engine, kind, name, data, *, flow="lobby", request_id=7):
    packet = engine.codec.packet(kind, name, data, request_id if kind != 1 else None)
    return engine.apply(flow, Frame.parse(engine.schema, packet), name, from_client=kind == 2)


def login(engine, account=42, flow="lobby"):
    return apply(
        engine,
        3,
        ".lq.Lobby.login",
        {"account_id": account, "account": {"account_id": account, "gold": 99}},
        flow=flow,
    )


def unpack(engine, raw, name):
    return dictionary(engine.codec.read(Frame.parse(engine.schema, raw), name))


def test_login_inventory_and_account_isolation(cosmetics):
    effect = login(cosmetics)
    account = unpack(cosmetics, effect.content, ".lq.Lobby.login")["account"]
    assert account["avatar_id"] == 400001 and account["gold"] == 99
    apply(cosmetics, 2, ".lq.Lobby.useTitle", {"title": 2})
    apply(cosmetics, 2, ".lq.Lobby.changeCharacterSkin", {"character_id": 200007, "skin": 400002})
    effect = apply(
        cosmetics,
        3,
        ".lq.Lobby.fetchInfo",
        {
            "bag_info": {
                "bag": {"items": [{"item_id": 10, "stack": 9}, {"item_id": 55, "stack": 7}]}
            }
        },
    )
    data = unpack(cosmetics, effect.content, ".lq.Lobby.fetchInfo")
    assert data["character_info"]["skins"] == [400001, 400002, 400003]
    assert data["character_info"]["characters"][0]["extra_emoji"] == [1, 2, 15]
    assert data["character_info"]["characters"][0]["skin"] == 400002
    items = {item["item_id"]: item["stack"] for item in data["bag_info"]["bag"]["items"]}
    assert items == {10: 9, 11: 1, 12: 1, 55: 7}
    assert len(data["all_common_views"]["views"]) == 10
    other = login(cosmetics, 99, "other")
    assert unpack(cosmetics, other.content, ".lq.Lobby.login")["account"]["title"] == 0
    assert StateStore(cosmetics.store.path).account(42)["title"] == 2
    assert "account_id" not in cosmetics.store.path.read_text()


@pytest.mark.parametrize(
    "method,data,response_key",
    [
        ("useTitle", {"title": 1}, None),
        ("setLoadingImage", {"images": [2, 3]}, None),
        ("changeMainCharacter", {"character_id": 200008}, None),
        ("changeCharacterSkin", {"character_id": 200007, "skin": 400002}, None),
        ("updateCharacterSort", {"sort": [200008, 200007]}, None),
        ("setHiddenCharacter", {"chara_list": [200008]}, "hidden_characters"),
        ("saveCommonViews", {"save_index": 1, "views": [{"slot": 5, "item_id": 10}]}, None),
        ("useCommonView", {"index": 1}, None),
        ("addFinishedEnding", {}, None),
        ("fetchRandomCharacter", {}, "enabled"),
        ("fetchTitleList", {}, "title_list"),
        (
            "setRandomCharacter",
            {"enabled": True, "pool": [{"character_id": 200007, "skin_id": 400002}]},
            None,
        ),
    ],
)
def test_local_methods_reply_with_original_request_id(cosmetics, method, data, response_key):
    login(cosmetics)
    name = ".lq.Lobby." + method
    result = apply(cosmetics, 2, name, data, request_id=65535)
    assert result.local and result.content is None
    frame = Frame.parse(cosmetics.schema, result.injections[0])
    assert frame.kind == 3 and frame.request_id == 65535 and frame.wrapper.name == ""
    decoded = unpack(cosmetics, result.injections[0], name)
    if response_key:
        assert response_key in decoded


def test_room_sequences_notifications_and_manual_skin(cosmetics):
    login(cosmetics)
    apply(
        cosmetics,
        3,
        ".lq.Lobby.joinRoom",
        {"room": {"seq": 10, "owner_id": 42, "persons": [{"account_id": 42}, {"account_id": 8}]}},
    )
    result = apply(
        cosmetics, 2, ".lq.Lobby.changeCharacterSkin", {"character_id": 200007, "skin": 400002}
    )
    assert len(result.injections) == 3  # response, account notice, room notice
    room = unpack(cosmetics, result.injections[-1], ".lq.NotifyRoomPlayerUpdate")
    assert room["seq"] == 11 and room["player_list"][0]["avatar_id"] == 400002
    result = apply(cosmetics, 1, ".lq.NotifyRoomPlayerReady", {"seq": 2})
    assert unpack(cosmetics, result.content, ".lq.NotifyRoomPlayerReady")["seq"] == 12
    apply(cosmetics, 1, ".lq.NotifyRoomKickOut", {})
    result = apply(cosmetics, 2, ".lq.Lobby.changeMainCharacter", {"character_id": 200008})
    assert len(result.injections) == 1


def test_random_match_reconnect_and_emoji_are_local(cosmetics):
    login(cosmetics)
    pool = [
        {"character_id": 200007, "skin_id": 400002},
        {"character_id": 200008, "skin_id": 400003},
    ]
    apply(cosmetics, 2, ".lq.Lobby.setRandomCharacter", {"enabled": True, "pool": pool})
    start = apply(cosmetics, 1, ".lq.NotifyMatchGameStart", {"game_uuid": "game"})
    assert len(start.injections) == 1
    chosen = deepcopy(cosmetics.accounts[42].choice)
    duplicate = apply(cosmetics, 1, ".lq.NotifyMatchGameStart", {"game_uuid": "game"})
    assert not duplicate.injections
    cosmetics.close("lobby")
    assert not cosmetics.sessions  # Choice survives even when every socket closes.
    for flow in ("game", "reconnect"):
        auth = apply(
            cosmetics,
            2,
            ".lq.FastTest.authGame",
            {"account_id": 42, "game_uuid": "game"},
            flow=flow,
        )
        assert not auth.local and auth.content is None
        effect = apply(
            cosmetics,
            3,
            ".lq.FastTest.authGame",
            {"players": [{"account_id": 42}], "seat_list": [7, 42, 3]},
            flow=flow,
        )
        assert (
            unpack(cosmetics, effect.content, ".lq.FastTest.authGame")["players"][0]["avatar_id"]
            == chosen["skin_id"]
        )
    effect = apply(
        cosmetics, 2, ".lq.FastTest.broadcastInGame", {"content": '{"emo_id":15}'}, flow="game"
    )
    assert effect.local and len(effect.injections) == 2
    assert unpack(cosmetics, effect.injections[1], ".lq.NotifyGameBroadcast")["seat"] == 1
    assert not apply(
        cosmetics, 2, ".lq.FastTest.broadcastInGame", {"content": '{"other":15}'}, flow="game"
    ).local


def test_room_entry_selects_only_once_and_auth_without_seat(cosmetics):
    login(cosmetics)
    apply(
        cosmetics,
        2,
        ".lq.Lobby.setRandomCharacter",
        {"enabled": True, "pool": [{"character_id": 200008, "skin_id": 400003}]},
    )
    room = {"room": {"seq": 2, "persons": [{"account_id": 42}]}}
    assert apply(cosmetics, 3, ".lq.Lobby.createRoom", room).injections
    assert not apply(cosmetics, 3, ".lq.Lobby.fetchRoom", room).injections
    apply(cosmetics, 1, ".lq.NotifyRoomGameStart", {"game_uuid": "room-game"})
    apply(
        cosmetics,
        2,
        ".lq.FastTest.authGame",
        {"account_id": 42, "game_uuid": "room-game"},
        flow="game",
    )
    effect = apply(
        cosmetics, 2, ".lq.FastTest.broadcastInGame", {"content": '{"emo_id":1}'}, flow="game"
    )
    assert effect.local and len(effect.injections) == 1


def test_invalid_random_pool_and_store_failure_roll_back(cosmetics, monkeypatch):
    login(cosmetics)
    before = deepcopy(cosmetics.store.accounts)
    with pytest.raises(ValueError):
        apply(
            cosmetics,
            2,
            ".lq.Lobby.setRandomCharacter",
            {"enabled": True, "pool": [{"character_id": 200007, "skin_id": 400003}]},
        )
    assert cosmetics.store.accounts == before

    def fail():
        raise OSError("disk full")

    monkeypatch.setattr(cosmetics.store, "save", fail)
    with pytest.raises(OSError):
        apply(cosmetics, 2, ".lq.Lobby.useTitle", {"title": 2})
    assert cosmetics.store.accounts == before


def test_notification_encoding_failure_rolls_back_selection(cosmetics, monkeypatch):
    login(cosmetics)
    apply(cosmetics, 3, ".lq.Lobby.joinRoom", {"room": {"seq": 9, "persons": [{"account_id": 42}]}})
    before = deepcopy((cosmetics.store.accounts, cosmetics.accounts))
    encode = cosmetics.codec.packet

    def fail_notification(kind, *args, **kwargs):
        if kind == 1:
            raise ValueError("notification cannot encode")
        return encode(kind, *args, **kwargs)

    monkeypatch.setattr(cosmetics.codec, "packet", fail_notification)
    with pytest.raises(ValueError):
        apply(
            cosmetics, 2, ".lq.Lobby.changeCharacterSkin", {"character_id": 200007, "skin": 400002}
        )
    assert (cosmetics.store.accounts, cosmetics.accounts) == before


@pytest.mark.parametrize("failure", ["malformed", "encoder", "store"])
def test_addon_blocks_local_failure_and_sends_error(cosmetics, monkeypatch, failure):
    flow = tflow.twebsocketflow()
    login(cosmetics, flow=flow.id)
    before = deepcopy(cosmetics.store.accounts)
    addon = CaptureAddon(cosmetics.schema, cosmetics=cosmetics)
    name = ".lq.Lobby.useTitle"
    raw = cosmetics.codec.packet(2, name, {"title": 2}, 7)
    if failure == "malformed":
        frame = Frame.parse(cosmetics.schema, raw)
        frame.wrapper.data = b"\xff"
        raw = frame.serialize()
    elif failure == "encoder":
        monkeypatch.setattr(
            cosmetics.codec, "packet", lambda *a: (_ for _ in ()).throw(ValueError("encode"))
        )
    else:
        monkeypatch.setattr(cosmetics.store, "save", lambda: (_ for _ in ()).throw(OSError("disk")))
    injected = []
    monkeypatch.setattr(addon, "_inject", lambda f, data: injected.append(data))
    message = websocket.WebSocketMessage(2, True, raw)
    flow.websocket.messages.append(message)
    addon.websocket_message(flow)
    assert message.dropped and message.content == raw
    assert unpack(cosmetics, injected[0], name)["error"]["code"] == 1
    assert cosmetics.store.accounts == before
    assert not addon.connections[flow.id].pending


def test_addon_injection_direction_and_no_reentry(cosmetics, monkeypatch):
    from types import SimpleNamespace

    from mitmproxy import ctx

    flow = tflow.twebsocketflow()
    login(cosmetics, flow=flow.id)
    calls = []
    monkeypatch.setattr(
        ctx,
        "master",
        SimpleNamespace(commands=SimpleNamespace(call=lambda *args: calls.append(args))),
        raising=False,
    )
    addon = CaptureAddon(cosmetics.schema, cosmetics=cosmetics)
    raw = cosmetics.codec.packet(2, ".lq.Lobby.useTitle", {"title": 1}, 9)
    message = websocket.WebSocketMessage(2, True, raw)
    flow.websocket.messages.append(message)
    addon.websocket_message(flow)
    assert message.dropped and calls[0][0] == "inject.websocket"
    assert calls[0][1] is flow and calls[0][2] is True and calls[0][4] is False
    injected = websocket.WebSocketMessage(2, False, calls[0][3], injected=True)
    flow.websocket.messages.append(injected)
    addon.websocket_message(flow)
    assert len(calls) == 1 and not injected.dropped
    addon.websocket_end(flow)
    assert not cosmetics.sessions


def test_ordinary_failure_and_unknown_schema_retain_original(cosmetics, monkeypatch):
    flow = tflow.twebsocketflow()
    addon = CaptureAddon(cosmetics.schema, cosmetics=cosmetics)
    monkeypatch.setattr(cosmetics, "apply", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError()))
    for raw in (cosmetics.codec.packet(2, ".lq.Lobby.login", {}, 7), b"\xff"):
        message = websocket.WebSocketMessage(2, True, raw)
        flow.websocket.messages.append(message)
        before = message.get_state()
        addon.websocket_message(flow)
        assert message.get_state() == before


def test_notifications_records_and_server_error(cosmetics):
    login(cosmetics)
    apply(cosmetics, 2, ".lq.Lobby.useTitle", {"title": 2})
    result = apply(
        cosmetics,
        3,
        ".lq.Lobby.fetchGameRecord",
        {"head": {"accounts": [{"account_id": 42}, {"account_id": 7, "character": {"level": 1}}]}},
    )
    record = unpack(cosmetics, result.content, ".lq.Lobby.fetchGameRecord")
    assert record["head"]["accounts"][0]["title"] == 2
    assert record["head"]["accounts"][1]["character"]["level"] == 5
    assert apply(cosmetics, 3, ".lq.Lobby.fetchInfo", {"error": {"code": 9}}).content is None
    result = apply(
        cosmetics,
        1,
        ".lq.NotifyAccountUpdate",
        {
            "update": {
                "character": {"characters": [{"charid": 200007, "level": 1}]},
                "bag": {"items": [{"item_id": 99, "stack": 2}]},
            }
        },
    )
    update = unpack(cosmetics, result.content, ".lq.NotifyAccountUpdate")["update"]
    assert "character" not in update and update["bag"]["items"][0]["stack"] == 2
    result = apply(
        cosmetics, 1, ".lq.NotifyGameFinishRewardV2", {"main_character": {"exp": 99, "add": 9}}
    )
    assert unpack(cosmetics, result.content, ".lq.NotifyGameFinishRewardV2")["main_character"] == {
        "exp": 1,
        "add": 0,
        "level": 5,
    }
