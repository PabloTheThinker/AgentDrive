"""Tests for external MCP Parent multiverse submission (Grok/Claude/Codex path)."""

from __future__ import annotations

import pytest

from agentdrive.operations.registry import run_operation


@pytest.fixture
def swarm_id(isolated_agentdrive_home):
    return "stabilization-wave-20260531"


def _sample_branches():
    return [
        {
            "branch_id": "branch:architect-0",
            "role": "architect",
            "path_summary": "Map system before intervening",
            "assumptions": ["Wiring complete"],
            "robustness_score": 0.8,
            "stress_test_passed": True,
        },
        {
            "branch_id": "branch:operator-1",
            "role": "operator",
            "path_summary": "Fund credits then judge Gate drafts",
            "assumptions": ["Draft quality is the load-bearing risk"],
            "robustness_score": 0.9,
            "stress_test_passed": True,
        },
    ]


def test_external_parent_decision_dry_run(swarm_id) -> None:
    result = run_operation(
        "external_parent_decision",
        dry_run=True,
        trigger="Interegy launch path",
        branches=_sample_branches(),
        collapsed_branch_id="branch:operator-1",
        swarm_id=swarm_id,
        reasoning_provider="grok-test",
    )
    assert result.get("success") is True
    assert result.get("dry_run") is True
    assert result.get("operation") == "external_parent_decision"


def test_external_parent_decision_records_external_session(swarm_id) -> None:
    result = run_operation(
        "external_parent_decision",
        trigger="External MCP parent smoke test",
        branches=_sample_branches(),
        collapsed_branch_id="branch:operator-1",
        invariants=[
            {
                "statement": "Draft quality at Gate is load-bearing",
                "branch_coverage": 1.0,
                "kind": "robust",
                "source_branches": ["branch:architect-0", "branch:operator-1"],
            }
        ],
        collapse_reason="Operator path: cheapest reversible quality proof",
        reasoning_provider="grok-test",
        program_id="grok-interegy-web@stabilization-wave-20260531",
        fabric_reasoning={
            "fabric_elements_considered": ["interegy-web/HANDOFF.md"],
            "decision_rationale": "Fund xAI before VPS",
            "expected_lift_signal": 0.12,
            "llm_mode": "external",
        },
        swarm_id=swarm_id,
    )
    assert result.get("success") is True
    payload = result.get("result") or {}
    assert payload.get("llm_mode") == "external"
    assert payload.get("reasoning_provider") == "grok-test"
    assert payload.get("collapsed_branch_id") == "branch:operator-1"
    session = payload.get("session") or {}
    assert session.get("llm_mode") == "external"
    assert session.get("reasoning_provider") == "grok-test"

    session_id = payload.get("session_id")
    assert session_id

    loaded = run_operation(
        "multiverse_get_session",
        session_id=session_id,
        swarm_id=swarm_id,
    )
    assert loaded.get("success") is True
    loaded_session = loaded.get("session") or {}
    assert loaded_session.get("llm_mode") == "external"


def test_external_parent_requires_branches(swarm_id) -> None:
    result = run_operation(
        "external_parent_decision",
        trigger="missing branches",
        branches=[],
        collapsed_branch_id="branch:x",
        swarm_id=swarm_id,
    )
    assert result.get("success") is False


def test_mcp_server_registers_external_parent_tool() -> None:
    pytest.importorskip("mcp.server.fastmcp")
    from agentdrive.adapters.mcp_server import create_mcp_server

    server = create_mcp_server()
    tools = set(server._tool_manager._tools.keys())  # noqa: SLF001
    assert "external_parent_decision" in tools


def test_suggest_reasoning_documents_external_flow(swarm_id) -> None:
    result = run_operation(
        "experience_graph_suggest_reasoning",
        swarm_id=swarm_id,
    )
    structure = result.get("structure") or {}
    assert "external_mcp_parent_flow" in structure
    modes = structure.get("reasoning_provider_modes") or {}
    assert "external_mcp" in modes
