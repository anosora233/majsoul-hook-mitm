import base64
import json
from types import SimpleNamespace

import pytest

from majsoul_hook.resources import CONFIG, INDEX, export_descriptor, update_resources
from majsoul_hook.schema import Schema

LUA = """
local pb=require('protobuf.protobuf')
module('Protol.test_pb')
local wrapper=pb.Descriptor()
wrapper.full_name='lq.Wrapper'
local name=pb.FieldDescriptor()
name.name='name'; name.number=1; name.type=9; name.label=1
local data=pb.FieldDescriptor()
data.name='data'; data.number=2; data.type=12; data.label=1
wrapper.fields={name,data}
Wrapper=pb.Message(wrapper)
local other=pb.Descriptor()
other.full_name='lqc.Values'
local value=pb.FieldDescriptor()
value.name='values'; value.number=1; value.type=5; value.label=3
other.fields={value}
Values=pb.Message(other)
"""


def test_legacy_lua_modules_and_namespaces():
    descriptor = export_descriptor(
        {
            "protol.test_pb": LUA,
            "protol.use_pb": "local d=require('Protol.test_pb'); assert(d.Wrapper.DESCRIPTOR)",
        }
    )
    schema = Schema(descriptor, {})
    cls = schema.pool.FindMessageTypeByName("lqc.Values")
    assert cls.fields[0].GetOptions().packed
    assert schema.parse("Wrapper", b"\x0a\x01x").name == "x"


def test_offline_resource_build_and_atomic_failure(tmp_path, monkeypatch):
    import hashlib

    import UnityPy

    base = "https://example.test/"
    cache = tmp_path / hashlib.sha256(base.encode()).hexdigest()[:16]
    cache.mkdir()
    bundle = "2_ts@-$d-$zo_hash.majset"
    for name in (INDEX, bundle):
        (cache / name).write_bytes(b"fixture")
    path = "luabyte/lua/protol/test_pb.lua.bytes"
    tree = {
        "assetInfos": [{"assetPath": p, "ownerBundleIndex": 0} for p in (path, CONFIG)],
        "bundleInfos": [{"name": bundle}],
    }
    config = {"service": {"Lobby": {"call": {"request": "Wrapper", "response": "Wrapper"}}}}
    assets = {path: LUA.encode(), CONFIG: json.dumps(config).encode()}

    class Pointer:
        def __init__(self, content):
            self.content = content

        def read(self):
            return SimpleNamespace(m_Script=self.content)

    def load(path):
        if str(path).endswith(INDEX):
            obj = SimpleNamespace(
                type=SimpleNamespace(name="MonoBehaviour"), read_typetree=lambda: tree
            )
            return SimpleNamespace(objects=[obj])
        return SimpleNamespace(container={p: Pointer(raw) for p, raw in assets.items()})

    monkeypatch.setattr(UnityPy, "load", load)
    output = tmp_path / "protocol.json"
    update_resources(output, tmp_path, base_url=base, offline=True)
    schema = Schema.load(output)
    assert ".lq.Lobby.call" in schema.methods
    document = json.loads(output.read_text())
    assert base64.b64decode(document["descriptor"])
    assert bundle in document["bundle_sha256"]
    before = output.read_bytes()
    del assets[CONFIG]
    with pytest.raises(ValueError, match="incomplete"):
        update_resources(output, tmp_path, base_url=base, offline=True)
    assert output.read_bytes() == before
    tree["bundleInfos"][0]["name"] = "../escape.majset"
    with pytest.raises(ValueError, match="Invalid bundle"):
        update_resources(output, tmp_path, base_url=base, offline=True)


def test_offline_missing_and_invalid_format(tmp_path):
    with pytest.raises(FileNotFoundError, match="Offline bundle missing"):
        update_resources(tmp_path / "out.json", tmp_path, offline=True)
    path = tmp_path / "out.json"
    path.write_text('{"format": 2}')
    with pytest.raises(ValueError, match="Unsupported"):
        Schema.load(path)
