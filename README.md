# majsoul-hook-mitm

**English** | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

Capture Mahjong Soul WebSocket traffic with Python and mitmproxy local mode. Decode requests, responses, notifications, and nested game actions. The Tkinter inspector shows received, modified, intercepted, and injected content. Capture is read-only by default; local cosmetic overrides are optional.

## Quick start

Install [uv](https://docs.astral.sh/uv/), then run from the repository root:

```powershell
uv sync --locked
uv run --locked majsoul-hook gui
```

uv manages Python 3.12 and `.venv`; no manual activation is needed. The GUI requires Python with working standard-library Tkinter support. The separate Windows GUI entry point is `uv run --locked majsoul-hook-gui`.

1. On first use, click **Update resources** to generate protocol and cosmetic data.
2. Enter the game's process name or PID; the default is `Jantama_MahjongSoul`.
3. Leave **Local cosmetics** unchecked for read-only inspection, or enable it for appearance overrides.
4. Click **Start capture**, then reconnect/restart the game so new connections enter capture. Click **Stop capture** when finished.

Windows local capture may request elevation for mitmproxy's redirection component. It needs neither Proxinject nor manual SOCKS/HTTP proxy settings. Other platforms depend on [mitmproxy local-capture support](https://docs.mitmproxy.org/stable/concepts/modes/#local-capture).

## Inspect messages

Fixed checkboxes select multiple actions: **Pass**, **Modified**, **Intercepted**, **Injected**, and **Error**. All start selected; clearing all hides every row without deleting history. Search and action filters stay visible while setup controls scroll.

Select a row for **Overview**, **Before**, **Actual content**, and **Wire bytes** (complete Base64 frames). An intercepted request and its local responses/notifications have separate rows. Error rows retain whether the original was forwarded or blocked. **Copy details** copies the selected record.

History retains the latest 2,000 records and approximately 64 MiB by serialized size; a single oversized message stays inspectable. Older queued display events are discarded and counted if the UI falls behind; forwarding continues. GUI details are not automatically written to disk. Full payloads and copied records may contain account information or tokens.

Windows HiDPI support scales fonts, rows, columns, and spacing, constrains the full window to the monitor work area, and keeps setup controls scrollable on small screens. Keyboard focus scrolls into view. Actual movement between mixed-DPI monitors still needs validation.

## Resources

**Check version** compares local/remote index SHA-256 fingerprints and shows generation time/configuration counts. An index change does not imply every protocol or table changed. **Update resources** validates and atomically replaces the snapshot, including cosmetic data. Resource tasks and capture are mutually exclusive.

```powershell
uv run --locked majsoul-hook resources
uv run --locked majsoul-hook resources --cosmetics
uv run --locked majsoul-hook resources --offline --cosmetics
```

The default origin is `https://game.maj-soul.com/assetbundles/DXT/`. Use `--base-url` for another trusted HTTPS origin. Output is `data/protocol.json`; `.cache/bundles/` is isolated by origin. Offline rebuilding requires that origin's cached bundles.

Following `majsoul-mirage`, the pipeline locates Unity bundles through `bundle_info_so.majset`, decodes Lua protocol/configuration assets, and builds dynamic protobuf descriptors and optional cosmetic tables. It uses Python without JS/TS, Node.js, or protoc. Builds execute trusted client Lua; this is not a hostile-resource sandbox. Capture never executes Lua or downloads resources.

## CLI capture

```powershell
uv run --locked majsoul-hook capture --process Jantama_MahjongSoul
uv run --locked majsoul-hook capture --process 1234 --output captures/session.jsonl
uv run --locked majsoul-hook capture --process chrome --host maj-soul.com --verbose
uv run --locked majsoul-hook capture --process Jantama_MahjongSoul --cosmetics
```

`--process` selects one name or PID. Browsers may use a separate network process. Repeat `--host` to filter decoding/output by suffix; it does **not** narrow interception scope. Native game connections may use IP addresses.

Plaintext `ws://` needs no CA. Intercepting certificate-verified `wss://` generally requires client trust in mitmproxy's CA; the program does not install it or change trust automatically. Logs show scheme, port, and both TLS flags. See [certificate documentation](https://docs.mitmproxy.org/stable/concepts/certificates/).

Capture uses isolated options and an explicit addon set, ignoring user YAML/external scripts and excluding generic modification/replay/redirect addons. Upstream TLS verification stays enabled. `--confdir` changes only the certificate directory, whose default is `~/.mitmproxy/`.

Console output is summary-only by default. `--verbose` and `--output` expose full original decoded payloads. CLI JSONL actions are `pass`, `modified`, `local`, `error_blocked`, and `error_passthrough`; the GUI separates intercepted requests from injected messages. Unknown schemas retain Base64; unmatched responses are `orphan_response`. Field names, bytes, and 64-bit integers follow protobuf JSON conventions.

## Local cosmetics

Prepare resources with `--cosmetics` or the GUI updater, enable cosmetic mode, reconnect, and use the game's existing controls:

- Local character/skin/title/emoji inventories, bond/ending display, and cosmetic-item completion preserving existing quantities.
- Character/skin/title/loading selection, sorting/hiding, and ten named common-view presets with active-preset state.
- The current user's appearance in rooms, authentication, account data, and replays; other players' bond display.
- Local random pools consistent across games/reconnects, and local emoji echoes using the authenticated seat.

Settings are account-scoped in `data/cosmetics-state.json`, without login tokens; change the CLI path with `--state`. Use one capture process per state file. Changes do not grant server-side ownership or alter what other players see.

Recognized local requests remain blocked on failure and receive an error response when possible. Ordinary failures pass the original message through. Patches preserve untouched unknown fields. Injection is client-only; there are no server-directed synthetic requests or automatic game actions.

## Development and status

```powershell
uv run --locked pytest
uv run --locked ruff check src tests
uv run --locked ruff format --check src tests
```

See [architecture](docs/architecture.md), [development](docs/development.md), [validation](docs/validation.md), [roadmap](docs/roadmap.md), and [contributor instructions](AGENTS.md). Code, UI, and internal docs use English; READMEs are also available in Japanese and Simplified Chinese.

Synthetic tests cover loopback forwarding, editing/injection, resources, state, and GUI behavior. Native Windows lobby decoding has been observed; full games, reconnects, WSS, real cosmetic screens, and mixed-monitor DPI still need user-assisted validation.

Caches, generated resources, account state, captures, temporary files, and certificates/keys are ignored. The archived `majsoul-hook-mitm/` and reference `majsoul-mirage/` directories remain unchanged and untracked.

## License and attribution

[GPL-3.0-or-later](LICENSE). Framing/action XOR were informed by the archived original; Unity discovery, Lua extraction, and cosmetic behavior were informed by `majsoul-mirage`, reorganized here as a Python implementation.
