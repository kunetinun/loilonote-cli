# LoiLoNote CLI

A command-line tool to automate [LoiLoNote School](https://loilonote.app) web UI via Playwright.

Designed for both human users and AI agents. Default output is JSON for machine readability.

## Features

- 🔐 **Session management** — Login once, reuse session
- 📚 **Course discovery** — List all courses with URLs
- 📝 **Note management** — List and read notes
- 📁 **Materials search** — Recursively search materials box by name
- 📤 **Submissions** — List submission boxes and upload files
- 📨 **Messaging** — Send files to individuals
- 🤖 **AI-first** — JSON output by default, `--human` for readable output
- 🔄 **Caching** — Course URLs cached for fast reuse

## Installation

### Prerequisites

- Python 3.9+
- Playwright + Chromium

### Install

```bash
# Clone the repository
git clone https://github.com/richi/loilonote-cli.git
cd loilonote-cli

# Install dependencies
pip install -e .

# Install Playwright browser
playwright install chromium
```

### Windows note

Playwright uses named pipes, which may be blocked in sandboxed environments.
Run with full access if needed.

## Usage

### First-time setup

```bash
# Login (opens browser for manual login)
loilonote login

# Verify session
loilonote status
```

### Commands

```bash
# Check environment
loilonote doctor

# List courses (cached after first run)
loilonote courses
loilonote courses --refresh

# Search materials (fast, uses UI search)
loilonote materials-search "古文単語"

# Search and open first match
loilonote materials-search "古文単語" --open

# Get material content
loilonote materials-get "古典文法　２学期小テスト計画"

# List materials in a folder
loilonote materials --path "学内共有/81期　国語科/１年次"

# Recursively list materials tree
loilonote materials-tree --depth 3

# List notes in a course
loilonote notes "https://loilonote.app/_/12345?tab=standardNoteList"

# Search notes across courses
loilonote notes-search "単語"

# Read a note/page
loilonote note "https://loilonote.app/_/12345?tab=standardNoteList"

# List submission boxes
loilonote submissions "https://loilonote.app/_/12345?tab=submissionBox"

# Upload file to submission box
loilonote submit "file.pdf" "https://loilonote.app/_/12345?tab=submissionBox"

# Send file to individual
loilonote send "file.pdf" "https://loilonote.app/_/12345?tab=submissionBox" --to "相手名"

# Create note
loilonote create-note "タイトル" "https://loilonote.app/_/12345?tab=standardNoteList"

# Save page HTML + screenshot
loilonote dump "https://loilonote.app/_/12345?tab=standardNoteList"
```

### Options

| Option | Description |
|---|---|
| `--headed` | Show browser window |
| `--slow N` | Slow motion (ms) |
| `--human` | Human-readable output |
| `--timeout N` | Navigation timeout (ms) |
| `--version` | Show version |

### JSON output (default)

All commands output JSON by default:

```json
{"ok": true, "count": 5, "items": ["..."]}
```

Use `--human` for readable output.

## Architecture

```
loilonote_cli/
├── __init__.py
├── browser.py      # Playwright browser management
├── cli.py          # Click CLI commands
└── selectors.py    # DOM selectors (update when UI changes)
```

## Known limitations

- **UI scraping**: No official API. Selectors may break on LoiLoNote updates.
- **PDF extraction**: Uses browser text layer. Some PDFs may have garbled text.
- **Headless detection**: LoiLoNote may show "browser not supported" warning in headless mode (handled via init script).
- **Sandboxed environments**: Playwright requires named pipes. May need elevated permissions.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .
```

## 免責事項

本ツールは個人利用のみを目的としています。ブラウザ自動化によりLoiLoNoteのWeb UIを操作します。ユーザーはLoiLoNoteの利用規約を遵守する責任があります。本ツールの使用によって生じた結果について、作者は責任を負いません。

## License

MIT
