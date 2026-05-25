"""Encounter-graded confidence — explicit trust scoring for genomes.

The flat-score model treats a genome used 3 times and one used 50 times at
the same average as equally trustworthy. They are not. This module replaces
that implicit model with an explicit star rating (0-5) derived from BOTH
encounter count AND success rate. A success is an outcome whose score >=
SUCCESS_THRESHOLD (default 0.6).

Confidence is *parallel* to ultimate promotion, not a replacement:
- ``ultimate.py`` answers "is this genome proven world-class?"
- ``confidence.py`` answers "how much do we trust the signal we have?"

Both write sidecars into the genome directory and both fire on the same
``record_outcome`` trigger site in the harness. Confidence updates every
encounter; ultimate promotion is a one-shot threshold crossing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentdrive.drive.drive import AgentDrive
    from agentdrive.registry import GenomeRegistry

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────


SUCCESS_THRESHOLD: float = 0.6
SIDECAR_NAME: str = "confidence.json"


def _default_thresholds() -> list[tuple[int, float]]:
    """Each tuple is (min_encounters, min_success_rate) to earn that tier.

    Index 0 → 1 star, index 4 → 5 stars. A genome earns the highest tier
    whose (encounters, success_rate) pair it meets or exceeds.
    """
    return [
        (3, 0.6),
        (10, 0.7),
        (25, 0.75),
        (50, 0.8),
        (100, 0.85),
    ]


@dataclass(frozen=True)
class ConfidenceRule:
    """Tunable thresholds for the star tiers."""

    stars_thresholds: list[tuple[int, float]] = field(default_factory=_default_thresholds)
    success_threshold: float = SUCCESS_THRESHOLD


# ─────────────────────────────────────────────────────────────────────
# Data
# ─────────────────────────────────────────────────────────────────────


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class ConfidenceRating:
    """Persisted confidence snapshot for a single genome."""

    stars: int = 0
    encounters: int = 0
    success_rate: float = 0.0
    avg_score: float = 0.0
    last_used: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)

    @classmethod
    def from_json(cls, data: str | bytes) -> ConfidenceRating:
        raw = json.loads(data)
        return cls(
            stars=int(raw.get("stars", 0) or 0),
            encounters=int(raw.get("encounters", 0) or 0),
            success_rate=float(raw.get("success_rate", 0.0) or 0.0),
            avg_score=float(raw.get("avg_score", 0.0) or 0.0),
            last_used=str(raw.get("last_used", "") or ""),
        )


# ─────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────


def _resolve_genome_dir(genome_id: str, registry: GenomeRegistry) -> Path | None:
    """Locate the on-disk genome directory regardless of id/version form."""
    # Direct registry hits
    for candidate in (
        genome_id,
        genome_id.split("@", 1)[0] if "@" in genome_id else genome_id,
    ):
        p = registry.get_genome_path(candidate)
        if p and p.is_dir():
            return p

    base = genome_id.split("@", 1)[0]
    try:
        for d in registry.list_genome_details():
            if genome_id in (d.get("dir_name"), d.get("genome_id"), d.get("id")):
                p = registry.root / d["dir_name"]
                if p.is_dir():
                    return p
            if d.get("id") == base:
                p = registry.root / d["dir_name"]
                if p.is_dir():
                    return p
    except Exception:
        logger.debug("Failed to walk registry for %s", genome_id, exc_info=True)
    return None


def _matches_genome(entry_id: str, target: str) -> bool:
    if not entry_id or not target:
        return False
    return entry_id.split("@", 1)[0] == target.split("@", 1)[0]


def _collect_score_series(
    genome_id: str,
    registry: GenomeRegistry,
) -> list[float]:
    """Reconstruct a per-encounter score series for this genome.

    Walks the genome's own provenance (ImprovementEvent list, each with a
    score_delta) so the series survives restarts without a schema change.
    """
    scores: list[float] = []
    try:
        g = registry.get_genome(genome_id) or registry.load(genome_id)
        if g is None:
            return scores
        current = float((g.manifest.evaluation_score or {}).get("reference_tasks", 0.0) or 0.0)
        improvements = list(g.provenance.improvements or [])
        running = current
        walked: list[float] = []
        for ev in reversed(improvements):
            walked.append(round(running, 4))
            delta = float(ev.score_delta or 0.0)
            running -= delta
        walked.reverse()
        if walked:
            scores = walked
        elif current > 0.0:
            scores = [round(current, 4)]
    except Exception:
        logger.debug("Failed to reconstruct score series for %s", genome_id, exc_info=True)
    return scores


def _count_pool_encounters(genome_id: str, pool: AgentDrive | None) -> int:
    """Count entries in the Drive's ingest log that came from a successful
    harness run (source contains 'improvement') and belong to this genome.
    """
    if pool is None:
        return 0
    try:
        return sum(
            1
            for entry in (getattr(pool, "_ingest_log", []) or [])
            if _matches_genome(str(entry.get("genome_id", "")), genome_id)
            and "improvement" in str(entry.get("source", "")).lower()
        )
    except Exception:
        logger.debug("Failed to scan pool ingest log", exc_info=True)
        return 0


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────


def compute_rating(
    genome_id: str,
    registry: GenomeRegistry,
    pool: AgentDrive | None = None,
    rule: ConfidenceRule | None = None,
) -> ConfidenceRating:
    """Pure function: compute the current confidence rating for a genome.

    Encounter count is the MAX of (pool ingest-log entries, score series
    length) so we don't undercount when one source is empty (e.g. tests
    that seed only one of the two).
    """
    rule = rule or ConfidenceRule()

    scores = _collect_score_series(genome_id, registry)
    pool_uses = _count_pool_encounters(genome_id, pool)
    encounters = max(len(scores), pool_uses)

    if encounters <= 0 or not scores:
        return ConfidenceRating(
            stars=0,
            encounters=encounters,
            success_rate=0.0,
            avg_score=0.0,
            last_used=_utc_now_iso(),
        )

    successes = sum(1 for s in scores if s >= rule.success_threshold)
    # If pool reports more encounters than the score series, treat the extras
    # as observations we can't grade — they pad encounters but don't
    # contribute to success_rate. Use the score series as the basis instead.
    rate_basis = len(scores)
    success_rate = successes / rate_basis if rate_basis else 0.0
    avg_score = sum(scores) / len(scores)

    stars = 0
    for tier_idx, (min_enc, min_rate) in enumerate(rule.stars_thresholds, start=1):
        if encounters >= min_enc and success_rate >= min_rate:
            stars = tier_idx

    return ConfidenceRating(
        stars=stars,
        encounters=encounters,
        success_rate=round(success_rate, 4),
        avg_score=round(avg_score, 4),
        last_used=_utc_now_iso(),
    )


def get_rating(genome_id: str, registry: GenomeRegistry) -> ConfidenceRating | None:
    """Read the persisted ConfidenceRating sidecar, or None if absent."""
    gdir = _resolve_genome_dir(genome_id, registry)
    if gdir is None:
        return None
    sidecar = gdir / SIDECAR_NAME
    if not sidecar.is_file():
        return None
    try:
        return ConfidenceRating.from_json(sidecar.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Failed to read confidence sidecar at %s", sidecar, exc_info=True)
        return None


def update(
    genome_id: str,
    registry: GenomeRegistry,
    pool: AgentDrive | None = None,
    rule: ConfidenceRule | None = None,
) -> ConfidenceRating | None:
    """Recompute the rating, write the sidecar, return the new rating.

    Returns None if the genome dir can't be resolved (e.g. genome was
    deleted between the outcome and the update).
    """
    rating = compute_rating(genome_id, registry, pool=pool, rule=rule)
    gdir = _resolve_genome_dir(genome_id, registry)
    if gdir is None:
        return None
    sidecar = gdir / SIDECAR_NAME
    try:
        sidecar.write_text(rating.to_json(), encoding="utf-8")
    except Exception:
        logger.warning("Failed to write confidence sidecar at %s", sidecar, exc_info=True)
        return None
    return rating


__all__ = [
    "ConfidenceRating",
    "ConfidenceRule",
    "SUCCESS_THRESHOLD",
    "SIDECAR_NAME",
    "compute_rating",
    "get_rating",
    "update",
]
