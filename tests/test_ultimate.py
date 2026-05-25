"""Tests for the genome promotion layer.

Covers:
- threshold logic (below/above/idempotent)
- sidecar persistence across registry re-init
- GenomeEvolved event emission on promotion
- is_ultimate flag surfaces through genomes_api.list_genomes
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentdrive.drive.drive import AgentDrive
from agentdrive.events import GenomeEvolved, default_bus, subscribe, unsubscribe
from agentdrive.genome.models import Genome, GenomeManifest
from agentdrive.registry import GenomeRegistry
from agentdrive.ultimate import (
    UltimateForm,
    UltimateRule,
    check_promotion,
    get_ultimate_info,
    is_ultimate,
    promote,
)

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


def _seed_genome(gid: str = "ultimate-test", score: float = 0.9) -> Genome:
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
    """Append `uses` ImprovementEvents so the score history reconstructs."""
    for _ in range(uses):
        g.record_improvement(
            description="seeded high-quality outcome",
            proposed_by="pytest",
            score_delta=0.0,  # score is already at target; deltas of zero
        )
    # Pin the manifest score
    g.manifest.evaluation_score = {"reference_tasks": score_each}


def _seed_pool_uses(pool: AgentDrive, genome: Genome, uses: int) -> None:
    """Drop N 'improvement' entries into pool ingest_log so use-count threshold is met."""
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


def test_check_promotion_returns_none_below_threshold(registry: GenomeRegistry) -> None:
    g = _seed_genome(score=0.9)
    registry.save(g)
    pool = AgentDrive(registry=registry)
    # Only 2 uses → below default min_uses=10
    _seed_pool_uses(pool, g, uses=2)
    _seed_history(g, uses=2, score_each=0.9)
    registry.save(g)

    form = check_promotion(g.genome_id, registry, pool)
    assert form is None


def test_check_promotion_promotes_when_threshold_met(registry: GenomeRegistry) -> None:
    g = _seed_genome(score=0.9)
    registry.save(g)
    pool = AgentDrive(registry=registry)
    _seed_pool_uses(pool, g, uses=12)
    _seed_history(g, uses=12, score_each=0.9)
    registry.save(g)

    form = check_promotion(g.genome_id, registry, pool)
    assert form is not None
    assert isinstance(form, UltimateForm)
    assert form.ultimate_version == "1.0.0-ultimate"
    assert form.genome_id == g.genome_id
    assert form.evidence["uses"] == 12
    assert form.evidence["avg_score"] >= 0.85
    assert len(form.evidence["recent_scores"]) == 3


def test_check_promotion_idempotent_when_already_ultimate(
    registry: GenomeRegistry,
) -> None:
    g = _seed_genome(score=0.9)
    registry.save(g)
    pool = AgentDrive(registry=registry)
    _seed_pool_uses(pool, g, uses=15)
    _seed_history(g, uses=15, score_each=0.9)
    registry.save(g)

    form = check_promotion(g.genome_id, registry, pool)
    assert form is not None
    promote(form, registry)

    # Second call: already ultimate → None
    again = check_promotion(g.genome_id, registry, pool)
    assert again is None


def test_promote_writes_sidecar_and_survives_restart(
    registry: GenomeRegistry, isolated_savant_home: Path
) -> None:
    g = _seed_genome(score=0.92)
    registry.save(g)
    pool = AgentDrive(registry=registry)
    _seed_pool_uses(pool, g, uses=11)
    _seed_history(g, uses=11, score_each=0.92)
    registry.save(g)

    form = check_promotion(g.genome_id, registry, pool)
    assert form is not None
    sidecar = promote(form, registry)
    assert sidecar.is_file()
    assert sidecar.name == "ultimate.json"

    # Re-init the registry from scratch — sidecar must still flag ultimate.
    fresh = GenomeRegistry()
    assert is_ultimate(g.genome_id, fresh) is True

    info = get_ultimate_info(g.genome_id, fresh)
    assert info is not None
    assert info.ultimate_version == "1.0.0-ultimate"
    assert info.genome_id == g.genome_id
    assert info.evidence.get("uses") == 11


def test_genome_evolved_event_emitted_on_promotion(
    registry: GenomeRegistry, clean_bus: None
) -> None:
    from agentdrive.harness.harness import Harness

    g = _seed_genome(gid="evolved-test", score=0.5)
    registry.save(g)
    pool = AgentDrive(registry=registry)
    # Pre-seed many improvement uses so harness only needs to push it over.
    _seed_pool_uses(pool, g, uses=15)
    _seed_history(g, uses=15, score_each=0.9)
    registry.save(g)

    harness = Harness(agent_id="evo-pytest", pool=pool)
    harness.pulled_dna = [{"genome_id": g.genome_id, "score": 0.9}]

    evolved: list[GenomeEvolved] = []
    token = subscribe(evolved.append, event_types=[GenomeEvolved])
    try:
        harness.record_outcome(
            {
                "status": "success",
                "quality": 0.95,
                "used_genomes": [g.genome_id],
                "task": "evolve me",
            }
        )
    finally:
        unsubscribe(token)

    assert len(evolved) >= 1, f"expected GenomeEvolved emission, got {len(evolved)}"
    evt = evolved[0]
    assert evt.genome_id.startswith("evolved-test")
    assert "ultimate" in evt.ultimate_version
    assert evt.evidence.get("uses", 0) >= 10


def test_genomes_api_list_includes_ultimate_flag(registry: GenomeRegistry) -> None:
    from agentdrive import genomes_api

    g = _seed_genome(gid="api-test", score=0.92)
    registry.save(g)

    # Pre-promote
    form = UltimateForm(
        genome_id=g.genome_id,
        ultimate_version="1.0.0-ultimate",
        evidence={"uses": 11, "avg_score": 0.92, "recent_scores": [0.92, 0.92, 0.92]},
    )
    promote(form, registry)

    entries = genomes_api.list_genomes(registry=registry)
    assert len(entries) >= 1
    by_id = {e.id: e for e in entries}
    assert "api-test" in by_id
    e = by_id["api-test"]
    assert e.is_ultimate is True
    assert e.ultimate_version == "1.0.0-ultimate"


def test_promotion_blocked_by_low_confidence_stars(
    isolated_savant_home, registry, clean_bus
) -> None:
    """A genome must NOT promote until confidence stars have caught up.

    Even when uses + avg_score satisfy the rule, the confidence-stars gate
    must hold the promotion until the encounter-based rating crosses
    UltimateRule.min_confidence_stars (default 3).
    """
    import json

    from agentdrive.confidence import (
        SIDECAR_NAME,
        _resolve_genome_dir,
        get_rating,
    )
    from agentdrive.ultimate import check_promotion

    # Seed a genome that passes the basic promotion thresholds.
    g = _seed_genome("promotion-candidate", score=0.9)
    registry.save(g)
    pool = AgentDrive(registry=registry)
    _seed_pool_uses(pool, g, uses=12)
    _seed_history(g, uses=12, score_each=0.9)
    registry.save(g)

    # Manually write a low-star confidence sidecar (1 star) to simulate
    # the encounter-based rating lagging the score-based path.
    gdir = _resolve_genome_dir(g.genome_id, registry)
    assert gdir is not None
    sidecar = gdir / SIDECAR_NAME
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(
        json.dumps(
            {
                "stars": 1,
                "encounters": 5,
                "success_rate": 0.6,
                "avg_score": 0.9,
                "last_used": "2026-05-24T00:00:00+00:00",
            }
        )
    )

    rating = get_rating(g.genome_id, registry)
    assert rating is not None and rating.stars < 3

    # Default rule has min_confidence_stars=3 — gate must hold.
    rule = UltimateRule()
    form = check_promotion(g.genome_id, registry, pool, rule)
    assert form is None, (
        f"promotion fired despite only {rating.stars}★ confidence "
        "(violates min_confidence_stars=3 gate)"
    )
