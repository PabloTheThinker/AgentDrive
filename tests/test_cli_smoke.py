"""Smoke tests for the Savant CLI entry point."""

import subprocess
import sys


def test_cli_version():
    # Run the installed / module entry
    result = subprocess.run(
        [sys.executable, "-m", "savant.cli", "--version"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "Savant" in result.stdout or "0.1.0" in result.stdout


def test_cli_doctor_runs(isolated_savant_home):
    result = subprocess.run(
        [sys.executable, "-m", "savant.cli", "doctor"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    # Doctor should succeed even on fresh isolated home
    assert result.returncode == 0
    assert "Savant Doctor" in result.stdout or "All checks" in result.stdout or "home:" in result.stdout
