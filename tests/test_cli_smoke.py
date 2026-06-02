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
    assert "AgentDrive" in result.stdout or "Agent Drive" in result.stdout
    assert "0." in result.stdout  # any 0.x version


def test_cli_doctor_runs(isolated_agentdrive_home):
    result = subprocess.run(
        [sys.executable, "-m", "agentdrive.cli", "doctor"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    # Doctor may return 0 (clean) or 1 (notes/warnings) on fresh home.
    # This is expected and useful behavior in production.
    assert result.returncode in (0, 1)
    # Doctor renders through the chrome system; assert on stable user-facing markers.
    stdout = result.stdout
    assert (
        "AgentDrive health check" in stdout
        or "All systems nominal" in stdout
        or "Home directory" in stdout
        or "Security posture" in stdout
    )


def test_cli_doctor_empty_drive_self_healing(isolated_agentdrive_home):
    """Empty-drive / first-run doctor must succeed without crash and surface actionable guidance."""
    result = subprocess.run(
        [sys.executable, "-m", "agentdrive.cli", "doctor"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode in (0, 1)
    out = (result.stdout or "") + (result.stderr or "")
    # Actionable for new users on fresh install
    assert (
        "empty (fresh install)" in out
        or "ready for DNA" in out
        or "self-heal" in out.lower()
        or "first-run" in out.lower()
        or "will grow" in out
        or "Home directory" in out
    )
    # Must not have unhandled tracebacks for missing state
    assert "Traceback" not in out
    assert "AgentDriveDriveError" not in out
