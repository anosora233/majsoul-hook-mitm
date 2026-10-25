# Roadmap

## Current scope

Python-only local capture, dynamic protobuf, optional Mirage-compatible cosmetics, client-only injection, resource maintenance, and Tkinter inspection are implemented. CLI capture defaults to read-only; GUI cosmetics are enabled by default. Native packaging and GitHub build workflows are prepared; see [packaging](packaging.md) and [validation](validation.md).

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
- Exercise the new release-assembly and draft workflow after the successful native build run; keep synthetic CI checks independent of elevated interception.

Acceptance: a clean checkout installs and runs synthetic tests without the game, reference repositories, downloaded resources, or Node.js.

## 4. Central proxy server (deferred)

Status: design proposal only. Implement after current desktop behavior and native packages have been validated. The current program does not expose an HTTP/SOCKS5 server command.

The proposed client/server deployment routes multiple clients through a central service:

```text
Game clients -> HTTP/SOCKS5 proxy server -> Game servers
               decode, modify, forward
```

The server would reuse mitmproxy's regular HTTP and SOCKS5 modes, the existing WebSocket decoder, and the built-in cosmetic rules. It would run from the CLI and fit a non-root Docker deployment with ordinary TCP listeners. This mode would not use local capture, host interception drivers, or eBPF.

### Initial scope

- Add a separate server command with explicit listener addresses/ports, proxy authentication, and destination restrictions. Existing `--host` only filters inspection; it is not a forwarding access-control list.
- Reuse a validated resource snapshot per server instance. Clients must use a compatible protocol snapshot in the initial version.
- Keep request correlation and runtime session state isolated per connection. Namespace saved preferences by authenticated proxy user and game account. Account-only state and source IP alone are insufficient boundaries for shared NAT, multiple users, or concurrent sessions using the same account.
- Start with one server process and a single coordinated persistence owner. Bound connections and buffers, clean up disconnected sessions, and prevent one client's failures from affecting another.
- Preserve existing byte-preservation, rollback, fail-closed local-request handling, and client-directed injection rules. Server mode must not introduce automatic game actions or synthetic requests to game servers.
- Persist resources, preferences, and interception CA material outside the image. HTTPS/WSS inspection requires explicit client trust in the proxy CA; plaintext WS does not. Keep upstream TLS verification enabled and do not install client trust automatically.

### Client routing and rollout

First verify whether the actual game client follows application/system proxy settings. Where it does not, use an existing process-level forwarding tool to reach the central proxy. A custom local forwarding agent, remote inspector GUI, management API, and multi-process/high-availability deployment are separate later projects.

Implement the listener and read-only forwarding first, then authentication and isolation, then enable the existing cosmetic business and container deployment. Merely changing the mitmproxy mode is a small change; reliable multi-client operation is a medium-sized extension. A self-developed traffic-forwarding client would add substantial platform-specific work.

Acceptance: concurrent clients with overlapping request IDs remain isolated; preferences do not cross proxy-user boundaries; reconnects and same-account sessions have defined behavior; authentication and destination restrictions apply to both proxy modes; WS/WSS, certificate trust, disconnect cleanup, and persistence failures have synthetic and native-client coverage. The Docker server must start without privileged mode or host-process access.

## Out of scope

Generic external business plugins, server-directed request injection, and automatic game actions remain outside the planned scope.
