# Packaging

Native packages use Python 3.14 and PyInstaller **onedir**. The GUI and console worker share native dependencies. Build each target on its own operating system and architecture; PyInstaller does not cross-compile these packages.

The package build hook generates translations and renders `src/majsoul_hook/assets/icon.svg` to a 1024px PNG during `uv sync` or wheel creation. PyInstaller consumes those generated assets without a second compilation step. The renderer and Babel are build/development dependencies; generated PNG/MO files are ignored and excluded from source distributions. SVG and PO changes invalidate uv's editable-build cache.

## Formats and CI targets

| Target | Artifacts | GitHub runner |
| --- | --- | --- |
| Windows x64 | Portable `.zip`, per-user `installer.exe` | `windows-2025` |
| macOS ARM64 | `Majsoul Hook.app` in `.tar.gz` | `macos-15` |
| macOS Intel | `Majsoul Hook.app` in `.tar.gz` | `macos-15-intel` |
| Linux x64 | Portable folder in `.tar.gz` | `ubuntu-24.04`, Debian 12 build container |
| Linux ARM64 | Portable folder in `.tar.gz` | `ubuntu-24.04-arm`, Debian 12 build container |
| Python | `.whl` and source `.tar.gz` | Ubuntu |
| Docker, Linux x64/ARM64 | Multi-platform versioned image in GHCR on version-tag pushes | Native Ubuntu runners |

The [Build packages workflow](../.github/workflows/build.yml) runs manually through **Actions → Build packages → Run workflow**, or automatically for `v*` tags. Builds reject a tag that differs from the version in `pyproject.toml`. Each desktop/Python job uploads an artifact named `packages-<target>`, with SHA-256 checksums. Python packages use `SHA256SUMS`. Docker builds run diagnostics on both architectures. Manual runs do not push images; version-tag pushes publish verified images to GHCR. The workflow does not upload to PyPI or submit to Microsoft Store.

Desktop CI checks Ruff, core tests, and every GUI test in a separate interpreter. Linux GUI tests and frozen smoke checks run under Xvfb. Build logs are uploaded even when a build fails. Linux packages are built against Debian 12's glibc baseline, not musl/Alpine. Kernel requirements for local capture are separate from the packaging baseline.

## Prepare a release

The `release-assets` job waits for all build jobs, verifies the eight desktop/Python packages against their checksums, and collects them with individual `.sha256` files and one combined `SHA256SUMS`. Only named public packages are copied; build reports and logs remain in Actions artifacts. Manual runs exercise this assembly without creating a Release. Docker images are distributed through GHCR rather than Release attachments.

For a new version, update `pyproject.toml`, run `uv lock`, and add English notes at `release/notes/v<VERSION>.md`. Commit and push the changes, then complete a manual build before pushing an annotated tag matching the project version:

```text
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

A successful tag-triggered build publishes the versioned GHCR manifest, then creates a **draft** GitHub Release and uploads the verified assets. Only the draft job receives `contents: write`. Rerunning it may refresh the draft; it refuses to change an already published Release. Container images are available before the draft is publicly published. Inspect the downloads and notes before manually publishing the draft. No tag or Release is created by the local preparation script.

## Build locally

Use a fresh output directory if an existing bundle contains local data. Existing macOS app bundles also require a fresh output directory. From the repository root on the desired native platform:

```text
uv sync --locked --group build
uv run --locked --group build python release/build.py
```

The Windows EXE installer requires Inno Setup 6.3+ or 7. CI installs the compiler automatically. Its local path may be supplied through `ISCC`.

```powershell
uv run --locked --group build python release/build.py --installer
```

Add `--resource-cache .cache/bundles` to rebuild real cached protocol/cosmetic resources during the smoke check without network access. Add `--output dist/local-build` to choose another output directory.

Outputs include the platform archive, `smoke.json`, `size.json`, and SHA-256 files. PyInstaller and installer logs are under `build/<target>/`. Build output is ignored by Git. Neither archives nor installers include local resource caches, settings, captures, interception certificates, or private keys. Certifi's public CA bundle remains included for upstream TLS verification.

## Running packages and storing data

Windows and Linux portable folders contain `majsoul-hook[-gui]` (with `.exe` on Windows) and `_internal/`. Keep the complete folder. On Linux, start `./majsoul-hook-gui` or use the console command. The macOS `.app` opens the GUI and keeps the console worker in `Contents/MacOS/majsoul-hook`.

| Distribution | Default mutable-data root |
| --- | --- |
| Windows/Linux portable folder | Beside the executables |
| Windows EXE installer | `%LOCALAPPDATA%/majsoul-hook` |
| macOS `.app` | `~/Library/Application Support/majsoul-hook` |
| Source install | Current working directory |

Under that root, `data/` holds generated resources, settings, and cosmetic state; `.cache/bundles/` holds downloads; frozen builds use `.mitmproxy/` for interception certificates. Source runs normally retain mitmproxy's default CA directory. `MAJSOUL_HOOK_HOME` overrides the mutable-data root and CA location for either source or frozen runs. Explicit relative CLI paths still use the current working directory.

The installed Windows marker `installed.json` is added only to installer payloads. It is not added to portable ZIPs. App resources and translations stay inside the bundle while settings remain outside installed application directories. Rebuilding or uninstalling program files does not intentionally delete user data.

## Signatures and platform requirements

The EXE installer is a per-user Inno Setup installer. Its desktop-shortcut checkbox is selected by default. It does not automatically install interception certificates or delete account settings. Signing is optional for this classic EXE installer; unsigned downloads may still trigger Windows reputation prompts. No signing certificate or trust change is generated automatically.

macOS builds use PyInstaller's default ad-hoc signing unless `MAJSOUL_CODESIGN_IDENTITY` supplies an available signing identity. CI currently does not import Developer ID credentials or notarize apps. Successful compilation is not a Gatekeeper/notarization check. Upstream macOS redirector resources are bundled unchanged; elevated capture still needs native-platform validation.

[mitmproxy local capture](https://docs.mitmproxy.org/stable/concepts/modes/#local-capture) supports Windows, macOS, and Linux, with platform-specific privileges. Linux officially requires kernel 6.8+ and privileged eBPF setup; process-name matching uses the first 16 characters. A desktop package building successfully does not establish support for all kernel, client, or transport combinations.

## Python and Docker packages

The proposed [central HTTP/SOCKS5 proxy server](roadmap.md#4-central-proxy-server-deferred) is deferred. The current Docker image does not implement that server mode; its present uses are resource preparation and diagnostics.

Build Python distributions with `uv build`. Install the wheel using uv/pip in a Python 3.14+ environment. It is a Python package, not a self-contained desktop bundle; native dependency compatibility still depends on the installation platform.

The Dockerfile builds a CLI-only image as a non-root user. It includes no GUI display server. For a local build:

```text
docker build -t majsoul-hook:local .
docker run --rm majsoul-hook:local doctor
```

Container builds use the same `build.yml` trigger as desktop packages. Each native Docker job builds once and runs diagnostics. Only version-tag pushes log in with the repository's `GITHUB_TOKEN` and push architecture images. After all builds and release-asset checks pass, a manifest joins their recorded digests under one version tag. There is no `latest` alias. Only Docker publishing jobs receive `packages: write`; no personal token is normally required.

For example, after publishing a `v0.1.1` tag that includes this workflow:

```text
docker pull ghcr.io/anosora233/majsoul-hook-mitm:0.1.1
docker run --rm ghcr.io/anosora233/majsoul-hook-mitm:0.1.1 doctor
```

Existing tags retain their original workflow; new version tags must include this configuration to publish images. Initially created GHCR packages are private by default; change the package visibility to Public once if anonymous pulls are wanted. Source labels link the image to this repository.

Container defaults use `/workspace`; mount a writable volume there to retain generated resources. Host-process local capture is not configured or tested by the image: host kernel, namespace, and privilege requirements remain the operator's responsibility. No privileged container is started by CI.

## Validation and size

Frozen smoke checks relocate the bundle into a path containing spaces and non-ASCII characters, launch from another working directory, check native helpers and TLS CA data, exercise worker JSONL errors, and open/close the GUI through its `--smoke-test` entry point on every platform. With a resource cache, they also extract resources and reopen the GUI with the generated schema. These checks never activate local interception or change trust.

The spec excludes mitmproxy's alternate interfaces, setuptools, and optional Pillow codecs. Separate GUI/console analyses keep worker dependencies out of the GUI Python archive. The console's superset `base_library.zip` is shared. UPX and binary stripping are disabled, and Python assertions/docstrings remain intact. `size.json` records component and archive sizes.

See [validation](validation.md) for completed local checks and pending native-platform tests.

### Size measurements

The Windows x64 build with the SVG-derived icon measured on 2026-10-25 occupies approximately 70.0 MiB unpacked and 34.6 MiB as a portable ZIP. These are build-specific measurements, not size limits. Cryptography is the largest individual third-party native component (9.44 MiB), followed by mitmproxy_rs (8.34 MiB). Python's OpenSSL DLLs add 7.22 MiB, and Tcl/Tk adds about 5.35 MiB. The console EXE also contains compressed dependency bytecode; its size is not the size of application code alone.

Earlier builds using the same source and locked dependency versions produced:

| Python distribution | Unpacked MiB | Portable ZIP MiB |
| --- | ---: | ---: |
| 3.12.14 | 74.63 | 34.12 |
| 3.14.7 | 71.13 | 35.56 |
| 3.15.1 | 73.42 | 36.51 |

Python 3.14 reduced unpacked size but increased the download size in this comparison. Python 3.15 also required several source-built dependencies. These results compare complete runtime/dependency builds and do not isolate the interpreter's contribution. Temporary comparison environments and artifacts have been removed.

Compare complete distributions consistently: mitmproxy's onefile EXEs contain compressed dependencies that are extracted at startup, whereas this project's onedir folder already contains those files. Further savings would require reducing supported dependency imports, especially UnityPy's eager texture/Pillow imports; deleting required TLS or texture libraries would break supported paths.
