"""Memory triage primitives for AgentDrive context packs.

This module gives AgentDrive a small control layer inspired by three stable
findings from human and LLM memory work:

- working memory is capacity-limited and should be actively selected;
- durable memory improves through rehearsal/consolidation rather than raw append;
- retrieval can reopen a memory for update when it conflicts with current evidence.

The implementation is deliberately deterministic and dependency-free so it can
run inside MCP, tests, and local model loops without introducing a model call.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def forgetting_curve_strength(
    age_days: float,
    *,
    rehearsal_count: int = 0,
    half_life_days: float = 7.0,
) -> float:
    """Return an Ebbinghaus-style retention signal in the 0..1 range.

    Rehearsal extends the half-life logarithmically. That keeps repeated access
    valuable without allowing a noisy item to become immortal solely by being
    retrieved many times.
    """
    age = max(0.0, float(age_days))
    half_life = max(0.25, float(half_life_days))
    rehearsal_boost = 1.0 + math.log1p(max(0, int(rehearsal_count)))
    return round(math.exp(-age / (half_life * rehearsal_boost)), 4)


@dataclass(frozen=True)
class MemoryTraceCandidate:
    """One graph/genome/learning candidate to route through memory control."""

    item_id: str
    source: str
    memory_kind: str = "episodic"
    age_days: float = 0.0
    rehearsal_count: int = 0
    salience: float = 0.5
    retrieval_relevance: float = 0.5
    coherence: float = 0.5
    trust: float = 0.7
    novelty: float = 0.3
    contradiction_pressure: float = 0.0
    consolidation_depth: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryTriageResult:
    """Scored routing decision for a memory candidate."""

    item_id: str
    source: str
    memory_kind: str
    route: str
    retention_strength: float
    working_score: float
    consolidation_score: float
    reconsolidation_score: float
    why: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _score_candidate(candidate: MemoryTraceCandidate) -> MemoryTriageResult:
    retention = forgetting_curve_strength(
        candidate.age_days,
        rehearsal_count=candidate.rehearsal_count,
    )
    salience = _clamp(candidate.salience)
    relevance = _clamp(candidate.retrieval_relevance)
    coherence = _clamp(candidate.coherence)
    trust = _clamp(candidate.trust)
    novelty = _clamp(candidate.novelty)
    contradiction = _clamp(candidate.contradiction_pressure)
    consolidation_depth = _clamp(candidate.consolidation_depth)

    working = (
        0.36 * relevance
        + 0.24 * salience
        + 0.18 * retention
        + 0.12 * trust
        + 0.10 * novelty
    )
    consolidation = (
        0.30 * salience
        + 0.24 * novelty
        + 0.20 * trust
        + 0.16 * (1.0 - consolidation_depth)
        + 0.10 * coherence
    )
    reconsolidation = (
        0.36 * contradiction
        + 0.24 * (1.0 - coherence)
        + 0.18 * relevance
        + 0.12 * salience
        + 0.10 * retention
    )

    if reconsolidation >= 0.62 and (contradiction >= 0.35 or coherence <= 0.55):
        route = "reconsolidate"
        why = "retrieved item is important but unstable or conflicting; reopen and update before reuse"
    elif working >= 0.66:
        route = "working_set"
        why = "high relevance and salience; keep in the active context budget"
    elif consolidation >= 0.62:
        route = "consolidate"
        why = "high-signal material has not yet earned durable abstraction"
    else:
        route = "archive"
        why = "low immediate utility; keep addressable but out of scarce context"

    return MemoryTriageResult(
        item_id=candidate.item_id,
        source=candidate.source,
        memory_kind=candidate.memory_kind,
        route=route,
        retention_strength=retention,
        working_score=round(working, 4),
        consolidation_score=round(consolidation, 4),
        reconsolidation_score=round(reconsolidation, 4),
        why=why,
        metadata=dict(candidate.metadata),
    )


def triage_memory_candidates(
    candidates: list[MemoryTraceCandidate],
    *,
    per_route_limit: int = 4,
) -> dict[str, Any]:
    """Route memory candidates into queues consumed by agents and consolidators."""
    scored = [_score_candidate(c) for c in candidates]
    route_priority = {
        "working_set": 3,
        "reconsolidate": 2,
        "consolidate": 1,
        "archive": 0,
    }
    scored.sort(
        key=lambda r: (
            route_priority.get(r.route, 0),
            max(r.working_score, r.consolidation_score, r.reconsolidation_score),
        ),
        reverse=True,
    )

    queues: dict[str, list[dict[str, Any]]] = {
        "working_set": [],
        "consolidate": [],
        "reconsolidate": [],
        "archive": [],
    }
    for result in scored:
        queue = queues[result.route]
        if len(queue) < per_route_limit:
            queue.append(result.to_dict())

    return {
        "model": "human-inspired-memory-triage-v1",
        "principles": [
            "limited working context",
            "rehearsal-sensitive retention",
            "salience-weighted consolidation",
            "retrieval-triggered reconsolidation for conflict",
        ],
        "queues": queues,
        "counts": {name: len(items) for name, items in queues.items()},
    }
