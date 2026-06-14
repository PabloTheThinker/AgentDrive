"""Tests for the cross-agent inheritance manifest layer.

Covers:
- round-trip to disk
- auto-absorb pulls new genomes into the target pool
- absorption is skipped when the genome already exists
- InheritanceReceived event fires off SubagentDone
- PoolIngest carries the inheritance source tag
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentdrive.drive.drive import AgentDrive
from agentdrive.events import (
    InheritanceAbsorbed,
    InheritanceReceived,
    PoolIngest,
    SubagentDone,
    default_bus,
    emit,
    subscribe,
    unsubscribe,
)
from agentdrive.genome.models import Genome, GenomeManifest
from agentdrive.inheritance import (
    InheritanceManifest,
    InheritanceResult,
    InheritedSkillCandidate,
    extract_skill_candidates_from_result,
    list_manifests,
    load_manifest,
    manifest_path,
    record_manifest,
    write_subagent_result_manifest,
)
from agentdrive.registry import GenomeRegistry
from agentdrive.skills.compose import match_skills_for_turn
from agentdrive.skills.registry import get_skill
from agentdrive.skills.usage import get_skill_usage

# ─────────────────────────────────────────────────────────────────────
# fixtures
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


@pytest.fixture
def inheritance_bus_subscribed() -> Iterator[None]:
    """Re-subscribe the inheritance hook into a freshly-cleared bus.

    The default subscription happens at import time, which our clean_bus
    fixture wipes. We re-attach so the SubagentDone test can verify the
    full path.
    """
    from agentdrive import inheritance as inh

    token = subscribe(inh._on_subagent_done, [SubagentDone])
    try:
        yield
    finally:
        unsubscribe(token)


def _seed_genome(gid: str, score: float = 0.8) -> Genome:
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


def _build_manifest(swarm_id: str, subagent_id: str, created: list[str]) -> InheritanceManifest:
    return InheritanceManifest(
        subagent_id=subagent_id,
        swarm_id=swarm_id,
        genomes_pulled=["pulled-1"],
        genomes_created=list(created),
        outcomes_logged=[{"genome_id": gid, "score": 0.82, "score_delta": 0.04} for gid in created],
        duration_s=12.5,
    )


def _skill_candidate(name: str = "incident-retrospective-playbook") -> InheritedSkillCandidate:
    return InheritedSkillCandidate(
        name=name,
        description="Reusable playbook learned by a sub-agent during incident review",
        body=(
            "# Incident Retrospective Playbook\n\n"
            "1. Pull the recent failure timeline.\n"
            "2. Compare the parent hypothesis against sub-agent findings.\n"
            "3. Record reusable prevention DNA and follow-up owners."
        ),
        tags=["incident", "retrospective", "subagent"],
        evidence={"score": 0.86, "source_task": "incident review"},
    )


# ─────────────────────────────────────────────────────────────────────
# tests
# ─────────────────────────────────────────────────────────────────────


def test_manifest_round_trips_to_disk(isolated_agentdrive_home: Path) -> None:
    swarm = "swarm-A"
    sub = "sub-001"
    manifest = _build_manifest(swarm, sub, ["learned-genome"])
    manifest.skills_created.append(_skill_candidate())

    p = manifest_path(swarm, sub)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(manifest.to_json(), encoding="utf-8")

    back = load_manifest(swarm, sub)
    assert back is not None
    assert back.subagent_id == sub
    assert back.swarm_id == swarm
    assert back.genomes_created == ["learned-genome"]
    assert back.skills_created[0].name == "incident-retrospective-playbook"
    assert back.duration_s == 12.5

    listed = list_manifests(swarm_id=swarm)
    assert len(listed) == 1
    assert listed[0].subagent_id == sub


def test_record_manifest_installs_subagent_skill_into_parent_bench(
    registry: GenomeRegistry,
    clean_bus: None,
    isolated_agentdrive_home: Path,
) -> None:
    parent_pool = AgentDrive(registry=registry)
    manifest = _build_manifest("swarm-A", "analyst-7", [])
    manifest.skills_created.append(_skill_candidate())

    absorbed_events: list[InheritanceAbsorbed] = []
    summary: list[InheritanceReceived] = []
    t1 = subscribe(absorbed_events.append, [InheritanceAbsorbed])
    t2 = subscribe(summary.append, [InheritanceReceived])
    try:
        result = record_manifest(
            manifest,
            target_pool=parent_pool,
            auto_absorb=True,
        )
    finally:
        unsubscribe(t1)
        unsubscribe(t2)

    assert result.skills_absorbed == ["incident-retrospective-playbook"]
    assert result.skills_rejected == []

    installed = get_skill("incident-retrospective-playbook")
    assert installed is not None
    assert installed.category == "inherited"
    assert installed.role == "shared"
    assert installed.source == "inheritance:swarm-A:analyst-7"
    assert "Pull the recent failure timeline" in installed.body

    usage_before_match = get_skill_usage("incident-retrospective-playbook")
    assert usage_before_match.runs == 0
    assert usage_before_match.successes == 0

    matched = match_skills_for_turn("run an incident retrospective after this outage")
    assert any(skill.name == "incident-retrospective-playbook" for skill in matched)
    assert any(e.skill_name == "incident-retrospective-playbook" for e in absorbed_events)
    assert summary[0].skills_absorbed == ["incident-retrospective-playbook"]


def test_extract_skill_candidates_from_subagent_handoff_block() -> None:
    result = """
Sub-agent complete.

```agentdrive-skill
name: outage-command-center
description: Use after an outage to coordinate findings into one command review.
tags: [incident, command, subagent]
---
# Outage Command Center

1. Gather each worker's timeline and confidence.
2. Collapse duplicate hypotheses before assigning owners.
3. Record the reusable prevention pattern.
```
"""

    candidates = extract_skill_candidates_from_result(
        result,
        task="coordinate outage review",
    )

    assert len(candidates) == 1
    skill = candidates[0]
    assert skill.name == "outage-command-center"
    assert "coordinate findings" in skill.description
    assert skill.tags == ["incident", "command", "subagent"]
    assert "Collapse duplicate hypotheses" in skill.body
    assert skill.evidence["source_task"] == "coordinate outage review"


def test_subagent_done_absorbs_skill_handoff_manifest(
    registry: GenomeRegistry,
    clean_bus: None,
    inheritance_bus_subscribed: None,
    isolated_agentdrive_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent_pool = AgentDrive(registry=registry)

    import agentdrive.drive.drive as pool_module

    monkeypatch.setattr(pool_module, "get_default_drive", lambda: parent_pool)

    result = """
```agentdrive-skill
name: worker-synthesis-handoff
description: Synthesize multiple worker reports into one parent-ready decision.
tags: [handoff, synthesis]
---
# Worker Synthesis Handoff

1. List each worker's strongest claim.
2. Mark contradictions and missing evidence.
3. Return one parent-ready decision with follow-up owners.
```
"""

    manifest = write_subagent_result_manifest(
        swarm_id="swarm-A",
        subagent_id="worker-9",
        task="summarize parallel worker findings",
        result=result,
        duration_s=3.5,
    )
    assert manifest is not None
    assert manifest.skills_created[0].name == "worker-synthesis-handoff"

    received: list[InheritanceReceived] = []
    token = subscribe(received.append, [InheritanceReceived])
    try:
        emit(
            SubagentDone(
                subagent_id="worker-9",
                swarm_id="swarm-A",
                ok=True,
                duration_s=3.5,
            )
        )
    finally:
        unsubscribe(token)

    installed = get_skill("worker-synthesis-handoff")
    assert installed is not None
    assert installed.source == "inheritance:swarm-A:worker-9"
    assert "parent-ready decision" in installed.body
    assert received[0].skills_absorbed == ["worker-synthesis-handoff"]

    usage = get_skill_usage("worker-synthesis-handoff")
    assert usage.runs == 1
    assert usage.successes == 1
    assert usage.failures == 0
    assert usage.sources["inheritance:swarm-A:worker-9"] == 1


def test_external_inherited_skills_are_not_installed_without_review(
    registry: GenomeRegistry,
    clean_bus: None,
    isolated_agentdrive_home: Path,
) -> None:
    parent_pool = AgentDrive(registry=registry)
    manifest = _build_manifest("federation-X", "peer-sub-1", [])
    manifest.skills_created.append(_skill_candidate("peer-dangerous-playbook"))

    result = record_manifest(
        manifest,
        target_pool=parent_pool,
        auto_absorb=True,
        quarantine_external=True,
    )

    assert result.skills_absorbed == []
    assert result.skills_rejected == ["peer-dangerous-playbook"]
    assert (
        "external inherited skills require review"
        in result.reason_per_rejected["skill:peer-dangerous-playbook"]
    )
    assert get_skill("peer-dangerous-playbook") is None


def test_oversized_inherited_skills_are_rejected(
    registry: GenomeRegistry,
    clean_bus: None,
    isolated_agentdrive_home: Path,
) -> None:
    parent_pool = AgentDrive(registry=registry)
    manifest = _build_manifest("swarm-A", "analyst-7", [])
    candidate = _skill_candidate("too-large-playbook")
    candidate.body = "# Too Large\n\n" + ("repeat this step\n" * 1200)
    manifest.skills_created.append(candidate)

    result = record_manifest(
        manifest,
        target_pool=parent_pool,
        auto_absorb=True,
    )

    assert result.skills_absorbed == []
    assert result.skills_rejected == ["too-large-playbook"]
    assert (
        "Inherited skill body must be <=" in result.reason_per_rejected["skill:too-large-playbook"]
    )
    assert get_skill("too-large-playbook") is None


def test_record_manifest_with_auto_absorb_ingests_new_genomes(
    registry: GenomeRegistry, clean_bus: None
) -> None:
    # Target pool is the parent's pool (uses the autoloaded registry).
    parent_pool = AgentDrive(registry=registry)

    # Sub-agent created a new genome inside its own pool.
    source_registry = GenomeRegistry(root=parent_pool.drive_path / "_subreg")
    source_pool = AgentDrive(registry=source_registry, name="source")
    learned = _seed_genome("learned-1", score=0.82)
    source_registry.save(learned)

    manifest = _build_manifest("swarm-A", "sub-abs", ["learned-1"])

    ingests: list[PoolIngest] = []
    absorbed_events: list[InheritanceAbsorbed] = []
    summary: list[InheritanceReceived] = []
    t1 = subscribe(ingests.append, [PoolIngest])
    t2 = subscribe(absorbed_events.append, [InheritanceAbsorbed])
    t3 = subscribe(summary.append, [InheritanceReceived])

    try:
        result: InheritanceResult = record_manifest(
            manifest,
            target_pool=parent_pool,
            auto_absorb=True,
            source_pool=source_pool,
        )
    finally:
        unsubscribe(t1)
        unsubscribe(t2)
        unsubscribe(t3)

    assert "learned-1" in result.genomes_absorbed
    assert result.genomes_rejected == []
    # PoolIngest fired with the inheritance source tag.
    inh_ingests = [e for e in ingests if e.source.startswith("inheritance:")]
    assert len(inh_ingests) == 1
    # InheritanceAbsorbed fired per-absorbed.
    assert any(e.genome_id == "learned-1" for e in absorbed_events)
    # Summary event fired once.
    assert len(summary) == 1
    assert "learned-1" in summary[0].genomes_absorbed


def test_record_manifest_skips_genomes_already_in_pool(
    registry: GenomeRegistry, clean_bus: None
) -> None:
    parent_pool = AgentDrive(registry=registry)

    # Genome already lives in the parent.
    existing = _seed_genome("already-here", score=0.7)
    registry.save(existing)

    source_registry = GenomeRegistry(root=parent_pool.drive_path / "_subreg2")
    source_pool = AgentDrive(registry=source_registry, name="source2")
    # Sub-agent has its own copy too.
    source_registry.save(_seed_genome("already-here", score=0.71))

    manifest = _build_manifest("swarm-A", "sub-dup", ["already-here"])
    result = record_manifest(
        manifest,
        target_pool=parent_pool,
        auto_absorb=True,
        source_pool=source_pool,
    )

    assert result.genomes_absorbed == []
    assert "already-here" in result.genomes_rejected
    assert "already" in result.reason_per_rejected["already-here"]


def test_inheritance_received_event_fires_on_subagent_done(
    registry: GenomeRegistry,
    clean_bus: None,
    inheritance_bus_subscribed: None,
    isolated_agentdrive_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent_pool = AgentDrive(registry=registry)

    # Force the auto-absorb path to use our parent_pool as the default pool.
    import agentdrive.drive.drive as pool_module

    monkeypatch.setattr(pool_module, "get_default_drive", lambda: parent_pool)

    # And make the swarm manager hand back a stub source pool.
    source_registry = GenomeRegistry(root=parent_pool.drive_path / "_subreg3")
    source_pool = AgentDrive(registry=source_registry, name="source3")
    source_registry.save(_seed_genome("ferried-home", score=0.81))

    import agentdrive.drive.swarm_manager as sm_module

    class _StubManager:
        def get_or_create_pool(self, _swarm: str, _sub: str) -> AgentDrive:
            return source_pool

    monkeypatch.setattr(sm_module, "get_swarm_drive_manager", lambda: _StubManager())

    # Drop the manifest on disk where the hook will look for it.
    swarm = "swarm-A"
    sub = "sub-fire"
    manifest = _build_manifest(swarm, sub, ["ferried-home"])
    p = manifest_path(swarm, sub)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(manifest.to_json(), encoding="utf-8")

    received: list[InheritanceReceived] = []
    token = subscribe(received.append, [InheritanceReceived])
    try:
        emit(
            SubagentDone(
                subagent_id=sub,
                swarm_id=swarm,
                ok=True,
                duration_s=5.0,
            )
        )
    finally:
        unsubscribe(token)

    assert len(received) == 1
    assert "ferried-home" in received[0].genomes_absorbed


def test_pool_ingest_source_marks_inheritance_origin(
    registry: GenomeRegistry, clean_bus: None
) -> None:
    parent_pool = AgentDrive(registry=registry)
    source_registry = GenomeRegistry(root=parent_pool.drive_path / "_subreg4")
    source_pool = AgentDrive(registry=source_registry, name="source4")
    source_registry.save(_seed_genome("origin-tagged", score=0.77))

    manifest = _build_manifest("swarm-A", "sub-tag", ["origin-tagged"])

    captured: list[PoolIngest] = []
    token = subscribe(captured.append, [PoolIngest])
    try:
        record_manifest(
            manifest,
            target_pool=parent_pool,
            auto_absorb=True,
            source_pool=source_pool,
        )
    finally:
        unsubscribe(token)

    inh = [e for e in captured if "inheritance" in e.source]
    assert len(inh) == 1
    assert inh[0].source == "inheritance:sub-tag"
    assert inh[0].actor == "sub-tag"


def test_quarantine_external_routes_through_quarantine_not_pool(
    registry: GenomeRegistry, clean_bus: None
) -> None:
    """When quarantine_external=True, incoming DNA must NOT land in the
    target pool directly — it goes to quarantine for explicit review.
    """
    from agentdrive.quarantine import QuarantineStatus, get_default_quarantine

    parent_pool = AgentDrive(registry=registry)
    source_registry = GenomeRegistry(root=parent_pool.drive_path / "_peerreg")
    source_pool = AgentDrive(registry=source_registry, name="peer-instance")
    source_registry.save(_seed_genome("from-peer", score=0.81))

    manifest = _build_manifest("federation-X", "peer-sub-1", ["from-peer"])

    pool_ingests: list[PoolIngest] = []
    received: list[InheritanceReceived] = []
    t1 = subscribe(pool_ingests.append, [PoolIngest])
    t2 = subscribe(received.append, [InheritanceReceived])
    try:
        result = record_manifest(
            manifest,
            target_pool=parent_pool,
            auto_absorb=True,
            source_pool=source_pool,
            quarantine_external=True,
        )
    finally:
        unsubscribe(t1)
        unsubscribe(t2)

    # Genome was NOT absorbed into the parent pool.
    assert result.genomes_absorbed == []
    assert "from-peer" in result.genomes_rejected
    assert "quarantined for review" in result.reason_per_rejected["from-peer"]
    # No inheritance-tagged PoolIngest should have fired.
    inh = [e for e in pool_ingests if "inheritance" in e.source]
    assert inh == [], "external DNA must not bypass quarantine"
    # Quarantine has the entry.
    q = get_default_quarantine()
    pending = q.list(status=QuarantineStatus.PENDING)
    # Quarantine reads `id@version` from the manifest; just check the prefix.
    assert any(e.genome_id.startswith("from-peer") for e in pending)


def test_quarantine_routing_resolves_id_at_version_form(
    registry: GenomeRegistry, clean_bus: None
) -> None:
    """Cross-pool inheritance must resolve canonical 'id@version' ids,
    not silently drop them.
    """
    from agentdrive.quarantine import QuarantineStatus, get_default_quarantine

    parent_pool = AgentDrive(registry=registry)
    source_registry = GenomeRegistry(root=parent_pool.drive_path / "_at_version_reg")
    source_pool = AgentDrive(registry=source_registry, name="peer-x")
    source_registry.save(_seed_genome("versioned-form", score=0.82))

    # Use the CANONICAL id@version form, as a federation peer would.
    manifest = _build_manifest("swarm-X", "peer-1", ["versioned-form@1.0.0"])

    result = record_manifest(
        manifest,
        target_pool=parent_pool,
        auto_absorb=True,
        source_pool=source_pool,
        quarantine_external=True,
    )

    # Must NOT be silently dropped with "source dir not resolvable".
    assert result.genomes_absorbed == []
    assert "versioned-form@1.0.0" in result.genomes_rejected
    reason = result.reason_per_rejected["versioned-form@1.0.0"]
    assert "quarantined for review" in reason, (
        f"id@version form was dropped instead of quarantined: {reason}"
    )

    # Quarantine should have the entry.
    q = get_default_quarantine()
    pending = q.list(status=QuarantineStatus.PENDING)
    assert any(e.genome_id.startswith("versioned-form") for e in pending)
