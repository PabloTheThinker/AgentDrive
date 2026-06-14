"""Tests for expanded AgentDrive CLI surfaces (commands, think, learnings, etc.)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from agentdrive.cli_catalog import CATALOG, search_catalog
from agentdrive.cli_surface import build_help_epilog


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _run_cli(
    *args: str,
    home: Path | None = None,
    timeout: int = 20,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if home is not None:
        env["AGENTDRIVE_HOME"] = str(home)
    env.setdefault("AGENTDRIVE_DISABLE_RETENTION_LOOP", "1")
    return subprocess.run(
        [sys.executable, "-m", "agentdrive.cli", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _json_from_stdout(stdout: str) -> dict:
    """Parse JSON from CLI stdout (skip any stray log lines)."""
    cleaned = _strip_ansi(stdout).strip()
    start = cleaned.find("{")
    if start < 0:
        raise json.JSONDecodeError("no JSON object in stdout", cleaned, 0)
    return json.loads(cleaned[start:])


def test_catalog_nonempty_and_search():
    assert len(CATALOG) >= 50
    hits = search_catalog("mcp install")
    assert any("mcp install" in e.command for e in hits)
    hits2 = search_catalog("learnings")
    assert any("learnings" in e.command for e in hits2)


def test_help_epilog_mentions_commands():
    epilog = build_help_epilog()
    assert "agentdrive commands list" in epilog
    assert "agentdrive think" in epilog


def test_commands_list(isolated_agentdrive_home):
    result = _run_cli("commands", "list", home=isolated_agentdrive_home)
    assert result.returncode == 0
    out = _strip_ansi(result.stdout)
    assert "AgentDrive commands" in out
    assert "agentdrive think" in out
    assert "mcp" in out and "install" in out


def test_commands_search(isolated_agentdrive_home):
    result = _run_cli("commands", "search", "dream", home=isolated_agentdrive_home)
    assert result.returncode == 0
    assert "dream" in result.stdout.lower()


def test_commands_tree(isolated_agentdrive_home):
    result = _run_cli("commands", "tree", home=isolated_agentdrive_home)
    assert result.returncode == 0
    assert "Drive" in result.stdout or "drive" in result.stdout


def test_think_dry_run(isolated_agentdrive_home):
    result = _run_cli(
        "think",
        "What genomes exist?",
        "--dry-run",
        "--json",
        home=isolated_agentdrive_home,
    )
    assert result.returncode == 0
    data = _json_from_stdout(result.stdout)
    assert data.get("success") is True
    assert data.get("dry_run") is True
    assert data.get("operation") == "think"


def test_learnings_log_and_list(isolated_agentdrive_home):
    log = _run_cli(
        "learnings",
        "log",
        "--key",
        "cli-test-key",
        "--insight",
        "CLI learnings surface works",
        "--type",
        "operational",
        home=isolated_agentdrive_home,
    )
    assert log.returncode == 0

    listed = _run_cli("learnings", "list", "--json", home=isolated_agentdrive_home)
    assert listed.returncode == 0
    data = _json_from_stdout(listed.stdout)
    assert data.get("success") is True
    assert data.get("count", 0) >= 1
    keys = [e.get("key") for e in data.get("entries", [])]
    assert "cli-test-key" in keys


def test_learnings_search(isolated_agentdrive_home):
    _run_cli(
        "learnings",
        "log",
        "--key",
        "searchable-cli",
        "--insight",
        "unique-token-xyzzy-cli-search",
        home=isolated_agentdrive_home,
    )
    result = _run_cli(
        "learnings",
        "search",
        "xyzzy-cli-search",
        "--json",
        home=isolated_agentdrive_home,
    )
    assert result.returncode == 0
    data = _json_from_stdout(result.stdout)
    assert data.get("success") is True
    assert len(data.get("hits", [])) >= 1


def test_harness_compose_dry_run(isolated_agentdrive_home):
    result = _run_cli(
        "harness",
        "compose",
        "--task",
        "smoke test harness",
        "--dry-run",
        "--json",
        home=isolated_agentdrive_home,
    )
    assert result.returncode == 0
    data = _json_from_stdout(result.stdout)
    assert data.get("success") is True
    assert data.get("dry_run") is True


def test_graph_suggest_dry_run(isolated_agentdrive_home):
    result = _run_cli(
        "graph",
        "suggest",
        "--dry-run",
        "--json",
        home=isolated_agentdrive_home,
    )
    assert result.returncode == 0
    data = _json_from_stdout(result.stdout)
    assert data.get("success") is True
    assert data.get("dry_run") is True


def test_pool_alias_status(isolated_agentdrive_home):
    result = _run_cli("pool", "status", home=isolated_agentdrive_home)
    assert result.returncode in (0, 1)
    assert "Traceback" not in result.stdout + result.stderr


def test_ops_list_shows_new_cli_commands(isolated_agentdrive_home):
    result = _run_cli("ops", "list", home=isolated_agentdrive_home)
    assert result.returncode == 0
    out = _strip_ansi(result.stdout).replace("\n", " ")
    assert "think" in out
    assert "learnings log" in out
    assert "harness" in out and "compose" in out


def test_repl_dispatch_line(isolated_agentdrive_home, monkeypatch):
    """REPL dispatch_line routes through the same argparse handlers."""
    from agentdrive.cli import build_parser
    from agentdrive.cli_repl import dispatch_line

    monkeypatch.setenv("AGENTDRIVE_HOME", str(isolated_agentdrive_home))
    parser = build_parser()
    assert dispatch_line("exit", parser) == -1
    assert dispatch_line("", parser) is None
    code = dispatch_line("commands list", parser)
    assert code == 0


def test_repl_subcommand_help(isolated_agentdrive_home):
    result = _run_cli("repl", "--help", home=isolated_agentdrive_home)
    assert result.returncode == 0
    assert "REPL" in result.stdout or "repl" in result.stdout.lower()


def test_cli_flag_in_help(isolated_agentdrive_home):
    result = _run_cli("--help", home=isolated_agentdrive_home)
    assert result.returncode == 0
    assert "--cli" in result.stdout


def test_eval_replay_missing_file(isolated_agentdrive_home):
    result = _run_cli(
        "eval",
        "replay",
        "/nonexistent/artifact.json",
        home=isolated_agentdrive_home,
    )
    assert result.returncode == 1
    assert "not found" in result.stdout.lower() or "Artifact" in result.stdout
