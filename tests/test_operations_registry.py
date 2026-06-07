"""Tests for the contract-first operations registry."""

from __future__ import annotations

import json

import pytest

from agentdrive.operations import (
    OPERATIONS,
    describe_operation,
    export_operations_json,
    get_operation,
    list_operations,
    parse_operation_kwargs,
    run_operation,
)


def test_list_operations_count_at_least_20() -> None:
    assert len(list_operations()) >= 20
    assert len(OPERATIONS) >= 20


def test_get_unknown_operation_returns_none() -> None:
    assert get_operation("not-a-real-operation") is None


def test_describe_unknown_raises_key_error() -> None:
    with pytest.raises(KeyError, match="unknown operation"):
        describe_operation("not-a-real-operation")


def test_describe_has_required_fields() -> None:
    detail = describe_operation("pool_status")
    for field in ("name", "description", "category", "read_only", "cli_command", "mcp_tool"):
        assert field in detail
    assert detail["name"] == "pool_status"
    assert isinstance(detail["read_only"], bool)


def test_run_unknown_raises_key_error() -> None:
    with pytest.raises(KeyError, match="unknown operation"):
        run_operation("not-a-real-operation")


def test_run_pool_status_dry_does_not_crash(isolated_agentdrive_home) -> None:
    result = run_operation("pool_status", dry_run=True)
    assert result.get("success") is True
    assert "stats" in result


def test_run_doctor_dry_does_not_crash(isolated_agentdrive_home) -> None:
    result = run_operation("doctor", dry_run=True)
    assert result.get("success") is True
    assert result.get("dry_run") is True
    assert "checks" in result


def test_export_operations_json_parses_as_valid_list() -> None:
    raw = export_operations_json()
    payload = json.loads(raw)
    assert isinstance(payload, list)
    assert len(payload) >= 20
    assert all("name" in item for item in payload)


def test_parse_operation_kwargs_coerces_types() -> None:
    parsed = parse_operation_kwargs(["limit=5", "dry_run=true", "question=hello world"])
    assert parsed["limit"] == 5
    assert parsed["dry_run"] is True
    assert parsed["question"] == "hello world"


def test_operations_include_required_names() -> None:
    names = {op.name for op in OPERATIONS}
    required = {
        "think",
        "pool_query",
        "pool_status",
        "ingest_genome",
        "reconcile_scan",
        "reconcile_seed",
        "doctor",
        "doctor_verbose",
        "sprint_ship",
        "patterns_list",
        "patterns_apply",
        "patterns_import_fabric",
        "dream_run",
        "dream_status",
        "cap_mint_mission",
        "experience_graph_context_pack",
        "experience_graph_record_reasoning",
        "learnings_log",
        "harness_compose",
    }
    assert required.issubset(names)