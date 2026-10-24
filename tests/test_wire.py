from majsoul_hook.schema import dictionary
from majsoul_hook.wire import Codec, Frame


def test_edit_preserves_unknown_fields_at_all_levels(cosmetic_schema):
    schema = cosmetic_schema
    codec = Codec(schema)
    unknown = b"\xa0\x06\x2a"  # synthetic unknown varint field 100
    response = schema.message_class("ResFetchInfo")()
    response.MergeFromString(unknown)
    response.bag_info.MergeFromString(unknown)
    item = response.bag_info.bag.items.add(item_id=10, stack=8)
    item.MergeFromString(unknown)
    wrapper = schema.message_class("Wrapper")(data=response.SerializeToString())
    wrapper.MergeFromString(unknown)
    frame = Frame(3, 65535, wrapper)
    after = dictionary(response)
    after["bag_info"]["bag"]["items"].insert(0, {"item_id": 11, "stack": 1})
    after["character_info"] = {"skins": [400001, 400002]}
    encoded = codec.replace(frame, response, after)
    edited_frame = Frame.parse(schema, encoded)
    edited = codec.read(edited_frame, ".lq.Lobby.fetchInfo")
    assert edited_frame.request_id == 65535
    assert unknown in edited_frame.wrapper.SerializeToString()
    assert unknown in edited.SerializeToString()
    assert unknown in edited.bag_info.SerializeToString()
    assert unknown not in edited.bag_info.bag.items[0].SerializeToString()
    assert unknown in edited.bag_info.bag.items[1].SerializeToString()
    assert edited.bag_info.bag.items[1].stack == 8
    assert edited.character_info.SerializeToString() == b"\x0a\x06\x81\xb5\x18\x82\xb5\x18"


def test_no_edit_keeps_payload_and_nested_unknowns(cosmetic_schema):
    codec = Codec(cosmetic_schema)
    packet = codec.packet(
        3,
        ".lq.Lobby.joinRoom",
        {
            "room": {
                "persons": [{"account_id": 42, "character": {"charid": 200007, "skin": 400001}}]
            }
        },
        9,
    )
    frame = Frame.parse(cosmetic_schema, packet)
    body = codec.read(frame, ".lq.Lobby.joinRoom")
    unknown = b"\xa0\x06\x2a"
    body.room.persons[0].character.MergeFromString(unknown)
    after = dictionary(body)
    after["room"]["persons"][0]["character"]["skin"] = 400002
    result = codec.read(
        Frame.parse(cosmetic_schema, codec.replace(frame, body, after)), ".lq.Lobby.joinRoom"
    )
    assert unknown in result.room.persons[0].character.SerializeToString()
    assert result.room.persons[0].character.skin == 400002


def test_duplicate_player_ids_keep_their_own_unknown_fields(cosmetic_schema):
    codec = Codec(cosmetic_schema)
    body = cosmetic_schema.message_class("ResAuth")()
    for value in (1, 2):
        player = body.players.add()  # Bots can share the default account_id.
        player.character.level = 1
        player.MergeFromString(b"\xa0\x06" + bytes([value]))
    frame = Frame(3, 1, cosmetic_schema.message_class("Wrapper")())
    data = dictionary(body)
    for player in data["players"]:
        player["character"]["level"] = 5
    edited = codec.read(
        Frame.parse(cosmetic_schema, codec.replace(frame, body, data)), ".lq.FastTest.authGame"
    )
    assert b"\xa0\x06\x01" in edited.players[0].SerializeToString()
    assert b"\xa0\x06\x02" in edited.players[1].SerializeToString()
