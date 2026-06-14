"""JSON CLI output must be machine-parseable (no Rich soft-wrap)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run(*args: str, home: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "AGENTDRIVE_HOME": str(home), "AGENTDRIVE_DISABLE_RETENTION_LOOP": "1"}
    return subprocess.run(
        [sys.executable, "-m", "agentdrive.cli", *args],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def test_think_json_parseable(isolated_agentdrive_home: Path):
    proc = _run("think", "test", "--dry-run", "--json", home=isolated_agentdrive_home)
    assert proc.returncode == 0
    data = json.loads(proc.stdout.strip())
    assert data.get("success") is True


def test_learnings_list_json_parseable(isolated_agentdrive_home: Path):
    proc = _run("learnings", "list", "--json", home=isolated_agentdrive_home)
    assert proc.returncode == 0
    data = json.loads(proc.stdout.strip())
    assert data.get("success") is True
