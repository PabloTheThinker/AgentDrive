"""Smoke tests for the AgentDrive CLI entry point."""

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
    # Accept either product name (rebrand carried-through) plus the current
    # major.minor — bump intentionally drops the version pin from the test so
    # the smoke test survives patch bumps.
    assert "AgentDrive" in result.stdout or "Savant" in result.stdout
    assert "0." in result.stdout  # any 0.x version


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
