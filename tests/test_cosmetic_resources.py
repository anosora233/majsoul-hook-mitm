import pytest

from majsoul_hook.cosmetic_resources import CFG_MODULES, export_cosmetics


def test_project_cosmetic_sheets_and_load_blocks():
    modules = {module.replace("/", "."): "return {}" for module in CFG_MODULES}
    modules.update(
        {
            "exceltool": """return {TryLoadBlock=function(value,group,name)
            if value.block then
              local block=require('Excels.Data.'..group..'.'..name..'_B1')
              for id,row in pairs(block.tb) do value.tb[id]=row end
            end
        end}""",
            "excels.data.item_definition.item": (
                "return {tb={[10]={category=5},[12]={category=8},[13]={category=1}}}"
            ),
            "excels.data.item_definition.character": (
                "return {tb={[200007]={init_skin=400001}},block=true}"
            ),
            "excels.data.item_definition.character_b1": "return {tb={[200008]={init_skin=400002}}}",
            "excels.data.item_definition.skin": (
                "return {tb={[400001]={character_id=200007},[400002]={character_id=200008}}}"
            ),
            "excels.data.item_definition.title": "return {tb={[1]={}}}",
            "excels.data.spot.rewards": "return {tb={[3]={}}}",
            "excels.data.character.emoji": "return {tb={[200007]={{charid=200007,sub_id=15}}}}",
        }
    )
    cfg = export_cosmetics(modules)
    assert cfg["characters"] == [[200007, 400001], [200008, 400002]]
    assert cfg["skin_owners"]["400002"] == 200008
    assert cfg["items"] == {"5": [10], "8": [12]}
    assert cfg["emojis"] == {"200007": [15]}
    modules.pop("const")
    with pytest.raises(ValueError, match="Missing cosmetic modules"):
        export_cosmetics(modules)
