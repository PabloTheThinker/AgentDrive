"""Tests for the encounter-graded confidence layer.

Covers:
- zero outcomes → zero stars
- threshold table behaviour
- failures dragging success_rate down
- sidecar survives registry restart
- ConfidenceUpdated event fires from harness.record_outcome
- genomes_api exposes confidence_stars + encounter_count
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentdrive.confidence import (
    ConfidenceRating,
    compute_rating,
    get_rating,
    update,
)
from agentdrive.drive.drive import AgentDrive
from agentdrive.events import ConfidenceUpdated, default_bus, subscribe, unsubscribe
from agentdrive.genome.models import Genome, GenomeManifest
from agentdrive.registry import GenomeRegistry

# ─────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def clean_bus() -> Iterator[None]:
    """Snapshot + restore default_bus subscribers around each test."""
    with default_bus._lock:  # type: ignore[attr-defined]
        saved = list(default_bus._subs)  # type: ignore[attr-defined]
        default_bus._subs.clear()  # type: ignore[attr-defined]
    try:
        yield
    finally:
        with default_bus._lock:  # type: ignore[attr-defined]
            default_bus._subs = saved  # type: ignore[attr-defined]


def _seed_genome(gid: str = "confidence-test", score: float = 0.9) -> Genome:
    manifest = GenomeManifest(
        id=gid,
        version="1.0.0",
        content_hash="sha256:" + "deadbeef" * 8,
        created=datetime.now(UTC),
        authors=[],
        evaluation_score={"reference_tasks": score},
    )
    g = Genome(manifest=manifest, framework={"steps": [{"id": "1", "name": "test"}]})
    g.finalize()
    return g


def _seed_history(g: Genome, uses: int, score_each: float) -> None:
    for _ in range(uses):
        g.record_improvement(
            description="seeded outcome",
            proposed_by="pytest",
            score_delta=0.0,
        )
    g.manifest.evaluation_score = {"reference_tasks": score_each}


def _seed_pool_uses(pool: AgentDrive, genome: Genome, uses: int) -> None:
    import json
    import time

    for _ in range(uses):
        entry = {
            "timestamp": time.time(),
            "genome_id": genome.genome_id,
            "source": "improvement",
            "actor": "pytest",
            "path": str(pool.registry.root / genome.manifest.id),
        }
        pool._ingest_log.append(entry)
        with open(pool.ingest_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")


# ─────────────────────────────────────────────────────────────────────
# tests
# ─────────────────────────────────────────────────────────────────────


def test_no_outcomes_returns_zero_stars(registry: GenomeRegistry) -> None:
    # Brand-new genome, no history, no pool log.
    g = _seed_genome(score=0.0)
    registry.save(g)
    pool = AgentDrive(registry=registry)

    rating = compute_rating(g.genome_id, registry, pool=pool)
    assert isinstance(rating, ConfidenceRating)
    assert rating.stars == 0
    assert rating.encounters == 0
    assert rating.success_rate == 0.0


def test_thresholds_match_rule(registry: GenomeRegistry) -> None:
    g = _seed_genome(gid="threshold-test", score=0.9)
    registry.save(g)
    pool = AgentDrive(registry=registry)

    # 3 encounters at score 0.9 → success_rate 1.0 → 1 star tier (>=3, >=0.6)
    _seed_pool_uses(pool, g, uses=3)
    _seed_history(g, uses=3, score_each=0.9)
    registry.save(g)
    r3 = compute_rating(g.genome_id, registry, pool=pool)
    assert r3.stars == 1
    assert r3.encounters >= 3

    # Step up: 10 encounters → 2 star tier (>=10, >=0.7)
    g2 = _seed_genome(gid="threshold-test-10", score=0.9)
    registry.save(g2)
    _seed_pool_uses(pool, g2, uses=10)
    _seed_history(g2, uses=10, score_each=0.9)
    registry.save(g2)
    r10 = compute_rating(g2.genome_id, registry, pool=pool)
    assert r10.stars == 2

    # 100 encounters → 5 star tier
    g100 = _seed_genome(gid="threshold-test-100", score=0.9)
    registry.save(g100)
    _seed_pool_uses(pool, g100, uses=100)
    _seed_history(g100, uses=100, score_each=0.9)
    registry.save(g100)
    r100 = compute_rating(g100.genome_id, registry, pool=pool)
    assert r100.stars == 5


def test_failures_drag_success_rate(registry: GenomeRegistry) -> None:
    """Below the success threshold each entry counts as a failure.

    Seed score 0.3 across 10 encounters → success_rate 0.0 → 0 stars even
    though encounter count would clear the 2-star encounter bar.
    """
    g = _seed_genome(gid="fail-test", score=0.3)
    registry.save(g)
    pool = AgentDrive(registry=registry)
    _seed_pool_uses(pool, g, uses=10)
    _seed_history(g, uses=10, score_each=0.3)
    registry.save(g)

    rating = compute_rating(g.genome_id, registry, pool=pool)
    assert rating.encounters >= 10
    assert rating.success_rate == 0.0
    assert rating.stars == 0


def test_sidecar_survives_restart(registry: GenomeRegistry, isolated_savant_home: Path) -> None:
    g = _seed_genome(gid="sidecar-test", score=0.9)
    registry.save(g)
    pool = AgentDrive(registry=registry)
    _seed_pool_uses(pool, g, uses=12)
    _seed_history(g, uses=12, score_each=0.9)
    registry.save(g)

    written = update(g.genome_id, registry, pool=pool)
    assert written is not None
    assert written.stars >= 2

    # Re-init the registry from scratch — sidecar must still be readable.
    fresh = GenomeRegistry()
    rating = get_rating(g.genome_id, fresh)
    assert rating is not None
    assert rating.stars == written.stars
    assert rating.encounters == written.encounters


def test_confidence_updated_event_emitted(registry: GenomeRegistry, clean_bus: None) -> None:
    from agentdrive.harness.harness import Harness

    g = _seed_genome(gid="event-test", score=0.5)
    registry.save(g)
    pool = AgentDrive(registry=registry)
    # Pre-seed enough encounters that the harness's single outcome pushes us
    # into a non-zero star tier and produces a recomputed rating.
    _seed_pool_uses(pool, g, uses=10)
    _seed_history(g, uses=10, score_each=0.9)
    registry.save(g)

    harness = Harness(agent_id="conf-pytest", pool=pool)
    harness.pulled_dna = [{"genome_id": g.genome_id, "score": 0.9}]

    captured: list[ConfidenceUpdated] = []
    token = subscribe(captured.append, event_types=[ConfidenceUpdated])
    try:
        harness.record_outcome(
            {
                "status": "success",
                "quality": 0.95,
                "used_genomes": [g.genome_id],
                "task": "rate me",
            }
        )
    finally:
        unsubscribe(token)

    assert len(captured) >= 1
    evt = captured[0]
    assert evt.genome_id.startswith("event-test")
    assert evt.encounters >= 10


def test_genomes_api_includes_stars_and_encounters(
    registry: GenomeRegistry,
) -> None:
    from agentdrive import genomes_api

    g = _seed_genome(gid="api-conf-test", score=0.9)
    registry.save(g)
    pool = AgentDrive(registry=registry)
    _seed_pool_uses(pool, g, uses=15)
    _seed_history(g, uses=15, score_each=0.9)
    registry.save(g)

    rating = update(g.genome_id, registry, pool=pool)
    assert rating is not None and rating.stars >= 2

    entries = genomes_api.list_genomes(registry=registry)
    by_id = {e.id: e for e in entries}
    assert "api-conf-test" in by_id
    e = by_id["api-conf-test"]
    assert e.confidence_stars == rating.stars
    assert e.encounter_count == rating.encounters
