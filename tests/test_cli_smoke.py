"""Smoke tests for the Savant CLI entry point."""

import subprocess
import sys


def test_cli_version():
    # Run the installed / module entry
    result = subprocess.run(
        [sys.executable, "-m", "agentdrive.cli", "--version"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "Savant" in result.stdout or "0.1.0" in result.stdout


def test_cli_doctor_runs(isolated_savant_home):
    result = subprocess.run(
        [sys.executable, "-m", "agentdrive.cli", "doctor"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    # Doctor should succeed even on fresh isolated home
    assert result.returncode == 0
    # Doctor renders through the chrome system; assert on stable user-facing markers.
    stdout = result.stdout
    assert (
        "Savant health check" in stdout
        or "All systems nominal" in stdout
        or "Home directory" in stdout
    )
