# Validation status

Passing synthetic checks does not establish support for every client platform, region, transport, or game screen.

## Automated coverage

Tests cover protocol parsing, fixture-based resource extraction, passthrough, cosmetics, rollback, and runtime cleanup. Loopback WebSockets exercise actual proxy forwarding and client-only injection. GUI checks cover communication, filters, selection/details, DPI, bounds, and constrained layouts.

DPI transitions at 125%, 150%, and 200% are simulated. Native Windows rendering has also been checked at 200%. A simulated 1366×728 work area preserves the inspector, fixed action filters, and scrollable setup access. Negative-coordinate work-area constraints are tested without requiring a second display.

Actual movement between mixed-DPI monitors is not covered. Ordinary pytest runs report Tk/display initialization failures as skips. The isolated GUI runner used by desktop CI rejects skips; see [development](development.md#setup-and-checks).

## Real Windows observations: 2026-10-24

- Native `Jantama_MahjongSoul` login, lobby queries, and heartbeats decoded successfully.
- Observed lobby flows used `scheme=http`, `client_tls=False`, and `server_tls=False`. Plaintext WebSockets needed no CA. This does not establish other connections' transport or certificate-verification behavior.
- The GUI backend checked the remote index and generated protocol/cosmetic resources. An unused test process selector reached local-capture readiness and stopped with exit code zero; the worker exited. This did not capture the game.
- Native window rendering verified complete work-area bounds and constrained layouts. Socket tests verified synthetic cosmetic edits/injections.

## Packaging observations: 2026-10-25

- Python 3.14 Windows onedir relocation, GUI startup/shutdown, worker JSONL transport, and offline extraction of 466 protocol methods passed locally.
- The SVG-derived icon passed the same Windows frozen checks. Wheels include the generated PNG; source distributions retain only the SVG. The renderer is build-only and absent from the frozen package.
- Installed Windows storage was exercised using the installer marker in a temporary copy; settings stayed outside the program directory.
- The Windows EXE installer compiled successfully with Inno Setup 7.1.0, including the desktop-shortcut option selected by default. Actual installation, upgrade, and uninstallation have not been tested.
- Python wheel/source archives were built and inspected for translations, packaging sources, and exclusion of local runtime data. Actionlint validated the GitHub workflow.
- [GitHub Actions run 40188124106](https://github.com/anosora233/majsoul-hook-mitm/actions/runs/40188124106) passed on Windows x64, macOS x64/ARM64, and Linux x64/ARM64. Each desktop target passed 120 core tests, 18 isolated GUI checks, and frozen startup/worker smoke checks. Both Docker builds passed diagnostics; Python distributions and all platform packages were uploaded.
- macOS ad-hoc signature structure passed `codesign --verify --deep --strict`. Developer ID signing/notarization, actual Windows installer lifecycle, frozen-package live interception, and real-resource extraction outside Windows remain unverified. The new release-assembly and draft-creation jobs still need their first CI run. See [packaging](packaging.md).

## Pending user-assisted validation

- Real cosmetic screens: inventories, character/skin/title/loading selection, named common views, hidden/sorted characters, persistence.
- Room updates, random pools, repeated match-start notices, complete disconnection/reconnect, emoji seat mapping.
- Full games, action streams, restored `syncGame` / `enterGame` data, lobby return, and replays.
- Real GUI start/stop/restart while reconnecting; mixed-DPI monitor movement.
- Verified WSS with explicitly configured client trust, if that transport needs testing.

Record results without identifying payloads. Turn defects into minimal synthetic regressions. Never change a recognized local request to failure passthrough as a workaround.
