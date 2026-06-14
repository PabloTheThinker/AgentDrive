"""Tests for agentdrive.genomes_api (Pattern 5 genome operations)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from agentdrive import genomes_api
from agentdrive.drive.drive import AgentDrive, DriveQuery
from agentdrive.genome.models import Genome, GenomeManifest
from agentdrive.registry import GenomeRegistry


def _seed_genome(
    gid: str = "api-test-genome",
    *,
    score: float = 0.85,
    domains: list[str] | None = None,
) -> Genome:
    manifest = GenomeManifest(
        id=gid,
        version="1.0.0",
        content_hash="sha256:" + "cafebabe" * 8,
        created=datetime.now(UTC),
        authors=[],
        evaluation_score={"reference_tasks": score},
        applicability={"domains": domains or ["testing"], "problem_signatures": []},
    )
    g = Genome(
        manifest=manifest,
        framework={"steps": [{"id": "1", "name": "analyze", "description": "Run checks"}]},
    )
    g.finalize()
    return g


def test_list_genomes_returns_registered_entries(registry: GenomeRegistry) -> None:
    g = _seed_genome(gid="list-api-test", score=0.9, domains=["security"])
    registry.save(g)

    entries = genomes_api.list_genomes(registry=registry)

    by_id = {e.id: e for e in entries}
    assert "list-api-test" in by_id
    entry = by_id["list-api-test"]
    assert entry.version == "1.0.0"
    assert "security" in entry.domains
    assert entry.score == pytest.approx(0.9)
    assert entry.num_steps == 1


def test_get_genome_missing_returns_none(registry: GenomeRegistry) -> None:
    assert genomes_api.get_genome("does-not-exist", registry=registry) is None


def test_search_genomes_with_mock_pool(registry: GenomeRegistry) -> None:
    g = _seed_genome(gid="search-hit", score=0.77, domains=["incident-response"])
    registry.save(g)

    pool = MagicMock()
    pool.query.return_value = [g]
    pool.registry = registry

    matches = genomes_api.search_genomes("security incident postmortem", pool=pool)

    pool.query.assert_called_once()
    call_arg = pool.query.call_args[0][0]
    assert isinstance(call_arg, DriveQuery)
    assert call_arg.task_description == "security incident postmortem"
    assert call_arg.limit == 5

    assert len(matches) == 1
    m = matches[0]
    assert m.id == "search-hit"
    assert m.genome_id == g.genome_id
    assert m.score == pytest.approx(0.77)
    assert "incident-response" in m.domains


def test_search_genomes_with_real_pool(registry: GenomeRegistry) -> None:
    g = _seed_genome(gid="real-search-hit", score=0.6, domains=["testing"])
    registry.save(g)
    pool = AgentDrive(registry=registry)

    matches = genomes_api.search_genomes("testing", pool=pool, limit=3)

    ids = {m.id for m in matches}
    assert "real-search-hit" in ids
