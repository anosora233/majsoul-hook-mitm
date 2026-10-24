from collections import OrderedDict
from copy import deepcopy

import pytest

from majsoul_hook.cosmetics import Cosmetics, StateStore
from majsoul_hook.wire import Frame

from .test_cosmetics import apply, login, unpack


def save_view(engine, index, name, *, flow="lobby", use=0):
    return apply(
        engine,
        2,
        ".lq.Lobby.saveCommonViews",
        {
            "save_index": index,
            "name": name,
            "is_use": use,
            "views": [{"slot": 5, "item_id": 10 + index}],
        },
        flow=flow,
    )


def test_preset_name_and_use_survive_restart(cosmetics):
    login(cosmetics)
    save_view(cosmetics, 2, "Local preset", use=1)
    save_view(cosmetics, 3, "Another preset", use=0)
    restored = Cosmetics(cosmetics.schema, cosmetics.cfg, StateStore(cosmetics.store.path))
    login(restored)
    data = unpack(
        restored, apply(restored, 3, ".lq.Lobby.fetchInfo", {}).content, ".lq.Lobby.fetchInfo"
    )
    views = data["all_common_views"]
    assert views["use"] == 2
    assert views["views"][2] == {
        "index": 2,
        "name": "Local preset",
        "values": [{"slot": 5, "item_id": 12}],
    }
    assert [view["index"] for view in views["views"]] == list(range(10))
    assert views["views"][3]["name"] == "Another preset"


def test_standalone_queries_match_initial_projection(cosmetics):
    login(cosmetics)
    save_view(cosmetics, 2, "Local preset", use=1)
    apply(cosmetics, 2, ".lq.Lobby.changeCharacterSkin", {"character_id": 200007, "skin": 400002})
    apply(cosmetics, 2, ".lq.Lobby.setHiddenCharacter", {"chara_list": [200008]})
    apply(cosmetics, 2, ".lq.Lobby.updateCharacterSort", {"sort": [200008, 200007]})
    info = unpack(
        cosmetics, apply(cosmetics, 3, ".lq.Lobby.fetchInfo", {}).content, ".lq.Lobby.fetchInfo"
    )
    for method, key in (
        ("fetchCharacterInfo", "character_info"),
        ("fetchAllCommonViews", "all_common_views"),
    ):
        effect = apply(cosmetics, 3, ".lq.Lobby." + method, {})
        assert unpack(cosmetics, effect.content, ".lq.Lobby." + method) == info[key]
        assert not effect.local and not effect.injections


def test_saving_slots_without_name_preserves_name_and_explicit_empty_clears_it(cosmetics):
    login(cosmetics)
    save_view(cosmetics, 2, "Keep this name", use=1)
    apply(
        cosmetics,
        2,
        ".lq.Lobby.saveCommonViews",
        {"save_index": 2, "views": [{"slot": 5, "item_id": 99}]},
    )
    assert cosmetics.store.account(42)["views"]["2"]["name"] == "Keep this name"
    assert cosmetics.store.account(42)["use"] == 2
    apply(cosmetics, 2, ".lq.Lobby.saveCommonViews", {"save_index": 2, "name": ""})
    assert cosmetics.store.account(42)["views"]["2"]["name"] == ""


def test_switching_accounts_discards_previous_slot_queries(cosmetics):
    login(cosmetics)
    apply(cosmetics, 2, ".lq.Lobby.fetchCommonViews", {"index": 2}, request_id=12)
    login(cosmetics, account=99)
    assert not cosmetics.sessions["lobby"].view_queries
    save_view(cosmetics, 2, "Other account")
    effect = apply(
        cosmetics, 3, ".lq.Lobby.fetchCommonViews", {"name": "Old response"}, request_id=12
    )
    assert effect.content is None


def test_manual_game_updates_roll_back_if_persistence_fails(cosmetics, monkeypatch):
    login(cosmetics)
    apply(
        cosmetics,
        2,
        ".lq.Lobby.setRandomCharacter",
        {"enabled": True, "pool": [{"character_id": 200007, "skin_id": 400001}]},
    )
    apply(cosmetics, 1, ".lq.NotifyMatchGameStart", {"game_uuid": "game"})
    apply(
        cosmetics, 2, ".lq.FastTest.authGame", {"account_id": 42, "game_uuid": "game"}, flow="game"
    )
    before = deepcopy((cosmetics.store.accounts, cosmetics.accounts, cosmetics.sessions))

    def fail():
        raise OSError("disk full")

    monkeypatch.setattr(cosmetics.store, "save", fail)
    with pytest.raises(OSError):
        apply(
            cosmetics, 2, ".lq.Lobby.changeCharacterSkin", {"character_id": 200007, "skin": 400002}
        )
    assert (cosmetics.store.accounts, cosmetics.accounts, cosmetics.sessions) == before


@pytest.mark.parametrize(
    "method", ["fetchCharacterInfo", "fetchAllCommonViews", "fetchCommonViews"]
)
def test_standalone_error_response_is_preserved(cosmetics, method):
    login(cosmetics)
    name = ".lq.Lobby." + method
    apply(cosmetics, 2, name, {"index": 0} if method == "fetchCommonViews" else {})
    before = deepcopy(cosmetics.store.accounts)
    effect = apply(cosmetics, 3, name, {"error": {"code": 9}})
    assert effect.content is None and not effect.injections
    assert cosmetics.store.accounts == before
    assert not cosmetics.sessions["lobby"].view_queries


def test_slot_queries_are_correlated_by_request_id_and_connection(cosmetics):
    login(cosmetics)
    save_view(cosmetics, 1, "First")
    save_view(cosmetics, 2, "Second")
    login(cosmetics, account=99, flow="other")
    save_view(cosmetics, 1, "Other account", flow="other")
    name = ".lq.Lobby.fetchCommonViews"
    for flow, request_id, index in (("lobby", 11, 1), ("lobby", 12, 2), ("other", 11, 1)):
        effect = apply(cosmetics, 2, name, {"index": index}, flow=flow, request_id=request_id)
        assert effect.content is None and not effect.local  # Queries still reach the server.
    for flow, request_id, expected in (
        ("lobby", 12, "Second"),
        ("other", 11, "Other account"),
        ("lobby", 11, "First"),
    ):
        effect = apply(
            cosmetics, 3, name, {"name": "Server preset"}, flow=flow, request_id=request_id
        )
        assert unpack(cosmetics, effect.content, name)["name"] == expected
    assert all(not session.view_queries for session in cosmetics.sessions.values())


def test_default_slot_and_uncorrelated_response(cosmetics):
    login(cosmetics)
    save_view(cosmetics, 0, "Default")
    name = ".lq.Lobby.fetchCommonViews"
    apply(cosmetics, 2, name, {})
    effect = apply(cosmetics, 3, name, {"name": "Server preset"})
    assert unpack(cosmetics, effect.content, name)["name"] == "Default"
    # No index is present in this response; do not guess a different local slot.
    assert apply(cosmetics, 3, name, {"name": "Uncorrelated"}).content is None


def test_query_context_expires_and_id_reuse_clears_old_slot(cosmetics):
    login(cosmetics)
    now = [0]
    cosmetics.clock = lambda: now[0]
    name = ".lq.Lobby.fetchCommonViews"
    apply(cosmetics, 2, name, {"index": 1})
    now[0] = 120
    assert apply(cosmetics, 3, name, {"name": "Expired"}).content is None
    apply(cosmetics, 2, name, {"index": 1})
    apply(cosmetics, 2, ".lq.Lobby.fetchCharacterInfo", {})  # Same request ID reused.
    assert not cosmetics.sessions["lobby"].view_queries
    session = cosmetics.sessions["lobby"]
    session.view_queries = OrderedDict((i, (1, 120)) for i in range(4096))
    apply(cosmetics, 2, name, {"index": 1}, request_id=5000)
    assert len(session.view_queries) == 4096 and 0 not in session.view_queries
    cosmetics.close("lobby")
    assert "lobby" not in cosmetics.sessions


def test_standalone_projection_keeps_unknown_fields(cosmetics):
    login(cosmetics)
    save_view(cosmetics, 2, "Local")
    name = ".lq.Lobby.fetchAllCommonViews"
    raw = cosmetics.codec.packet(3, name, {"views": [{"index": 2, "name": "Server"}]}, 7)
    frame = Frame.parse(cosmetics.schema, raw)
    original = cosmetics.codec.read(frame, name)
    unknown = b"\xa0\x06\x2a"
    original.MergeFromString(unknown)
    original.views[0].MergeFromString(unknown)
    frame.wrapper.data = original.SerializeToString()
    effect = cosmetics.apply("lobby", frame, name, from_client=False)
    edited = cosmetics.codec.read(Frame.parse(cosmetics.schema, effect.content), name)
    assert unknown in edited.SerializeToString()
    assert unknown in edited.views[2].SerializeToString()
    assert edited.views[2].name == "Local"


@pytest.mark.parametrize("before_auth_request", [True, False])
def test_manual_skin_reaches_pending_auth_and_reconnect(cosmetics, before_auth_request):
    login(cosmetics)
    pool = [{"character_id": 200007, "skin_id": 400001}]
    apply(cosmetics, 2, ".lq.Lobby.setRandomCharacter", {"enabled": True, "pool": pool})
    apply(cosmetics, 1, ".lq.NotifyMatchGameStart", {"game_uuid": "game"})
    if not before_auth_request:
        apply(
            cosmetics,
            2,
            ".lq.FastTest.authGame",
            {"account_id": 42, "game_uuid": "game"},
            flow="game",
        )
    apply(cosmetics, 2, ".lq.Lobby.changeCharacterSkin", {"character_id": 200007, "skin": 400002})
    for flow in ("game", "reconnect"):
        if before_auth_request or flow == "reconnect":
            apply(
                cosmetics,
                2,
                ".lq.FastTest.authGame",
                {"account_id": 42, "game_uuid": "game"},
                flow=flow,
            )
        effect = apply(
            cosmetics,
            3,
            ".lq.FastTest.authGame",
            {"players": [{"account_id": 42}], "seat_list": [42]},
            flow=flow,
        )
        assert (
            unpack(cosmetics, effect.content, ".lq.FastTest.authGame")["players"][0]["avatar_id"]
            == 400002
        )
    assert cosmetics.store.account(42)["random"]["pool"] == pool
    assert cosmetics.accounts[42].game_choice["skin_id"] == 400002


def test_manual_main_updates_bound_game_but_other_character_skin_does_not(cosmetics):
    login(cosmetics)
    pool = [{"character_id": 200007, "skin_id": 400001}]
    apply(cosmetics, 2, ".lq.Lobby.setRandomCharacter", {"enabled": True, "pool": pool})
    apply(cosmetics, 1, ".lq.NotifyRoomGameStart", {"game_uuid": "game"})
    # No room choice exists here. Select a deterministic match choice instead.
    apply(cosmetics, 1, ".lq.NotifyMatchGameStart", {"game_uuid": "matched-game"})
    apply(
        cosmetics,
        2,
        ".lq.FastTest.authGame",
        {"account_id": 42, "game_uuid": "matched-game"},
        flow="game",
    )
    apply(cosmetics, 2, ".lq.Lobby.changeCharacterSkin", {"character_id": 200008, "skin": 400003})
    assert cosmetics.sessions["game"].choice["character_id"] == 200007
    apply(cosmetics, 2, ".lq.Lobby.changeMainCharacter", {"character_id": 200008})
    assert cosmetics.sessions["game"].choice == {"character_id": 200008, "skin_id": 400003}
    effect = apply(
        cosmetics,
        3,
        ".lq.FastTest.authGame",
        {"players": [{"account_id": 42}], "seat_list": [42]},
        flow="game",
    )
    player = unpack(cosmetics, effect.content, ".lq.FastTest.authGame")["players"][0]
    assert player["avatar_id"] == 400003 and player["character"]["charid"] == 200008
    assert cosmetics.store.account(42)["random"]["pool"] == pool
