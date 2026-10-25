# 🀄 majsoul-hook-mitm

**English** | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

A Mahjong Soul traffic inspector with local cosmetic customization.

<p>
  <a href="https://www.python.org/"><img src="https://raw.githubusercontent.com/tandpfun/skill-icons/main/icons/Python-Dark.svg" width="32" height="32" alt="Python"></a>
  <a href="https://docs.astral.sh/uv/"><img src="https://raw.githubusercontent.com/astral-sh/uv/main/docs/assets/logo-letter.svg" width="32" height="32" alt="uv"></a>
  <a href="https://mitmproxy.org/"><img src="https://www.mitmproxy.org/logo-navbar.png" height="32" alt="mitmproxy"></a>
</p>

## ✨ Features

- Inspect WebSocket messages, search and filter actions, and compare original and actual content.
- Customize local characters, skins, titles, and emoji through the game’s existing controls.
- English, Japanese, and Simplified Chinese GUI with automatic language detection and HiDPI support.

## 🚀 Quick start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from the repository root:

```powershell
uv sync --locked
uv run --locked majsoul-hook gui
```

Python 3.14 is managed by uv. The GUI needs working Tkinter support; Windows capture may request administrator permission.

## 🎮 Use the GUI

1. Click **Update resources** on first use.
2. Enter the game’s process name or PID; the default is `Jantama_MahjongSoul`.
3. Click **Start capture**, then reconnect or restart the game.
4. Select a message to inspect its contents. Click **Stop capture** when finished.

**Local cosmetics** is enabled by default; uncheck it for read-only capture. Cosmetic changes are visible only locally. Change the interface language using **Language**.

## 📚 Documentation

[CLI and usage](docs/usage.md) · [Packages and CI](docs/packaging.md) · [Development](docs/development.md) · [Localization](docs/localization.md) · [Architecture](docs/architecture.md) · [Validation status](docs/validation.md) · [Roadmap](docs/roadmap.md)

## 📄 License & credits

[GPL-3.0-or-later](LICENSE). Inspired by `majsoul-hook-mitm` and `majsoul-mirage`. Icons: [Skill Icons](https://github.com/tandpfun/skill-icons), [uv](https://github.com/astral-sh/uv), and [mitmproxy](https://mitmproxy.org/).
