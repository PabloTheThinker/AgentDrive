"""Tests for growth merge — experience + patterns + memory compounding."""

from __future__ import annotations

import pytest

from agentdrive.learning.auto_absorb import (
    LearningSession,
    maybe_absorb_operation_outcome,
    reset_sessions,
)
from agentdrive.learning.growth_merge import (
    GrowthAxes,
    merge_session_growth,
    recognize_growth_patterns,
)
from agentdrive.memory import MemoryBankStore
from agentdrive.operations.registry import run_operation


@pytest.fixture(autouse=True)
def _clean_sessions():
    reset_sessions()
    yield
    reset_sessions()


@pytest.fixture
def swarm_id(isolated_agentdrive_home):
    return "growth-merge-test-swarm"


def test_growth_axes_merge_ready() -> None:
    assert GrowthAxes(experience=True, patterns=True).merge_ready() is True
    assert GrowthAxes(experience=True).merge_ready() is False


def test_recognize_growth_patterns_from_memory(swarm_id) -> None:
    MemoryBankStore(swarm_id).store(
        kind="pattern",
        title="Gateway bootstrap auth",
        content="Interegy gateway uses X-Ren-API-Key for bootstrap requests.",
        vault="interegy",
        topic="auth",
    )
    patterns = recognize_growth_patterns(
        swarm_id=swarm_id,
        trigger="gateway bootstrap auth header",
    )
    assert patterns
    assert any(p.source == "memory_bank" for p in patterns)


def test_merge_session_growth_writes_compound_memory(
    swarm_id, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENTDRIVE_AUTO_GROWTH_MERGE", "1")
    session = LearningSession(swarm_id=swarm_id, program_id="test-program")
    session.ops = [
        ("experience_graph_record_reasoning", "reasoning"),
        ("codebase_mimic", "mimic"),
    ]
    session.experience_traces = ["trace-abc"]
    session.pattern_projects = ["demo-project"]
    session.distilled_skills = ["auto-think-demo"]

    record = merge_session_growth(session, trigger="Ship gateway helper")
    assert record is not None
    assert record.memory_id
    assert "experience" in record.axes.present()
    assert "patterns" in record.axes.present()
    assert "skills" in record.axes.present()

    store = MemoryBankStore(swarm_id)
    recalled = store.recall(record.memory_id)
    assert recalled is not None
    assert recalled.vault == "growth"
    assert recalled.topic == "merge"
    assert "Growth merge" in recalled.title


def test_auto_absorb_emits_growth_merge(swarm_id, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTDRIVE_AUTO_GROWTH_MERGE", "1")
    MemoryBankStore(swarm_id).store(
        kind="insight",
        title="Prior gateway work",
        content="Bootstrap uses credits before deploy.",
    )
    result = {
        "success": True,
        "swarm_id": swarm_id,
        "trace_slug": "fabric-trace-1",
        "result": {"directive": "Fund credits first"},
    }
    absorbed = maybe_absorb_operation_outcome(
        "experience_graph_record_reasoning",
        {"trigger": "Gateway deploy", "program_id": "growth-test", "swarm_id": swarm_id},
        result,
    )
    assert absorbed is not None
    # First op may not merge yet — simulate richer session
    result2 = {
        "success": True,
        "swarm_id": swarm_id,
        "project_id": "demo-project",
        "mimicry_prompt": "Match handler naming in api/",
    }
    absorbed2 = maybe_absorb_operation_outcome(
        "codebase_mimic",
        {
            "trigger": "Gateway deploy",
            "program_id": "growth-test",
            "swarm_id": swarm_id,
            "project_id": "demo-project",
        },
        result2,
    )
    assert absorbed2 is not None
    assert absorbed2.get("growth_merge") or absorbed2.get("memory")


def test_growth_merge_briefing_operation(swarm_id) -> None:
    MemoryBankStore(swarm_id).store(
        kind="insight",
        title="Growth merge: deploy flow",
        content="Compound growth from experience and patterns.",
        vault="growth",
        topic="merge",
    )
    result = run_operation(
        "growth_merge_briefing",
        query="deploy flow",
        swarm_id=swarm_id,
    )
    assert result.get("success") is True
    assert "growth_briefing" in result
    assert result.get("axes_integrated")
