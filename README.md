# LoiLoNote CLI

LoiLoNote School（ロイロノート・スクール）の Web UI および内部 API を Playwright で自動操作するコマンドラインツールです。
人間によるターミナル操作と、AI エージェントからのプログラム呼び出しの双方を想定しており、デフォルトで機械可読な JSON を出力します。

---

## 主な特徴

- **セッション管理** — 一度手動でログインすればセッション（`state.json`）を保存・再利用可能
- **コース一覧・キャッシュ** — 所属コースと URL を一覧取得し、ローカルにキャッシュして高速再利用
- **ノート管理** — コース内のノート一覧取得、横断検索、本文テキストの抽出、内部構造解析、ZIP ダウンロード
- **資料検索・閲覧** — 資料箱のキーワード検索、テキスト抽出、フォルダ指定・ツリー構造の取得
- **提出・送信** — 提出箱一覧の取得、提出箱へのファイルアップロード、個人宛てファイル送信
- **資料箱アップロード** — コマンドによる単発アップロード、およびフォルダ監視による自動アップロード（`loilonote_auto_upload.py`）
- **AI ファースト設計** — デフォルトは JSON 出力（`--human` で人間向けの整形出力に切り替え可能）

---

## 前提条件・動作環境

- **OS:** Windows / macOS / Linux（クロスプラットフォーム対応）
- **Python:** 3.9 以上
- **ブラウザ:** Playwright + Chromium

### OS 別の起動方法

| OS | CLI 起動 | 自動アップロード起動 |
|---|---|---|
| Windows | `loilonote.bat` または `python loilonote.py` | `auto_upload.bat` のダブルクリック |
| macOS / Linux | `./loilonote.sh` または `python3 loilonote.py` | `./auto_upload.sh` |

---

## インストール

```bash
# リポジトリをクローン
git clone https://github.com/kunetinun/loilonote-cli.git
cd loilonote-cli

# 依存関係をインストール
pip install -e .

# Playwright 用の Chromium をインストール
playwright install chromium
```

### OS 別の注意点

**Windows:** Playwright は内部で名前付きパイプを使用するため、AI エージェント等の制限付きサンドボックス環境からは起動がブロックされる場合があります。エラーになる場合は、通常のターミナルや適切な権限下で実行してください。

**macOS / Linux:** `loilonote.sh` と `auto_upload.sh` に実行権限を付与してください:
```bash
chmod +x loilonote.sh auto_upload.sh
```

---

## 初回セットアップ

利用を開始する前に、一度ブラウザを開いて手動ログインし、セッション情報を保存する必要があります。

```bash
# 1. 環境チェック
loilonote doctor

# 2. ログイン（ブラウザが開くので手動でログインし、完了後にターミナルで Enter を押す）
loilonote login

# 3. セッションが有効か確認
loilonote status

# 4. コース一覧を取得してキャッシュに保存
loilonote courses
```

---

## コマンド一覧

### 基本・セッション確認

```bash
# 環境・依存パッケージのチェック
loilonote doctor

# ログインセッションの有効性確認
loilonote status

# コース一覧（初回取得後は ~/.loilonote/courses.json にキャッシュ）
loilonote courses
loilonote courses --refresh
```

### 資料箱（Materials）

```bash
# 資料箱をキーワード検索
loilonote materials-search "古文単語"

# 検索して最初の一致を開き、本文テキストを取得
loilonote materials-search "古文単語" --open

# 資料名を指定して開き、本文テキストを取得
loilonote materials-get "古典文法 ２学期小テスト計画"

# 指定パス内の資料・フォルダ一覧を取得
loilonote materials --path "学内共有/81期 国語科/１年次"

# 資料箱のフォルダ構造を再帰的にツリー表示
loilonote materials-tree --depth 3

# 資料箱へファイルをアップロード（パス指定）
loilonote materials-upload "file.pdf" --path "マイフォルダ/同期用"

# 資料箱へファイルをアップロード（フォルダ URL 直接指定・高速）
loilonote materials-upload "file.pdf" --folder-url "https://loilonote.app/_/material-box/287069612"
```

### ノート・提出箱・送信

```bash
# コース内のノート一覧を取得
loilonote notes "https://loilonote.app/_/12345?tab=standardNoteList"

# キャッシュ済みコースを横断してノートタイトルを検索
loilonote notes-search "単語"

# ノート・ページのテキストを取得
loilonote note "https://loilonote.app/_/12345?tab=standardNoteList"

# ノート ID を指定してテキストを抽出（ZIP 内部を解析）
loilonote note-text 1458859786

# ノート ID を指定して内部構造を解析（カード・ガジェット・フレーム）
loilonote note-inspect 1458859786

# ノートを ZIP ファイルとしてダウンロード
loilonote note-download 1458859786
loilonote note-download 1458859786 -o ./my_note.zip

# 提出箱の一覧を取得
loilonote submissions "https://loilonote.app/_/12345?tab=submissionBox"

# 提出箱へファイルをアップロード
loilonote submit "file.pdf" "https://loilonote.app/_/12345?tab=submissionBox"

# 個人へファイルを送信
loilonote send "file.pdf" "https://loilonote.app/_/12345?tab=submissionBox" --to "相手名"

# 新規ノートを作成
loilonote create-note "タイトル" "https://loilonote.app/_/12345?tab=standardNoteList"

# デバッグ用：ページの HTML とスクリーンショットを保存
loilonote dump "https://loilonote.app/_/12345?tab=standardNoteList"
```

### グローバルオプション

すべてのサブコマンドの前に指定できます。

| オプション | 説明 |
|---|---|
| `--headed` | ヘッドレスではなくブラウザウィンドウを表示して実行 |
| `--slow N` | 操作ごとに N ミリ秒のスローモーション待機を挿入 |
| `--human` | JSON ではなく人間が読みやすい形式で出力 |
| `--timeout N` | ページ遷移のタイムアウト時間をミリ秒で指定（デフォルト: 60000） |
| `--dump` | コマンド実行後にページの HTML とスクリーンショットを保存（デフォルト: 無効） |
| `--version` | バージョン情報を表示 |

### 出力形式（デフォルト JSON）

すべてのコマンドはデフォルトで 1 行の JSON を標準出力に返します。

```json
{"ok": true, "count": 5, "items": ["..."]}
```

エラー時は `ok: false` と `error` メッセージを返します。

```json
{"ok": false, "error": "no session; run login first"}
```

---

## 自動アップロード（Auto-Upload Watcher）

指定したローカルフォルダを監視し、ファイルが追加されるたびに自動でロイロノートの資料箱へアップロードする常駐スクリプトです。単発のアップロードには `loilonote materials-upload`、フォルダ投入による自動同期には `loilonote_auto_upload.py` を使い分けます。

### セットアップ・起動

```bash
# 監視用フォルダを作成
mkdir ~/Desktop/loilonote-upload

# 監視を開始（Windows: auto_upload.bat / macOS・Linux: ./auto_upload.sh）
python -X utf8 loilonote_auto_upload.py

# 1回だけフォルダを確認して終了する場合
python -X utf8 loilonote_auto_upload.py --once
```

### 処理の流れ

1. 監視フォルダ（デフォルト: `~/Desktop/loilonote-upload`）へのファイル追加を検知する
2. ファイルの書き込み完了（ファイルサイズの安定）を待機する
3. ロイロノート内部のアップロード API（署名付き URL 取得 → ストレージ転送 → 登録完了の 3 ステップ）で資料箱へ送信する
4. 成功したファイルは `uploaded/` フォルダへ、失敗したファイルは `failed/` フォルダへ自動移動する

### オプション

| オプション | 説明 |
|---|---|
| `--watch-dir PATH` | 監視対象フォルダを指定（デフォルト: `~/Desktop/loilonote-upload`） |
| `--folder-id ID` | アップロード先フォルダ ID（デフォルト: `287069612`） |
| `--folder-url URL` | アップロード先フォルダ URL（auth_token 取得時に使用） |
| `--material-path PATH` | 表示・ログ用の資料箱パス名（デフォルト: `マイフォルダ/同期用`） |
| `--loilonote-dir DIR` | loilonote-cli のディレクトリパス |
| `--once` | 常駐せず 1 回だけチェックして終了 |
| `--interval N` | フォルダの監視間隔を秒単位で指定（デフォルト: 2） |
| `--dump` | デバッグ用に API 応答の詳細ログを出力 |

### 自動除外されるファイル

以下のファイル・フォルダは監視対象から自動的に除外されます。

- ドットから始まる隠しファイル（`.hidden` など）
- ダウンロード・編集中の一次ファイル（`.tmp`, `.part`, `.crdownload` など）
- スクリプトファイル（`.bat`, `.cmd`, `.ps1`, `.py` など）
- システムファイル（`desktop.ini`, `Thumbs.db`）
- `uploaded/` および `failed/` サブフォルダ内のファイル

### 自動アップロードの補足

- 初回実行時に Playwright 経由で auth_token を取得するため、ブラウザが一瞬起動します。取得したトークンは `.auth_token.json` にキャッシュされ、次回以降は再利用されます。
- 事前に `loilonote login` を実行し、`~/.loilonote/state.json` が作成されている必要があります。
- 画像ファイル（`.png`, `.jpg` など）は縦横サイズを自動取得し、適切なメタデータ付きでアップロードされます。
- ノートにカードとして追加できない形式（`.pptx`, `.docx`, `.md`, `.txt` など）は、LibreOffice がインストールされている場合に自動で PDF に変換してからアップロードされます（LibreOffice 未導入の場合はスキップされ `failed/` に退避されます）。

---

## データ・キャッシュの保存場所と取り扱い

実行時に以下の認証情報・キャッシュファイルが生成されます。

| ファイル | 役割 |
|---|---|
| `~/.loilonote/state.json` | ログイン済みブラウザセッション（Cookie / LocalStorage） |
| `~/.loilonote/courses.json` | 取得済みコース一覧と URL のキャッシュ |
| `~/.loilonote/out/` | `--dump` または `dump` コマンドで保存された HTML / PNG |
| `.auth_token.json` | 自動アップロードスクリプト用の認証トークンキャッシュ |

### セキュリティ上の注意

`state.json` と `.auth_token.json` にはアカウントの認証情報が含まれます。共有 PC での利用には注意し、Git リポジトリへ誤ってコミットしないよう管理してください。

---

## トラブルシューティング

- **セッション切れ・認証エラーが出る場合:** `loilonote login` を再実行して `state.json` を更新してください。自動アップロードで認証エラーが続く場合は、`.auth_token.json` を削除して再実行するとトークンを再取得します。
- **新しいコースが一覧に出ない場合:** `loilonote courses --refresh` でキャッシュを更新してください。

---

## アーキテクチャ

```
loilonote-cli/
├── loilonote_cli/
│   ├── __init__.py
│   ├── browser.py          # Playwright ブラウザ・セッション管理
│   ├── cli.py              # Click ベースの CLI コマンド定義
│   └── selectors.py        # DOM セレクタ定義（UI 更新時の修正箇所）
├── tests/                  # テストコード
├── loilonote.py            # CLI エントリポイント
├── loilonote.bat           # Windows 用起動ラッパー
└── loilonote_auto_upload.py # フォルダ監視・自動アップロードスクリプト
```

## 既知の制限事項

- **非公式の UI / 内部 API 操作:** 公式の公開 API は存在しないため、LoiLoNote 側のアップデートによりセレクタや内部 API 仕様が変わり、動作しなくなる場合があります。
- **PDF テキスト抽出:** ブラウザ上のテキストレイヤーから取得しているため、PDF のエンコーディングによっては一部文字化けすることがあります。
- **ヘッドレスモード判定:** ヘッドレス環境では LoiLoNote 側に「ブラウザ非対応」の警告が表示される場合があります（init_script による DOM 除去で回避しています）。
- **サンドボックス環境での制限:** Playwright は名前付きパイプを使用するため、制限の強いサンドボックス環境では権限昇格やサンドボックス外での実行が必要になることがあります。

---

## 開発・テスト

```bash
# 開発用依存関係をインストール
pip install -e ".[dev]"

# テストを実行
pytest

# コードの静的解析（Lint）
ruff check .
```

---

## クレジット・謝辞

- ノート内部構造の解析・ダウンロード機能は [samcct-bit/loilonote-cli](https://github.com/samcct-bit/loilonote-cli)（MIT License）を参考に実装しました。
  ノート ZIP のダウンロード API および内部構造の解析ロジックは、同プロジェクトの実装を参考にしています。

## ライセンス

MIT License