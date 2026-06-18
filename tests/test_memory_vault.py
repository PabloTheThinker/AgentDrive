"""Tests for AgentDrive Memory Bank vault/topic/anchor/relation/dialogue APIs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentdrive.memory import (
    MemoryBankStore,
    MemoryRelationGraph,
    build_session_anchor,
    import_dialogue_file,
    lexical_bm25_scores,
    rank_memory_candidates,
    resolve_topic,
)
from agentdrive.memory.store import MemoryEntry
from agentdrive.operations.registry import run_operation


@pytest.fixture
def swarm_id(isolated_agentdrive_home):
    return "memory-vault-test-swarm"


def test_memory_entry_ignores_legacy_fields() -> None:
    entry = MemoryEntry.from_dict(
        {
            "memory_id": "mem-1",
            "kind": "episode",
            "title": "Legacy",
            "content": "body",
            "wing": "old-vault",
            "room": "old-topic",
            "source_file": "/tmp/session.jsonl",
            "chunk_index": 2,
            "verbatim": False,
        }
    )
    assert entry.vault == ""
    assert entry.topic == ""
    assert entry.origin_path == ""
    assert entry.shard_index is None
    assert entry.preserves_source is True


def test_search_scoped_by_vault_and_topic(swarm_id) -> None:
    store = MemoryBankStore(swarm_id)
    store.store(
        kind="fact",
        title="Interegy auth",
        content="Uses X-Ren-API-Key header",
        vault="interegy",
        topic="auth",
    )
    store.store(
        kind="fact",
        title="Other project",
        content="Unrelated deployment notes",
        vault="other",
        topic="deploy",
    )
    hits = store.search("auth header", vault="interegy", limit=5)
    assert hits
    assert all(hit.vault in ("interegy", "") for hit in hits)


def test_ranking_prefers_matching_documents() -> None:
    candidates = [
        {"text": "gateway bootstrap key", "signal_score": 1.0},
        {"text": "unrelated gardening tips", "signal_score": 1.0},
    ]
    ranked = rank_memory_candidates(candidates, "gateway bootstrap")
    assert ranked[0][1]["text"].startswith("gateway")


def test_lexical_bm25_scores_nonzero_for_overlap() -> None:
    scores = lexical_bm25_scores("deploy gateway", ["deploy the gateway service", "cats and dogs"])
    assert scores[0] > scores[1]


def test_resolve_topic_from_tags() -> None:
    assert resolve_topic("episode", ["auto-ingest", "claude"]) == "claude"
    assert resolve_topic("fact", []) == "fact"


def test_build_session_anchor_includes_tiers(swarm_id, isolated_agentdrive_home) -> None:
    identity = isolated_agentdrive_home / "identity.txt"
    identity.write_text("## Agent\nTest operator", encoding="utf-8")
    MemoryBankStore(swarm_id).store(
        kind="insight",
        title="Anchor memory",
        content="Essential project context for session start.",
        confidence=0.95,
        vault="test-vault",
    )
    pack = build_session_anchor(swarm_id, vault="test-vault", query="project context")
    assert "Test operator" in pack["anchor_text"]
    assert "Essential memories" in pack["anchor_text"]
    assert pack["tiers"]["agent_brief"]
    assert pack["tiers"]["essential"]
    assert pack["token_estimate"] > 0


def test_memory_bank_anchor_operation(swarm_id) -> None:
    result = run_operation("memory_bank_anchor", swarm_id=swarm_id)
    assert result.get("success") is True
    assert "anchor_text" in result
    assert result.get("operation") == "memory_bank_anchor"


def test_import_dialogue_file_jsonl(swarm_id, tmp_path: Path) -> None:
    dialogue = tmp_path / "session.jsonl"
    dialogue.write_text(
        json.dumps({"role": "user", "content": "Remember to fund xAI credits before deploy."})
        + "\n",
        encoding="utf-8",
    )
    result = import_dialogue_file(dialogue, swarm_id=swarm_id, vault="test-dialogues")
    assert result["imported"] >= 1
    store = MemoryBankStore(swarm_id)
    hits = store.search("xAI credits", vault="test-dialogues")
    assert hits
    assert hits[0].preserves_source is True
    assert hits[0].origin_path == str(dialogue.resolve())


def test_memory_relation_record_and_query(swarm_id) -> None:
    graph = MemoryRelationGraph(swarm_id)
    relation = graph.record("Interegy", "uses_auth", "X-Ren-API-Key")
    assert relation.relation_id.startswith("rel-")
    hits = graph.query("Interegy")
    assert len(hits) == 1
    assert hits[0].predicate == "uses_auth"


def test_memory_relation_expire_operation(swarm_id) -> None:
    run_operation(
        "memory_relation_record",
        subject="Gateway",
        predicate="requires",
        object="credits",
        swarm_id=swarm_id,
    )
    result = run_operation(
        "memory_relation_expire",
        subject="Gateway",
        predicate="requires",
        object="credits",
        swarm_id=swarm_id,
    )
    assert result.get("success") is True
    assert result.get("updated") == 1
    query = run_operation("memory_relation_query", entity="Gateway", swarm_id=swarm_id)
    assert query.get("success") is True
    relations = query.get("relations") or []
    assert relations and relations[0].get("valid_to")
