"""Tests for end-to-end automatic learning on run_operation."""

from __future__ import annotations

import pytest

from agentdrive.learning.auto_absorb import reset_sessions
from agentdrive.operations.registry import run_operation
from agentdrive.skills import get_skill


@pytest.fixture(autouse=True)
def _clean_learning_sessions():
    reset_sessions()
    yield
    reset_sessions()


@pytest.fixture
def swarm_id(isolated_agentdrive_home):
    return "stabilization-wave-20260531"


def _sample_branches():
    return [
        {
            "branch_id": "branch:operator-1",
            "role": "operator",
            "path_summary": "Fund credits then judge Gate drafts",
            "robustness_score": 0.9,
            "stress_test_passed": True,
        },
    ]


def test_dry_run_skips_auto_learning(swarm_id) -> None:
    result = run_operation(
        "external_parent_decision",
        dry_run=True,
        trigger="No absorb on dry run",
        branches=_sample_branches(),
        collapsed_branch_id="branch:operator-1",
        swarm_id=swarm_id,
    )
    assert result.get("success") is True
    assert "auto_learning" not in result


def test_auto_learning_disabled(monkeypatch: pytest.MonkeyPatch, swarm_id) -> None:
    monkeypatch.setenv("AGENTDRIVE_AUTO_LEARN", "0")
    result = run_operation(
        "external_parent_decision",
        trigger="Disabled auto learn",
        branches=_sample_branches(),
        collapsed_branch_id="branch:operator-1",
        swarm_id=swarm_id,
        reasoning_provider="test",
    )
    assert result.get("success") is True
    assert "auto_learning" not in result


def test_external_parent_decision_auto_distills_skill(swarm_id) -> None:
    result = run_operation(
        "external_parent_decision",
        trigger="Interegy fund xAI before VPS",
        branches=_sample_branches(),
        collapsed_branch_id="branch:operator-1",
        collapse_reason="Operator path",
        reasoning_provider="grok-test",
        program_id="grok-test@stabilization-wave-20260531",
        fabric_reasoning={
            "decision_rationale": "Draft quality unproven",
            "llm_mode": "external",
        },
        swarm_id=swarm_id,
    )
    assert result.get("success") is True
    auto = result.get("auto_learning") or {}
    assert auto.get("operation") == "external_parent_decision"
    skill = auto.get("skill") or {}
    assert skill.get("name", "").startswith("learned-parent-decision")
    installed = get_skill(skill["name"])
    assert installed is not None
    assert "auto-learned" in installed.tags
    assert installed.category in ("inherited", "promoted")


def test_think_after_context_pack_auto_records_reasoning(swarm_id) -> None:
    run_operation(
        "experience_graph_context_pack",
        swarm_id=swarm_id,
        max_tokens=400,
    )
    result = run_operation(
        "think",
        question="What is the next move for Interegy launch?",
        swarm_id=swarm_id,
    )
    assert result.get("success") is True
    auto = result.get("auto_learning") or {}
    assert auto.get("reasoning_trace") or auto.get("skill")


def test_auto_learn_updates_existing_skill_revision(swarm_id) -> None:
    first = run_operation(
        "external_parent_decision",
        trigger="Same trigger revision one",
        branches=_sample_branches(),
        collapsed_branch_id="branch:operator-1",
        swarm_id=swarm_id,
        reasoning_provider="test",
    )
    second = run_operation(
        "external_parent_decision",
        trigger="Same trigger revision one",
        branches=_sample_branches(),
        collapsed_branch_id="branch:operator-1",
        swarm_id=swarm_id,
        reasoning_provider="test",
    )
    name1 = (first.get("auto_learning") or {}).get("skill", {}).get("name")
    name2 = (second.get("auto_learning") or {}).get("skill", {}).get("name")
    assert name1 and name1 == name2
    entry = get_skill(name1)
    assert entry is not None
    assert entry.body.count("Auto-learned playbook") >= 1