#!/usr/bin/env bash
# Wrapper script for auto-upload watcher (macOS / Linux)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
python3 -X utf8 loilonote_auto_upload.py "$@"