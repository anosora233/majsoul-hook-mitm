tool = "mhmp"

excludes = [
    "mitmproxy.tools.web",
    "mitmproxy.tools.console",
]

a = Analysis(
    [tool],
    excludes=excludes,
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    upx=True,
    name=tool,
    console=True,
    icon="mhmp.ico",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    upx=True,
    name=tool,
)
