# LoiLoNote CLI

[LoiLoNote School](https://loilonote.app) の Web UI を Playwright で自動操作するコマンドラインツールです。

人間ユーザーと AI エージェントの両方を想定しています。デフォルトの出力は機械可読な JSON です。

## 特徴

- 🔐 **セッション管理** — 一度ログインすれば再利用可能
- 📚 **コース発見** — すべてのコースと URL を一覧表示
- 📝 **ノート管理** — ノートの一覧表示と内容取得
- 📁 **資料検索** — 資料箱を名前で再帰検索
- 📤 **提出** — 提出箱の一覧表示とファイルアップロード
- 📨 **メッセージング** — 個人へのファイル送信
- 🤖 **AI ファースト** — デフォルトは JSON 出力、`--human` で読みやすい出力
- 🔄 **キャッシュ** — コース URL をキャッシュして高速再利用

## インストール

### 前提条件

- Python 3.9+
- Playwright + Chromium

### インストール手順

```bash
# リポジトリをクローン
git clone https://github.com/richi/loilonote-cli.git
cd loilonote-cli

# 依存関係をインストール
pip install -e .

# Playwright のブラウザをインストール
playwright install chromium
```

### Windows での注意点

Playwright は名前付きパイプを使用するため、サンドボックス環境ではブロックされる場合があります。
必要に応じてフルアクセス権で実行してください。

## 使い方

### 初回セットアップ

```bash
# ログイン（ブラウザが開くので手動でログイン）
loilonote login

# セッション確認
loilonote status
```

### コマンド一覧

```bash
# 環境チェック
loilonote doctor

# コース一覧（初回以降はキャッシュ）
loilonote courses
loilonote courses --refresh

# 資料検索（UI 検索を使用、高速）
loilonote materials-search "キーワード"

# 検索して最初の一致を開く
loilonote materials-search "キーワード" --open

# 資料の内容を取得
loilonote materials-get "資料名"

# フォルダ内の資料一覧
loilonote materials --path "フォルダ/サブフォルダ"

# 資料ツリーを再帰的に一覧
loilonote materials-tree --depth 3

# コース内のノート一覧
loilonote notes "https://loilonote.app/_/12345?tab=standardNoteList"

# コース横断でノート検索
loilonote notes-search "キーワード"

# ノート/ページを読む
loilonote note "https://loilonote.app/_/12345?tab=standardNoteList"

# 提出箱一覧
loilonote submissions "https://loilonote.app/_/12345?tab=submissionBox"

# 提出箱へファイルをアップロード
loilonote submit "file.pdf" "https://loilonote.app/_/12345?tab=submissionBox"

# 個人へファイル送信
loilonote send "file.pdf" "https://loilonote.app/_/12345?tab=submissionBox" --to "相手名"

# ノートを作成
loilonote create-note "タイトル" "https://loilonote.app/_/12345?tab=standardNoteList"

# ページの HTML + スクリーンショットを保存
loilonote dump "https://loilonote.app/_/12345?tab=standardNoteList"
```

### オプション

| オプション | 説明 |
|---|---|
| `--headed` | ブラウザウィンドウを表示 |
| `--slow N` | スローモーション（ミリ秒） |
| `--human` | 人間可読な出力 |
| `--timeout N` | ナビゲーションのタイムアウト（ミリ秒） |
| `--version` | バージョン表示 |

### JSON 出力（デフォルト）

すべてのコマンドはデフォルトで JSON を出力します:

```json
{"ok": true, "count": 5, "items": ["..."]}
```

読みやすい出力には `--human` を使用してください。

## アーキテクチャ

```
loilonote_cli/
├── __init__.py
├── browser.py      # Playwright ブラウザ管理
├── cli.py          # Click CLI コマンド
└── selectors.py    # DOM セレクタ（UI 変更時に更新）
```

## 既知の制限

- **UI スクレイピング**: 公式 API はありません。LoiLoNote のアップデートでセレクタが壊れる可能性があります。
- **PDF 抽出**: ブラウザのテキストレイヤーを使用。一部の PDF は文字化けする場合があります。
- **ヘッドレス検出**: ヘッドレスモードでは LoiLoNote が「ブラウザ非対応」警告を表示する場合があります（init スクリプトで対応済み）。
- **サンドボックス環境**: Playwright は名前付きパイプを必要とします。権限の昇格が必要な場合があります。

## 開発

```bash
# 開発用依存関係をインストール
pip install -e ".[dev]"

# テスト実行
pytest

# Lint
ruff check .
```

## ライセンス

MIT
```