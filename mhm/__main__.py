from .common import start_inject, start_proxy
from .config import config, load_resource
from .hook import Hook
from .resource import ResourceManager
from .tui import app


# TODO: Plugins should be independent of this project and should be loaded from a folder
def create_hooks(resger: ResourceManager) -> list[Hook]:
    hooks = []
    if config.base.aider:
        from .hook.aider import DerHook

        hooks.append(DerHook())
    if config.base.chest:
        from .hook.chest import EstHook

        hooks.append(EstHook(resger))
    if config.base.skins:
        from .hook.skins import KinHook

        hooks.append(KinHook(resger))
    return hooks


def main():
    app.add_note(f"Debug: {config.base.debug}")
    app.add_note("Load Resource")
    app.add_note("[magenta]Fetch LQC.LQBIN")
    qbin_version, resger = load_resource()
    app.add_note(f"LQBin Version: [cyan3]{qbin_version}")
    app.add_note(f"> {len(resger.item_rows):0>3} items")
    app.add_note(f"> {len(resger.title_rows):0>3} titles")
    app.add_note(f"> {len(resger.character_rows):0>3} characters")

    app.add_note("Init Hooks")
    hooks = create_hooks(resger)
    for h in hooks:
        app.add_note(f"> [cyan3]{h.__class__.__name__}")

    if config.mitmdump.args:
        app.run_worker(start_proxy([h.run for h in hooks]))
        app.add_note(f"[i]Start mitmdump @ {config.mitmdump.args.get('mode')}")
    if config.proxinject.path:
        app.run_worker(start_inject())
        app.add_note(f"[i]Start proxinject @ {config.proxinject.args.get('set-proxy')}")
