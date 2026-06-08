"""Tests for the canonical golden-path module and CLI."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from agentdrive.golden_path import GOLDEN_STEPS, run_walkthrough, verify_all, verify_step


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _json_from_stdout(stdout: str) -> dict | list:
    cleaned = _strip_ansi(stdout).strip()
    start_obj = cleaned.find("{")
    start_arr = cleaned.find("[")
    if start_arr >= 0 and (start_obj < 0 or start_arr < start_obj):
        return json.loads(cleaned[start_arr:])
    return json.loads(cleaned[start_obj:])


def test_golden_steps_count():
    assert len(GOLDEN_STEPS) == 7
    ids = [s.id for s in GOLDEN_STEPS]
    assert ids == ["install", "doctor", "mcp", "seed", "think", "learnings", "query"]


def test_verify_install(isolated_agentdrive_home: Path):
    result = verify_step("install")
    assert result["success"] is True
    assert str(isolated_agentdrive_home) in result.get("detail", "")


def test_run_walkthrough_dry_run(isolated_agentdrive_home: Path):
    result = run_walkthrough(dry_run=True, stop_on_fail=False)
    assert result["dry_run"] is True
    assert result["total"] >= 5
    step_ids = [s["step"] for s in result["steps"]]
    assert "doctor" in step_ids
    assert "think" in step_ids
    assert "query" in step_ids


def test_verify_all_dry(isolated_agentdrive_home: Path):
    result = verify_all()
    assert "steps" in result
    assert result["total"] == 7
    # install should pass; learnings may fail on fresh home
    install_check = next(s for s in result["steps"] if s["step"] == "install")
    assert install_check["success"] is True


def test_cli_golden_path_steps(isolated_agentdrive_home: Path):
    env = {
        **os.environ,
        "AGENTDRIVE_HOME": str(isolated_agentdrive_home),
        "AGENTDRIVE_DISABLE_RETENTION_LOOP": "1",
    }
    proc = subprocess.run(
        [sys.executable, "-m", "agentdrive.cli", "golden-path", "steps", "--json"],
        capture_output=True,
        text=True,
        timeout=20,
        env=env,
    )
    assert proc.returncode == 0
    data = _json_from_stdout(proc.stdout)
    assert isinstance(data, list)
    assert len(data) == 7


def test_cli_golden_path_run_dry(isolated_agentdrive_home: Path):
    env = {
        **os.environ,
        "AGENTDRIVE_HOME": str(isolated_agentdrive_home),
        "AGENTDRIVE_DISABLE_RETENTION_LOOP": "1",
    }
    proc = subprocess.run(
        [sys.executable, "-m", "agentdrive.cli", "golden-path", "run", "--dry-run", "--json"],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert proc.returncode == 0
    data = _json_from_stdout(proc.stdout)
    assert isinstance(data, dict)
    assert data.get("dry_run") is True
    assert data.get("success") is True