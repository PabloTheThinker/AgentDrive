"""
scoring — weighted candidate scoring for Deep promotion and REM reinforcement.

Design goals:
- Keep the OpenClaw math recognizable while adapting it to a living Loom.
- Separate raw component calculation from lane choice and storage.
- No new magic — just disciplined composition + Agent Drive / Genome idioms.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from agentdrive.dreaming.candidate import DreamCandidate
from agentdrive.genome.models import Genome


@dataclass
class ScoreWeights:
    """Weights for the six core scoring signals plus dream-specific modifiers."""

    frequency: float = 0.24
    relevance: float = 0.30
    query_diversity: float = 0.15
    recency: float = 0.15
    consolidation: float = 0.10
    conceptual_richness: float = 0.06
    reinforcement: float = 0.10
    adversary_survival_bonus: float = 0.08
    adversary_failure_penalty: float = 0.15


@dataclass
class CandidateScore:
    """Computed score breakdown for one dream candidate."""

    candidate_id: str = ""
    components: dict[str, float] = field(default_factory=dict)
    reinforcement_boost: float = 0.0
    adversary_adjustment: float = 0.0
    total_score: float = 0.0


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def compute_component_scores(
    candidate: DreamCandidate, now: float | None = None
) -> dict[str, float]:
    """Compute the six base signal components for a candidate."""
    now = now or time.time()
    signal_count = max(candidate.occurrence_count, len(candidate.supporting_signals))
    qualities = [
        signal.retrieval_quality
        for signal in candidate.supporting_signals
        if signal.retrieval_quality
    ]
    saliences = [signal.salience for signal in candidate.supporting_signals if signal.salience]
    age_seconds = max(0.0, now - (candidate.updated_at or now))
    recency_half_life = 86_400.0
    components = {
        "frequency": _clamp(math.log1p(signal_count) / math.log1p(12)),
        "relevance": _clamp(
            (sum(qualities) / len(qualities))
            if qualities
            else (sum(saliences) / len(saliences))
            if saliences
            else 0.0
        ),
        "query_diversity": _clamp(
            max(candidate.distinct_contexts, len(candidate.source_substrates)) / 6.0
        ),
        "recency": _clamp(math.exp(-age_seconds / recency_half_life)),
        "consolidation": _clamp(
            (candidate.recurrence_days + len(candidate.source_substrates)) / 8.0
        ),
        "conceptual_richness": _clamp(len(candidate.concepts) / 10.0),
    }
    return components


def compute_reinforcement_boost(candidate: DreamCandidate) -> float:
    """Compute REM reinforcement for a candidate using recency-decayed hits."""
    boost = math.log1p(max(0, candidate.reinforcement_hits)) / math.log1p(10)
    return _clamp(boost)


def score_candidate(
    candidate: DreamCandidate,
    weights: ScoreWeights | None = None,
    now: float | None = None,
) -> CandidateScore:
    """Score a dream candidate and update its cached score fields."""
    weights = weights or ScoreWeights()
    components = compute_component_scores(candidate, now=now)
    base_score = (
        components["frequency"] * weights.frequency
        + components["relevance"] * weights.relevance
        + components["query_diversity"] * weights.query_diversity
        + components["recency"] * weights.recency
        + components["consolidation"] * weights.consolidation
        + components["conceptual_richness"] * weights.conceptual_richness
    )
    reinforcement_boost = compute_reinforcement_boost(candidate) * weights.reinforcement
    adversary_adjustment = -abs(candidate.adversary_penalty)
    total_score = _clamp(base_score + reinforcement_boost + adversary_adjustment, 0.0, 1.0)
    candidate.score_components = components
    candidate.total_score = total_score
    return CandidateScore(
        candidate_id=candidate.candidate_id,
        components=components,
        reinforcement_boost=reinforcement_boost,
        adversary_adjustment=adversary_adjustment,
        total_score=total_score,
    )


def rank_candidates(
    candidates: list[DreamCandidate],
    weights: ScoreWeights | None = None,
    now: float | None = None,
) -> list[DreamCandidate]:
    """Score and sort candidates from strongest to weakest."""
    weights = weights or ScoreWeights()
    ranked: list[DreamCandidate] = []
    for candidate in candidates:
        score = score_candidate(candidate, weights=weights, now=now)
        candidate.score_components = score.components
        candidate.total_score = score.total_score
        ranked.append(candidate)
    ranked.sort(key=lambda item: item.total_score, reverse=True)
    return ranked


def genome_scoring_anchor(genome: Genome | None) -> str:
    """Return a stable Genome anchor for future score backfills."""
    return genome.genome_id if genome else ""
