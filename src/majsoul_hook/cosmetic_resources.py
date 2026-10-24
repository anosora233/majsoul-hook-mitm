"""Extract the configuration projection used by the Mirage cosmetic business rules."""

import re

CFG_MODULES = (
    "exceltool",
    "const",
    "excels/params",
    "excels/data/item_definition/item",
    "excels/data/item_definition/character",
    "excels/data/item_definition/skin",
    "excels/data/item_definition/title",
    "excels/data/character/emoji",
    "excels/data/spot/rewards",
)
CFG_PATTERN = re.compile(
    r"^luabyte/lua/(?:exceltool|const|excels/params|excels/data/"
    r"(?:item_definition/(?:item|character|skin|title)|character/emoji|spot/rewards)"
    r"(?:_b\d+)?)\.lua\.bytes$"
)


def export_cosmetics(modules: dict[str, str]) -> dict:
    from lupa.lua51 import LuaRuntime

    missing = {module.replace("/", ".") for module in CFG_MODULES} - modules.keys()
    if missing:
        raise ValueError(f"Missing cosmetic modules: {sorted(missing)}")
    lua = LuaRuntime(unpack_returned_tuples=True, register_eval=False, register_builtins=False)
    lua.globals().source_for = lambda name: modules[name.lower()]
    lua.execute("""
        io,os,package,debug,python,dofile,loadfile=nil,nil,nil,nil,nil,nil,nil
        local cache={}
        function require(name)
          local key=string.lower(name)
          if cache[key]~=nil then return cache[key] end
          local value=assert(loadstring(source_for(name),name))()
          cache[key]=value;return value
        end
        require('CONST')
        function sheet(group,name)
          local value=require('Excels.Data.'..group..'.'..name)
          require('ExcelTool').TryLoadBlock(value,group,name)
          return value.tb
        end
    """)

    def rows(group, name):
        return sorted(lua.globals().sheet(group, name).items())

    items = rows("item_definition", "item")
    characters = rows("item_definition", "character")
    skins = rows("item_definition", "skin")
    emojis = rows("character", "emoji")
    snapshot = {
        "items": {
            str(category): [int(i) for i, row in items if row.category == category]
            for category in (5, 8)
        },
        "characters": [[int(i), int(row.init_skin)] for i, row in characters],
        "titles": [int(i) for i, _ in rows("item_definition", "title")],
        "skins": [int(i) for i, _ in skins],
        "skin_owners": {str(int(i)): int(row.character_id) for i, row in skins},
        "rewards": [int(i) for i, _ in rows("spot", "rewards")],
        "emojis": {},
    }
    for charid, group in emojis:
        entries = [row for _, row in sorted(group.items())]
        if any(row.charid != charid for row in entries):
            raise ValueError("Emoji character mismatch")
        snapshot["emojis"][str(int(charid))] = [int(row.sub_id) for row in entries]
    if not all(snapshot.values()) or any(skin <= 0 for _, skin in snapshot["characters"]):
        raise ValueError("Incomplete cosmetic configuration")
    return snapshot
