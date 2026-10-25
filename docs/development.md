# Development

## Setup and checks

Use uv from the repository root. Development Python is pinned to 3.14; uv manages the environment. Runtime-only installations may use `uv sync --locked --no-dev`.

```powershell
uv sync --locked
uv run --locked pytest
uv run --locked ruff check src tests release hatch_build.py
uv run --locked ruff format --check src tests release hatch_build.py
```

Apply formatting with `uv run --locked ruff format src tests release hatch_build.py`. Update dependencies with uv and commit `uv.lock`; do not add a second dependency list or machine-specific interpreter paths.

The protobuf runtime requires version 7.36.2 or later within major version 7. Wire patches use the modern descriptor API; older runtimes are unsupported. The lockfile pins the tested release.

Tkinter requires a Python distribution with working Tk support. CLI capture does not import the GUI. Without Tk/display support, GUI tests report skips; other tests still run.

See [GUI localization](localization.md) for gettext catalogs, Babel commands, and translation maintenance. Babel is development/build tooling; the application uses standard-library gettext at runtime.

See [packaging](packaging.md) for native builds and GitHub Actions. Use `uv run --locked python release/test_gui.py` to isolate each GUI regression in its own interpreter. This runner rejects skips and requires working Tk/display support; on Linux, run it under Xvfb or a desktop session.

For restricted Windows cache paths:

```powershell
$env:UV_CACHE_DIR = "$PWD/.cache/uv"
uv run --locked pytest --basetemp .cache/pytest-local-run
```

Use a fresh `--basetemp` path each run. Some Windows Tk installations intermittently fail initialization when creating several interpreters in one process. Report skips and rerun affected cases separately; a skip is not validation.

## Tests

Fixtures build synthetic protobuf descriptors in Python. Tests require neither reference checkout, generated client resources, real accounts, nor live downloads. Resource tests replace bundle/HTTP access; runtime tests use loopback WebSockets rather than elevated interception.

- Protocol: correlation, ID reuse/expiry, malformed frames, unknown schemas, nested actions.
- Wire/business: unknown fields, local responses, room sequences, query correlation, rollback, account isolation, random choices, reconnect state.
- Loopback: real forwarding and client-only injection ordering; local requests never reach upstream.
- GUI: task controls, snapshots, filter combinations, bounded history, worker failure, broken-pipe cleanup during startup/shutdown, DPI, window bounds, and small-viewport controls.
- Localization: system UI language detection, saved overrides, translation placeholders, and live switching during capture. Protocol data and raw diagnostics retain their original text.

Keep real traffic, tokens, account IDs, downloaded assets, and keys out of fixtures. Synthetic Unicode data is appropriate for testing UTF-8 transport.

## Resource maintenance

See [resource commands](usage.md#resources) for online and offline rebuilding. Validate extraction/descriptors before replacing output. Resource tests must cover extraction failures and preserve usable output. Lua accepts trusted client resources only and is not a hostile-code sandbox.

## Commit hygiene

Inspect `git status --short`, `git diff --cached --stat`, `git diff --cached --check`, and the full staged file list. Track source, synthetic tests, docs, license, build configuration, and the lockfile. Ignore environments, resources/state, downloads, captures, logs, temporary files, credentials, and certificate/key material.

Do not edit or stage the ignored `archive/majsoul-hook-mitm/` and `archive/majsoul-mirage/` reference checkouts. Do not force-add ignored runtime files.
