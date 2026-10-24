# 🀄 majsoul-hook-mitm

[English](README.md) | **日本語** | [简体中文](README.zh-CN.md)

雀魂の通信を確認し、ローカルの外観をカスタマイズするツールです。

<p>
  <a href="https://www.python.org/"><img src="https://raw.githubusercontent.com/tandpfun/skill-icons/main/icons/Python-Dark.svg" width="32" height="32" alt="Python"></a>
  <a href="https://docs.astral.sh/uv/"><img src="https://raw.githubusercontent.com/astral-sh/uv/main/docs/assets/logo-letter.svg" width="32" height="32" alt="uv"></a>
  <a href="https://mitmproxy.org/"><img src="https://www.mitmproxy.org/logo-navbar.png" height="32" alt="mitmproxy"></a>
</p>

## ✨ 主な機能

- WebSocket メッセージの詳細確認、検索・処理別フィルター、変更前後の比較。
- ゲーム内の操作でキャラクター、衣装、称号、スタンプをローカルに変更。
- 英語・日本語・簡体字中国語の GUI、システム言語の自動検出、HiDPI 対応。

## 🚀 クイックスタート

[uv](https://docs.astral.sh/uv/getting-started/installation/) をインストールし、リポジトリのルートで実行します。

```powershell
uv sync --locked
uv run --locked majsoul-hook gui
```

Python 3.12 は uv が管理します。GUI には正常な Tkinter 環境が必要です。Windows のキャプチャでは管理者権限を求められる場合があります。

## 🎮 GUI の使い方

1. 初回は「リソース更新」をクリックします。
2. ゲームのプロセス名または PID を入力します。初期値は `Jantama_MahjongSoul` です。
3. 「キャプチャ開始」をクリックし、ゲームを再接続または再起動します。
4. メッセージを選択して内容を確認します。終了時は「キャプチャ停止」をクリックします。

「ローカル外観設定」は初期状態でオンです。読み取り専用にする場合はオフにしてください。外観の変更は自分のクライアントだけに反映されます。「言語」から表示言語を変更できます。

## 📚 ドキュメント（英語）

[CLI・使い方](docs/usage.md) · [開発](docs/development.md) · [翻訳](docs/localization.md) · [構成](docs/architecture.md) · [検証状況](docs/validation.md) · [ロードマップ](docs/roadmap.md)

## 📄 ライセンス・参考実装

[GPL-3.0-or-later](LICENSE)。`majsoul-hook-mitm` と `majsoul-mirage` を参考にしています。アイコン：[Skill Icons](https://github.com/tandpfun/skill-icons)、[uv](https://github.com/astral-sh/uv)、[mitmproxy](https://mitmproxy.org/)。
