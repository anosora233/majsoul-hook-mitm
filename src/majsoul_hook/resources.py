"""Extract current protocol descriptors from Unity bundles, following majsoul-mirage.

Lua is used only by this explicit resource build step, never during capture.
"""

import base64
import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from google.protobuf import descriptor_pb2

from .cosmetic_resources import CFG_PATTERN, export_cosmetics
from .schema import Schema

DEFAULT_BASE_URL = "https://game.maj-soul.com/assetbundles/DXT/"
INDEX = "bundle_info_so.majset"
CONFIG = "myassets/docs/proto_config.bytes"
MODULE = re.compile(r"^luabyte/lua/protol/[^/]+_pb\.lua\.bytes$")
XOR_KEY = b"wrelupqezdfrqdsd"
logger = logging.getLogger(__name__)


def normalize_base_url(base_url: str) -> str:
    base_url = base_url.strip().rstrip("/") + "/"
    if urlsplit(base_url).scheme != "https":
        raise ValueError("Resource base URL must use HTTPS")
    return base_url


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def export_descriptor(modules: dict[str, str]) -> bytes:
    from lupa.lua51 import LuaRuntime

    lua = LuaRuntime(unpack_returned_tuples=True, register_eval=False, register_builtins=False)
    lua.globals().source_for = lambda name: modules[name.lower()]
    lua.execute("""
        CAPTURE_MESSAGES = {}; CAPTURE_ENUMS = {}
        local constructors = {
          Descriptor=function() return {} end,
          FieldDescriptor=function() return {} end,
          EnumDescriptor=function()
            local d={}; table.insert(CAPTURE_ENUMS,d); return d
          end,
          EnumValueDescriptor=function() return {} end,
          Message=function(d)
            CAPTURE_MESSAGES[d.full_name]=d; return {DESCRIPTOR=d}
          end
        }
        local cache = {['protobuf.protobuf']=constructors}
        io, os, package, debug, python, dofile, loadfile = nil,nil,nil,nil,nil,nil,nil
        function module(name)
          local key=string.lower(name)
          local environment=cache[key] or {}
          cache[key]=environment
          setmetatable(environment,{__index=_G})
          setfenv(2,environment)
        end
        function require(name)
          local key=string.lower(name)
          if cache[key] ~= nil then return cache[key] end
          local chunk=assert(loadstring(source_for(name),name))
          local result=chunk()
          if result ~= nil then cache[key]=result end
          return cache[key]
        end
    """)
    for module in sorted(modules):
        lua.globals().require(module)
    # Represent client namespaces as descriptor containers so cross-namespace
    # references resolve in one atomic file without dependency ordering.
    descriptor = descriptor_pb2.FileDescriptorProto(name="majsoul.proto", syntax="proto2")
    nodes = {}

    def message_node(full_name):
        full_name = full_name.lstrip(".")
        if full_name not in nodes:
            parent, _, name = full_name.rpartition(".")
            collection = descriptor.message_type if not parent else message_node(parent).nested_type
            nodes[full_name] = collection.add(name=name)
        return nodes[full_name]

    messages = lua.globals().CAPTURE_MESSAGES
    if not list(messages.items()):
        raise ValueError("No Lua message descriptors found")
    for name, source in sorted(messages.items()):
        target = message_node(name)
        for _, field in sorted(source.fields.items(), key=lambda pair: pair[1].number):
            result = target.field.add(
                name=field.name,
                number=int(field.number),
                type=int(field.type),
                label=int(field.label),
            )
            if field.type in (11, 14):
                reference = field.message_type if field.type == 11 else field.enum_type
                result.type_name = "." + reference.full_name.lstrip(".")
            if field.label == 3 and field.type not in (9, 11, 12):
                result.options.packed = True
            if field.has_default_value and field.default_value is not None:
                if field.type == 8:
                    result.default_value = "true" if field.default_value else "false"
                elif field.type not in (11, 12, 14):
                    result.default_value = str(field.default_value)
    seen_enums = set()
    for _, source in sorted(
        lua.globals().CAPTURE_ENUMS.items(), key=lambda pair: pair[1].full_name or ""
    ):
        if not source.full_name or source.full_name in seen_enums:
            continue
        seen_enums.add(source.full_name)
        parent, _, name = source.full_name.lstrip(".").rpartition(".")
        collection = descriptor.enum_type if not parent else message_node(parent).enum_type
        target = collection.add(name=name)
        target.options.allow_alias = True
        for _, value in sorted(source["values"].items(), key=lambda pair: pair[1].number):
            target.value.add(name=value.name, number=int(value.number))
    return descriptor.SerializeToString()


def update_resources(
    output: Path,
    cache: Path,
    *,
    base_url: str = DEFAULT_BASE_URL,
    offline: bool = False,
    include_cosmetics: bool = False,
) -> dict:
    import UnityPy

    UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.62f2"
    base_url = normalize_base_url(base_url)
    # Isolate caches across regions and custom origins.
    cache = cache / hashlib.sha256(base_url.encode()).hexdigest()[:16]
    hashes = {}

    def download(name: str, *, refresh: bool = False) -> Path:
        if (
            not name.endswith(".majset")
            or name in (".", "..")
            or any(c in name for c in "/\\:\x00\r\n")
            or Path(name).name != name
        ):
            raise ValueError(f"Invalid bundle name: {name}")
        destination = cache / name
        if offline:
            if not destination.is_file():
                raise FileNotFoundError(f"Offline bundle missing: {destination}")
        elif refresh or not destination.exists():
            logger.info("Downloading %s", name)
            request = Request(base_url + quote(name), headers={"Cache-Control": "no-cache"})
            with urlopen(request, timeout=60) as response:
                atomic_write(destination, response.read())
        hashes[name] = hashlib.sha256(destination.read_bytes()).hexdigest()
        return destination

    index = download(INDEX, refresh=True)
    trees = [
        obj.read_typetree()
        for obj in UnityPy.load(str(index)).objects
        if obj.type.name == "MonoBehaviour"
    ]
    candidates = [tree for tree in trees if "assetInfos" in tree and "bundleInfos" in tree]
    if len(candidates) != 1:
        raise ValueError("Expected one resource index")
    tree = candidates[0]
    wanted = {}
    for asset in tree["assetInfos"]:
        path = asset["assetPath"].lower()
        if (
            path == CONFIG
            or MODULE.fullmatch(path)
            or include_cosmetics
            and CFG_PATTERN.fullmatch(path)
        ):
            wanted[path] = tree["bundleInfos"][asset["ownerBundleIndex"]]["name"]
    if CONFIG not in wanted or not any(MODULE.fullmatch(path) for path in wanted):
        raise ValueError("Resource index is missing protocol assets")
    modules, cfg_modules, config, extracted = {}, {}, None, set()
    for bundle in sorted(set(wanted.values())):
        for path, pointer in UnityPy.load(str(download(bundle))).container.items():
            path = path.lower()
            if path not in wanted or wanted[path] != bundle:
                continue
            raw = pointer.read().m_Script
            if isinstance(raw, str):
                raw = raw.encode("utf-8", "surrogateescape")
            if path == CONFIG:
                config = json.loads(raw)
            else:
                if not raw.lstrip().startswith((b"local ", b"--", b"module", b"require")):
                    raw = bytes(value ^ XOR_KEY[i % len(XOR_KEY)] for i, value in enumerate(raw))
                if MODULE.fullmatch(path):
                    module = "protol." + path.rsplit("/", 1)[1].removesuffix(".lua.bytes")
                    modules[module] = raw.decode("utf-8")
                else:
                    module = path.removeprefix("luabyte/lua/").removesuffix(".lua.bytes")
                    cfg_modules[module.replace("/", ".")] = raw.decode("utf-8")
            extracted.add(path)
    if extracted != set(wanted) or not config or "service" not in config:
        raise ValueError("Protocol extraction is incomplete")
    descriptor = export_descriptor(modules)
    schema = Schema(descriptor, config["service"])
    document = {
        "format": 1,
        "base_url": base_url,
        "bundle_sha256": hashes,
        "descriptor": base64.b64encode(descriptor).decode(),
        "service": config["service"],
        "generated_at": datetime.now(UTC).isoformat(),
        "resource_version": hashes[INDEX],
    }
    if include_cosmetics:
        document["cosmetics"] = export_cosmetics(cfg_modules)
    # Validate before replacing the last usable resource file.
    if not schema.methods:
        raise ValueError("Protocol has no service methods")
    atomic_write(output, (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode())
    return {"modules": len(modules), "methods": len(schema.methods), "output": str(output)}
