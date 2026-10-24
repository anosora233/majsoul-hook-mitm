# Usage

Run commands from the repository root. Relative resource and state paths use the working directory. uv manages Python 3.12 and the project environment.

## GUI

```powershell
uv sync --locked
uv run --locked majsoul-hook gui
```

The GUI requires working standard-library Tkinter support. Windows also has the `uv run --locked majsoul-hook-gui` entry point. Local capture may request administrator permission. Other platforms depend on [mitmproxy local-capture support](https://docs.mitmproxy.org/stable/concepts/modes/#local-capture).

Update resources on first use, choose the game's process name or PID, start capture, and reconnect the game. The default selector is `Jantama_MahjongSoul`; a browser may use a separate network process. Local cosmetics start enabled in the GUI. Uncheck the option for read-only inspection.

The Language selector offers English, Japanese, Simplified Chinese, and System default. Automatic mode detects the system UI language at startup, falling back to English for unsupported languages. Manual choices are remembered in `data/gui-settings.json`. Switching languages preserves capture, history, and selection; protocol data and raw diagnostics retain their original text.

## Inspect messages

Search matches raw values and displayed text. Action checkboxes select Pass, Modified, Intercepted, Injected, and Error; clearing all hides rows without deleting history. Select a row for Overview, Before, Actual content, and complete Base64 Wire bytes. Intercepted requests and injected responses/notifications have separate rows. Copy details copies the selected record.

History retains the latest 2,000 records and approximately 64 MiB by serialized size; one oversized message remains inspectable. Older queued display events are discarded and counted if the UI falls behind. Details are not automatically saved. Full payloads, exports, and copied records may contain account information or tokens.

Windows HiDPI support scales fonts and layout, constrains the complete window to its monitor work area, and keeps setup controls scrollable on small screens. See [validation status](validation.md) for tested and pending scenarios.

## Resources

Check version compares local and remote index fingerprints and shows generation time and configuration counts. An index change does not imply that every protocol or table changed. Update resources builds and validates the snapshot, including cosmetic data. Resource tasks and capture cannot run simultaneously.

```powershell
uv run --locked majsoul-hook resources
uv run --locked majsoul-hook resources --cosmetics
uv run --locked majsoul-hook resources --offline --cosmetics
```

Output defaults to `data/protocol.json`. Bundle caches under `.cache/bundles/` are isolated by origin. Offline rebuilding requires the same origin's cached bundles. The default origin is `https://game.maj-soul.com/assetbundles/DXT/`; `--base-url` selects another trusted HTTPS origin. Builds execute trusted client Lua; this is not a hostile-resource sandbox. Capture never executes Lua or downloads resources.

## CLI capture

```powershell
uv run --locked majsoul-hook capture --process Jantama_MahjongSoul
uv run --locked majsoul-hook capture --process Jantama_MahjongSoul --cosmetics
uv run --locked majsoul-hook capture --process 1234 --output captures/session.jsonl
uv run --locked majsoul-hook capture --process chrome --host maj-soul.com --verbose
uv run --locked majsoul-hook capture --help
```

CLI capture is read-only unless `--cosmetics` is provided. `--process` selects one name or PID. Repeat `--host` to filter decoding/output by domain suffix; it does not narrow interception scope. Native clients may connect directly to IP addresses. Stop CLI capture with Ctrl+C.

Console output contains summaries by default. `--verbose` and `--output` include full original decoded payloads. CLI JSONL actions are `pass`, `modified`, `local`, `error_blocked`, and `error_passthrough`. Unknown schemas retain Base64; unmatched responses are `orphan_response`. Field names, bytes, and 64-bit integers follow protobuf JSON conventions.

Plaintext `ws://` needs no CA. Intercepting certificate-verified `wss://` generally requires the client to trust mitmproxy's CA. The program does not install CAs or change trust automatically. Logs show scheme, port, and both TLS flags. `--confdir` selects a certificate directory, defaulting to `~/.mitmproxy/`, without loading user YAML. See [mitmproxy's certificate documentation](https://docs.mitmproxy.org/stable/concepts/certificates/).

## Local cosmetics

Prepare cosmetic resources, enable cosmetic mode, reconnect, and use the game's existing controls. Supported behavior includes local character/skin/title/emoji inventories, bond and ending display, character sorting/hiding, loading images, ten named common-view presets, random character pools, and local emoji echoes. Appearance overrides cover the current user's room, account, game authentication, and replay data. Changes do not grant server-side ownership or alter what other players see.

Account preferences live in `data/cosmetics-state.json`, without login tokens. CLI `--state` changes that path. Use one cosmetic capture process per state file. Injection is client-only; there are no server-directed synthetic requests or automatic game actions. See [architecture](architecture.md) for protocol, rollback, and forwarding behavior.
