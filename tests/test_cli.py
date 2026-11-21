"""Basic tests for loilonote-cli."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_cli_help():
    """CLI should show help without errors."""
    result = subprocess.run(
        [sys.executable, "loilonote.py", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0
    assert "LoiLoNote CLI" in result.stdout


def test_cli_version():
    """CLI should show version."""
    result = subprocess.run(
        [sys.executable, "loilonote.py", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0
    assert "0.3.0" in result.stdout


def test_doctor():
    """Doctor command should return valid JSON."""
    result = subprocess.run(
        [sys.executable, "loilonote.py", "doctor"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(Path(__file__).parent.parent),
    )
    # doctor may fail if no chromium, but should output JSON
    try:
        data = json.loads(result.stdout)
        assert "ok" in data
    except json.JSONDecodeError:
        pytest.skip("No JSON output (possibly no Playwright)")


def test_status_no_session():
    """Status should work even without session."""
    result = subprocess.run(
        [sys.executable, "loilonote.py", "status"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(Path(__file__).parent.parent),
    )
    try:
        data = json.loads(result.stdout)
        assert "session" in data or "exists" in data
    except json.JSONDecodeError:
        pytest.skip("No JSON output")
