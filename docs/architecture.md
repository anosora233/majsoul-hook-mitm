# Architecture

## Entry points and data flow

`majsoul-hook` dispatches CLI commands; `majsoul-hook-gui` starts Tkinter. `python -m majsoul_hook` uses the same CLI.

```text
Trusted client bundles -> resource extraction -> data/protocol.json
                                                     |
Selected local process -> mitmproxy -> per-flow decoder -> summary / inspector
                               |              |
                               |       optional cosmetic rules
                               |              |
                               +---- edited frames / local client responses
```

Resource files contain a format marker, source URL, bundle SHA-256 values, an index fingerprint, generation time, a serialized protobuf descriptor, RPC mappings, and optional cosmetic configuration. Capture loads this snapshot once; it does not download resources or execute Lua.

## Modules

| Module | Responsibility |
| --- | --- |
| `cli.py` | Arguments, process selection, and dispatch. |
| `resources.py` | HTTPS bundle discovery/cache, protocol Lua extraction, descriptors, and atomic output. |
| `cosmetic_resources.py` | ExcelTool/block-table loading and configuration projection. |
| `schema.py` | Independent descriptor pool, dynamic messages, and protobuf JSON conversion. |
| `wire.py` | Shared frame parsing/encoding and patches preserving untouched unknown fields. |
| `protocol.py` | Per-flow, bidirectional request correlation and nested action decoding. |
| `cosmetics.py` | Account settings, room/game state, local requests, overrides, and notifications. |
| `addon.py` | Mitmproxy hooks, effects, client injection, summaries, JSONL, and observer snapshots. |
| `runtime.py` | Isolated addon set, shutdown signals, stop events, and cleanup. |
| `gui.py` | Tk controls, fixed multi-action filters, selected-message inspection, and task state. |
| `gui_backend.py` | Bounded history/inbox, resource fingerprints, and subprocess transport. |
| `gui_worker.py` | Private JSONL task protocol; capture stays on the worker's main thread. |
| `gui_dpi.py` | Windows DPI awareness, scaling, and full-frame work-area constraints. |
| `gui_widgets.py` | Scrollable setup controls and keyboard-focus visibility. |

## Protocol and editing

Frame kind `1` denotes notifications, `2` requests, and `3` responses. Requests/responses carry a little-endian 16-bit ID before the protobuf Wrapper. Responses recover their method from the opposite direction's pending request. Requests expire after 120 seconds and are capped at 4,096 per connection. The default frame limit is 16 MiB.

Unknown message types retain Base64 payloads. Unmatched responses are `orphan_response`, expected when capture starts mid-connection. Nested action failures retain the original field and add a warning. The decoder never changes traffic.

Cosmetic mode handles supported Lobby configuration requests locally and overrides inventory/character/common-view data and the current user's room/game/replay appearance. Local emoji echoes use the authenticated seat. Random choices survive game authentication and reconnects; manual changes synchronize the active selection.

Editing patches only changed known fields. Repeated messages retain unknown fields by stable business identity, or by position when no identity exists. Encode responses/notifications before persisting settings. A failed local request remains blocked and gets an error response when possible; ordinary traffic falls back to passthrough. Injection is client-only and injected callbacks are ignored.

## Runtime and GUI lifecycle

The runtime explicitly registers forwarding, TLS, DNS, diagnostics, and capture. User YAML, external scripts, and generic replay/modification addons are excluded. Upstream TLS verification stays enabled.

The GUI starts one worker at a time. Stdout carries UTF-8 JSONL events; stderr carries diagnostics. The inbox preserves lifecycle ordering and discards older queued messages under load. History retains up to 2,000 records and approximately 64 MiB by serialized size; one oversized message remains inspectable. These limits apply to displayed history, not mitmproxy's own flow buffers.

An intercepted request and each successfully injected message have separate rows. Tabs show metadata, original/actual decoded content, and complete Base64 frames. Filters do not delete history. Details are not automatically written to disk.

Stop commands use stdin; EOF also stops capture if the GUI disappears. The worker disables interception and clears state before exiting. GUI closure requests graceful shutdown before terminating its own worker on timeout. The game process is never terminated.

## Local files

| Path | Contents | Tracked |
| --- | --- | --- |
| `pyproject.toml`, `uv.lock`, `.python-version` | Build, dependencies, Python version | Yes |
| `data/protocol.json` | Generated protocol/cosmetic snapshot | No |
| `data/cosmetics-state.json` | Account settings, without login tokens | No |
| `.cache/bundles/` | Download cache, isolated by origin | No |
| `captures/`, `*.jsonl` | Optional decoded traffic | No |
| `~/.mitmproxy/` or `--confdir` | Certificates and private keys | No |

Use only one cosmetic capture process per state file. Room/random game choices live in memory; saved preferences survive restarts.
