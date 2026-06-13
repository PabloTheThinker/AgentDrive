"""Experience Graph v3 — isolated tests for ExperienceGraphRecorder and helpers.

Hermetic: uses autouse ``isolated_agentdrive_home`` + ``get_default_drive_path()``.
No IntegratedRealTimeEvolutionSystem, no network, no Mission Control hub required.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from agentdrive.constants import get_default_drive_path, new_correlation_id
from agentdrive.evolution.experience_graph import (
    CONNECTION_STRENGTHENED_BY,
    CROSS_CYCLE_CONTINUATION,
    DENSIFIED_VIA_GARDENER,
    DENSIFICATION_INVERSE_MAP,
    FABRIC_COHERENCE_CONTRIBUTED,
    FABRIC_LINK,
    GRAPH_COHERENCE_LIFT,
    LoopEdge,
    PARENT_FABRIC_REASONING_TRACE,
    ExperienceGraphRecorder,
    get_recorder_for_drive,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def drive_path(isolated_agentdrive_home: Path) -> Path:
    """Default AgentDrive data directory under the isolated home."""
    path = get_default_drive_path()
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def recorder(drive_path: Path) -> ExperienceGraphRecorder:
    return ExperienceGraphRecorder(drive_path, swarm_id="test-swarm")


def _sample_reasoning(**overrides: object) -> dict:
    base = {
        "fabric_elements_considered": ["elem-alpha", "elem-beta"],
        "structural_pattern_matched": "cross-cycle-densif-pattern",
        "decision_rationale": "Structural continuation from prior weak cluster warrants densification.",
        "expected_lift_signal": 0.05,
    }
    base.update(overrides)
    return base


def _load_cycle_json(recorder: ExperienceGraphRecorder, cycle_id: str) -> dict:
    path = recorder.loops_dir / f"{cycle_id}.json"
    assert path.exists(), f"expected persisted cycle at {path}"
    return json.loads(path.read_text())


def _kg_edges(drive_path: Path) -> list[dict]:
    edges_path = drive_path / "knowledge" / "edges.jsonl"
    if not edges_path.exists():
        return []
    return [json.loads(line) for line in edges_path.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Init + cycle lifecycle
# ---------------------------------------------------------------------------


def test_recorder_init_creates_meta_evolution_loops_dir(drive_path: Path) -> None:
    rec = ExperienceGraphRecorder(drive_path)
    assert rec.loops_dir == drive_path / "meta_evolution" / "loops"
    assert rec.loops_dir.is_dir()


def test_start_cycle_returns_cycle_id_and_persists(recorder: ExperienceGraphRecorder) -> None:
    cid_corr = new_correlation_id()
    cycle_id = recorder.start_cycle(cid_corr, {"goal": "unit-test"})
    assert cycle_id.startswith("evo-cycle-")
    assert cycle_id in recorder._active_cycles
    data = _load_cycle_json(recorder, cycle_id)
    assert data["cycle_id"] == cycle_id
    assert data["root_correlation_id"] == cid_corr
    assert data["metadata"]["initial_context"]["goal"] == "unit-test"
    assert data["status"] == "open"


def test_record_artifact_adds_to_cycle(recorder: ExperienceGraphRecorder) -> None:
    cycle_id = recorder.start_cycle("corr-artifact-001")
    recorder.record_artifact(cycle_id, "briefing:001", "overseer_briefing", content_ref="summary")
    graph = recorder.get_cycle_graph(cycle_id)
    assert "briefing:001" in graph["nodes"]
    assert graph["artifacts"][0]["slug"] == "briefing:001"
    assert graph["artifacts"][0]["type"] == "overseer_briefing"


def test_record_connection_creates_loop_edge_and_persists(recorder: ExperienceGraphRecorder) -> None:
    cycle_id = recorder.start_cycle("corr-conn-001")
    edge = recorder.record_connection(
        cycle_id,
        "node-a",
        "node-b",
        "overseer_briefing_informed_parent_decision",
        metadata={"note": "test"},
    )
    assert isinstance(edge, LoopEdge)
    assert edge.source == "node-a"
    assert edge.target == "node-b"
    data = _load_cycle_json(recorder, cycle_id)
    relations = {c["relation"] for c in data["connections"]}
    assert "overseer_briefing_informed_parent_decision" in relations
    # Bidirectional mirror (Obsidian-style)
    assert any(
        c["source"] == "node-b" and c["target"] == "node-a" for c in data["connections"]
    )


def test_record_connection_unknown_cycle_creates_minimal_cycle(
    recorder: ExperienceGraphRecorder,
) -> None:
    orphan_id = "orphan-cycle-manual"
    recorder.record_connection(
        orphan_id,
        "src-x",
        "tgt-y",
        FABRIC_LINK,
        metadata={"correlation_id": "orphan-corr"},
    )
    assert orphan_id in recorder._active_cycles
    data = _load_cycle_json(recorder, orphan_id)
    assert data["cycle_id"] == orphan_id
    assert data["root_correlation_id"] == "orphan-corr"
    assert any(c["relation"] == FABRIC_LINK for c in data["connections"])


def test_get_cycle_graph_returns_graph_after_connections(recorder: ExperienceGraphRecorder) -> None:
    cycle_id = recorder.start_cycle("corr-graph-001")
    recorder.record_artifact(cycle_id, "art-1", "synthesis")
    recorder.record_connection(cycle_id, "art-1", "art-2", "produced_synthesis")
    graph = recorder.get_cycle_graph(cycle_id)
    assert graph["cycle_id"] == cycle_id
    assert "art-1" in graph["nodes"]
    assert len(graph["edges"]) >= 2  # forward + inverse mirror
    assert all("source" in e and "target" in e for e in graph["edges"])


# ---------------------------------------------------------------------------
# Fabric / parent reasoning surfaces
# ---------------------------------------------------------------------------


def test_record_fabric_contribution_basic(recorder: ExperienceGraphRecorder) -> None:
    src = recorder.start_cycle("corr-fabric-src")
    tgt = recorder.start_cycle("corr-fabric-tgt")
    recorder.record_fabric_contribution(
        src,
        target_cycle=tgt,
        contribution_type=CROSS_CYCLE_CONTINUATION,
        metadata={"fusion_checkpoint": "test"},
    )
    data = _load_cycle_json(recorder, src)
    assert any(
        c["relation"] == CROSS_CYCLE_CONTINUATION and f"cycle:{tgt}" in c["target"]
        for c in data["connections"]
    )


def test_record_parent_fabric_reasoning_stores_trace(recorder: ExperienceGraphRecorder) -> None:
    cycle_id = recorder.start_cycle("corr-reason-001")
    slug = recorder.record_parent_fabric_reasoning(cycle_id, _sample_reasoning())
    assert slug is not None
    assert slug.startswith("parent_fabric_reasoning:")
    graph = recorder.get_cycle_graph(cycle_id)
    assert slug in graph["nodes"]
    relations = {e["relation"] for e in graph["edges"]}
    assert PARENT_FABRIC_REASONING_TRACE in relations


def test_record_parent_fabric_reasoning_dedup_within_window(
    recorder: ExperienceGraphRecorder,
) -> None:
    cycle_id = recorder.start_cycle("corr-dedup-001")
    reasoning = _sample_reasoning()
    first = recorder.record_parent_fabric_reasoning(cycle_id, reasoning)
    second = recorder.record_parent_fabric_reasoning(cycle_id, reasoning)
    assert first is not None
    assert second is not None
    assert second.startswith("parent_fabric_reasoning_dupe_suppressed:")


def test_get_fabric_context_pack_returns_expected_keys(recorder: ExperienceGraphRecorder) -> None:
    pack = recorder.get_fabric_context_pack(lookback_days=3, reasoning_style="balanced")
    for key in (
        "swarm_id",
        "fabric_coherence",
        "lookback_days",
        "generated_at",
        "reasoning_style",
        "top_weak_clusters",
        "strong_continuations",
        "recent_high_value_densifications",
        "memory_systems_triage",
        "actionable_structural_recommendations",
        "compact_graph_summary",
    ):
        assert key in pack
    assert pack["reasoning_style"] == "balanced"
    assert isinstance(pack["top_weak_clusters"], list)
    assert set(pack["memory_systems_triage"]["queues"]) == {
        "working_set",
        "consolidate",
        "reconsolidate",
        "archive",
    }
    assert (
        pack["memory_systems_triage"]["control_plan"]["primary_context_order"][0]
        == "working_set"
    )


def test_get_recent_parent_fabric_reasoning_traces_returns_list(
    recorder: ExperienceGraphRecorder,
) -> None:
    cycle_id = recorder.start_cycle("corr-traces-001")
    recorder.record_parent_fabric_reasoning(cycle_id, _sample_reasoning())
    traces = recorder.get_recent_parent_fabric_reasoning_traces(lookback=5)
    assert isinstance(traces, list)
    assert len(traces) >= 1
    hit = next(t for t in traces if t.get("slug", "").startswith("parent_fabric_reasoning:"))
    assert hit["cycle_id"] == cycle_id
    assert hit.get("structural_pattern_matched") == "cross-cycle-densif-pattern"
    assert hit.get("expected_lift_signal") == 0.05
    reasoning_ref = hit.get("reasoning_ref", {})
    if isinstance(reasoning_ref, dict):
        raw = reasoning_ref.get("raw_ref", "")
        assert "elem-alpha" in raw or "elem-alpha" in reasoning_ref.get(
            "fabric_elements_considered", []
        )


def test_suggest_fabric_reasoning_structure_returns_schema(recorder: ExperienceGraphRecorder) -> None:
    schema = recorder.suggest_fabric_reasoning_structure()
    assert "fabric_reasoning_prompt_template" in schema
    template = schema["fabric_reasoning_prompt_template"]
    assert "required_fields" in template
    assert "fabric_elements_considered" in template["required_fields"]
    assert "schema" in template
    assert "few_shot_good_traces" in schema
    assert isinstance(schema["few_shot_good_traces"], list)


# ---------------------------------------------------------------------------
# Constants + LoopCycle unit behavior via recorder
# ---------------------------------------------------------------------------


def test_densification_relation_constants_exist() -> None:
    assert DENSIFIED_VIA_GARDENER == "densified_via_gardener"
    assert CONNECTION_STRENGTHENED_BY == "connection_strengthened_by"
    assert GRAPH_COHERENCE_LIFT == "graph_coherence_lift"
    assert CROSS_CYCLE_CONTINUATION == "cross_cycle_continuation"
    assert FABRIC_COHERENCE_CONTRIBUTED == "fabric_coherence_contributed"
    assert DENSIFIED_VIA_GARDENER in DENSIFICATION_INVERSE_MAP
    assert DENSIFICATION_INVERSE_MAP[DENSIFIED_VIA_GARDENER] == "gardener_applied_densification"


def test_loop_cycle_add_artifact_and_edge_via_recorder(recorder: ExperienceGraphRecorder) -> None:
    cycle_id = recorder.start_cycle("corr-loop-unit")
    cycle = recorder._active_cycles[cycle_id]
    cycle.add_artifact("slug-direct", "direct_type", content_ref=42)
    edge = LoopEdge(source="s1", target="s2", relation=DENSIFIED_VIA_GARDENER)
    cycle.add_connection(edge)
    recorder._persist_cycle(cycle)
    reloaded = recorder.get_cycle_graph(cycle_id)
    assert "slug-direct" in reloaded["nodes"]
    rels = {e["relation"] for e in reloaded["edges"]}
    assert DENSIFIED_VIA_GARDENER in rels
    assert DENSIFICATION_INVERSE_MAP[DENSIFIED_VIA_GARDENER] in rels


# ---------------------------------------------------------------------------
# Cross-cycle isolation + KG dual-write
# ---------------------------------------------------------------------------


def test_cross_cycle_two_cycles_isolated(recorder: ExperienceGraphRecorder) -> None:
    c1 = recorder.start_cycle(new_correlation_id())
    c2 = recorder.start_cycle(new_correlation_id())
    recorder.record_artifact(c1, "only-in-a", "test-artifact")
    recorder.record_artifact(c2, "only-in-b", "test-artifact")
    g1 = recorder.get_cycle_graph(c1)
    g2 = recorder.get_cycle_graph(c2)
    assert c1 != c2
    assert "only-in-a" in g1["nodes"]
    assert "only-in-b" not in g1["nodes"]
    assert "only-in-b" in g2["nodes"]
    assert "only-in-a" not in g2["nodes"]
    assert (recorder.loops_dir / f"{c1}.json").exists()
    assert (recorder.loops_dir / f"{c2}.json").exists()


def test_kg_dual_write_edges_jsonl_after_record_connection(
    recorder: ExperienceGraphRecorder,
    drive_path: Path,
) -> None:
    cycle_id = recorder.start_cycle("corr-kg-001")
    before = len(_kg_edges(drive_path))
    recorder.record_connection(
        cycle_id,
        "kg-src",
        "kg-tgt",
        "test_kg_dual_write",
        metadata={"correlation_id": "corr-kg-001"},
    )
    after = _kg_edges(drive_path)
    assert len(after) > before
    match = [e for e in after if e.get("relation") == "test_kg_dual_write"]
    assert match, "expected KG edge for record_connection relation"
    assert match[-1]["source"] == "kg-src"
    assert match[-1]["target"] == "kg-tgt"


# ---------------------------------------------------------------------------
# Densification, similarity, mission control, metadata
# ---------------------------------------------------------------------------


def test_record_densification_lift_updates_coherence(recorder: ExperienceGraphRecorder) -> None:
    cycle_id = recorder.start_cycle("corr-lift-001")
    cycle = recorder._active_cycles[cycle_id]
    cycle.enter_densification_phase()
    recorder.record_densification_lift(cycle_id, pre_coherence=0.55, post_coherence=0.72, new_edge_count=3)
    data = _load_cycle_json(recorder, cycle_id)
    assert data["coherence_score"] >= 0.72
    assert data["status"] == "closed"
    rels = {c["relation"] for c in data["connections"]}
    assert GRAPH_COHERENCE_LIFT in rels
    assert DENSIFIED_VIA_GARDENER in rels


def test_find_structural_similarities_empty_ok(recorder: ExperienceGraphRecorder) -> None:
    results = recorder.find_structural_similarities("nonexistent-element-xyz", lookback=3)
    assert results == []


def test_attach_mission_control_noop_without_hub(recorder: ExperienceGraphRecorder) -> None:
    assert recorder._mission_hub is None
    recorder.attach_mission_control(None)
    # Must not raise when hub absent
    recorder._emit_loop_or_fabric_event("fabric_update", fabric_coherence=0.5, summary="noop")
    cycle_id = recorder.start_cycle("corr-mc-noop")
    recorder.record_connection(cycle_id, "a", "b", "mc_noop_edge")


def test_record_connection_metadata_includes_correlation_id(
    recorder: ExperienceGraphRecorder,
) -> None:
    corr = "explicit-correlation-abc123"
    cycle_id = recorder.start_cycle(corr)
    edge = recorder.record_connection(
        cycle_id,
        "meta-src",
        "meta-tgt",
        "metadata_probe",
        metadata={"correlation_id": corr, "custom_flag": True},
    )
    assert edge.metadata.get("correlation_id") == corr
    assert edge.metadata.get("custom_flag") is True
    assert edge.metadata.get("cycle_id") == cycle_id


# ---------------------------------------------------------------------------
# Additional helpers / convenience surfaces
# ---------------------------------------------------------------------------


def test_get_recorder_for_drive_factory(drive_path: Path) -> None:
    rec = get_recorder_for_drive(drive_path, swarm_id="factory-swarm")
    assert isinstance(rec, ExperienceGraphRecorder)
    assert rec.drive_path == drive_path
    assert rec.swarm_id == "factory-swarm"


def test_close_cycle_writes_observation_and_removes_active(
    recorder: ExperienceGraphRecorder,
    drive_path: Path,
) -> None:
    cycle_id = recorder.start_cycle("corr-close-001")
    recorder.record_artifact(cycle_id, "closing-art", "synthesis")
    closed = recorder.close_cycle(cycle_id, outcome_effectiveness=0.8, parent_notes="done")
    assert closed is not None
    assert closed.status == "closed"
    assert cycle_id not in recorder._active_cycles
    obs = drive_path / "observations" / "meta-evolution" / f"loop-experience-graph-{cycle_id}.json"
    assert obs.exists()
    payload = json.loads(obs.read_text())
    assert payload["page_type"] == "loop-experience-graph"


def test_set_active_evolution_context_and_attach(recorder: ExperienceGraphRecorder) -> None:
    cycle_id = recorder.start_cycle("corr-active-001")
    recorder.set_active_evolution_context(cycle_id, correlation_id="corr-active-001")
    assert recorder.get_active_evolution_cycle_id() == cycle_id
    ok = recorder.attach_to_active_cycle("runtime-art", "runtime_producer", content_ref="x")
    assert ok is True
    graph = recorder.get_cycle_graph(cycle_id)
    assert "runtime-art" in graph["nodes"]


def test_normalize_fabric_reasoning_shapes_payload(recorder: ExperienceGraphRecorder) -> None:
    norm = recorder.normalize_fabric_reasoning({"rationale": "short", "lift": 0.03})
    assert "fabric_elements_considered" in norm
    assert norm["decision_rationale"] == "short"
    assert norm["expected_lift_signal"] == 0.03
    assert "_validation_warnings" in norm


def test_loop_edge_to_typed_edge_carries_provenance() -> None:
    edge = LoopEdge(
        source="a",
        target="b",
        relation="test_rel",
        metadata={"cycle_id": "c-1", "correlation_id": "corr-1"},
    )
    typed = edge.to_typed_edge(swarm_id="sw-1")
    assert typed.source == "a"
    assert typed.target == "b"
    assert typed.provenance["cycle_id"] == "c-1"
    assert typed.provenance["swarm_id"] == "sw-1"


def test_compute_cycle_density_after_connections(recorder: ExperienceGraphRecorder) -> None:
    cycle_id = recorder.start_cycle("corr-density")
    recorder.record_artifact(cycle_id, "n1", "type-a")
    recorder.record_artifact(cycle_id, "n2", "type-b")
    recorder.record_connection(cycle_id, "n1", "n2", "produced")
    density = recorder.compute_cycle_density(cycle_id)
    assert 0.0 < density <= 1.0


def test_get_cycle_graph_not_found_returns_error(recorder: ExperienceGraphRecorder) -> None:
    missing = recorder.get_cycle_graph("does-not-exist-cycle")
    assert missing.get("error") == "not found"


def test_find_weak_connections_on_sparse_cycle(recorder: ExperienceGraphRecorder) -> None:
    cycle_id = recorder.start_cycle("corr-weak")
    recorder.record_connection(
        cycle_id,
        "low-conf-src",
        "low-conf-tgt",
        "weak_link",
        metadata={},
    )
    # Manually lower confidence on the forward edge in-memory then persist
    cycle = recorder._active_cycles[cycle_id]
    for e in cycle.connections:
        if e.source == "low-conf-src" and e.relation == "weak_link":
            e.confidence = 0.2
    recorder._persist_cycle(cycle)
    weak = recorder.find_weak_connections(cycle_id, min_confidence=0.6)
    assert any(w.get("source") == "low-conf-src" for w in weak)


def test_aggregate_graph_across_cycles_includes_both(recorder: ExperienceGraphRecorder) -> None:
    c1 = recorder.start_cycle(new_correlation_id())
    c2 = recorder.start_cycle(new_correlation_id())
    recorder.record_fabric_contribution(c1, target_cycle=c2, contribution_type=CROSS_CYCLE_CONTINUATION)
    agg = recorder.aggregate_graph_across_cycles(lookback_days=7)
    assert agg.get("cycle_count", 0) >= 2
    participating = set(agg.get("participating_cycles", []))
    assert c1 in participating
    assert c2 in participating
