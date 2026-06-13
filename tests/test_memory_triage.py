"""Tests for human-inspired memory triage primitives."""

from __future__ import annotations

from agentdrive.memory import (
    MemoryTraceCandidate,
    forgetting_curve_strength,
    triage_memory_candidates,
)


def test_forgetting_curve_decays_and_rehearsal_helps() -> None:
    fresh = forgetting_curve_strength(0)
    old = forgetting_curve_strength(14)
    rehearsed_old = forgetting_curve_strength(14, rehearsal_count=5)

    assert fresh == 1.0
    assert old < fresh
    assert rehearsed_old > old


def test_triage_routes_high_relevance_to_working_set() -> None:
    summary = triage_memory_candidates(
        [
            MemoryTraceCandidate(
                item_id="active-brief",
                source="test",
                salience=0.9,
                retrieval_relevance=0.95,
                trust=0.9,
                novelty=0.3,
            )
        ]
    )

    assert summary["queues"]["working_set"][0]["item_id"] == "active-brief"
    assert summary["counts"]["working_set"] == 1


def test_triage_routes_conflict_to_reconsolidation() -> None:
    summary = triage_memory_candidates(
        [
            MemoryTraceCandidate(
                item_id="unstable-memory",
                source="test",
                salience=0.8,
                retrieval_relevance=0.8,
                coherence=0.2,
                contradiction_pressure=0.9,
            )
        ]
    )

    assert summary["queues"]["reconsolidate"][0]["item_id"] == "unstable-memory"
    assert summary["counts"]["reconsolidate"] == 1


def test_triage_routes_novel_salient_low_depth_item_to_consolidation() -> None:
    summary = triage_memory_candidates(
        [
            MemoryTraceCandidate(
                item_id="new-pattern",
                source="test",
                age_days=21,
                salience=0.95,
                retrieval_relevance=0.0,
                coherence=0.75,
                trust=0.9,
                novelty=0.9,
                consolidation_depth=0.0,
            )
        ]
    )

    assert summary["queues"]["consolidate"][0]["item_id"] == "new-pattern"
    assert summary["counts"]["consolidate"] == 1


def test_triage_caps_each_route_and_preserves_schema() -> None:
    candidates = [
        MemoryTraceCandidate(
            item_id=f"active-{i}",
            source="test",
            salience=0.9,
            retrieval_relevance=0.95,
            trust=0.9,
        )
        for i in range(5)
    ]

    summary = triage_memory_candidates(candidates, per_route_limit=2)

    assert summary["model"] == "human-inspired-memory-triage-v1"
    assert set(summary["queues"]) == {
        "working_set",
        "consolidate",
        "reconsolidate",
        "archive",
    }
    assert summary["counts"]["working_set"] == 2
