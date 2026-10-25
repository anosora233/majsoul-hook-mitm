# Native PyInstaller onedir bundle: two entry points share dependencies.
import os
import sys
import tomllib
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).parent
version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
datas = collect_data_files("majsoul_hook", includes=["locale/**/*.mo", "assets/*.png"])
datas += collect_data_files("mitmproxy", excludes=["tools/web/*", "test/*"])
datas += collect_data_files("UnityPy")
for distribution in ("mitmproxy", "mitmproxy-rs", "protobuf", "UnityPy", "lupa"):
    datas += copy_metadata(distribution)
binaries = []
if sys.platform == "win32":
    import mitmproxy_windows
    native = Path(mitmproxy_windows.__file__).parent
    datas += collect_data_files("mitmproxy_windows", includes=["*.sys", "LICENSE", "WINDIVERT_VERSION"])
    binaries += [(str(native / name), "mitmproxy_windows") for name in ("windows-redirector.exe", "WinDivert.dll")]
elif sys.platform == "linux":
    import mitmproxy_linux
    binaries += [(str(mitmproxy_linux.executable_path()), ".")]
elif sys.platform == "darwin":
    datas += collect_data_files("mitmproxy_macos")
    # Include public documentation before the app bundle is assembled and signed.
    datas += [(str(root / name), ".") for name in ("LICENSE", "README.md", "README.ja.md", "README.zh-CN.md")]
    datas += [(str(path), "docs") for path in (root / "docs").glob("*.md")]
    datas += [(os.environ["MAJSOUL_PYTHON_LICENSE"], "python-license")]
analysis = Analysis(
    [str(root / "release/entry.py")],
    pathex=[str(root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=["UnityPy.UnityPyBoost", "lupa.lua51"],
    hookspath=[str(root / "release/hooks")],
    excludes=[
        "pytest", "ruff", "babel", "IPython", "setuptools",
        # Like upstream's mitmdump build, omit mitmproxy's alternate frontends.
        "mitmproxy.tools.console", "mitmproxy.tools.web",
        # Unity text assets need neither image codecs nor font rendering.
        "PIL.AvifImagePlugin", "PIL._avif", "PIL.WebPImagePlugin", "PIL._webp",
        "PIL.ImageCms", "PIL._imagingcms", "PIL._imagingft",
    ],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
console = EXE(
    pyz, analysis.scripts, [], exclude_binaries=True, name="majsoul-hook",
    console=True, debug=False, strip=False, upx=False,
    codesign_identity=os.environ.get("MAJSOUL_CODESIGN_IDENTITY"),
    icon=str(root / "src/majsoul_hook/assets/icon.png") if sys.platform != "linux" else None,
    contents_directory="_internal",
)
gui_analysis = Analysis(
    [str(root / "release/gui_entry.py")],
    pathex=[str(root / "src")],
    excludes=["pytest", "ruff", "babel", "IPython", "setuptools"],
    noarchive=False,
)
worker_modules = {"majsoul_hook.cli", "majsoul_hook.resources", "majsoul_hook.runtime"}
if worker_modules.intersection(entry[0] for entry in gui_analysis.pure):
    raise ValueError("The GUI must not import console or worker implementation modules")
gui = EXE(
    PYZ(gui_analysis.pure), gui_analysis.scripts, [], exclude_binaries=True,
    name="majsoul-hook-gui", console=False, debug=False, strip=False, upx=False,
    codesign_identity=os.environ.get("MAJSOUL_CODESIGN_IDENTITY"),
    icon=str(root / "src/majsoul_hook/assets/icon.png") if sys.platform != "linux" else None,
    contents_directory="_internal",
)
# The console also supports `gui`, so its base library is a superset of the GUI's.
# Keep that copy rather than replacing it with the smaller GUI bootstrap library.
gui_datas = [entry for entry in gui_analysis.datas if entry[0] != "base_library.zip"]
bundle = COLLECT(
    console, gui, analysis.binaries, analysis.datas,
    gui_analysis.binaries, gui_datas, strip=False, upx=False, name="majsoul-hook",
)
if sys.platform == "darwin":
    app = BUNDLE(
        gui, bundle.toc, name="Majsoul Hook.app", icon=str(root / "src/majsoul_hook/assets/icon.png"),
        bundle_identifier="io.github.majsoul-hook.inspector",
        version=version,
        info_plist={"CFBundleDisplayName": "Majsoul Hook", "NSHighResolutionCapable": True},
    )
