"""Tests for MCP client configuration and doctor."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import timedelta

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


def test_stdio_mcp_client_initializes_and_lists_tools(tmp_path):
    pytest.importorskip("mcp")
    import anyio
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    async def smoke() -> None:
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", "agentdrive.adapters.mcp_server", "--transport", "stdio"],
            env={
                "AGENTDRIVE_HOME": str(tmp_path / ".agentdrive"),
                "PYTHONUNBUFFERED": "1",
            },
        )
        async with stdio_client(server) as (read, write):
            async with ClientSession(
                read,
                write,
                read_timeout_seconds=timedelta(seconds=5),
            ) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                assert "agentdrive_mcp_catalog" in names
                assert "experience_graph_get_context_pack" in names
                assert "agentdrive_review_inherited_skills" in names
                assert "agentdrive_assimilate_inherited_skills" in names
                assert "agentdrive_promote_inherited_skill" in names
                assert "agentdrive_prune_inherited_skill" in names
                assert "agentdrive_ingest_skill_dna" in names

    anyio.run(smoke)


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
