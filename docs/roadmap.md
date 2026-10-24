# Roadmap

## Current scope

Python-only local capture, dynamic protobuf, optional Mirage-compatible cosmetics, client-only injection, resource maintenance, and Tkinter inspection are implemented. Read-only remains the default. See [architecture](architecture.md) and [validation](validation.md).

## 1. Real client behavior

Complete the pending [validation scenarios](validation.md), prioritizing cosmetic screens, rooms, full games, reconnects, and GUI start/stop. Record platform/transport and reproduce defects with synthetic fixtures.

Acceptance: game controls retain consistent local settings, local requests stay off the server, reconnects keep the intended choice, and temporary interception exits cleanly.

## 2. Diagnostics

- Unify lifecycle/connection summaries; include host, port, scheme, and both TLS flags in structured output.
- Reduce routine connection/ping/pong noise while preserving errors and an explicit diagnostic mode.
- Add counters/reasons for unknown schemas, orphan responses, malformed frames, and nested-action failures.

Acceptance: readiness, transport, and parsing failures are recognizable without repetitive low-level logs. Output failures never affect forwarding.

## 3. Reproducibility

- Offline replay of synthetic or reviewed anonymized binary samples through the existing decoder.
- Report descriptor/method counts and mappings whose message types are absent from public resources.
- Extend checks for deterministic resource content, interruption recovery, and corrupt/missing caches.
- Locked-uv Windows/Linux CI for tests and Ruff, without elevated interception.

Acceptance: a clean checkout installs and runs synthetic tests without the game, reference repositories, downloaded resources, or Node.js.

## Out of scope

Generic external business plugins, server-directed request injection, automatic game actions, and release packaging are not planned for the initial version.
