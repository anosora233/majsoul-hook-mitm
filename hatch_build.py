"""Generate GUI assets for wheels and editable installs."""

from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po
from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from resvg_py import svg_to_bytes


class AssetBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        if self.target_name != "wheel":
            return
        assets = Path(self.root) / "src/majsoul_hook/assets"
        # Tk and PyInstaller consume PNG; SVG is the only tracked design source.
        (assets / "icon.png").write_bytes(
            svg_to_bytes(svg_path=str(assets / "icon.svg"), width=1024, skip_system_fonts=True)
        )
        build_data["artifacts"].append("src/majsoul_hook/assets/icon.png")
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
