# LoiLoNote CLI

[LoiLoNote School](https://loilonote.app) の Web UI を Playwright で自動操作するコマンドラインツールです。

人間ユーザーと AI エージェントの両方を想定しています。デフォルトの出力は機械可読な JSON です。

## 特徴

- **セッション管理** — 一度ログインすれば再利用可能
- **コース発見** — すべてのコースと URL を一覧表示
- **ノート管理** — ノートの一覧表示と内容取得
- **資料検索** — 資料箱を名前で再帰検索
- **提出** — 提出箱の一覧表示とファイルアップロード
- **メッセージング** — 個人へのファイル送信
- **AI ファースト** — デフォルトは JSON 出力、`--human` で読みやすい出力
- **キャッシュ** — コース URL をキャッシュして高速再利用
- **自動アップロード** — フォルダ監視による自動ファイルアップロード（`loilonote_auto_upload.py`）

## インストール

### 前提条件

- Python 3.9+
- Playwright + Chromium

### インストール手順

```bash
# リポジトリをクローン
git clone https://github.com/kunetinun/loilonote-cli.git
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
loilonote materials-search "古文単語"

# 検索して最初の一致を開く
loilonote materials-search "古文単語" --open

# 資料の内容を取得
loilonote materials-get "古典文法　２学期小テスト計画"

# フォルダ内の資料一覧
loilonote materials --path "学内共有/81期　国語科/１年次"

# 資料ツリーを再帰的に一覧
loilonote materials-tree --depth 3

# コース内のノート一覧
loilonote notes "https://loilonote.app/_/12345?tab=standardNoteList"

# コース横断でノート検索
loilonote notes-search "単語"

# ノート/ページを読む
loilonote note "https://loilonote.app/_/12345?tab=standardNoteList"

# 提出箱一覧
loilonote submissions "https://loilonote.app/_/12345?tab=submissionBox"

# 提出箱へファイルをアップロード
loilonote submit "file.pdf" "https://loilonote.app/_/12345?tab=submissionBox"

# 資料箱へファイルをアップロード
loilonote materials-upload "file.pdf" --path "マイフォルダ/同期用"

# 直接フォルダURL指定（高速）
loilonote materials-upload "file.pdf" --folder-url "https://loilonote.app/_/material-box/287069612"

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
| `--dump` | コマンド実行後にページの HTML + スクリーンショットを保存（デフォルト: 無効） |

### JSON 出力（デフォルト）

すべてのコマンドはデフォルトで JSON を出力します:

```json
{"ok": true, "count": 5, "items": ["..."]}
```

読みやすい出力には `--human` を使用してください。

## 自動アップロード（Auto-Upload Watcher）

フォルダを監視し、ファイルが追加されるたびに自動でロイロノート資料箱にアップロードする監視スクリプトです。

### セットアップ

```bash
# 監視フォルダを作成
mkdir ~/Desktop/loilonote-upload

# 監視を開始（Windows: auto_upload.bat をダブルクリック）
python -X utf8 loilonote_auto_upload.py

# 1回だけチェックして終了
python -X utf8 loilonote_auto_upload.py --once
```

### 動作

1. 監視フォルダ（デフォルト: `~/Desktop/loilonote-upload`）にファイルが追加される
2. ファイルの書き込みが完了するまで待機（安定性チェック）
3. 3ステップAPIで資料箱にアップロード
4. 成功 → `uploaded/` フォルダに移動
5. 失敗 → `failed/` フォルダに移動

### オプション

| オプション | 説明 |
|---|---|
| `--watch-dir PATH` | 監視フォルダを指定（デフォルト: `~/Desktop/loilonote-upload`） |
| `--folder-id ID` | アップロード先フォルダID（デフォルト: `287069612`） |
| `--folder-url URL` | アップロード先フォルダURL（auth_token取得用） |
| `--material-path PATH` | 表示用パス名（デフォルト: `マイフォルダ/同期用`） |
| `--loilonote-dir DIR` | loilonote-cli のディレクトリ |
| `--once` | 1回だけチェックして終了 |
| `--interval N` | 監視間隔（秒、デフォルト: 2） |
| `--dump` | デバッグ: API応答を詳細ログに出力 |

### 除外ファイル

以下のファイルは自動的にアップロード対象外です:

- ドットファイル（`.hidden` など）
- 一時ファイル（`.tmp`, `.part`, `.crdownload` など）
- スクリプトファイル（`.bat`, `.cmd`, `.ps1`, `.py` など）
- `desktop.ini`, `Thumbs.db`
- `uploaded/` / `failed/` サブフォルダ内のファイル

### 注意事項

- 初回実行時にPlaywrightでauth_tokenを取得します（ブラウザが一瞬開きます）
- auth_tokenは `.auth_token.json` にキャッシュされます
- loilonote-cli の `state.json`（Playwrightセッション）が必要です
- 画像ファイル（`.png`, `.jpg` など）は自動でサイズ情報を取得し、正しいメタデータでアップロードされます

---

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
- **自動アップロード**: 3ステップAPIを使用。LoiLoNoteの内部APIに依存するため、UI変更で動作しなくなる可能性があります

## 開発

```bash
# 開発用依存関係をインストール
pip install -e ".[dev]"

# テスト実行
pytest

# Lint
ruff check .
```

## 免責事項

- 本ツールは **非公式** です。株式会社 LoiLo とは一切関係ありません。
- ロイロノート・スクールの利用規約（10.3「提供コンテンツの利用」、10.7「提供コンテンツの利用範囲」、12.1「妨害行為」等）に抵触する可能性があります。**利用は自己責任**で行ってください。
- 本ツールは Playwright による自動操作を行います。過度なアクセスはサービスの運営を妨げる可能性があり、アカウント停止・BAN のリスクがあります。
- 学校・教育委員会が管理するアカウントでは、自動化ツールの利用が禁止されている場合があります。
- 本ツールの使用により生じたいかなる損害・不利益についても、作者は責任を負いません。
- ロイロノートの UI 変更により動作しなくなる可能性があります。

## ライセンス

MIT
```<|end|><|start|>tool to=bash<|channel|>analysis <|constrain|>xml<|message|><rfl:parameter name="command">
cd "C:\Users\omaeu\OneDrive\ドキュメント\loilonote-cli"
git add README.md
git commit -m "Update README: add auto-upload section and feature list"
git push origin master 2>&1 | Select-Object -Last 5