"""Tests for RRF retrieval fusion in Drive.query."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentdrive.drive.drive import AgentDrive, DriveQuery
from agentdrive.drive.retrieval import reciprocal_rank_fusion
from agentdrive.genome.models import Genome, GenomeManifest


def _genome(
    gid: str,
    *,
    patterns: list[str] | None = None,
    framework_steps: list[str] | None = None,
) -> Genome:
    manifest = GenomeManifest(
        id=gid,
        version="1.0.0",
        content_hash="sha256:" + ("ab" * 32),
        created=datetime.now(UTC),
        authors=[],
    )
    return Genome(
        manifest=manifest,
        framework={
            "steps": [{"id": str(i), "name": s} for i, s in enumerate(framework_steps or [])]
        },
        reasoning_patterns={p: {"weight": 1.0} for p in (patterns or [])},
    )


def test_rrf_favors_consensus_rankings():
    rankings = {
        "a": ["g1", "g2", "g3"],
        "b": ["g2", "g1", "g3"],
    }
    scores = reciprocal_rank_fusion(rankings, k=60)
    assert scores["g1"] > scores["g3"]
    assert scores["g2"] > scores["g3"]


def test_query_rrf_orders_by_reasoning_overlap(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTDRIVE_RRF_FUSION", "1")
    drive = AgentDrive(drive_path=tmp_path / "drive", auto_seed=False)
    drive.ingest(_genome("morning-brief", patterns=["daily summary briefing"]))
    drive.ingest(_genome("security-postmortem", patterns=["incident triage postmortem"]))
    drive.ingest(_genome("unrelated-topic", patterns=["widget inventory"]))

    results = drive.query(DriveQuery(task_description="incident triage postmortem", limit=3))
    assert results
    ids = [g.genome_id for g in results]
    assert any("security-postmortem" in gid for gid in ids)
    assert all("unrelated-topic" not in gid for gid in ids[:1])
    top_fusion = getattr(results[0], "_hybrid_fusion", {}) or {}
    assert top_fusion.get("mode") == "rrf"


def test_query_flag_off_uses_additive_mode(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTDRIVE_RRF_FUSION", raising=False)
    drive = AgentDrive(drive_path=tmp_path / "drive", auto_seed=False)
    drive.ingest(_genome("alpha", patterns=["alpha"]))
    results = drive.query(DriveQuery(task_description="alpha", limit=1))
    assert results
    fusion = getattr(results[0], "_hybrid_fusion", None)
    if fusion:
        assert fusion.get("mode") in (None, "additive")
