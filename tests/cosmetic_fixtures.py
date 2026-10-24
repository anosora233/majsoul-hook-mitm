"""Small synthetic descriptors; no real account data or generated game artifacts."""

import pytest
from google.protobuf import descriptor_pb2

from majsoul_hook.cosmetics import Cosmetics, StateStore
from majsoul_hook.schema import Schema

DEFINITIONS = {
    "Wrapper": "name:string data:bytes",
    "Error": "code:uint32",
    "ReqCommon": "",
    "ResCommon": "error:Error",
    "Character": "charid:uint32 skin:uint32 level:uint32 exp:uint32 is_upgraded:bool "
    "rewarded_level:uint32* views:ViewSlot* extra_emoji:uint32*",
    "ViewSlot": "slot:uint32 type:uint32 item_id:uint32 item_id_list:uint32*",
    "Account": "account_id:uint32 nickname:string avatar_id:uint32 title:uint32 "
    "avatar_frame:uint32 loading_image:uint32* gold:uint32",
    "PlayerGameView": "account_id:uint32 character:Character avatar_id:uint32 title:uint32 "
    "avatar_frame:uint32 views:ViewSlot*",
    "RecordAccount": "account_id:uint32 character:Character avatar_id:uint32 title:uint32 "
    "avatar_frame:uint32 views:ViewSlot*",
    "RecordGame": "accounts:RecordAccount*",
    "ReqTitle": "title:uint32",
    "ReqLoading": "images:uint32*",
    "ReqCharacter": "character_id:uint32",
    "ReqSkin": "character_id:uint32 skin:uint32",
    "ReqSort": "sort:uint32*",
    "ReqHidden": "chara_list:uint32*",
    "ResHidden": "error:Error hidden_characters:uint32*",
    "ReqView": "index:uint32",
    "ReqSaveViews": "save_index:uint32 views:ViewSlot* name:string is_use:uint32",
    "ViewSetting": "index:uint32 values:ViewSlot* name:string",
    "AllViews": "use:uint32 views:ViewSetting* error:Error",
    "ResViews": "views:ViewSlot* name:string error:Error",
    "RandomEntry": "character_id:uint32 skin_id:uint32",
    "ReqRandom": "enabled:bool pool:RandomEntry*",
    "ResRandom": "error:Error enabled:bool pool:RandomEntry*",
    "ResTitles": "error:Error title_list:uint32*",
    "ResLogin": "error:Error account_id:uint32 account:Account",
    "CharacterInfo": "skins:uint32* finished_endings:uint32* rewarded_endings:uint32* "
    "main_character_id:uint32 character_sort:uint32* hidden_characters:uint32* "
    "characters:Character* send_gift_count:uint32 send_gift_limit:uint32 error:Error",
    "BagItem": "item_id:uint32 stack:uint32",
    "Bag": "items:BagItem*",
    "BagInfo": "bag:Bag",
    "ResFetchInfo": "error:Error random_character:ResRandom character_info:CharacterInfo "
    "all_common_views:AllViews title_list:ResTitles bag_info:BagInfo",
    "Room": "persons:PlayerGameView* owner_id:uint32 robot_count:uint32 seq:uint32 "
    "robots:PlayerGameView* positions:uint32*",
    "ResRoom": "error:Error room:Room",
    "ResRecord": "error:Error head:RecordGame",
    "ResAccount": "error:Error account:Account",
    "ReqAuth": "account_id:uint32 game_uuid:string",
    "ResAuth": "error:Error players:PlayerGameView* seat_list:uint32*",
    "ReqBroadcast": "content:string",
    "NotifyGameBroadcast": "seat:uint32 content:string",
    "CharacterUpdate": "characters:Character*",
    "AccountUpdate": "character:CharacterUpdate main_character:RandomEntry bag:Bag",
    "NotifyAccountUpdate": "update:AccountUpdate",
    "NotifyRoomPlayerUpdate": "owner_id:uint32 robot_count:uint32 player_list:PlayerGameView* "
    "seq:uint32 robots:PlayerGameView* positions:uint32*",
    "NotifyRoomPlayerReady": "seq:uint32",
    "NotifyRoomPlayerDressing": "seq:uint32",
    "NotifyRoomKickOut": "",
    "NotifyRoomGameStart": "game_uuid:string",
    "NotifyMatchGameStart": "game_uuid:string",
    "Reward": "exp:uint32 add:uint32 level:uint32",
    "NotifyGameFinishRewardV2": "main_character:Reward",
}
METHODS = {
    "Lobby": {
        **{m: ("ReqCommon", "ResLogin") for m in ("login", "emailLogin", "oauth2Login")},
        "fetchInfo": ("ReqCommon", "ResFetchInfo"),
        "fetchCharacterInfo": ("ReqCommon", "CharacterInfo"),
        "fetchAllCommonViews": ("ReqCommon", "AllViews"),
        "fetchCommonViews": ("ReqView", "ResViews"),
        "fetchAccountInfo": ("ReqCommon", "ResAccount"),
        "fetchGameRecord": ("ReqCommon", "ResRecord"),
        **{m: ("ReqCommon", "ResRoom") for m in ("createRoom", "fetchRoom", "joinRoom")},
        "leaveRoom": ("ReqCommon", "ResCommon"),
        "useTitle": ("ReqTitle", "ResCommon"),
        "setLoadingImage": ("ReqLoading", "ResCommon"),
        "changeMainCharacter": ("ReqCharacter", "ResCommon"),
        "changeCharacterSkin": ("ReqSkin", "ResCommon"),
        "updateCharacterSort": ("ReqSort", "ResCommon"),
        "setHiddenCharacter": ("ReqHidden", "ResHidden"),
        "useCommonView": ("ReqView", "ResCommon"),
        "saveCommonViews": ("ReqSaveViews", "ResCommon"),
        "setRandomCharacter": ("ReqRandom", "ResCommon"),
        "fetchRandomCharacter": ("ReqCommon", "ResRandom"),
        "fetchTitleList": ("ReqCommon", "ResTitles"),
        "addFinishedEnding": ("ReqCommon", "ResCommon"),
    },
    "FastTest": {
        "authGame": ("ReqAuth", "ResAuth"),
        "broadcastInGame": ("ReqBroadcast", "ResCommon"),
    },
}


@pytest.fixture
def cosmetic_schema():
    source = descriptor_pb2.FileDescriptorProto(
        name="cosmetic-test.proto", package="lq", syntax="proto2"
    )
    scalars = {"uint32": 13, "string": 9, "bytes": 12, "bool": 8}
    for name, specification in DEFINITIONS.items():
        message = source.message_type.add(name=name)
        for number, spec in enumerate(specification.split(), 1):
            field_name, type_name = spec.split(":")
            repeated = type_name.endswith("*")
            type_name = type_name.rstrip("*")
            target = message.field.add(
                name=field_name,
                number=number,
                type=scalars.get(type_name, 11),
                label=3 if repeated else 1,
            )
            if type_name not in scalars:
                target.type_name = ".lq." + type_name
            elif repeated and type_name == "uint32":
                target.options.packed = True
    schema = Schema(
        source.SerializeToString(),
        {
            service: {
                method: {"request": pair[0], "response": pair[1]}
                for method, pair in methods.items()
            }
            for service, methods in METHODS.items()
        },
    )
    # The production name is nested; business tests use an equivalent synthetic descriptor.
    original = schema.message_class
    schema.message_class = lambda name: original(
        "RecordAccount" if name == "RecordGame.AccountInfo" else name
    )
    return schema


@pytest.fixture
def cosmetic_config():
    return {
        "characters": [[200007, 400001], [200008, 400003]],
        "skins": [400001, 400002, 400003],
        "skin_owners": {"400001": 200007, "400002": 200007, "400003": 200008},
        "titles": [1, 2],
        "rewards": [3],
        "items": {"5": [10, 11], "8": [12]},
        "emojis": {"200007": [1, 2, 15], "200008": [3]},
    }


@pytest.fixture
def cosmetics(cosmetic_schema, cosmetic_config, tmp_path):
    return Cosmetics(cosmetic_schema, cosmetic_config, StateStore(tmp_path / "state.json"))
