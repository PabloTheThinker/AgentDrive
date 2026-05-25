"""Genome promotion — automatic validation tier for proven genomes.

When a genome accumulates enough successful uses *and* maintains a high
average score, it gets promoted: a derived, validated marker on the
genome that surfaces everywhere genomes are listed.

The promotion is non-destructive:
- We do NOT fork the genome directory.
- We write an `ultimate.json` sidecar inside the existing genome dir.
- We bump a synthetic `ultimate_version` (e.g. "1.0.0-ultimate") for display.
- The Genome manifest is untouched, so schema/migration is a non-event.

The trigger lives in `harness.record_outcome` (right after PoolOutcome emit).
Readers (`genomes_api`, CLI, chat) consult `is_ultimate()` / `get_ultimate_info()`
to render the badge.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agentdrive.drive.drive import AgentDrive
    from agentdrive.registry import GenomeRegistry

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class UltimateRule:
    """Promotion rule. Defaults: a genome must be used N times AND maintain
    an average score above the threshold over the last K outcomes.
    """

    min_uses: int = 10
    min_avg_score: float = 0.85
    min_recent_outcomes: int = 3  # avg is computed over the last N outcomes
    # Confidence gate. Promotion requires the genome already to have
    # earned at least this many confidence stars — prevents the visible
    # contradiction of a "★☆☆☆☆ ◆ PROMOTED" entry that gets there via
    # the score path before the encounter-count path catches up.
    min_confidence_stars: int = 3


# ─────────────────────────────────────────────────────────────────────
# Data
# ─────────────────────────────────────────────────────────────────────


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class UltimateForm:
    """An evolved marker for a genome. Persisted as a sidecar."""

    genome_id: str
    ultimate_version: str  # e.g. "1.0.0-ultimate"
    promoted_at: str = field(default_factory=_utc_now_iso)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)

    @classmethod
    def from_json(cls, data: str | bytes) -> UltimateForm:
        raw = json.loads(data)
        return cls(
            genome_id=raw["genome_id"],
            ultimate_version=raw["ultimate_version"],
            promoted_at=raw.get("promoted_at") or _utc_now_iso(),
            evidence=dict(raw.get("evidence") or {}),
        )


SIDECAR_NAME = "ultimate.json"


# ─────────────────────────────────────────────────────────────────────
# Internal: locating the genome dir + counting uses/scores
# ─────────────────────────────────────────────────────────────────────


def _resolve_genome_dir(genome_id: str, registry: GenomeRegistry) -> Path | None:
    """Find the on-disk directory for a genome regardless of whether the
    caller passed `id`, `id@ver`, or the directory name itself.
    """
    # Direct hits via registry
    for candidate in (genome_id, genome_id.split("@", 1)[0] if "@" in genome_id else genome_id):
        p = registry.get_genome_path(candidate)
        if p and p.is_dir():
            return p

    # Walk the registry to find a matching one
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
        pass
    return None


def _matches_genome(entry_id: str, target: str) -> bool:
    """A pool ingest_log entry is for our genome if the base id matches."""
    if not entry_id or not target:
        return False
    return entry_id.split("@", 1)[0] == target.split("@", 1)[0]


def _count_uses_and_scores(
    genome_id: str,
    registry: GenomeRegistry,
    pool: AgentDrive | None,
) -> tuple[int, list[float]]:
    """Returns (uses, recent_score_series).

    `uses` counts entries in the Drive's ingest log that belong to this
    genome and originated from a successful run (source="improvement").
    `recent_score_series` is reconstructed from the genome's own
    ImprovementEvent provenance (each carries a score_delta) walking
    backward from the current manifest score. This keeps state-of-truth
    on disk (survives restarts) without a schema change.
    """
    uses = 0
    if pool is not None:
        try:
            for entry in getattr(pool, "_ingest_log", []) or []:
                if _matches_genome(str(entry.get("genome_id", "")), genome_id):
                    if "improvement" in str(entry.get("source", "")).lower():
                        uses += 1
        except Exception:
            logger.debug("Failed to scan pool ingest log", exc_info=True)

    # Reconstruct score history from provenance
    scores: list[float] = []
    try:
        g = registry.get_genome(genome_id) or registry.load(genome_id)
        if g is not None:
            current = float((g.manifest.evaluation_score or {}).get("reference_tasks", 0.0) or 0.0)
            # newest first
            improvements = list(g.provenance.improvements or [])
            # Walk backward: scores[i] is value AFTER improvement i applied.
            running = current
            walked: list[float] = []
            for ev in reversed(improvements):
                walked.append(round(running, 4))
                delta = float(ev.score_delta or 0.0)
                running -= delta
            walked.reverse()  # oldest first
            if walked:
                scores = walked
            elif current > 0.0:
                # No improvement events but a non-zero score: count as one observation
                scores = [round(current, 4)]
    except Exception:
        logger.debug("Failed to reconstruct score series", exc_info=True)

    return uses, scores


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────


def is_ultimate(genome_id: str, registry: GenomeRegistry) -> bool:
    """Cheap predicate: does the sidecar exist?"""
    gdir = _resolve_genome_dir(genome_id, registry)
    if gdir is None:
        return False
    return (gdir / SIDECAR_NAME).is_file()


def get_ultimate_info(genome_id: str, registry: GenomeRegistry) -> UltimateForm | None:
    """Load and return the persisted UltimateForm, or None."""
    gdir = _resolve_genome_dir(genome_id, registry)
    if gdir is None:
        return None
    sidecar = gdir / SIDECAR_NAME
    if not sidecar.is_file():
        return None
    try:
        return UltimateForm.from_json(sidecar.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Failed to read ultimate sidecar at %s", sidecar, exc_info=True)
        return None


def check_promotion(
    genome_id: str,
    registry: GenomeRegistry,
    pool: AgentDrive | None = None,
    rule: UltimateRule | None = None,
) -> UltimateForm | None:
    """Pure function: should this genome be promoted right now?

    Returns an UltimateForm to apply, or None if the rule isn't met or
    the genome is already ultimate. Does NOT mutate disk.
    """
    rule = rule or UltimateRule()

    # Already evolved → nothing to do.
    if is_ultimate(genome_id, registry):
        return None

    g = None
    try:
        g = registry.get_genome(genome_id) or registry.load(genome_id)
    except Exception:
        g = None
    if g is None:
        return None

    uses, scores = _count_uses_and_scores(genome_id, registry, pool)

    if uses < rule.min_uses:
        return None
    if len(scores) < rule.min_recent_outcomes:
        return None

    recent = scores[-rule.min_recent_outcomes :]
    avg = sum(recent) / len(recent) if recent else 0.0
    if avg < rule.min_avg_score:
        return None

    # Confidence-stars gate. Block promotion until the encounter-based
    # confidence rating has caught up; otherwise we ship a genome that
    # renders as "★☆☆☆☆ ◆ PROMOTED" which reads as broken.
    try:
        from agentdrive.confidence import get_rating as _get_rating

        rating = _get_rating(genome_id, registry)
        if rating is not None and rating.stars < rule.min_confidence_stars:
            return None
    except Exception:
        logger.debug("confidence lookup failed for %s", genome_id, exc_info=True)

    base_version = g.manifest.version
    ultimate_version = f"{base_version}-ultimate"

    return UltimateForm(
        genome_id=g.genome_id,
        ultimate_version=ultimate_version,
        evidence={
            "uses": uses,
            "avg_score": round(avg, 4),
            "recent_scores": [round(s, 4) for s in recent],
            "rule": {
                "min_uses": rule.min_uses,
                "min_avg_score": rule.min_avg_score,
                "min_recent_outcomes": rule.min_recent_outcomes,
                "min_confidence_stars": rule.min_confidence_stars,
            },
        },
    )


def promote(form: UltimateForm, registry: GenomeRegistry) -> Path:
    """Persist the ultimate marker as a sidecar in the genome's directory.

    Returns the path to the written sidecar. Idempotent: re-promoting an
    already-promoted genome overwrites the sidecar (useful for refresh).
    """
    gdir = _resolve_genome_dir(form.genome_id, registry)
    if gdir is None:
        raise FileNotFoundError(
            f"Cannot promote: no on-disk directory for genome {form.genome_id!r} "
            f"under registry root {registry.root}"
        )
    sidecar = gdir / SIDECAR_NAME
    sidecar.write_text(form.to_json(), encoding="utf-8")
    return sidecar


__all__ = [
    "UltimateRule",
    "UltimateForm",
    "check_promotion",
    "promote",
    "is_ultimate",
    "get_ultimate_info",
    "SIDECAR_NAME",
]
