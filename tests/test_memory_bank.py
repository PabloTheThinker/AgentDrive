"""Tests for AgentDrive Memory Bank."""

from __future__ import annotations

import pytest

from agentdrive.learning.auto_absorb import reset_sessions
from agentdrive.memory import MemoryBankStore, build_deep_briefing, build_memory_briefing
from agentdrive.operations.registry import run_operation


@pytest.fixture(autouse=True)
def _clean_sessions():
    reset_sessions()
    yield
    reset_sessions()


@pytest.fixture
def swarm_id(isolated_agentdrive_home):
    return "stabilization-wave-20260531"


def test_memory_bank_store_and_recall(swarm_id) -> None:
    store = MemoryBankStore(swarm_id)
    entry = store.store(
        kind="fact",
        title="Gateway auth header",
        content="Interegy uses X-Ren-API-Key for bootstrap, not X-Ren-Bootstrap-Key.",
        confidence=0.9,
        source="user",
        tags=["interegy", "auth"],
    )
    assert entry.memory_id.startswith("mem-")
    recalled = store.recall(entry.memory_id)
    assert recalled is not None
    assert recalled.title == "Gateway auth header"


def test_memory_bank_search(swarm_id) -> None:
    store = MemoryBankStore(swarm_id)
    store.store(kind="procedure", title="Deploy flow", content="Fund xAI credits before VPS deploy")
    store.store(kind="fact", title="Unrelated", content="Something else entirely")
    hits = store.search("xAI VPS deploy", limit=5)
    assert hits
    assert any("Deploy" in h.title or "xAI" in h.content for h in hits)


def test_memory_bank_briefing(swarm_id) -> None:
    store = MemoryBankStore(swarm_id)
    store.store(
        kind="insight", title="Test insight", content="Memory bank grows with every session."
    )
    pack = build_memory_briefing(swarm_id, limit=5)
    assert pack["memory_count"] >= 1
    assert "Memory Bank" in pack["briefing"]
    assert pack["integrated_layers"]


def test_memory_bank_store_operation(swarm_id) -> None:
    result = run_operation(
        "memory_bank_store",
        kind="preference",
        title="User prefers Drive terminology",
        content="Use Drive in docs; Pool is internal engine module name.",
        swarm_id=swarm_id,
    )
    assert result.get("success") is True
    memory = result.get("memory") or {}
    assert memory.get("memory_id")


def test_auto_ingest_from_external_parent(swarm_id) -> None:
    branches = [
        {
            "branch_id": "branch:op-1",
            "role": "operator",
            "path_summary": "Fund credits first",
            "robustness_score": 0.9,
        }
    ]
    result = run_operation(
        "external_parent_decision",
        trigger="Memory bank auto ingest test",
        branches=branches,
        collapsed_branch_id="branch:op-1",
        swarm_id=swarm_id,
        reasoning_provider="test",
    )
    assert result.get("success") is True
    auto = result.get("auto_learning") or {}
    mem = auto.get("memory")
    if mem:
        assert mem.get("memory_id")
    store = MemoryBankStore(swarm_id)
    assert store.count() >= 1


def test_deep_briefing_includes_graph_and_memory(swarm_id) -> None:
    MemoryBankStore(swarm_id).store(
        kind="fact",
        title="Deep briefing test",
        content="Unified structural + personal memory.",
    )
    pack = build_deep_briefing(swarm_id, memory_limit=5, max_tokens=500)
    assert "fabric_context_pack" in pack
    assert "memory_bank" in pack
    assert "deep_briefing" in pack
    assert pack["memory_count"] >= 1


def test_learnings_log_writes_memory(swarm_id) -> None:
    result = run_operation(
        "learnings_log",
        key="memory-bank-test",
        insight="Learnings also flow into the deep memory bank.",
        type="operational",
        swarm_id=swarm_id,
    )
    assert result.get("success") is True
    assert result.get("memory") or MemoryBankStore(swarm_id).count() >= 1
