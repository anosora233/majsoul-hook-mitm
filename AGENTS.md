# Contributor instructions

## Scope

- This repository contains the rebuilt Python package `majsoul_hook`.
- `archive/majsoul-hook-mitm/` and `archive/majsoul-mirage/` are ignored, read-only reference checkouts. Never edit, format, stage, or vendor them.
- Use Python only. Do not add JavaScript, TypeScript, Node.js, generated protocol modules, or a protoc requirement. Embedded Lua belongs only to explicit resource extraction.
- Use English for code, comments, source UI strings, commit messages, and documentation. The Japanese and Chinese READMEs and GUI translation catalog are exceptions. Synthetic Unicode test data is permitted.
- CLI capture is read-only unless `--cosmetics` is provided. The GUI defaults its local cosmetics checkbox to enabled; users may uncheck it for read-only capture. Do not add automatic game actions or server-directed synthetic requests.

## Environment

Use uv with `pyproject.toml`, `uv.lock`, and `.python-version`. Do not add a second dependency list or require manual environment activation.

```powershell
uv sync --locked
uv run --locked majsoul-hook gui
uv run --locked majsoul-hook resources --cosmetics
uv run --locked majsoul-hook resources --offline --cosmetics
uv run --locked majsoul-hook capture --process Jantama_MahjongSoul
uv run --locked pytest
uv run --locked ruff check src tests
uv run --locked ruff format --check src tests
```

Development uses Python 3.14. After dependency changes, run `uv lock` and include the lockfile. If Windows restricts caches, use project-local `UV_CACHE_DIR` and a fresh pytest `--basetemp` under `.cache/`. Never commit machine-specific runtime paths.

## Implementation invariants

- Read-only capture must not change bytes, drop/injected flags, or message lists. Cosmetics may use only built-in rules and client-directed injection.
- Recognized local requests fail closed on parse, encode, or persistence failure. Ordinary failures pass the original through. Encode all effects before saving; roll back business state on failure. Never process injected messages again.
- Construct isolated mitmproxy Options/Master objects. Do not use user YAML, `tools.main.run`, `default_addons`, external scripts, or generic modification/replay/redirect addons. `--confdir` selects certificates only. Keep upstream TLS verification enabled.
- Request correlation is per connection and direction, bounded by capacity/timeout, and released on disconnect. Distinguish unknown schemas, orphan responses, and malformed frames; retain raw nested payloads on failure.
- Use current descriptors, original protobuf field names, protobuf JSON conventions, and patches that retain untouched unknown fields.
- Validate resource extraction/descriptors before atomically replacing usable output. Preserve offline rebuilds. Lua accepts trusted client resources only, is not a hostile-code sandbox, and never runs during capture.
- Tk widgets belong to the main thread; capture/download/extraction belongs to the worker. Capture and resource tasks are mutually exclusive. Closing requests graceful shutdown before terminating its own worker on timeout.
- Bound GUI history/inbox memory. Observers must not affect forwarding. Separate intercepted and injected rows and retain original/actual content and wire bytes. Keep action checkboxes outside the scrollable setup area.
- Enable Windows DPI awareness before Tk. Update fonts/layout without rebuilding or losing selection. Constrain the complete native frame to the work area, including negative desktop coordinates, and reserve room for the inspector on small screens.
- Maintain GUI translations in `locale/*/LC_MESSAGES/messages.po` using the gettext workflow in `docs/localization.md`. Mark deferred labels with `N_`; keep English msgids and placeholders stable. Track PO/POT sources, never generated MO files. Babel is build/development tooling only.
- Track `assets/icon.svg` as the icon source. The package build hook generates the ignored PNG for Tk and native packaging; keep SVG rendering dependencies out of runtime imports and frozen bundles.
- Native builds use PyInstaller onedir with sibling GUI/console executables; macOS wraps these in an app bundle. Frozen workers launch the console binary, never `python -m`. Portable Windows/Linux data stays beside the binaries; installed Windows and macOS apps use user data directories. Never package local state, caches, captures, or keys; never overwrite a used bundle during rebuilding. See `docs/packaging.md`.
- Cross-platform packages are built natively by GitHub Actions. Windows distributes a portable ZIP and Inno Setup EXE installer. Keep macOS signing/notarization and live local-capture validation distinct from successful compilation. Docker CI must not start privileged containers or intercept host traffic. Manual builds only assemble verified assets; matching version-tag pushes may create draft Releases after all builds pass. Public publication remains manual. Do not publish releases, registries, PyPI, or Store submissions as part of a build-only task.
- Keep GUI imports independent of CLI, capture, and extraction implementations so its separately analyzed executable stays small. Shared defaults, validation, and atomic writes belong in `config.py`.
- Keep container builds in `build.yml`. Manual runs build/diagnose without pushing; matching version-tag pushes may push verified architecture images and publish a versioned GHCR manifest by digest after all builds and asset checks pass, before creating the Release draft. Scope package-write permission to Docker publishing jobs. Do not attach Docker exports to new Releases or add `latest` aliases.

## Validation and hygiene

- Run relevant regressions and Ruff for implementation changes. Use synthetic fixtures and loopback sockets; normal tests must not require the game, real credentials, live downloads, or elevated interception.
- Report GUI skips when Tk/display support is unavailable. Distinguish simulated DPI changes from actual mixed-monitor testing.
- Never stage environments, caches, bundles, generated resources, account state, captures, logs, temporary files, or certificate/private-key material. Inspect the staged manifest. Keep `uv.lock` tracked.
- Use the user-specified process/PID for live tests. `--host` filters decoding/output, not interception scope. Do not install CAs or alter trust automatically.
- WS needs no CA; verified WSS generally requires client trust in the interception CA. Check each flow's scheme and both TLS flags; decoding success or port numbers do not prove certificate behavior.
- Stop temporary capture workers/redirection when finished. Never terminate the user's game or unrelated sessions.

See [architecture](docs/architecture.md), [development](docs/development.md), [validation](docs/validation.md), and [roadmap](docs/roadmap.md).
