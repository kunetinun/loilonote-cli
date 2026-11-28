#!/usr/bin/env bash
# Wrapper script for loilonote CLI (macOS / Linux)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/loilonote.py" "$@"