# Validation status

Passing synthetic checks does not establish support for every client platform, region, transport, or game screen.

## Automated coverage

Tests cover protocol parsing, fixture-based resource extraction, passthrough, cosmetics, rollback, and runtime cleanup. Loopback WebSockets exercise actual proxy forwarding and client-only injection. GUI checks cover communication, filters, selection/details, DPI, bounds, and constrained layouts.

DPI transitions at 125%, 150%, and 200% are simulated. Native Windows rendering has also been checked at 200%. A simulated 1366×728 work area preserves the inspector, fixed action filters, and scrollable setup access. Negative-coordinate work-area constraints are tested without requiring a second display.

Actual movement between mixed-DPI monitors is not covered. Tk/display initialization failures are reported as skips and require a separate rerun.

## Real Windows observations: 2026-10-24

- Native `Jantama_MahjongSoul` login, lobby queries, and heartbeats decoded successfully.
- Observed lobby flows used `scheme=http`, `client_tls=False`, and `server_tls=False`. Plaintext WebSockets needed no CA. This does not establish other connections' transport or certificate-verification behavior.
- The GUI backend checked the remote index and generated protocol/cosmetic resources. An unused test process selector reached local-capture readiness and stopped with exit code zero; the worker exited. This did not capture the game.
- Native window rendering verified complete work-area bounds and constrained layouts. Socket tests verified synthetic cosmetic edits/injections.

## Pending user-assisted validation

- Real cosmetic screens: inventories, character/skin/title/loading selection, named common views, hidden/sorted characters, persistence.
- Room updates, random pools, repeated match-start notices, complete disconnection/reconnect, emoji seat mapping.
- Full games, action streams, restored `syncGame` / `enterGame` data, lobby return, and replays.
- Real GUI start/stop/restart while reconnecting; mixed-DPI monitor movement.
- Verified WSS with explicitly configured client trust, if that transport needs testing.

Record results without identifying payloads. Turn defects into minimal synthetic regressions. Never change a recognized local request to failure passthrough as a workaround.
