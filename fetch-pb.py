"""For fetching the protobuf code of the `mhm.proto` module."""

import argparse
import importlib
import os
import random
import subprocess
import sys
from pathlib import Path

import httpx


def response(url: str):
    resp = httpx.get(url)
    resp.raise_for_status()
    return resp


def generate_sheets_proto(config_table):
    proto_content = 'syntax = "proto3";\n\n'
    for schema in config_table.schemas:
        for sheet in schema.sheets:
            class_words = f"{schema.name}_{sheet.name}".split("_")
            class_name = "".join(name.capitalize() for name in class_words)
            proto_content += f"message {class_name} {{\n"
            for field in sheet.fields:
                proto_content += f'  {"repeated" if field.array_length > 0 else ""} {field.pb_type} {field.field_name} = {field.pb_index};\n'  # noqa: E501
            proto_content += "}\n\n"
    return proto_content


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="https://game.maj-soul.com/1")
    parser.add_argument("--root", type=str, default="./mhm/proto")
    parser.add_argument("--skip-clean", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--parse-path", type=str, default="parse.py")
    parser.add_argument("--protoc-path", type=str, default="protoc")
    args = parser.parse_args()

    host = args.host
    root = Path(args.root)
    parse = Path(args.parse_path)
    protoc = Path(args.protoc_path)
    doclean = not args.skip_clean
    dobuild = not args.skip_build

    def generate_pb2_py(proto: Path):
        if dobuild:
            os.system(f"{protoc} --python_out=. {proto}")

    def server_version():
        rand_a: int = random.randint(0, int(1e9))
        rand_b: int = random.randint(0, int(1e9))
        url = f"{host}/version.json?randv={rand_a}{rand_b}"
        return response(url).json().get("version")

    def query_prefix(path: str):
        return resdict["res"][path]["prefix"]

    version = server_version()
    resdict = response(f"{host}/resversion{version}.json").json()

    def build_config():
        path = "res/proto/config.proto"
        pre = query_prefix(path)
        url = f"{host}/{pre}/{path}"
        resp = response(url)
        print("config prefix:", pre)

        proto = root / "config.proto"
        with proto.open("wb") as f:
            f.write(resp.content)
        generate_pb2_py(proto)

    def fetch_lqcbin():
        path = "res/config/lqc.lqbin"
        pre = query_prefix(path)
        url = f"{host}/{pre}/{path}"
        resp = response(url)
        print("lqcbin prefix:", pre)
        return resp.content

    build_config()

    config_pb2 = importlib.import_module("mhm.proto.config_pb2")
    config_table = config_pb2.ConfigTables()
    config_table.ParseFromString(fetch_lqcbin())

    def build_sheets():
        proto = root / "sheets.proto"
        with proto.open("w") as f:
            f.write(generate_sheets_proto(config_table))
        generate_pb2_py(proto)

    def build_riichi():
        path = "res/proto/liqi.json"
        pre = query_prefix(path)
        url = f"{host}/{pre}/{path}"
        resp = response(url)
        print("riichi prefix:", pre)

        proto = root / "liqi.proto"
        with proto.open("w") as f:
            proc = subprocess.Popen(
                [sys.executable, parse],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
            buf, _ = proc.communicate(input=resp.content)
            text = buf.decode().replace(
                "uint32 robot_count = 4;",
                "optional uint32 robot_count = 4;",
            )  # HACK: Fixed an issue where room robots could not be removed
            f.write(text)
        generate_pb2_py(proto)

    build_sheets()
    build_riichi()

    if doclean:
        for file in root.rglob("*.proto"):
            file.unlink()
