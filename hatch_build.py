"""Compile gettext catalogs for wheels and editable installs."""

from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class TranslationBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        if self.target_name != "wheel":
            return
        directory = Path(self.root) / "src/majsoul_hook/locale"
        for source in sorted(directory.glob("*/LC_MESSAGES/messages.po")):
            with source.open("rb") as stream:
                catalog = read_po(stream)
            errors = list(catalog.check())
            if catalog.fuzzy or errors or any(not item.string or item.fuzzy for item in catalog):
                raise ValueError(f"Incomplete or invalid translation catalog: {source}: {errors}")
            with source.with_suffix(".mo").open("wb") as stream:
                write_mo(stream, catalog)
        build_data["artifacts"].append("src/majsoul_hook/locale/**/*.mo")
