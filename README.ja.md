# majsoul-hook-mitm

[English](README.md) | **日本語** | [简体中文](README.zh-CN.md)

Python と mitmproxy の local mode で雀魂の WebSocket 通信をキャプチャし、リクエスト、レスポンス、通知、入れ子の対局アクションを解析します。Tkinter で受信内容、変更、ローカル処理、注入を確認できます。標準は読み取り専用で、ローカルの外観変更は任意です。

## クイックスタート

[uv](https://docs.astral.sh/uv/) をインストールし、リポジトリのルートで実行します。

```powershell
uv sync --locked
uv run --locked majsoul-hook gui
```

uv が Python 3.12 と `.venv` を管理するため、手動で仮想環境を有効にする必要はありません。GUI には正常な標準ライブラリの Tkinter 環境が必要です。Windows の独立した GUI エントリーポイントは `uv run --locked majsoul-hook-gui` です。

1. 初回は **Update resources** でプロトコルと外観設定のデータを生成します。
2. プロセス名または PID を入力します。標準は `Jantama_MahjongSoul` です。
3. 読み取り専用なら **Local cosmetics** をオフにし、外観変更を使う場合だけオンにします。
4. **Start capture** を押した後、ゲームを再接続・再起動して新しい接続を捕捉します。終了時は **Stop capture** を押します。

Windows では mitmproxy のリダイレクト用コンポーネントが管理者権限を要求する場合があります。Proxinject や手動の SOCKS/HTTP プロキシ設定は不要です。他の OS は [mitmproxy の local capture 対応状況](https://docs.mitmproxy.org/stable/concepts/modes/#local-capture)を参照してください。

## メッセージの確認

固定チェックボックスで **Pass**（透過）、**Modified**（変更）、**Intercepted**（ローカル処理のため遮断）、**Injected**（注入）、**Error**（エラー）を複数選択できます。初期状態は全選択です。すべて外しても一覧を隠すだけで、履歴は削除しません。検索とアクションのフィルターは設定欄をスクロールしても表示されます。

行を選択すると **Overview**、**Before**、**Actual content**、**Wire bytes**（完全なフレームの Base64）を確認できます。遮断したリクエストとローカルのレスポンス・通知は別々の行です。エラー行では元の通信が転送されたか遮断されたかも確認できます。**Copy details** で選択内容をコピーします。

履歴は直近 2,000 件、シリアライズ後のサイズで約 64 MiB まで保持し、単独の巨大なメッセージは完全な内容を残します。GUI が追いつかない場合は古い表示イベントを破棄して件数を表示しますが、転送は継続します。詳細は自動保存されません。ペイロードやコピー内容にはアカウント情報・トークンが含まれる場合があります。

Windows の HiDPI に合わせてフォント、行、列、余白を調整し、ウィンドウ全体を画面の作業領域内に収めます。小さい画面では設定欄がスクロールし、キーボードのフォーカスも自動で表示範囲に入ります。異なる倍率の実機モニター間での移動は未検証です。

## リソース

**Check version** はローカル・リモートのインデックスの SHA-256 を比較し、生成日時と設定件数を表示します。インデックスの変更は、すべてのプロトコルや表の変更を意味しません。**Update resources** は外観設定を含むデータを検証してからアトミックに置き換えます。キャプチャとリソース操作は同時に実行できません。

```powershell
uv run --locked majsoul-hook resources
uv run --locked majsoul-hook resources --cosmetics
uv run --locked majsoul-hook resources --offline --cosmetics
```

標準の配信元は `https://game.maj-soul.com/assetbundles/DXT/` です。別の信頼できる HTTPS 配信元は `--base-url` で指定します。生成先は `data/protocol.json`、配信元別のキャッシュは `.cache/bundles/` です。オフライン再生成には同じ配信元の bundle が必要です。

`majsoul-mirage` を参考に、`bundle_info_so.majset` から Unity bundle を特定し、Lua のプロトコル・設定を展開して動的 protobuf 記述子と任意の外観設定表を生成します。Python で実装し、JS/TS、Node.js、protoc は不要です。生成時は信頼するクライアントの Lua を実行します。悪意のあるリソース用のサンドボックスではありません。キャプチャ中は Lua の実行やダウンロードを行いません。

## CLI キャプチャ

```powershell
uv run --locked majsoul-hook capture --process Jantama_MahjongSoul
uv run --locked majsoul-hook capture --process 1234 --output captures/session.jsonl
uv run --locked majsoul-hook capture --process chrome --host maj-soul.com --verbose
uv run --locked majsoul-hook capture --process Jantama_MahjongSoul --cosmetics
```

`--process` は 1 つの名前または PID を選びます。ブラウザーでは通信専用プロセスを使う場合があります。`--host` は複数指定できますが、解析・出力だけを絞り込み、捕捉範囲は狭めません。ネイティブクライアントは IP アドレスで接続する場合があります。

平文の `ws://` に CA は不要です。証明書検証を行う `wss://` の復号には、通常クライアントが mitmproxy CA を信頼する必要があります。CA のインストールや信頼設定は自動変更しません。ログは scheme、ポート、両側の TLS 状態を記録します。[証明書の説明](https://docs.mitmproxy.org/stable/concepts/certificates/)も参照してください。

独立した設定と明示的な addon 集合を使い、ユーザーの YAML や外部スクリプトは読み込みません。上流の TLS 検証を維持し、汎用の変更・リプレイ・リダイレクト addon は含めません。`--confdir` は証明書ディレクトリだけを変更し、標準は `~/.mitmproxy/` です。

通常のコンソール出力は概要だけです。`--verbose` と `--output` は元の完全な解析済みペイロードを含みます。CLI JSONL のアクションは `pass`、`modified`、`local`、`error_blocked`、`error_passthrough` です。GUI は遮断したリクエストと注入を分けます。未知の型は Base64 を残し、対応リクエストがない応答は `orphan_response` です。フィールド名、bytes、64 ビット整数は protobuf JSON に従います。

## ローカルの外観変更

`--cosmetics` または GUI でリソースを準備し、外観変更を有効にして再接続した後、ゲーム本来の画面で操作します。

- キャラクター・スキン・称号・スタンプのローカル一覧、絆・エンディング表示、既存数量を保った装飾アイテム補完。
- キャラクター・スキン・称号・ロード画像の選択、並べ替え・非表示、名前と有効状態を含む 10 組の装飾プリセット。
- ルーム、対局認証、アカウント情報、牌譜内の本人の外観、および他プレイヤーの絆表示。
- 対局・再接続で一貫したランダム候補と、認証済みの席に基づくローカルのスタンプ表示。

設定はログイントークンを含めず、アカウントごとに `data/cosmetics-state.json` へ保存します。CLI の `--state` で変更できます。1 つの状態ファイルを複数のキャプチャで同時使用しないでください。サーバー上の所有権や他プレイヤーに見える外観は変更しません。

認識済みのローカルリクエストは失敗時も転送せず、可能ならエラーレスポンスを返します。通常の通信は失敗すると元の内容を透過します。編集では変更しない未知の protobuf フィールドを保持します。注入先はクライアントのみで、サーバー向けの合成リクエストや自動ゲーム操作はありません。

## 開発と検証状況

```powershell
uv run --locked pytest
uv run --locked ruff check src tests
uv run --locked ruff format --check src tests
```

英語の[構成](docs/architecture.md)、[開発](docs/development.md)、[検証状況](docs/validation.md)、[ロードマップ](docs/roadmap.md)、[協力者向け指示](AGENTS.md)を参照してください。コード、GUI、内部文書は英語です。

合成テストではループバック転送、変更・注入、リソース、状態、GUI を確認します。Windows ネイティブクライアントのロビー解析は確認済みですが、完全な対局、再接続、WSS、実際の外観画面、異なる DPI のモニター間移動は実機検証が必要です。

キャッシュ、生成リソース、アカウント設定、キャプチャ、一時ファイル、証明書・秘密鍵は Git の対象外です。`majsoul-hook-mitm/` と `majsoul-mirage/` は変更せず、追跡対象に含めません。

## ライセンスと参考実装

[GPL-3.0-or-later](LICENSE)。フレーム構造とアクション XOR は旧プロジェクト、Unity 探索、Lua 抽出、外観変更の挙動は `majsoul-mirage` を参考に、Python の構成として実装し直しています。
