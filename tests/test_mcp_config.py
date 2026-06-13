"""Tests for MCP client configuration and doctor."""

from __future__ import annotations

import json
import shutil

import pytest

from agentdrive.adapters.mcp_config import (
    count_mcp_tools,
    export_client_bundle,
    get_mcp_server_block,
    mcp_package_available,
    resolve_mcp_launcher,
    run_mcp_doctor,
    write_client_config,
)


def test_mcp_package_available_when_installed():
    assert mcp_package_available() is True


def test_resolve_mcp_launcher_returns_stdio_args():
    launcher = resolve_mcp_launcher()
    assert launcher.command
    transport_index = launcher.args.index("--transport")
    assert launcher.args[transport_index + 1] == "stdio"
    assert launcher.method in ("binary", "module", "uvx")


def test_export_client_bundle_has_mcp_servers():
    bundle = export_client_bundle()
    assert "mcpServers" in bundle
    assert "agentdrive" in bundle["mcpServers"]
    assert bundle["mcpServers"]["agentdrive"]["command"]


def test_get_mcp_server_block_matches_launcher():
    block = get_mcp_server_block()
    launcher = resolve_mcp_launcher()
    assert block["agentdrive"]["command"] == launcher.command
    assert block["agentdrive"]["args"] == launcher.args


def test_run_mcp_doctor_passes_in_dev_env():
    report = run_mcp_doctor()
    assert report.get("tool_count", 0) >= 25
    assert any(c["name"] == "mcp package" and c["ok"] for c in report.get("checks", []))


def test_count_mcp_tools_at_least_registry_ops():
    if not mcp_package_available():
        pytest.skip("mcp not installed")
    assert count_mcp_tools() >= 25


def test_write_client_config_dry_run_cursor(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = write_client_config("cursor", dry_run=True)
    assert result["client"] == "cursor"
    assert result["written"] is False
    assert result["path"]


def test_write_client_config_creates_cursor_json(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = write_client_config("cursor", dry_run=False)
    assert result["written"] is True
    path = result["path"]
    assert path
    data = json.loads(open(path, encoding="utf-8").read())
    assert "agentdrive" in data.get("mcpServers", {})


@pytest.mark.skipif(shutil.which("agentdrive-mcp") is None, reason="binary not on PATH")
def test_binary_launcher_when_on_path():
    launcher = resolve_mcp_launcher()
    if shutil.which("agentdrive-mcp"):
        assert launcher.method == "binary"
