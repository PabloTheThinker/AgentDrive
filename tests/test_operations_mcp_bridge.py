"""Tests for MCP auto-registration from operations registry."""

from __future__ import annotations

import json

import pytest

from agentdrive.operations.mcp_bridge import register_operations_as_mcp_tools
from agentdrive.operations.registry import export_operations_json, run_operation


@pytest.fixture
def mcp_server():
    mcp = pytest.importorskip("mcp")
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        pytest.skip("mcp package not installed")
    from agentdrive.adapters.mcp_server import create_mcp_server

    return create_mcp_server()


def test_export_operations_json_all_have_mcp_tool():
    payload = json.loads(export_operations_json())
    assert len(payload) >= 20
    missing = [item["name"] for item in payload if not item.get("mcp_tool")]
    assert missing == [], f"ops missing mcp_tool: {missing}"


def test_mcp_server_registers_auto_ops(mcp_server) -> None:
    tools = set(mcp_server._tool_manager._tools.keys())  # noqa: SLF001
    assert "agentdrive_doctor" in tools
    assert "agentdrive_dream_run" in tools
    assert "agentdrive_harness_compose" in tools


def test_auto_registered_doctor_dry_run_via_run_operation(isolated_agentdrive_home) -> None:
    result = run_operation("doctor", dry_run=True)
    assert result.get("success") is True
    assert result.get("dry_run") is True


def test_register_skips_existing_names() -> None:
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("test-skip")
    server.add_tool(lambda: "ok", name="agentdrive_doctor", description="manual")
    before = set(server._tool_manager._tools.keys())  # noqa: SLF001
    registered = register_operations_as_mcp_tools(server, skip_names=before)
    assert "agentdrive_doctor" not in registered
    assert "agentdrive_patterns_list" in registered