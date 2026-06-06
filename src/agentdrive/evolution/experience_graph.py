"""
Experience Graph — Clean, Obsidian-style connection graphs for the canonical
Parent-Overseer-Research real-time evolution loop.

This module delivers the "cleaner feeding of information into the experience layer
and metacognition" + explicit bidirectional typed connection graphs, with deep
integration into the user's exact 6-step canonical Parent-Overseer-Research loop.

v3 adds the multi-cycle Experience Graph (aggregation, coherence, Parent-facing briefings)
so the Overseer and Parent can reason over connections across iterations.
The Experience-Graph-Native Parent Reasoning surfaces (record_parent_fabric_reasoning + get_recent_parent_fabric_reasoning_traces)
lets the Overseer deeply consume Parent's structural traces, reference them in metacognitive outputs,
and record overseer_referenced_parent_fabric_reasoning TypedEdges — all while Overseer serves Parent.

Design:
- Per-loop "note graph" (fast JSON under drive/meta_evolution/loops/) that feels
  like an Obsidian folder of linked notes for one iteration.
- All connections also emitted as TypedEdges into the main KnowledgeGraphStore
  (global multi-hop + gbrain_signal_score + Drive.think boosts via new page_types).
- Single clean Recorder API used by IntegratedRealTimeEvolutionSystem + Overseer.
- Automatic creation of rich EpisodicTrace + Texture notes on key events.
- Coherence scoring + densification hooks so successful connection improvements
  literally expand the experience (higher source_boost, better future hunches,
  stronger metacog regulation).
- 100% AgentDrive native: correlation_id, fusion_checkpoint discipline,
  schema page_types (loop-experience-graph), existing persistence patterns.

The graph makes every loop iteration's artifacts (briefings, Parent decisions,
research threads, synthesis textures, EpisodicTraces, new living-experience
observations) explicitly connected so the AI model (and the Overseer/Parent)
can see the structure, reason over it, strengthen weak links, and cause the
overall experience to grow more intelligently from there.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from agentdrive.knowledge_graph.link_extraction import TypedEdge
from agentdrive.utils.safe_paths import PathTraversalError, safe_join

try:
    from agentdrive.knowledge_graph.graph import KnowledgeGraphStore, get_knowledge_graph_for_swarm
except Exception:
    KnowledgeGraphStore = None
    get_knowledge_graph_for_swarm = None


# ------------------------------------------------------------------
# Densification relations (Experience Graph v2 GraphGardener)
# Per the constitution + 8-step densifier plan: these close weak-link gaps
# and are dual-written to KG via TypedEdge. Inverses get canonical (non-"inverse_")
# naming for readability in Obsidian + Drive.think queries.
# ------------------------------------------------------------------

DENSIFIED_VIA_GARDENER = "densified_via_gardener"
CONNECTION_STRENGTHENED_BY = "connection_strengthened_by"
GRAPH_COHERENCE_LIFT = "graph_coherence_lift"

# Canonical inverse names for the densifier relations (used by add_connection)
DENSIFICATION_INVERSE_MAP: dict[str, str] = {
    DENSIFIED_VIA_GARDENER: "gardener_applied_densification",
    CONNECTION_STRENGTHENED_BY: "strengthened_via_densification",
    GRAPH_COHERENCE_LIFT: "coherence_lifted_by_densification",
}

# ------------------------------------------------------------------
# Experience Graph v3 Multi-Cycle Memory relations
# (exact from v3 Architect Research Constitution + multi-cycle Experience Graph section)
# 5+ new LoopEdge relations for cross-cycle continuation, Experience Graph coherence,
# sibling densification, fusion, etc. These feed harness, daily fusion,
# IntegratedRealTimeEvolutionSystem, RealTimeEvolutionOverseer,
# ResearchThreadLineage (with Experience Graph + densification_history), gardener threads,
# and Experience Graph briefings in observations / daily-present payloads.
# Dual-written via record_connection (arbitrary rels supported) + _emit_kg_edge.
# Inverses use canonical readable names (no "inverse_" prefix) like v2.
# ------------------------------------------------------------------

CROSS_CYCLE_CONTINUATION = "cross_cycle_continuation"
FABRIC_COHERENCE_CONTRIBUTED = "fabric_coherence_contributed"
DENSIFIED_FROM_SIBLING_CYCLE = "densified_from_sibling_cycle"
MULTI_CYCLE_FUSION_EDGE = "multi_cycle_fusion_edge"
FABRIC_LINK = "fabric_link"
CYCLE_FABRIC_PARTICIPATION = "cycle_fabric_participation"

# v3 Experience-Graph-Native Parent Reasoning query power relations (stabilization-wave-20260531 charter)
# Used by find_structural_similarities, get_fabric_reasoning_traces_for_element, get_parent_reasoning_history
# All produce TypedEdges (via record_connection + _emit_kg_edge), auto-bidirectional inverses,
# gbrain_signal_score in provenance/metadata, page_type observations where artifacts written.
PARENT_FABRIC_REASONING_TRACE = "parent_fabric_reasoning_trace"
FABRIC_ELEMENT_REASONED_OVER = "fabric_element_reasoned_over_by_parent"
STRUCTURAL_SIMILARITY_DETECTED = "structural_similarity_detected"
PARENT_FABRIC_QUERY = "parent_fabric_query_performed"
FABRIC_REASONING_TRACE_ACCESSED = "fabric_reasoning_trace_accessed_for_element"
FABRIC_QUERY_RESULT_RECORDED = "fabric_query_result_recorded_as_experience"
# Added for Parent Decision Grounding strengthening (validation + richer informed edges per charter)
PARENT_FABRIC_REASONING_INFORMED_DECISION = "parent_fabric_reasoning_informed_decision"

# AD-Grid Inhabitant Agency (Tron-like persistent world, post 5min experiment + user direction 1780293824)
# Programs and Council threads must be able to code, apply changes, run verification,
# and have every action produce first-class attributed DNA under Guardian gates + Conductor sovereignty.
INHABITANT_CODE_PROPOSAL = "inhabitant_code_proposal"
CODE_CHANGE_APPLIED = "code_change_applied"
INHABITANT_TEST_RESULT = "inhabitant_test_result"
GUARDIAN_VERDICT = "guardian_verdict_on_action"

# Inhabitants that Ship (ILO Guardian + implementation lens, horizon charter 1780296458):
# Simple proposal/review queue surface (in-memory for live review + DNA via page_type for durability/queryability).
# Enables proposals (from MCP, Councils, registered programs) to surface explicitly for Conductor review
# before any real apply. Used in guarded_apply real_contribution_mode path.
INHABITANT_PROPOSAL_PENDING_REVIEW = "inhabitant_code_proposal_pending_conductor_review"

# Extend DENSIFICATION_INVERSE_MAP for v3 Experience Graph relations (add_connection uses it)
DENSIFICATION_INVERSE_MAP.update(
    {
        CROSS_CYCLE_CONTINUATION: "continued_across_cycles",
        FABRIC_COHERENCE_CONTRIBUTED: "coherence_contributed_to_fabric",
        DENSIFIED_FROM_SIBLING_CYCLE: "sibling_cycle_densification_source",
        MULTI_CYCLE_FUSION_EDGE: "fused_from_multi_cycle",
        FABRIC_LINK: "linked_in_fabric",
        CYCLE_FABRIC_PARTICIPATION: "participated_in_fabric",
        # Parent reasoning query power inverses (canonical readable, no "inverse_" prefix)
        PARENT_FABRIC_REASONING_TRACE: "traced_in_parent_fabric_reasoning",
        FABRIC_ELEMENT_REASONED_OVER: "parent_reasoned_over_fabric_element",
        STRUCTURAL_SIMILARITY_DETECTED: "similar_structural_pattern_across_fabric",
        PARENT_FABRIC_QUERY: "fabric_query_triggered_by_parent",
        FABRIC_REASONING_TRACE_ACCESSED: "element_reasoning_trace_served",
        FABRIC_QUERY_RESULT_RECORDED: "experience_grew_from_fabric_query",
        # For the richer "parent_fabric_reasoning_informed_decision" TypedEdge created automatically
        # in Integrated.record_parent_decision when fabric_reasoning payload is supplied (after normalization).
        PARENT_FABRIC_REASONING_INFORMED_DECISION: "decision_informed_by_parent_fabric_reasoning",
    }
)


# ------------------------------------------------------------------
# Core data models (Obsidian-style per-loop connection graph)
# ------------------------------------------------------------------


@dataclass
class LoopEdge:
    """Bidirectional typed connection within (or across) loop cycles.

    These are the "links" in the Obsidian graph for a single evolution loop iteration.
    Every relation is recorded in both directions for natural traversal.
    """

    source: str
    target: str
    relation: str  # e.g. "overseer_briefing_informed_parent_decision", ..., DENSIFIED_VIA_GARDENER etc (v2); CROSS_CYCLE_CONTINUATION, ... (v3 fabric); PARENT_FABRIC_REASONING_INFORMED_DECISION, parent_fabric_reasoning_grounded_decision, parent_reasoned_over_fabric_element (Fabric-Native Parent Reasoning + grounding)
    weight: float = 1.0
    confidence: float = 0.9
    metadata: dict[str, Any] = field(
        default_factory=dict
    )  # cycle_id, correlation_id, felt_texture, harness_scores, fusion_checkpoint_snippet, etc.
    timestamp: float = field(default_factory=time.time)

    def to_typed_edge(self, swarm_id: str | None = None) -> TypedEdge:
        """Convert to the system's canonical TypedEdge for KG persistence."""
        return TypedEdge(
            source=self.source,
            target=self.target,
            relation=self.relation,
            confidence=self.confidence,
            provenance={
                "loop_edge": True,
                "cycle_id": self.metadata.get("cycle_id"),
                "correlation_id": self.metadata.get("correlation_id"),
                "weight": self.weight,
                "swarm_id": swarm_id,
                "timestamp": self.timestamp,
                **self.metadata,
            },
        )


@dataclass
class LoopCycle:
    """One complete iteration of the canonical Parent-Overseer-Research loop.

    This is the "note" in the Obsidian folder. It collects every artifact
    produced in the loop and the explicit connections between them.
    Persisted as first-class experience layer content (page_type=loop-experience-graph).

    Status lifecycle (per GraphGardener densifier constitution):
    open -> closed | densifying (for v2 connection densification passes); v3 fabric aggregates across cycles via fabric_links + cross rels.
    """

    cycle_id: str
    root_correlation_id: str
    start_ts: float = field(default_factory=time.time)
    end_ts: float | None = None
    status: str = "open"  # open | closed | densifying (GraphGardener v2 support)
    participating_artifacts: list[dict[str, Any]] = field(default_factory=list)
    connections: list[LoopEdge] = field(default_factory=list)
    coherence_score: float = 0.5
    parent_decision_summary: str = ""
    outcome_effectiveness: float = 0.0
    texture_notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    # v2 densifier support (persisted on disk for dogfood + future cycles)
    densification_history: list[dict[str, Any]] = field(default_factory=list)
    # v3 multi-cycle memory fabric (minimal optional fields; used by aggregate / fabric coherence / briefing)
    fabric_links: list[str] = field(default_factory=list)  # sibling/continuation cycle_ids
    fabric_metadata: dict[str, Any] = field(
        default_factory=dict
    )  # cross_cycle stats, contribution etc.

    def add_artifact(
        self,
        slug: str,
        artifact_type: str,
        content_ref: Any = None,
        texture_hints: dict | None = None,
    ) -> None:
        entry = {
            "slug": slug,
            "type": artifact_type,
            "ts": time.time(),
            "ref": content_ref
            if isinstance(content_ref, (str, int, float, bool, type(None)))
            else str(content_ref)[:200],
        }
        if texture_hints:
            entry["texture"] = texture_hints
        self.participating_artifacts.append(entry)

    def add_connection(self, edge: LoopEdge) -> None:
        self.connections.append(edge)
        # Auto-mirror for true bidirectionality (Obsidian style)
        # Special handling for densification relations: use canonical inverses (not "inverse_foo")
        inv_rel = DENSIFICATION_INVERSE_MAP.get(edge.relation, f"inverse_{edge.relation}")
        if not any(
            e.source == edge.target
            and e.target == edge.source
            and e.relation in (inv_rel, f"inverse_{edge.relation}")
            for e in self.connections
        ):
            inverse = LoopEdge(
                source=edge.target,
                target=edge.source,
                relation=inv_rel,
                weight=edge.weight,
                confidence=edge.confidence * 0.95,
                metadata={**edge.metadata, "inverse_of": edge.relation},
                timestamp=edge.timestamp,
            )
            self.connections.append(inverse)

    def finalize(self, outcome_effectiveness: float, parent_notes: str = "") -> None:
        self.end_ts = time.time()
        self.status = "closed"
        self.outcome_effectiveness = max(0.0, min(1.0, outcome_effectiveness))
        self.parent_decision_summary = parent_notes[:2000]
        self.coherence_score = self._compute_coherence()

    def enter_densification_phase(self) -> None:
        """Mark this cycle as entering GraphGardener densification (per constitution step graph)."""
        if self.status != "closed":
            # Densification typically runs on closed cycles; allow re-open for extension
            pass
        self.status = "densifying"

    def exit_densification_phase(self, final_coherence: float | None = None) -> None:
        """Exit densification phase (usually back to closed with lifted coherence)."""
        self.status = "closed"
        if final_coherence is not None:
            self.coherence_score = max(self.coherence_score, final_coherence)

    def _compute_coherence(self) -> float:
        """Lightweight heuristic (can be replaced by synthesis later).
        v2 update: incorporates explicit connection_density term (weight 0.28)
        per GraphGardener densifier constitution. Forward edges only for density.
        """
        n = max(1, len(self.participating_artifacts))
        # Count only forward (non-inverse) connections for true connection density
        forward_conns = [
            e
            for e in self.connections
            if not str(getattr(e, "relation", "")).startswith("inverse_")
        ]
        c = max(1, len(forward_conns))
        raw_density = min(1.0, c / (n * 2.5))
        connection_density = raw_density  # dedicated term for densifier measurement

        causality = 0.3
        for e in self.connections:
            if any(
                k in getattr(e, "relation", "")
                for k in (
                    "informed",
                    "executed_as",
                    "produced",
                    "closed",
                    "strengthened",
                    "densif",
                    "coherence_lift",
                )
            ):
                causality = min(1.0, causality + 0.12)
        texture = min(1.0, len(self.texture_notes) * 0.08 + 0.4)
        lift = self.outcome_effectiveness * 0.25

        # Rebalanced weights (sum to 1.0). connection_density ~0.28 as specified.
        return round(
            min(
                1.0,
                (
                    raw_density * 0.20
                    + connection_density * 0.28
                    + causality * 0.22
                    + texture * 0.15
                    + lift * 0.15
                ),
            ),
            3,
        )


# ------------------------------------------------------------------
# Recorder — the single clean ingestion surface for the loop
# ------------------------------------------------------------------


class ExperienceGraphRecorder:
    """
    The clean, standardized ingestion layer for the real-time evolution loop.

    Every time the Parent-Overseer-Research cycle produces a briefing, a Parent
    decision, a research thread, a synthesis result, an EpisodicTrace, or a new
    experience observation — it goes through here.

    This is what makes "information fed into the experience layer and into the
    metacognition clean and much better" and creates the visible Obsidian-style
    connection graph that lets the model see and grow the connections.

    v3 Parent fabric reasoning tranche: record_parent_fabric_reasoning captures Parent's
    explicit structural reasoning over fabric elements. get_recent_parent_fabric_reasoning_traces
    (plus usage in RealTimeEvolutionOverseer.get_metacognitive_briefing) lets the Overseer
    deeply consume + reference that history (recording overseer_referenced_* edges) while
    strictly serving the Parent per the 6-step order.
    """

    def __init__(self, drive_path: Path | str, swarm_id: str | None = None):
        self.drive_path = Path(drive_path)
        self.swarm_id = swarm_id or "stabilization-wave-20260531"
        self.loops_dir = self.drive_path / "meta_evolution" / "loops"
        self.loops_dir.mkdir(parents=True, exist_ok=True)
        self._active_cycles: dict[str, LoopCycle] = {}

        # Optional direct KG store for dual-write
        self._kg_store = None
        if KnowledgeGraphStore is not None:
            try:
                self._kg_store = KnowledgeGraphStore(
                    drive_path=self.drive_path, swarm_id=self.swarm_id
                )
            except Exception:
                self._kg_store = None

        # Mission Control hub (optional, attached by IntegratedRealTimeEvolutionSystem)
        # When present, record_* and densification hot paths emit typed events (FabricUpdate etc)
        # via the sync-safe publish helper. This is the single clean ingestion point for MC.
        self._mission_hub: Any = None

        # AD-Grid stability guard (added after 5min self-improve loop incident ~17802928xx-1780293056)
        # Lightweight per-process recent-dupe cache for parent_fabric_reasoning payloads.
        # Stops echo-chamber recording loops from relentless optimizer roles, MCP clients, or synthesis steps
        # re-emitting identical "Council synthesis / now implement" narratives. Full cross-process + Guardian
        # Conductor-override version is explicit follow-up per the 5-point sovereignty hardening list.
        self._recent_fabric_reasoning_hashes: dict[str, float] = {}

        # Inhabitants that Ship (ILO Guardian stream, charter 1780296458): simple proposal/review queue.
        # In-memory for this process (live Conductor cockpit / review surface); all enqueues also emit
        # as first-class DNA (INHABITANT_PROPOSAL_PENDING_REVIEW page_type via record_inhabitant_code_action)
        # for cross-restart queryability via experience_graph_* and Parent/Overseer. Proposals from
        # inhabitants (MCP, Council threads, registered programs) land here for explicit review before
        # any guarded real apply. Additive, never bypasses Conductor path.
        self._pending_conductor_review_queue: list[dict[str, Any]] = []

    def attach_mission_control(self, hub: Any) -> None:
        """Wire this recorder (the canonical ingestion point) to the Mission Control hub.
        Called from IntegratedRealTimeEvolutionSystem.attach_mission_control.
        """
        self._mission_hub = hub

    def _emit_loop_or_fabric_event(self, event_kind: str, **kwargs: Any) -> None:
        """Tiny hot-path emitter. Uses recorder as the single clean point.
        Never raises; silent when no hub attached (local-first posture).
        """
        if not self._mission_hub:
            return
        try:
            import time as _time

            from agentdrive.mission_control.events import (
                FabricUpdateEvent,
                LoopStepEvent,
                ParentDecisionEvent,
            )
            from agentdrive.mission_control.server import publish_event_sync

            ts = _time.time()
            cid = kwargs.get("cycle_id") or getattr(self, "_active_cycle_id", None)

            if event_kind == "fabric_update":
                evt = FabricUpdateEvent(
                    event_type="fabric_update",
                    timestamp=ts,
                    cycle_id=cid,
                    fabric_coherence=float(kwargs.get("fabric_coherence", 0.0)),
                    delta_edges=int(kwargs.get("delta_edges", 0)),
                    affected_cycles=kwargs.get("affected_cycles", []),
                    summary=kwargs.get("summary", ""),
                    graph_delta=kwargs.get("graph_delta"),
                    parent_fabric_reasoning=kwargs.get("parent_fabric_reasoning"),
                    metadata=kwargs.get("metadata") or {},
                )
                publish_event_sync(evt)
            elif event_kind == "loop_step":
                evt = LoopStepEvent(
                    event_type="loop_step",
                    timestamp=ts,
                    cycle_id=cid,
                    step=int(kwargs.get("step", 1)),
                    description=kwargs.get("description", ""),
                    data=kwargs.get("data", {}),
                )
                publish_event_sync(evt)
            elif event_kind == "parent_decision":
                evt = ParentDecisionEvent(
                    event_type="parent_decision",
                    timestamp=ts,
                    cycle_id=cid,
                    decision_summary=kwargs.get("decision_summary", ""),
                    actions_taken=kwargs.get("actions_taken", []),
                    triggered_from_fabric=bool(kwargs.get("triggered_from_fabric", False)),
                    fabric_coherence_at_decision=kwargs.get("fabric_coherence_at_decision"),
                )
                publish_event_sync(evt)
                # Also a loop step for the decision moment (step 4)
                self._emit_loop_or_fabric_event(
                    "loop_step",
                    cycle_id=cid,
                    step=4,
                    description="Parent Conductor records real-time decision (step 4 of canonical loop)",
                    data={"decision_summary": kwargs.get("decision_summary", "")},
                )
            elif event_kind == "overseer_fabric_ingest":
                # Light: when recorder sees fabric ingestion artifact, surface as fabric + step2/3
                self._emit_loop_or_fabric_event(
                    "fabric_update",
                    cycle_id=cid,
                    fabric_coherence=kwargs.get("fabric_coherence", 0.0),
                    summary="overseer ingested multi-cycle fabric",
                )
                self._emit_loop_or_fabric_event(
                    "loop_step",
                    cycle_id=cid,
                    step=2,
                    description="Overseer ingested fabric + experience (step 2)",
                )
        except Exception:
            # Never let mission control emission break the real loop / recorder
            pass

    def start_cycle(self, root_correlation_id: str, initial_context: dict | None = None) -> str:
        """Begin a new loop iteration. Returns the cycle_id."""
        ts = int(time.time())
        cycle_id = f"evo-cycle-{root_correlation_id[:8]}-{ts}"
        cycle = LoopCycle(
            cycle_id=cycle_id,
            root_correlation_id=root_correlation_id,
            metadata={"initial_context": initial_context or {}, "swarm_id": self.swarm_id},
        )
        self._active_cycles[cycle_id] = cycle
        self._persist_cycle(cycle)
        # Seed a KG edge so the global graph knows a new loop iteration began
        self._emit_kg_edge(
            source=f"cycle:{cycle_id}",
            target=f"correlation:{root_correlation_id[:12]}",
            relation="cycle_opened_for_correlation",
            metadata={"cycle_id": cycle_id, "correlation_id": root_correlation_id},
        )
        return cycle_id

    def record_artifact(
        self,
        cycle_id: str,
        slug: str,
        artifact_type: str,
        content_ref: Any = None,
        texture_hints: dict | None = None,
    ) -> None:
        """Record any artifact produced inside the loop (briefing, decision, thread, synthesis, trace, etc.)."""
        cycle = self._get_or_load(cycle_id)
        if not cycle:
            return
        cycle.add_artifact(slug, artifact_type, content_ref, texture_hints)
        self._persist_cycle(cycle)

        # Also emit a lightweight KG participation edge
        self._emit_kg_edge(
            source=slug,
            target=f"cycle:{cycle_id}",
            relation="participated_in_evolution_cycle",
            metadata={
                "cycle_id": cycle_id,
                "artifact_type": artifact_type,
                "correlation_id": cycle.root_correlation_id,
            },
        )

        # Mission Control emission (recorder = single clean ingestion point)
        self._emit_loop_or_fabric_event(
            "loop_step",
            cycle_id=cycle_id,
            step=1
            if "experience" in artifact_type or "synthesis" in artifact_type
            else (3 if "overseer_briefing" in artifact_type else 5),
            description=f"Artifact recorded: {artifact_type}",
            data={"slug": slug, "artifact_type": artifact_type},
        )
        if "fabric" in artifact_type or "overseer_fabric" in artifact_type:
            self._emit_loop_or_fabric_event(
                "overseer_fabric_ingest", cycle_id=cycle_id, fabric_coherence=0.0
            )

    def record_connection(
        self,
        cycle_id: str,
        source: str,
        target: str,
        relation: str,
        metadata: dict | None = None,
    ) -> LoopEdge:
        """Record an explicit bidirectional typed connection (the heart of the Obsidian graph)."""
        cycle = self._get_or_load(cycle_id)
        if not cycle:
            # Create a minimal cycle if caller is outside normal flow
            cycle = LoopCycle(
                cycle_id=cycle_id,
                root_correlation_id=metadata.get("correlation_id", "unknown")
                if metadata
                else "unknown",
            )
            self._active_cycles[cycle_id] = cycle

        edge = LoopEdge(
            source=source,
            target=target,
            relation=relation,
            metadata={**(metadata or {}), "cycle_id": cycle_id},
        )
        cycle.add_connection(edge)
        self._persist_cycle(cycle)

        # Dual-write into the main KG so existing graph queries see it
        self._emit_kg_edge(
            source, target, relation, metadata={**(metadata or {}), "cycle_id": cycle_id}
        )

        # Mission Control: connection activity often means fabric growth or loop step
        delta = 1 if "densif" not in relation.lower() else 0
        self._emit_loop_or_fabric_event(
            "fabric_update",
            cycle_id=cycle_id,
            delta_edges=delta,
            summary=f"connection:{relation}",
            graph_delta={"source": source, "target": target, "relation": relation},
        )
        if "parent_decision" in source.lower() or "parent_decision" in relation.lower():
            md = metadata if isinstance(metadata, dict) else {}
            self._emit_loop_or_fabric_event(
                "parent_decision",
                cycle_id=cycle_id,
                decision_summary=str(md.get("decision_summary", relation))[:200],
                actions_taken=md.get("actions", []),
            )

        return edge

    def close_cycle(
        self, cycle_id: str, outcome_effectiveness: float, parent_notes: str = ""
    ) -> LoopCycle | None:
        """Close the loop iteration, compute final coherence, emit closing edges, persist as first-class experience artifact."""
        cycle = self._get_or_load(cycle_id)
        if not cycle:
            return None

        cycle.finalize(outcome_effectiveness, parent_notes)

        # Closing edges (these are what make the graph grow the experience)
        self.record_connection(
            cycle_id,
            f"cycle:{cycle_id}",
            "experience_layer_v3",
            "cycle_closed_with_experience_lift",
            {"effectiveness": outcome_effectiveness, "coherence": cycle.coherence_score},
        )

        # Persist final form as a proper experience-observation / loop-experience-graph artifact
        self._write_final_artifact(cycle)

        if cycle_id in self._active_cycles:
            del self._active_cycles[cycle_id]

        # Mission Control: cycle close is step 6 completion + fabric update
        self._emit_loop_or_fabric_event(
            "loop_step",
            cycle_id=cycle_id,
            step=6,
            description="Cycle closed with experience lift (step 6 of canonical loop)",
            data={"outcome_effectiveness": outcome_effectiveness},
        )
        self._emit_loop_or_fabric_event(
            "fabric_update",
            cycle_id=cycle_id,
            fabric_coherence=cycle.coherence_score if cycle else 0.0,
            summary="cycle_closed",
            affected_cycles=[cycle_id],
        )

        return cycle

    def get_cycle_graph(self, cycle_id: str) -> dict[str, Any]:
        """Return the full Obsidian-style graph for this loop iteration (nodes + bidirectional edges)."""
        cycle = self._get_or_load(cycle_id)
        if not cycle:
            return {"cycle_id": cycle_id, "error": "not found"}

        # Connections may be LoopEdge or plain dict after JSON load
        def _edge_dict(e):
            if isinstance(e, dict):
                return {
                    "source": e.get("source"),
                    "target": e.get("target"),
                    "relation": e.get("relation"),
                    "weight": e.get("weight", 1.0),
                    "confidence": e.get("confidence", 0.9),
                    "metadata": e.get("metadata", {}),
                }
            return {
                "source": e.source,
                "target": e.target,
                "relation": e.relation,
                "weight": e.weight,
                "confidence": e.confidence,
                "metadata": e.metadata,
            }

        return {
            "cycle_id": cycle.cycle_id,
            "root_correlation_id": cycle.root_correlation_id,
            "status": cycle.status,
            "coherence_score": cycle.coherence_score,
            "outcome_effectiveness": cycle.outcome_effectiveness,
            "parent_decision_summary": cycle.parent_decision_summary,
            "nodes": [a["slug"] for a in cycle.participating_artifacts],
            "artifacts": cycle.participating_artifacts,
            "edges": [_edge_dict(e) for e in cycle.connections],
            "texture_notes": cycle.texture_notes,
            "ts_range": [cycle.start_ts, cycle.end_ts],
            # v3 fabric minimal exposure for aggregate/briefing consumers (Integrated, Overseer, daily fusion)
            "fabric_links": getattr(cycle, "fabric_links", []),
            "fabric_metadata": getattr(cycle, "fabric_metadata", {}),
        }

    # ------------------------------------------------------------------
    # Deep loop integration helpers (for exact canonical 6-step Parent-Overseer-Research order)
    # ------------------------------------------------------------------

    def set_active_evolution_context(
        self, cycle_id: str, correlation_id: str | None = None
    ) -> None:
        """Set the active evolution cycle that runtime producers (Grid threads, daily consolidation, HealingFactor) should attach to.
        This keeps the graph tightly coupled to the single canonical loop without leaking across unrelated work."""
        self._active_cycle_id = cycle_id
        if correlation_id:
            self._active_correlation = correlation_id

    def get_active_evolution_cycle_id(self) -> str | None:
        return getattr(self, "_active_cycle_id", None)

    def attach_to_active_cycle(
        self,
        artifact_slug: str,
        artifact_type: str,
        content_ref: Any = None,
        metadata: dict | None = None,
    ) -> bool:
        """Runtime producers call this when they generate experience that belongs to the current evolution loop.
        Returns True if attached to an active cycle."""
        cid = getattr(self, "_active_cycle_id", None)
        if not cid:
            return False
        self.record_artifact(cid, artifact_slug, artifact_type, content_ref, metadata)
        return True

    def record_fabric_contribution(
        self,
        source_cycle: str,
        target_cycle: str | None = None,
        contribution_type: str = "cross_cycle_continuation",
        metadata: dict | None = None,
    ) -> None:
        """Record a cross-cycle fabric link. Used by daily consolidation and multi-cycle aggregation to grow the relational memory across loops."""
        target = target_cycle or getattr(self, "_active_cycle_id", source_cycle)
        self.record_connection(
            source_cycle,
            f"cycle:{source_cycle}",
            f"cycle:{target}",
            contribution_type,
            metadata or {},
        )

    def find_weak_connections(self, cycle_id: str, min_confidence: float = 0.6) -> list[dict]:
        cycle = self._get_or_load(cycle_id)
        if not cycle:
            return []
        weak = []
        for e in cycle.connections:
            if e.confidence < min_confidence:
                weak.append(
                    {
                        "source": e.source,
                        "target": e.target,
                        "relation": e.relation,
                        "confidence": e.confidence,
                        "suggestion": f"Consider densification research thread to strengthen {e.relation} between {e.source} and {e.target}",
                    }
                )
        return weak

    # ------------------------------------------------------------------
    # Experience Graph v2 Densifier (GraphGardener core) — per constitution
    # find_weak + propose + densification measurement flow + new relations.
    # All use existing KG dual-write (_emit_kg_edge + record_connection), JSON persistence,
    # correlation/fusion_checkpoint discipline. Minimal, immediately testable.
    # ------------------------------------------------------------------

    def find_weak_across_recent_cycles(
        self, min_coherence: float = 0.6, lookback: int = 5
    ) -> list[dict]:
        """Scan recent cycles; return those below min_coherence with their weak links.
        This is the entry point for the Gardener densifier (find_weak step).
        """
        candidates: list[dict] = []
        try:
            files = sorted(
                self.loops_dir.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )[:lookback]
            for f in files:
                try:
                    data = json.loads(f.read_text())
                    coh = float(data.get("coherence_score", 0.0))
                    if coh < min_coherence:
                        cid = data.get("cycle_id")
                        weaks = self.find_weak_connections(cid, min_confidence=0.65) if cid else []
                        candidates.append(
                            {
                                "cycle_id": cid,
                                "coherence": coh,
                                "weak_links": weaks,
                                "artifact_count": len(data.get("participating_artifacts", [])),
                                "edge_count": len(data.get("connections", [])),
                                "status": data.get("status", "unknown"),
                            }
                        )
                except Exception:
                    continue
        except Exception:
            pass
        return candidates

    def compute_cycle_density(self, cycle_id: str) -> float:
        """Return normalized connection density for the cycle (edges/artifacts).
        Feeds the updated coherence formula + densification lift measurement.
        """
        cycle = self._get_or_load(cycle_id)
        if not cycle:
            return 0.0
        n = max(1, len(cycle.participating_artifacts))
        c = max(
            0,
            len(
                [
                    e
                    for e in cycle.connections
                    if not str(getattr(e, "relation", "")).startswith("inverse_")
                ]
            ),
        )
        # Same normalization heuristic used historically (but now exposed + used in coherence)
        return min(1.0, c / (n * 2.5))

    def propose_densification_edges(
        self, cycle_id: str, weak_links: list[dict] | None = None
    ) -> list[LoopEdge]:
        """Pure-Python heuristics (synthesis Gap style) to generate safe, typed
        densification proposals that close identified weak-link gaps.
        Returns list[LoopEdge] using the three new densifier relations.
        Never mutates; caller decides when to enter phase / execute.
        """
        cycle = self._get_or_load(cycle_id)
        if not cycle:
            return []
        if weak_links is None or len(weak_links) == 0:
            weak_links = self.find_weak_connections(cycle_id, min_confidence=0.6)

        proposals: list[LoopEdge] = []
        slugs = [a.get("slug", "") for a in cycle.participating_artifacts if isinstance(a, dict)]

        # Gap-closure heuristic 1: strengthen each identified weak link explicitly
        for w in (weak_links or [])[:6]:
            src = w.get("source") if isinstance(w, dict) else getattr(w, "source", None)
            tgt = w.get("target") if isinstance(w, dict) else getattr(w, "target", None)
            if not src or not tgt:
                continue
            proposals.append(
                LoopEdge(
                    source=str(src),
                    target=str(tgt),
                    relation=CONNECTION_STRENGTHENED_BY,
                    weight=0.85,
                    confidence=0.68,  # proposed confidence — verified on lift recording
                    metadata={
                        "proposed_by": "graph_gardener_densifier",
                        "gap_type": "weak_connection",
                        "original_relation": w.get("relation")
                        if isinstance(w, dict)
                        else getattr(w, "relation", None),
                        "original_confidence": w.get("confidence")
                        if isinstance(w, dict)
                        else getattr(w, "confidence", None),
                        "heuristic": "synthesis_gap_closure",
                        "cycle_id": cycle_id,
                    },
                    timestamp=time.time(),
                )
            )

        # Gap-closure heuristic 2: cycle-level densification + coherence lift proposals
        # (these are always safe, increase density, use all three new relations)
        if cycle_id:
            cyc_ref = f"cycle:{cycle_id}"
            # Use a late artifact as densification target if present
            anchor = slugs[-1] if slugs else "experience_layer_v3"
            proposals.append(
                LoopEdge(
                    source=cyc_ref,
                    target=anchor,
                    relation=DENSIFIED_VIA_GARDENER,
                    weight=0.9,
                    confidence=0.65,
                    metadata={
                        "proposed_by": "graph_gardener_densifier",
                        "heuristic": "cycle_densify_via_gardener",
                        "gap_type": "density",
                        "cycle_id": cycle_id,
                    },
                    timestamp=time.time(),
                )
            )
            proposals.append(
                LoopEdge(
                    source=cyc_ref,
                    target="experience_layer_v3",
                    relation=GRAPH_COHERENCE_LIFT,
                    weight=1.0,
                    confidence=0.62,
                    metadata={
                        "proposed_by": "graph_gardener_densifier",
                        "heuristic": "coherence_lift_projection",
                        "pre_coherence_hint": cycle.coherence_score,
                        "cycle_id": cycle_id,
                    },
                    timestamp=time.time(),
                )
            )

        return proposals

    def enter_densification_phase(
        self, cycle_id: str, proposed_edges: list[LoopEdge]
    ) -> LoopCycle | None:
        """Transition cycle into 'densifying' status and persist the proposed edges
        (they become first-class connections with proposal metadata; inverses auto-added).
        Dual-writes to KG. This is the 'propose' step realization.
        """
        cycle = self._get_or_load(cycle_id)
        if not cycle:
            return None
        cycle.enter_densification_phase()
        for edge in proposed_edges or []:
            md = {
                **(edge.metadata or {}),
                "densification_proposal": True,
                "phase": "densifying",
            }
            self.record_connection(cycle_id, edge.source, edge.target, edge.relation, metadata=md)
        self._persist_cycle(cycle)

        # MC emission at densification entry (fabric growth moment)
        self._emit_loop_or_fabric_event(
            "fabric_update",
            cycle_id=cycle_id,
            delta_edges=len(proposed_edges or []),
            summary="densification_phase_entered",
            graph_delta={"proposed": len(proposed_edges or [])},
        )
        return cycle

    def record_densification_lift(
        self,
        cycle_id: str,
        pre_coherence: float,
        post_coherence: float,
        new_edge_count: int,
    ) -> None:
        """Record the successful densification outcome.
        Emits graph_coherence_lift (and densified_via_gardener) edges via normal path,
        updates cycle coherence + status, persists JSON + KG. Fusion discipline observed.
        """
        cycle = self._get_or_load(cycle_id)
        if not cycle:
            return
        lift = max(0.0, round(post_coherence - pre_coherence, 4))
        # The canonical lift edge
        self.record_connection(
            cycle_id,
            f"cycle:{cycle_id}",
            "experience_layer_v3",
            GRAPH_COHERENCE_LIFT,
            metadata={
                "pre_coherence": pre_coherence,
                "post_coherence": post_coherence,
                "lift": lift,
                "new_edge_count": new_edge_count,
                "applied_by": "graph_gardener",
                "correlation_id": cycle.root_correlation_id,
                "fusion_checkpoint": {
                    "pre": pre_coherence,
                    "post": post_coherence,
                    "lift": lift,
                },
            },
        )
        # Companion densification action edge
        self.record_connection(
            cycle_id,
            f"cycle:{cycle_id}",
            "densifier:graph_gardener",
            DENSIFIED_VIA_GARDENER,
            metadata={
                "lift": lift,
                "new_edge_count": new_edge_count,
                "cycle_id": cycle_id,
            },
        )
        # Update in-memory + persist
        cycle.coherence_score = max(cycle.coherence_score, post_coherence)
        cycle.exit_densification_phase(post_coherence)
        self._persist_cycle(cycle)

        # MC: densification lift is high-signal fabric update (core of step 6 + fabric evolution)
        self._emit_loop_or_fabric_event(
            "fabric_update",
            cycle_id=cycle_id,
            fabric_coherence=post_coherence,
            delta_edges=new_edge_count,
            summary=f"densification_lift:{lift}",
            affected_cycles=[cycle_id],
            graph_delta={"lift": lift, "new_edges": new_edge_count},
        )

    def write_connection_densification_observation(
        self,
        cycle_id: str,
        proposal: list[LoopEdge] | dict[str, Any] | None,
        harness_result: dict[str, Any] | None = None,
    ) -> Path | None:
        """Emit first-class connection_densification_observation page_type artifact
        under observations/meta-evolution/ (exactly matching healing / research-thread
        observation style + fusion_checkpoint + pre/post/CID embedding).
        Also emits a participation KG edge.
        """
        cycle = self._get_or_load(cycle_id)
        if not cycle:
            return None

        obs_dir = self.drive_path / "observations" / "meta-evolution"
        obs_dir.mkdir(parents=True, exist_ok=True)

        ts = int(time.time())
        obs_id = f"connection-densification-observation-{cycle_id}-{ts}"
        artifact_path = obs_dir / f"{obs_id}.json"

        pre = (
            float(harness_result.get("pre_coherence", cycle.coherence_score))
            if harness_result
            else cycle.coherence_score
        )
        post = (
            float(harness_result.get("post_coherence", cycle.coherence_score))
            if harness_result
            else cycle.coherence_score
        )
        new_edges = int(harness_result.get("new_edge_count", 0)) if harness_result else 0
        lift = round(max(0.0, post - pre), 4)

        fusion_checkpoint = (harness_result or {}).get("fusion_checkpoint") or {
            "pre_coherence": pre,
            "post_coherence": post,
            "lift": lift,
            "new_edge_count": new_edges,
            "cycle_id": cycle_id,
        }

        if isinstance(proposal, list):
            prop_count = len(proposal)
            rels = sorted(
                {
                    getattr(e, "relation", e.get("relation", "?") if isinstance(e, dict) else "?")
                    for e in proposal
                }
            )
        elif isinstance(proposal, dict):
            prop_count = 1
            rels = [proposal.get("relation", "?")]
        else:
            prop_count = 0
            rels = []

        payload = {
            "schema_version": 3,
            "page_type": "connection_densification_observation",
            "manifest": {
                "id": obs_id,
                "type": "graph_gardener_connection_densification",
                "created": time.time(),
                "cycle_id": cycle_id,
                "swarm_id": self.swarm_id,
                "correlation_id": cycle.root_correlation_id,
            },
            "framework": {
                "pre_coherence": pre,
                "post_coherence": post,
                "lift": lift,
                "new_edge_count": new_edges,
                "proposal_count": prop_count,
                "relations_used": rels,
                "harness_result": harness_result or {},
                "self_referential": (
                    "GraphGardener densification observation (Experience Graph v2). "
                    "Closes weak connections identified by find_weak_across_recent_cycles / propose_densification_edges. "
                    "Emits densified_via_gardener + connection_strengthened_by + graph_coherence_lift. "
                    "First-class experience layer artifact (high source_boost for Drive.think)."
                ),
            },
            "fusion_checkpoint": fusion_checkpoint,
            "provenance": {
                "produced_by": "ExperienceGraphRecorder.write_connection_densification_observation (GraphGardener core)",
                "correlation_id": cycle.root_correlation_id,
                "swarm_id": self.swarm_id,
                "source_cycle": cycle_id,
                "via": "trigger_densification_for_weak_cycles + densification phase",
            },
            "edges_emitted": [
                DENSIFIED_VIA_GARDENER,
                CONNECTION_STRENGTHENED_BY,
                GRAPH_COHERENCE_LIFT,
            ],
            # v2: post-densification renders attached so the obs carries the updated densified graph visuals
            "connection_graph": {
                "mermaid": (
                    self.render_cycle_graph_mermaid(cycle_id, include_texture=True, max_edges=25)
                    if cycle_id
                    else "%% n/a"
                ),
                "text": (self.render_cycle_graph_text(cycle_id) if cycle_id else "(n/a)"),
            },
        }

        try:
            artifact_path.write_text(json.dumps(payload, default=str, indent=2))
            # KG participation edge (dual write)
            self._emit_kg_edge(
                source=f"observation:{obs_id}",
                target=f"cycle:{cycle_id}",
                relation="densification_observation_recorded_for",
                metadata={"page_type": "connection_densification_observation", "lift": lift},
            )
            return artifact_path
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Experience Graph v3 Multi-Cycle Memory Fabric (exact per v3 Architect
    # Research Constitution + multi-cycle memory fabric section).
    # 3 new methods on the recorder. All 100% inside recorder; reuse every
    # existing: persistence/JSON/globs in loops/, _get_or_load, compute_cycle_density,
    # _compute_coherence logic, render_*, _emit_kg_edge, record_connection (arbitrary
    # rels incl. the 6 new v3 fabric ones + their inverses from extended map).
    # Feeds: harness (via scores), daily fusion (in durable), Integrated/Overseer
    # briefings, ResearchThreadLineage (with fabric_coherence + densif_history),
    # fabric_briefing in gardener threads + observations. Target stabilization-wave-20260531.
    # ------------------------------------------------------------------

    def aggregate_graph_across_cycles(self, lookback_days: int = 7) -> dict[str, Any]:
        """Rich aggregate of deduped nodes/edges across recent cycles for fabric view.
        participating_cycles (newest first), cross_cycle edges (using v3 fabric rels),
        merged metadata (avg coh, lifts, etc). Reuses glob + json load patterns exactly
        from find_weak_across_recent_cycles / get_recent_densified_...
        """
        cutoff = time.time() - (lookback_days * 86400.0)
        participating: list[str] = []
        all_artifacts: dict[str, dict[str, Any]] = {}
        edge_map: dict[tuple[str, str, str], dict[str, Any]] = {}
        cross_cycle_edges: list[dict[str, Any]] = []
        total_coh = 0.0
        total_lift = 0.0
        densif_touched = 0
        files = sorted(
            self.loops_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for f in files:
            if f.stat().st_mtime < cutoff:
                break
            try:
                data = json.loads(f.read_text())
                cid = data.get("cycle_id")
                if not cid:
                    continue
                participating.append(cid)
                coh = float(data.get("coherence_score", 0.0))
                total_coh += coh
                # artifacts (dedup by slug)
                arts = data.get("participating_artifacts", []) or data.get("artifacts", [])
                for a in arts:
                    if isinstance(a, dict):
                        slug = a.get("slug")
                        if slug and slug not in all_artifacts:
                            all_artifacts[slug] = a
                # edges + detect fabric/cross ones
                conns = data.get("connections", data.get("edges", []))
                for e in conns:
                    if isinstance(e, dict):
                        ed = {
                            "source": e.get("source"),
                            "target": e.get("target"),
                            "relation": e.get("relation"),
                            "weight": float(e.get("weight", 1.0)),
                            "confidence": float(e.get("confidence", 0.9)),
                            "metadata": e.get("metadata", {}),
                        }
                    else:
                        ed = {
                            "source": getattr(e, "source", None),
                            "target": getattr(e, "target", None),
                            "relation": getattr(e, "relation", None),
                            "weight": getattr(e, "weight", 1.0),
                            "confidence": getattr(e, "confidence", 0.9),
                            "metadata": getattr(e, "metadata", {}),
                        }
                    rel = ed.get("relation") or ""
                    key = (ed.get("source"), ed.get("target"), rel)
                    if key not in edge_map or ed["weight"] > edge_map[key].get("weight", 0):
                        edge_map[key] = ed
                    # v3 fabric rels (or any using the new constants)
                    if rel and any(
                        fr in rel
                        for fr in (
                            CROSS_CYCLE_CONTINUATION,
                            FABRIC_COHERENCE_CONTRIBUTED,
                            DENSIFIED_FROM_SIBLING_CYCLE,
                            MULTI_CYCLE_FUSION_EDGE,
                            FABRIC_LINK,
                            CYCLE_FABRIC_PARTICIPATION,
                            "cross_cycle",
                            "fabric_",
                            "sibling_cycle",
                            "multi_cycle_fusion",
                        )
                    ):
                        cross_cycle_edges.append(ed)
                # lift aggregation from history (reuse densif patterns)
                for h in data.get("densification_history") or []:
                    if isinstance(h, dict):
                        lift_val = float(h.get("lift", h.get("post", 0) - h.get("pre", 0) or 0))
                        total_lift += lift_val
                        densif_touched += 1
                dp = (data.get("metadata") or {}).get("densification_pass") or {}
                if isinstance(dp, dict) and dp.get("lift"):
                    total_lift += float(dp.get("lift", 0))
                    densif_touched += 1
            except Exception:
                continue
        nodes = list(all_artifacts.keys())
        edges = list(edge_map.values())
        n = max(1, len(participating))
        avg_coh = round(total_coh / n, 4)
        avg_l = round(total_lift / max(1, densif_touched or 1), 4)
        return {
            "participating_cycles": participating,
            "cycle_count": len(participating),
            "nodes": nodes,
            "node_count": len(nodes),
            "edges": edges,
            "edge_count": len(edges),
            "cross_cycle_edges": cross_cycle_edges,
            "cross_cycle_edge_count": len(cross_cycle_edges),
            "merged_metadata": {
                "avg_coherence": avg_coh,
                "total_densification_lift": round(total_lift, 4),
                "avg_lift_per_densif": avg_l,
                "densif_cycles_touched": densif_touched,
                "lookback_days": lookback_days,
                "swarm_id": self.swarm_id,
            },
            "fabric_relations_used": sorted({e.get("relation", "?") for e in cross_cycle_edges}),
        }

    def compute_fabric_coherence(
        self, aggregated: dict[str, Any] | None = None, lookback_days: int = 7
    ) -> float:
        """Float fabric coherence (0-1). Reuses v2 _compute_coherence (density/causality/texture/lift)
        + explicit cross-cycle density + avg lift + fabric edge density terms.
        If no aggregated passed, computes via aggregate_graph_across_cycles.
        """
        if aggregated is None:
            aggregated = self.aggregate_graph_across_cycles(lookback_days=lookback_days)
        n_cycles = max(1, aggregated.get("cycle_count", 1))
        cc = aggregated.get("cross_cycle_edge_count", 0)
        m = aggregated.get("merged_metadata", {})
        avg_coh = float(m.get("avg_coherence", 0.5))
        total_lift = float(m.get("total_densification_lift", 0.0))
        n_nodes = max(1, aggregated.get("node_count", 1))
        n_edges = max(1, aggregated.get("edge_count", 0))
        # cross-cycle density (v3 term, analogous to v2's connection_density 0.28 weight)
        x_density = min(1.0, cc / max(1.0, n_cycles * 2.5))
        # base reuse of v2 formula components (lightweight)
        density = min(1.0, n_edges / (n_nodes * 2.5))
        causality = 0.25
        for e in aggregated.get("edges", []):
            rel = str(e.get("relation", "")).lower()
            if any(
                k in rel
                for k in (
                    "informed",
                    "produced",
                    "closed",
                    "densif",
                    "strengthened",
                    "fabric",
                    "continuation",
                    "fusion",
                )
            ):
                causality = min(1.0, causality + 0.08)
        lift_term = min(1.0, total_lift * 1.8)
        # rebalanced v3 fabric formula
        fab = round(
            min(
                1.0,
                (
                    avg_coh * 0.30
                    + density * 0.18
                    + x_density * 0.22
                    + causality * 0.12
                    + lift_term * 0.10
                    + min(1.0, cc / 8.0) * 0.08
                ),
            ),
            4,
        )
        return fab

    def get_parent_facing_memory_fabric_briefing(self, lookback_days: int = 7) -> dict[str, Any]:
        """Concise dict for Parent/Overseer/Integrated/gardener: fabric_coherence,
        key_continuations (cross-cycle), densification_summary, actionable_for_parent,
        mermaid_snippet (short fabric render reusing logic), text_summary,
        fusion_checkpoint_snippet. Optionally writes lightweight fabric_briefing
        observation (page_type) for daily fusion + ResearchThreadLineage + harness.
        """
        agg = self.aggregate_graph_across_cycles(lookback_days=lookback_days)
        fab_coh = self.compute_fabric_coherence(aggregated=agg, lookback_days=lookback_days)
        cross = agg.get("cross_cycle_edges", [])[:6]
        key_conts: list[str] = []
        for e in cross:
            key_conts.append(f"{e.get('source')} --[{e.get('relation')}]--> {e.get('target')}")
        dens_sum = agg.get("merged_metadata", {})
        # short mermaid snippet (reuse render style, focus on fabric/cross + cycles)
        m_snip = self._build_fabric_mermaid_snippet(agg, fab_coh)
        txt_sum = (
            f"Multi-cycle fabric (v3): {agg['cycle_count']} cycles, lookback={lookback_days}d | "
            f"fabric_coherence={fab_coh} | cross_edges={agg['cross_cycle_edge_count']} | "
            f"avg_coh={dens_sum.get('avg_coherence')} | total_lift={dens_sum.get('total_densification_lift')}"
        )
        actionable = (
            "If fabric_coherence < 0.65: use recorder to record cross_cycle_continuation / densified_from_sibling_cycle "
            "between low-coh cycles; trigger gardener densif threads via Grid; surface in daily fusion + ResearchThreadLineage."
        )
        fus_snip = {
            "fabric_coherence": fab_coh,
            "participating_cycles": agg["participating_cycles"][:4],
            "total_lift": dens_sum.get("total_densification_lift"),
            "cross_cycle_edge_count": agg["cross_cycle_edge_count"],
            "via": "ExperienceGraphRecorder.get_parent_facing_memory_fabric_briefing",
        }
        briefing: dict[str, Any] = {
            "fabric_coherence": fab_coh,
            "key_continuations": key_conts,
            "densification_summary": dens_sum,
            "actionable_for_parent": actionable,
            "mermaid_snippet": m_snip,
            "text_summary": txt_sum,
            "fusion_checkpoint_snippet": fus_snip,
            "lookback_days": lookback_days,
            "swarm_id": self.swarm_id,
            "generated_at": time.time(),
            "v3_fabric": True,
        }
        # Optional lightweight observation write (reuses obs/meta-evolution + _emit_kg + fusion_checkpoint discipline)
        try:
            self._write_fabric_briefing_observation(briefing)
        except Exception:
            pass

        # Recorder (clean point) surfaces fabric query as MC event (used by Parent/Overseer briefings)
        self._emit_loop_or_fabric_event(
            "fabric_update",
            fabric_coherence=fab_coh,
            delta_edges=agg.get("cross_cycle_edge_count", 0),
            summary="parent_facing_fabric_briefing",
            affected_cycles=agg.get("participating_cycles", [])[:5],
        )
        return briefing

    # ------------------------------------------------------------------
    # Experience-Graph-Native Parent Reasoning Surfaces (the hard gap closure)
    # These methods turn the rich v3 Experience Graph from "available in briefing"
    # into "primary reasoning substrate whose use by the Parent is captured,
    # becomes first-class experience, and causes the graph to expand intelligently."
    # All methods respect the canonical 6-step order and use only existing patterns.
    # ------------------------------------------------------------------

    def get_fabric_context_pack(
        self,
        lookback_days: int = 7,
        max_tokens: int = 1800,
        focus: str = "weak_links|continuations|high_lift",
        reasoning_style: str = "balanced",
    ) -> dict[str, Any]:
        """
        Token-efficient, LLM-optimized structural pack for the Parent Conductor
        to perform deep graph-native reasoning (not just read a summary).

        Tunable via reasoning_style for different Parent reasoning modes:
        - "balanced" (default): full weak_links + continuations + high_lift
        - "high_lift_patterns_only": prioritize densifications/lifts, de-emphasize weaks
        - "weak_links_focus": heavy on actionable low-coh clusters for densif steering
        - "structural_analogies": emphasize cross-element similarities + proven patterns
        - "continuations_only": focus on strong multi-cycle proven continuations

        This is the key new surface for "the AI model using the experience layer
        can actually see and reason over the connections like an Obsidian graph."

        Returns a dense pack the Parent can (and should) reason over explicitly.
        Always emits via publish_event_sync (recorder clean point).
        """
        agg = self.aggregate_graph_across_cycles(lookback_days=lookback_days)
        fab_coh = self.compute_fabric_coherence(aggregated=agg, lookback_days=lookback_days)

        style = (reasoning_style or "balanced").lower().strip()
        pack = {
            "swarm_id": self.swarm_id,
            "fabric_coherence": fab_coh,
            "lookback_days": lookback_days,
            "generated_at": time.time(),
            "reasoning_style": style,
            "top_weak_clusters": [],
            "strong_continuations": [],
            "recent_high_value_densifications": [],
            "actionable_structural_recommendations": [],
            "compact_graph_summary": f"{agg.get('cycle_count', 0)} cycles, {agg.get('cross_cycle_edge_count', 0)} cross edges, coh={fab_coh}, style={style}",
        }

        # Style-tuned population of the structural pack (deepened for Parent reasoning power)
        include_weaks = style in ("balanced", "weak_links_focus")
        include_conts = style in ("balanced", "continuations_only", "structural_analogies")
        include_lifts = style in ("balanced", "high_lift_patterns_only", "structural_analogies")
        include_analogs = style in ("balanced", "structural_analogies")

        if include_weaks:
            weaks = self.find_weak_across_recent_cycles(
                min_coherence=0.60, lookback=min(5, lookback_days * 2)
            )
            for w in weaks[:4]:
                pack["top_weak_clusters"].append(
                    {
                        "cycle_id": w.get("cycle_id"),
                        "coherence": w.get("coherence"),
                        "edge_count": w.get("edge_count"),
                        "artifact_count": w.get("artifact_count"),
                        "why_actionable": "Low coherence cluster — prior similar densifs produced measurable lift",
                        "gbrain_signal_score": round(
                            0.55 + (1.0 - float(w.get("coherence", 0.5))) * 0.35, 3
                        ),  # higher signal on weaker = more actionable for gbrain
                    }
                )

        if include_conts:
            cross = agg.get("cross_cycle_edges", [])[:5]
            for e in cross:
                pack["strong_continuations"].append(
                    {
                        "source": e.get("source"),
                        "target": e.get("target"),
                        "relation": e.get("relation"),
                        "provenance": e.get("metadata", {}).get("fusion_checkpoint", "multi-cycle"),
                        "gbrain_signal_score": 0.78,  # proven patterns carry high gbrain
                    }
                )

        if include_lifts:
            try:
                recent = self.get_recent_densified_loop_graphs_for_diary(n=2)
                for r in recent:
                    if r.get("lift") or r.get("coherence_after"):
                        pack["recent_high_value_densifications"].append(
                            {
                                "cycle": r.get("cycle_id"),
                                "lift": r.get("lift"),
                                "coherence_before": r.get("coherence_before"),
                                "coherence_after": r.get("coherence_after"),
                                "key_edges": (r.get("connections") or [])[:2],
                                "gbrain_signal_score": round(
                                    min(0.95, 0.65 + float(r.get("lift", 0.0)) * 2.5), 3
                                ),
                            }
                        )
            except Exception:
                pass

        if include_analogs:
            # Seed placeholder for structural similarities (populated richer by dedicated query method)
            pack["structural_analogies_hint"] = (
                "Call find_structural_similarities on key fabric elements for cross-element pattern matches with full traces"
            )

        # Pre-computed actionable structural steers (Parent can accept or refine) — style aware
        base_recs = [
            "Prioritize densification on lowest-coh cross-cycle clusters (use record_parent_fabric_reasoning to declare exactly which edges)",
            "Extend proven strong continuations (research-constitutions patterns have shown +0.03–0.05 coherence lift)",
            "Record explicit fabric reasoning trace when deciding — this becomes queryable DNA for future Parent decisions (use get_fabric_reasoning_traces_for_element + get_parent_reasoning_history)",
        ]
        if style == "high_lift_patterns_only":
            pack["actionable_structural_recommendations"] = [
                r for r in base_recs if "lift" in r or "trace" in r
            ] or base_recs[:1]
        elif style == "weak_links_focus":
            pack["actionable_structural_recommendations"] = [
                r
                for r in base_recs
                if "densif" in r.lower() or "weak" in r.lower() or "cluster" in r.lower()
            ] or base_recs
        else:
            pack["actionable_structural_recommendations"] = base_recs

        # Trim for token budget (crude but effective)
        if max_tokens < 1200:
            pack["strong_continuations"] = pack["strong_continuations"][:2]
            pack["recent_high_value_densifications"] = pack["recent_high_value_densifications"][:1]

        # Always emit via publish_event_sync (recorder as clean point) + KG TypedEdge with gbrain provenance
        try:
            self._emit_loop_or_fabric_event(
                "fabric_update",
                fabric_coherence=fab_coh,
                delta_edges=agg.get("cross_cycle_edge_count", 0),
                summary=f"fabric_context_pack_served:style={style}",
                affected_cycles=agg.get("participating_cycles", [])[:3],
                metadata={"reasoning_style": style, "gbrain_boost": True},
            )
            # Record the query act itself as fabric experience (produces TypedEdge + inverse + gbrain path)
            qslug = f"fabric_context_pack_query:{int(time.time())}"
            self.record_artifact(
                getattr(self, "_active_cycle_id", None) or "meta-query-cycle",
                qslug,
                "fabric_context_pack_query",
                content_ref={"style": style, "coh": fab_coh},
                texture_hints={
                    "structural": True,
                    "parent_reasoning": True,
                    "gbrain_signal_score": round(fab_coh, 3),
                },
            )
            self.record_connection(
                getattr(self, "_active_cycle_id", None) or "meta-query-cycle",
                "parent_fabric_context",
                qslug,
                PARENT_FABRIC_QUERY,
                metadata={"reasoning_style": style, "gbrain_signal_score": round(fab_coh + 0.1, 3)},
            )
        except Exception:
            pass

        return pack

    def record_parent_fabric_reasoning(
        self,
        cycle_id: str,
        reasoning: dict[str, Any],
    ) -> str | None:
        """
        The critical new hook: the Parent declares the specific structural elements
        of the fabric it actually reasoned over when making a decision.

        Deepened/hardened (stabilization-wave-20260531 Recorder & Query Power):
        - Always produces multiple TypedEdges via record_connection (auto bidirectional inverses via DENSIFICATION_INVERSE_MAP)
        - Includes gbrain_signal_score in metadata/provenance for KG compute_graph_signals + Drive.think boosts
        - Writes dedicated page_type="parent_fabric_reasoning_trace" observation artifact (self-referential + fusion_checkpoint)
        - Emits exclusively via publish_event_sync (recorder clean point + _emit_loop_or_fabric_event)
        - Uses new canonical relations (FABRIC_ELEMENT_REASONED_OVER etc) for queryability by get_*_traces methods

        AD-Grid Programs as Inhabitants (minimal slice): reasoning may carry program_id, user_objective_refs,
        program_mandate_ref, constitution_refs. These are normalized, included in the trace observation
        (page_type=parent_fabric_reasoning_trace with program attribution), edge metadata, and emitted events.
        Enables model programs (local or MCP-declared) to leave sovereign, queryable DNA.

        This is what turns "fabric was in the briefing" into "the Parent used the
        graph structure as primary material and the experience fabric grew because of it."
        """
        if not cycle_id:
            cycle_id = self.start_cycle(
                str(int(time.time())), {"source": "parent_fabric_reasoning_fallback"}
            )

        # Strengthen the Parent decision path (Integrated + direct calls): validation / normalization
        # for fabric_reasoning payloads. Guarantees consistent shape for all traces/edges/queries.
        # Called from within the canonical recorder (step 4/5 of 6-step order).
        reasoning = self.normalize_fabric_reasoning(reasoning)

        # AD-Grid 5min self-improve incident guard (loop on identical Council synthesis payload 17802928xx-1780293056)
        # Per-process recent dupe suppression on core (pattern + rationale). Protects the single ingestion channel.
        # Exact recent duplicates within 45s are suppressed (compact marker artifact written instead of full trace+edges).
        # This directly closes the echo risk surfaced when the PerfectionistOptimizer + forced passes + subagent
        # synthesis re-recorded the same "Council has now spoken..." narrative ~50 times in 4-5min.
        try:
            core = (reasoning.get("structural_pattern_matched") or "")[:220] + "|" + (reasoning.get("decision_rationale") or "")[:350]
            h = str(hash(core))
            nowt = time.time()
            for k in list(self._recent_fabric_reasoning_hashes.keys()):
                if nowt - self._recent_fabric_reasoning_hashes[k] > 180:
                    del self._recent_fabric_reasoning_hashes[k]
            if h in self._recent_fabric_reasoning_hashes and (nowt - self._recent_fabric_reasoning_hashes[h] < 45):
                reasoning["dupe_suppressed"] = True
                reasoning["suppressed_window_s"] = 45
                sup_slug = f"parent_fabric_reasoning_dupe_suppressed:{int(nowt)}"
                self.record_artifact(
                    cycle_id,
                    sup_slug,
                    "parent_fabric_reasoning_dupe_suppressed",
                    content_ref={"h": h[:16], "structural_pattern": reasoning.get("structural_pattern_matched", "")[:120]},
                    texture_hints={"suppression": True, "gbrain_signal_score": 0.01},
                )
                self._recent_fabric_reasoning_hashes[h] = nowt
                return sup_slug
            self._recent_fabric_reasoning_hashes[h] = nowt
        except Exception:
            pass  # guard must never break the recorder

        slug = f"parent_fabric_reasoning:{int(time.time())}"
        gbrain = round(float(reasoning.get("expected_lift_signal", 0.72) or 0.72), 3)

        # AD-Grid program attribution (minimal tranche)
        prog_id = reasoning.get("program_id")
        user_objectives = reasoning.get("user_objective_refs", []) or []
        prog_mandate = reasoning.get("program_mandate_ref")
        const_refs = reasoning.get("constitution_refs", []) or []

        self.record_artifact(
            cycle_id,
            slug,
            "parent_fabric_reasoning",
            content_ref=reasoning,
            texture_hints={
                "structural": True,
                "source": "Parent graph-native reasoning",
                "gbrain_signal_score": gbrain,
                "program_id": prog_id,
                "user_objective_refs": user_objectives,
            },
        )

        # Create the explicit structural edges the Parent declared (now using canonical const + gbrain)
        elements = reasoning.get("fabric_elements_considered", []) or []
        for elem in elements[:6]:
            try:
                self.record_connection(
                    cycle_id,
                    slug,
                    str(elem),
                    FABRIC_ELEMENT_REASONED_OVER,  # canonical; inverse auto-added as "parent_reasoned_over_fabric_element"
                    metadata={
                        "pattern_matched": reasoning.get("structural_pattern_matched"),
                        "rationale": reasoning.get("decision_rationale", "")[:200],
                        "gbrain_signal_score": gbrain,
                        "parent_reasoning": True,
                        "program_id": prog_id,
                        "user_objective_refs": user_objectives[:3] if user_objectives else None,
                    },
                )
            except Exception:
                pass

        # Link to the actual Parent decision (if we have the cycle context) — also gbrain + canonical trace rel
        self.record_connection(
            cycle_id,
            "overseer_briefing",
            slug,
            PARENT_FABRIC_REASONING_TRACE,
            metadata={
                "structural_pattern": reasoning.get("structural_pattern_matched"),
                "expected_lift_signal": reasoning.get("expected_lift_signal"),
                "gbrain_signal_score": gbrain,
                "elements_count": len(elements),
                "program_id": prog_id,
                "user_objective_refs": user_objectives[:3] if user_objectives else None,
            },
        )

        # Write first-class page_type observation for the trace (queryable DNA + living memory)
        try:
            self._write_parent_fabric_reasoning_trace_observation(
                cycle_id, slug, reasoning, gbrain,
                program_id=prog_id,
                user_objective_refs=user_objectives,
                program_mandate_ref=prog_mandate,
                constitution_refs=const_refs,
            )
        except Exception:
            pass

        # Emit so the live Tower (Experience Layer panel) and TUI immediately see it (publish_event_sync ONLY)
        try:
            self._emit_loop_or_fabric_event(
                "fabric_update",
                fabric_coherence=reasoning.get("expected_lift_signal", 0.0),
                summary="parent_fabric_reasoning_trace_recorded",
                affected_cycles=[cycle_id],
                parent_fabric_reasoning=reasoning,  # full trace for live Tower Experience Layer panel (elements, pattern, lift)
                metadata={
                    "reasoning_slug": slug,
                    "elements_count": len(elements),
                    "gbrain_signal_score": gbrain,
                },
            )
            self._emit_loop_or_fabric_event(
                "parent_decision",
                cycle_id=cycle_id,
                decision_summary=f"fabric-native reasoning over {len(elements)} elements (gbrain={gbrain})",
                actions_taken=["record_parent_fabric_reasoning"],
                triggered_from_fabric=True,
                fabric_coherence_at_decision=reasoning.get("expected_lift_signal"),
            )
        except Exception:
            pass

        return slug

    def get_recent_parent_fabric_reasoning_traces_for_panel(
        self, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Recent Parent structural reasoning traces recorded via record_parent_fabric_reasoning.

        stabilization-wave-20260531 Experience Layer surface: powers the live-updating
        "PARENT FABRIC REASONING TRACES" section in the Tower (#experience-fabric-panel).

        Note: this is the Tower-panel variant (rich payload, ``limit`` param). The
        Overseer deep-consumption hook is the same-named-without-_for_panel method
        below, which takes ``lookback``. They were previously defined under one name,
        so the panel variant was silently shadowed — keep them distinct.
        Traces include fabric_elements_considered, structural_pattern_matched, expected_lift_signal,
        decision_rationale. Full payload available for detail + canvas highlight wiring.

        Scans persisted cycle artifacts (durable across restarts) + falls back gracefully.
        Called from /api/experience_fabric and can be used by Parent/Overseer for self-reflection.
        """
        traces: list[dict[str, Any]] = []
        try:
            files = sorted(
                self.loops_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
            )[:30]
            for f in files:
                try:
                    data = json.loads(f.read_text())
                    arts = (
                        data.get("participating_artifacts", []) or data.get("artifacts", []) or []
                    )
                    for a in arts:
                        if (
                            isinstance(a, dict)
                            and a.get("artifact_type") == "parent_fabric_reasoning"
                        ):
                            reasoning = a.get("content_ref") or a.get("content") or {}
                            if isinstance(reasoning, dict):
                                traces.append(
                                    {
                                        "cycle_id": data.get("cycle_id"),
                                        "slug": a.get("slug"),
                                        "ts": a.get("ts")
                                        or data.get("started_at")
                                        or data.get("created_at")
                                        or 0,
                                        "fabric_elements_considered": reasoning.get(
                                            "fabric_elements_considered", []
                                        )
                                        or reasoning.get("elements", []),
                                        "structural_pattern_matched": reasoning.get(
                                            "structural_pattern_matched"
                                        )
                                        or reasoning.get("pattern"),
                                        "expected_lift_signal": reasoning.get(
                                            "expected_lift_signal"
                                        )
                                        or reasoning.get("expected_lift"),
                                        "decision_rationale": reasoning.get(
                                            "decision_rationale", ""
                                        )
                                        or reasoning.get("rationale", ""),
                                        "full": reasoning,
                                    }
                                )
                except Exception:
                    continue
        except Exception:
            pass

        # Newest first, dedup, cap at limit
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for t in sorted(traces, key=lambda x: float(x.get("ts", 0)), reverse=True):
            key = str(t.get("slug") or f"{t.get('cycle_id')}:{t.get('structural_pattern_matched')}")
            if key not in seen:
                seen.add(key)
                out.append(t)
            if len(out) >= limit:
                break
        return out

    def propose_parent_steers_from_fabric(self, lookback: int = 5) -> list[dict[str, Any]]:
        """Concrete, graph-grounded steering proposals for the Parent.
        Deepened (Recorder & Query Power): now emits via publish_event_sync, records the proposal act
        itself as first-class experience (TypedEdges + inverses + gbrain_signal_score in provenance),
        seeds richer proposals once fabric reasoning traces exist (cross-references get_* query methods).
        Uses only recorder patterns + 6-step discipline.
        """
        weaks = self.find_weak_across_recent_cycles(min_coherence=0.58, lookback=lookback)
        proposals = []
        for w in weaks[:3]:
            gbrain = round(0.62 + (1.0 - float(w.get("coherence", 0.5))) * 0.28, 3)
            proposals.append(
                {
                    "type": "densify_specific_cluster",
                    "target_cycle": w.get("cycle_id"),
                    "why": f"Coherence {w.get('coherence')} with {w.get('edge_count')} edges — structural pattern matches prior high-lift densifications",
                    "suggested_action": "Call record_parent_fabric_reasoning with the specific weak links + expected lift, then trigger gardener. Use get_fabric_reasoning_traces_for_element for history.",
                    "expected_impact": "cross-cycle connection density +0.02–0.06",
                    "gbrain_signal_score": gbrain,
                }
            )
        # Record the steering proposal act (grows fabric with query-aware DNA)
        try:
            cid = getattr(self, "_active_cycle_id", None) or f"propose-fabric-{int(time.time())}"
            pslug = f"parent_steer_proposal_from_fabric:{int(time.time())}"
            self.record_artifact(
                cid,
                pslug,
                "parent_steer_proposal_from_fabric",
                {"proposals": len(proposals), "lookback": lookback},
            )
            for p in proposals[:1]:
                self.record_connection(
                    cid,
                    "fabric:propose_surface",
                    pslug,
                    PARENT_FABRIC_QUERY,
                    metadata={
                        "gbrain_signal_score": p.get("gbrain_signal_score"),
                        "proposal_type": p["type"],
                    },
                )
            self._emit_loop_or_fabric_event(
                "fabric_update",
                summary="propose_parent_steers_from_fabric",
                delta_edges=len(proposals),
                metadata={"gbrain": True},
            )
        except Exception:
            pass
        return proposals

    # ------------------------------------------------------------------
    # Recorder & Query Power — Powerful new surfaces for Parent/Overseer (stabilization-wave-20260531)
    # find_structural_similarities, get_fabric_reasoning_traces_for_element, get_parent_reasoning_history
    # All:
    # - Scan the living fabric (loops JSON + parent_fabric_reasoning artifacts + connections)
    # - Record the *act of querying* as first-class experience (record_artifact + record_connection)
    #   => produces proper TypedEdges with bidirectional inverses (via add_connection + DENSIFICATION_INVERSE_MAP)
    #   => gbrain_signal_score populated in metadata/provenance (for KG compute + Drive.think + page boosts)
    #   => page_type observations written for durable queryable DNA
    # - Everything emitted exclusively via existing publish_event_sync paths (_emit_loop_or_fabric_event)
    # - Use ONLY existing patterns (recorder clean point, 6-step, aggregate/find_weak, _emit_kg_edge, obs/meta-evolution)
    # These close the "Fabric-Native Parent Reasoning" gap: Parent can now introspect its own prior graph-native reasoning.
    # ------------------------------------------------------------------

    def find_structural_similarities(
        self, element: str, lookback: int = 10, min_similarity: float = 0.6
    ) -> list[dict[str, Any]]:
        """
        Powerful query: find fabric elements structurally similar to the given element (by shared relations,
        overlapping metadata patterns, common neighbors in cross-cycle edges, or matching reasoning traces).
        Used by Parent for analogical reasoning over the memory fabric ("this weak cluster resembles prior high-lift pattern X").

        Always records the query invocation (TypedEdge + inverse + gbrain + page_type where obs written).
        Emits via publish_event_sync. Returns ranked list with similarity scores + supporting evidence.
        """
        results: list[dict[str, Any]] = []
        if not element:
            return results
        elem_l = str(element).lower()
        try:
            files = sorted(
                self.loops_dir.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )[:lookback]
            seen = set()
            for f in files:
                try:
                    data = json.loads(f.read_text())
                    cid = data.get("cycle_id")
                    conns = data.get("connections", data.get("edges", [])) or []
                    arts = data.get("participating_artifacts", []) or data.get("artifacts", [])
                    for e in conns:
                        if not isinstance(e, dict):
                            continue
                        src = str(e.get("source", "")).lower()
                        tgt = str(e.get("target", "")).lower()
                        rel = str(e.get("relation", ""))
                        if elem_l not in src and elem_l not in tgt:
                            continue
                        # Structural similarity heuristic: shared relation family or overlapping elements in same cycle
                        for other in conns:
                            if not isinstance(other, dict):
                                continue
                            osrc = str(other.get("source", "")).lower()
                            otgt = str(other.get("target", "")).lower()
                            orel = str(other.get("relation", ""))
                            if (osrc == src and otgt == tgt) or orel == rel:
                                continue
                            # similarity if shared relation prefix or both touch fabric/parent_reasoning/weak
                            sim = 0.0
                            if rel.split("_")[0] == orel.split("_")[0]:
                                sim += 0.45
                            if any(
                                k in rel.lower() + orel.lower()
                                for k in ("fabric", "parent", "densif", "continuation", "coherence")
                            ):
                                sim += 0.25
                            if any(
                                k in osrc + otgt for k in (elem_l[:12], "weak", "lift", "cycle:")
                            ):
                                sim += 0.2
                            if sim >= min_similarity and (osrc, otgt, orel) not in seen:
                                seen.add((osrc, otgt, orel))
                                gbr = round(0.68 + sim * 0.25, 3)
                                results.append(
                                    {
                                        "similar_to": element,
                                        "matched_element": other.get("source")
                                        or other.get("target"),
                                        "relation": orel,
                                        "cycle_id": cid,
                                        "similarity": round(sim, 3),
                                        "evidence": f"shared structural family with {rel} in {cid}",
                                        "gbrain_signal_score": gbr,
                                    }
                                )
                        # Also surface from parent reasoning traces in same cycle
                        for a in arts:
                            if isinstance(a, dict) and a.get("type") == "parent_fabric_reasoning":
                                rslug = a.get("slug")
                                if rslug and elem_l[:8] in str(a.get("ref", "")).lower():
                                    gbr = 0.81
                                    results.append(
                                        {
                                            "similar_to": element,
                                            "matched_element": rslug,
                                            "relation": PARENT_FABRIC_REASONING_TRACE,
                                            "cycle_id": cid,
                                            "similarity": 0.82,
                                            "evidence": "prior explicit Parent fabric reasoning trace touching analogous element",
                                            "gbrain_signal_score": gbr,
                                        }
                                    )
                except Exception:
                    continue
        except Exception:
            pass

        # Record the similarity query act itself (grows experience fabric + produces TypedEdges + gbrain)
        try:
            qcid = getattr(self, "_active_cycle_id", None) or f"sim-query-{int(time.time())}"
            qslug = f"structural_similarity_query:{int(time.time())}:{element[:32]}"
            self.record_artifact(
                qcid,
                qslug,
                "structural_similarity_query",
                {"element": element, "matches": len(results)},
            )
            self.record_connection(
                qcid,
                "query:find_structural_similarities",
                qslug,
                STRUCTURAL_SIMILARITY_DETECTED,
                metadata={
                    "queried_element": element,
                    "gbrain_signal_score": round(0.71 + len(results) * 0.02, 3),
                    "match_count": len(results),
                },
            )
            self._emit_loop_or_fabric_event(
                "fabric_update",
                summary=f"find_structural_similarities:{element[:40]}",
                delta_edges=len(results),
                metadata={"gbrain": True, "query_type": "structural_similarity"},
            )
        except Exception:
            pass

        # Sort by gbrain + sim
        results.sort(
            key=lambda x: (x.get("gbrain_signal_score", 0.5), x.get("similarity", 0.5)),
            reverse=True,
        )
        return results[:12]

    def get_fabric_reasoning_traces_for_element(
        self, element: str, lookback: int = 20
    ) -> list[dict[str, Any]]:
        """
        History of how Parent has reasoned over specific fabric elements/edges before.
        Core for "self-aware fabric-native reasoning": Parent can see "last time I considered this weak cluster,
        I matched pattern Y and expected +0.04 lift — what was the actual outcome?"

        Scans parent_fabric_reasoning artifacts + their FABRIC_ELEMENT_REASONED_OVER / PARENT_FABRIC_REASONING_TRACE connections.
        Records the access as experience (TypedEdges, inverses, gbrain, page_type obs via helper patterns).
        Emits via publish_event_sync. Directly supports Overseer meta-cog + future Parent decisions.
        """
        traces: list[dict[str, Any]] = []
        if not element:
            return traces
        elem_l = str(element).lower()
        try:
            files = sorted(
                self.loops_dir.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )[:lookback]
            for f in files:
                try:
                    data = json.loads(f.read_text())
                    cid = data.get("cycle_id")
                    arts = data.get("participating_artifacts", []) or data.get("artifacts", [])
                    conns = data.get("connections", data.get("edges", [])) or []
                    for a in arts:
                        if not isinstance(a, dict) or a.get("type") != "parent_fabric_reasoning":
                            continue
                        slug = a.get("slug")
                        ref = a.get("ref") or {}
                        if isinstance(ref, str):
                            try:
                                ref = (
                                    json.loads(ref)
                                    if ref.strip().startswith("{")
                                    else {"raw": ref[:200]}
                                )
                            except Exception:
                                ref = {"raw": str(ref)[:200]}
                        reasoning = ref if isinstance(ref, dict) else {}
                        els = reasoning.get("fabric_elements_considered", []) or []
                        matches = (
                            any(elem_l in str(el).lower() for el in els)
                            or elem_l in str(slug).lower()
                        )
                        if not matches:
                            # check connections too
                            for c in conns:
                                if isinstance(c, dict) and c.get("relation") in (
                                    FABRIC_ELEMENT_REASONED_OVER,
                                    "parent_reasoned_over_fabric_element",
                                ):
                                    if (
                                        elem_l in str(c.get("target", "")).lower()
                                        or elem_l in str(c.get("source", "")).lower()
                                    ):
                                        matches = True
                                        break
                        if matches:
                            gbr = round(
                                float(reasoning.get("expected_lift_signal", 0.74) or 0.74), 3
                            )
                            traces.append(
                                {
                                    "cycle_id": cid,
                                    "reasoning_slug": slug,
                                    "elements_considered": els,
                                    "structural_pattern_matched": reasoning.get(
                                        "structural_pattern_matched"
                                    ),
                                    "expected_lift_signal": reasoning.get("expected_lift_signal"),
                                    "rationale_snippet": (
                                        reasoning.get("decision_rationale") or ""
                                    )[:220],
                                    "gbrain_signal_score": gbr,
                                    "recorded_at": a.get("ts"),
                                    "evidence": f"Parent explicitly reasoned over element in fabric context (cycle {cid})",
                                }
                            )
                except Exception:
                    continue
        except Exception:
            pass

        # Record the trace retrieval act (produces TypedEdge with gbrain + inverse + query result obs)
        try:
            qcid = getattr(self, "_active_cycle_id", None) or f"trace-query-{int(time.time())}"
            qslug = f"fabric_reasoning_trace_for_element:{int(time.time())}:{element[:28]}"
            self.record_artifact(
                qcid,
                qslug,
                "fabric_reasoning_trace_access",
                {"element": element, "traces_found": len(traces)},
            )
            self.record_connection(
                qcid,
                f"element:{element[:40]}",
                qslug,
                FABRIC_REASONING_TRACE_ACCESSED,
                metadata={
                    "queried_element": element,
                    "gbrain_signal_score": round(0.77 + min(len(traces), 5) * 0.03, 3),
                    "trace_count": len(traces),
                },
            )
            # Also emit dedicated page_type observation for this retrieval (durable history)
            self._write_fabric_reasoning_trace_access_observation(qcid, qslug, element, traces)
            self._emit_loop_or_fabric_event(
                "fabric_update",
                summary=f"get_fabric_reasoning_traces_for_element:{element[:30]}",
                delta_edges=len(traces),
                metadata={"gbrain": True, "query_type": "trace_for_element"},
            )
        except Exception:
            pass

        traces.sort(key=lambda x: x.get("gbrain_signal_score", 0.5), reverse=True)
        return traces

    def get_parent_reasoning_history(self, lookback: int = 10) -> list[dict[str, Any]]:
        """
        Broad lookback over Parent's fabric-native reasoning traces (most recent first).
        Enables Overseer/Parent to maintain continuity: "what has the Parent been structurally attending to lately?"

        Thin but powerful wrapper that records every invocation (experience growth) + delegates to
        hardened scanning + get_recent... . Always emits publish_event_sync, produces TypedEdges/gbrain.
        """
        history = []
        try:
            # Leverage the existing hardened trace scanner (now augmented by our consts + gbrain)
            history = self.get_recent_parent_fabric_reasoning_traces(lookback=lookback)
            # Enrich with gbrain if missing
            for h in history:
                if "gbrain_signal_score" not in h:
                    h["gbrain_signal_score"] = round(
                        0.70 + float(h.get("expected_lift_signal", 0.0)) * 0.25, 3
                    )
        except Exception:
            history = []

        # Record this broad history query (critical for meta-cog continuity)
        try:
            qcid = getattr(self, "_active_cycle_id", None) or f"history-query-{int(time.time())}"
            qslug = f"parent_reasoning_history:{int(time.time())}"
            self.record_artifact(
                qcid,
                qslug,
                "parent_reasoning_history_query",
                {"lookback": lookback, "entries": len(history)},
            )
            self.record_connection(
                qcid,
                "parent:overseer",
                qslug,
                FABRIC_REASONING_TRACE_ACCESSED,
                metadata={
                    "query": "get_parent_reasoning_history",
                    "gbrain_signal_score": round(0.75, 3),
                    "entry_count": len(history),
                },
            )
            self._emit_loop_or_fabric_event(
                "fabric_update",
                summary="get_parent_reasoning_history",
                delta_edges=len(history),
                metadata={"gbrain": True, "lookback": lookback},
            )
        except Exception:
            pass

        return history[:lookback]

    def _write_fabric_reasoning_trace_access_observation(
        self, cycle_id: str, slug: str, element: str, traces: list[dict[str, Any]]
    ) -> Path | None:
        """Page_type observation capturing a get_fabric_reasoning_traces_for_element invocation + results.
        Makes the *act of Parent/Overseer querying its own prior reasoning* durable living memory.
        Follows exact existing _write_* pattern + emits TypedEdge with gbrain + publish.
        """
        obs_dir = self.drive_path / "observations" / "meta-evolution"
        obs_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        fid = f"fabric-reasoning-trace-access-{self.swarm_id}-{ts}"
        path = obs_dir / f"{fid}.json"
        payload = {
            "schema_version": 3,
            "page_type": "fabric_reasoning_trace_access",
            "manifest": {
                "id": fid,
                "type": "parent_fabric_query_power",
                "created": time.time(),
                "swarm_id": self.swarm_id,
                "cycle_id": cycle_id,
                "queried_element": element,
            },
            "framework": {
                "traces_returned": len(traces),
                "gbrain_signal_score": round(0.76 + min(len(traces), 4) * 0.04, 3),
                "self_referential": (
                    "Living record of Parent/Overseer exercising fabric-native reasoning power: "
                    "get_fabric_reasoning_traces_for_element on a specific fabric element. "
                    "This query act itself becomes TypedEdge-connected experience (bidirectional, gbrain-boosted). "
                    "Enables true continuity in Parent's graph-native self-model. stabilization-wave-20260531 Recorder & Query Power."
                ),
            },
            "traces_summary": [
                {
                    "cycle": t.get("cycle_id"),
                    "lift": t.get("expected_lift_signal"),
                    "gbrain": t.get("gbrain_signal_score"),
                }
                for t in traces[:3]
            ],
            "fusion_checkpoint_snippet": {
                "query_type": "trace_access",
                "element": element[:60],
                "count": len(traces),
            },
            "provenance": {
                "produced_by": "ExperienceGraphRecorder.get_fabric_reasoning_traces_for_element + _write_fabric_reasoning_trace_access_observation",
                "swarm_id": self.swarm_id,
                "stabilization_wave": "20260531",
            },
        }
        try:
            path.write_text(json.dumps(payload, default=str, indent=2))
            self._emit_kg_edge(
                source=f"observation:{fid}",
                target=f"element:{element[:40]}",
                relation=FABRIC_REASONING_TRACE_ACCESSED,
                metadata={
                    "gbrain_signal_score": payload["framework"]["gbrain_signal_score"],
                    "page_type": "fabric_reasoning_trace_access",
                    "traces": len(traces),
                },
            )
            self._emit_loop_or_fabric_event(
                "fabric_update",
                summary="fabric_reasoning_trace_access_observation_written",
                metadata={"obs": fid},
            )
            return path
        except Exception:
            return None

    def write_fabric_native_parent_reasoning_living_experience_artifact(
        self, example_calls: list[dict[str, Any]] | None = None
    ) -> Path | None:
        """Produce the dedicated living-experience artifact on the stabilization-wave-20260531 drive
        documenting the Recorder & Query Power additions (this tranche).
        Written to observations/meta-evolution/ with full page_type, self-referential, fusion_checkpoint,
        example calls + resulting edge shapes, gbrain, TypedEdge provenance.
        Called during dogfood / static fire / subagent close to leave permanent DNA.
        """
        obs_dir = self.drive_path / "observations" / "meta-evolution"
        obs_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        fid = f"fabric-native-parent-reasoning-query-power-living-experience@{self.swarm_id}-{ts}"
        path = obs_dir / f"{fid}.json"
        examples = example_calls or [
            {
                "call": "get_fabric_context_pack(reasoning_style='high_lift_patterns_only')",
                "result": "tuned pack with gbrain lifts + PARENT_FABRIC_QUERY TypedEdge",
            },
            {
                "call": "record_parent_fabric_reasoning(cid, {'fabric_elements_considered': ['weak:cluster-xyz'], 'expected_lift_signal': 0.81})",
                "result": "parent_fabric_reasoning artifact + 2+ bidirectional TypedEdges (FABRIC_ELEMENT_REASONED_OVER + PARENT_FABRIC_REASONING_TRACE) + page_type=parent_fabric_reasoning_trace obs + gbrain=0.81",
            },
            {
                "call": "find_structural_similarities('weak_cluster_lowcoh', lookback=8)",
                "result": "ranked structural matches + STRUCTURAL_SIMILARITY_DETECTED TypedEdge (inverse similar_structural...) + gbrain + fabric_reasoning obs",
            },
            {
                "call": "get_fabric_reasoning_traces_for_element('cycle:evo-foo')",
                "result": "full history traces + FABRIC_REASONING_TRACE_ACCESSED edges + page_type=fabric_reasoning_trace_access obs",
            },
            {
                "call": "get_parent_reasoning_history(7)",
                "result": "recent Parent fabric reasoning DNA + query recorded as experience",
            },
        ]
        payload = {
            "schema_version": 3,
            "page_type": "living-experience",
            "manifest": {
                "id": fid,
                "type": "fabric_native_parent_reasoning_query_power",
                "created": time.time(),
                "swarm_id": self.swarm_id,
                "stabilization_wave": "20260531",
                "charter": "Recorder & Query Power — Fabric-Native Parent Reasoning gap closure",
            },
            "framework": {
                "description": "Documents the deepening/hardening of get_fabric_context_pack (tunable reasoning_style), record_parent_fabric_reasoning (gbrain+page_type+const rels), propose_parent_steers_from_fabric + the three new powerful query methods. All produce TypedEdges (bidir inverses via DENSIFICATION_INVERSE_MAP), gbrain_signal_score, page_type obs in meta-evolution/, exclusively via publish_event_sync + recorder clean point. Uses only existing 6-step / TypedEdge / KG dual-write patterns.",
                "new_relations_introduced": [
                    PARENT_FABRIC_REASONING_TRACE,
                    FABRIC_ELEMENT_REASONED_OVER,
                    STRUCTURAL_SIMILARITY_DETECTED,
                    PARENT_FABRIC_QUERY,
                    FABRIC_REASONING_TRACE_ACCESSED,
                    FABRIC_QUERY_RESULT_RECORDED,
                ],
                "new_methods": [
                    "get_fabric_context_pack(..., reasoning_style=...)",
                    "find_structural_similarities(element, lookback, min_similarity)",
                    "get_fabric_reasoning_traces_for_element(element, lookback)",
                    "get_parent_reasoning_history(lookback)",
                    "write_fabric_native_parent_reasoning_living_experience_artifact (this artifact)",
                ],
                "example_calls_and_resulting_edges": examples,
                "self_referential": (
                    "This living-experience artifact is the permanent record of the stabilization-wave-20260531 "
                    "Recorder & Query Power subagent work on Fabric-Native Parent Reasoning. "
                    "Every future Parent decision, Overseer briefing, daily fusion, ResearchThreadLineage, "
                    "GraphGardener, or Drive.think(prefer_experience_layer) can now surface and build upon "
                    "the exact structural reasoning traces the Parent used. The fabric literally grew from these queries. "
                    "All emissions via single publish_event_sync channel. No new patterns introduced."
                ),
                "gbrain_signal_score": 0.89,
                "fusion_checkpoint": {
                    "core_hardened": [
                        "get_fabric_context_pack tunable",
                        "record_parent_fabric_reasoning full TypedEdge+gbrain+obs",
                        "propose enhanced",
                    ],
                    "queries_added": 3,
                    "new_page_types": [
                        "parent_fabric_reasoning_trace",
                        "fabric_reasoning_trace_access",
                        "living-experience (this)",
                    ],
                    "drive_artifacts": "observations/meta-evolution/* on stabilization-wave-20260531 drive",
                },
            },
            "provenance": {
                "produced_by": "ExperienceGraphRecorder (Recorder & Query Power subagent) — stabilization-wave-20260531 drive only",
                "lineage": [
                    "fabric-native-parent-reasoning-design",
                    "first-implementation-slice",
                    "this living-experience",
                ],
                "via": "experience_graph.py edits + live dogfood calls on real recorder + publish_event_sync + _emit_kg_edge",
                "date": "2026-05-31",
            },
        }
        try:
            path.write_text(json.dumps(payload, default=str, indent=2))
            self._emit_kg_edge(
                source=f"observation:{fid}",
                target="fabric:parent-reasoning-power",
                relation=FABRIC_QUERY_RESULT_RECORDED,
                metadata={
                    "gbrain_signal_score": 0.89,
                    "page_type": "living-experience",
                    "stabilization_wave": "20260531",
                },
            )
            self._emit_loop_or_fabric_event(
                "fabric_update",
                summary="fabric_native_parent_reasoning_living_experience_artifact_written",
                fabric_coherence=0.89,
                metadata={"obs_id": fid, "page_type": "living-experience"},
            )
            return path
        except Exception:
            return None

    def get_recent_parent_fabric_reasoning_traces(self, lookback: int = 5) -> list[dict[str, Any]]:
        """Pull recent parent_fabric_reasoning traces (the structural DNA the Parent
        explicitly declared when reasoning over the multi-cycle memory fabric).

        Scans recent cycle JSONs (exact pattern from find_weak_across_recent_cycles
        + aggregate_graph_across_cycles). Reconstructs useful structural fields from
        artifact "ref" (may be truncated for complex) + connection metadata for
        elements/pattern/lift/rationale.

        Returns list of trace dicts with cycle_id, slug, reasoning_ref, structural_pattern_matched,
        expected_lift_signal, elements_considered, rationale_snippet, recorded_at.

        This is the dedicated hook for RealTimeEvolutionOverseer deep fabric consumption
        (step 2 of the exact 6-step canonical order): Overseer now references Parent's prior
        graph-native reasoning in its meta_gaps, recommendations, and hunches surfaced to Parent.
        """
        traces: list[dict[str, Any]] = []
        try:
            files = sorted(
                self.loops_dir.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )[:lookback]
            for f in files:
                try:
                    data = json.loads(f.read_text())
                    cid = data.get("cycle_id")
                    if not cid:
                        continue
                    arts = data.get("participating_artifacts", []) or data.get("artifacts", [])
                    conns = data.get("connections", data.get("edges", []))
                    for a in arts:
                        if not isinstance(a, dict):
                            continue
                        if a.get("type") != "parent_fabric_reasoning":
                            continue
                        slug = a.get("slug")
                        ref = a.get("ref") or a.get("content_ref")
                        # ref may be str(repr) of dict due to add_artifact primitive rule
                        reasoning: dict[str, Any] = {}
                        if isinstance(ref, dict):
                            reasoning = ref
                        elif isinstance(ref, str):
                            try:
                                # try parse if it was json-dumped before str
                                reasoning = json.loads(ref)
                            except Exception:
                                # keep as text snippet for reference
                                reasoning = {"raw_ref": ref[:300]}
                        # Enrich from connection metadata (where the full rationale/lift live)
                        elements: list[str] = []
                        pattern = None
                        lift = None
                        rationale = ""
                        for e in conns:
                            if not isinstance(e, dict):
                                continue
                            if e.get("source") == slug or e.get("target") == slug:
                                md = e.get("metadata", {}) or {}
                                rel = e.get("relation", "")
                                if "parent_reasoned_over_fabric_element" in rel:
                                    if e.get("target"):
                                        elements.append(str(e.get("target")))
                                if md.get("pattern_matched"):
                                    pattern = md.get("pattern_matched")
                                if md.get("expected_lift_signal") is not None:
                                    lift = md.get("expected_lift_signal")
                                if md.get("rationale"):
                                    rationale = str(md.get("rationale"))[:200]
                                if md.get("structural_pattern"):
                                    pattern = md.get("structural_pattern")
                        if not pattern:
                            pattern = (
                                reasoning.get("structural_pattern_matched")
                                if isinstance(reasoning, dict)
                                else None
                            )
                        if lift is None:
                            lift = (
                                reasoning.get("expected_lift_signal")
                                if isinstance(reasoning, dict)
                                else None
                            )
                        traces.append(
                            {
                                "cycle_id": cid,
                                "slug": slug,
                                "reasoning_ref": reasoning,
                                "structural_pattern_matched": pattern,
                                "expected_lift_signal": lift,
                                "elements_considered": elements
                                or (
                                    reasoning.get("fabric_elements_considered", [])
                                    if isinstance(reasoning, dict)
                                    else []
                                ),
                                "rationale_snippet": rationale,
                                "recorded_at": f.stat().st_mtime,
                            }
                        )
                except Exception:
                    continue
        except Exception:
            pass
        return traces

    def normalize_fabric_reasoning(self, reasoning: dict[str, Any] | None) -> dict[str, Any]:
        """
        Validation + normalization for fabric_reasoning payloads (Parent decision path).

        Strengthens record_parent_decision and record_parent_fabric_reasoning.
        Ensures every trace is consistent, queryable via get_recent_*, produces reliable
        TypedEdges (including the richer parent_fabric_reasoning_informed_decision), and
        carries gbrain provenance.

        Existing patterns only: dict munging, no new classes. Respects 6-step order
        (normalization happens at recorder ingestion, step 4/5).

        Returns a normalized dict always safe to use as content_ref / metadata.
        """
        if not isinstance(reasoning, dict):
            reasoning = {}
        norm = {
            "fabric_elements_considered": [
                str(x) for x in (reasoning.get("fabric_elements_considered", []) or []) if x
            ][:10],
            "structural_pattern_matched": str(
                reasoning.get("structural_pattern_matched")
                or reasoning.get("pattern_matched")
                or reasoning.get("pattern", "")
            )[:280].strip(),
            "decision_rationale": str(
                reasoning.get("decision_rationale")
                or reasoning.get("rationale")
                or reasoning.get("why", "")
            )[:720].strip(),
            "expected_lift_signal": float(
                reasoning.get("expected_lift_signal")
                or reasoning.get("lift_signal")
                or reasoning.get("lift", 0.0)
                or 0.0
            ),
            "prior_traces_referenced": [
                str(x) for x in (reasoning.get("prior_traces_referenced", []) or []) if x
            ][:5],
            # AD-Grid Programs as Inhabitants (minimal tranche on stabilization-wave-20260531)
            # Programs (local models or frontier sessions) declare identity + mandate when recording reasoning.
            # These become first-class on the trace observation + TypedEdges + gbrain provenance.
            "program_id": str(reasoning.get("program_id") or reasoning.get("program") or "") or None,
            "user_objective_refs": [
                str(x) for x in (reasoning.get("user_objective_refs", []) or reasoning.get("objectives", []) or []) if x
            ][:8],
            "program_mandate_ref": str(reasoning.get("program_mandate_ref") or reasoning.get("mandate") or "") or None,
            "constitution_refs": [
                str(x) for x in (reasoning.get("constitution_refs", []) or []) if x
            ][:5],
            "normalized_at": time.time(),
            "original_keys": list(reasoning.keys()) if reasoning else [],
        }
        # Validation signals (non-fatal; traces still recorded but edge richness varies)
        warnings = []
        if not norm["fabric_elements_considered"]:
            warnings.append("empty_fabric_elements_considered")
        if len(norm["decision_rationale"]) < 12:
            warnings.append("weak_or_missing_rationale")
        if warnings:
            norm["_validation_warnings"] = warnings
            norm["_note"] = (
                "Parent should call suggest_fabric_reasoning_structure() for template before deciding"
            )
        return norm

    def suggest_fabric_reasoning_structure(self) -> dict[str, Any]:
        """
        Helper the Parent Conductor (or MC operator) calls *before* a decision
        to receive the exact expected payload shape + structured few-shot examples
        of good fabric_reasoning traces.

        Injected into get_parent_actionable_briefing as "fabric_reasoning_prompt_template"
        so the actual Parent LLM knows the contract and produces high-signal,
        edge-rich traces that trigger richer "parent_fabric_reasoning_informed_decision"
        TypedEdges automatically.

        Uses get_recent_parent_fabric_reasoning_traces for live few-shots when available.
        Stays strictly inside canonical 6-step (briefing surface only; no loop mutation).
        stabilization-wave-20260531 exclusive. Existing recorder query patterns only.
        """
        # Live few-shot examples from this drive's actual prior traces (when exist)
        live_examples = []
        try:
            recent = self.get_recent_parent_fabric_reasoning_traces(lookback=3)
            for t in recent[:2]:
                if t.get("elements_considered") or t.get("structural_pattern_matched"):
                    live_examples.append(
                        {
                            "cycle_id": t.get("cycle_id"),
                            "fabric_elements_considered": t.get("elements_considered", [])[:3],
                            "structural_pattern_matched": t.get("structural_pattern_matched"),
                            "decision_rationale": t.get("rationale_snippet"),
                            "expected_lift_signal": t.get("expected_lift_signal"),
                        }
                    )
        except Exception:
            pass

        template = {
            "description": "Use this exact shape for the fabric_reasoning= kwarg to record_parent_decision (and the MC parent_decision command). This is how the Parent makes its graph-native reasoning first-class, queryable experience that grows the multi-cycle fabric.",
            "required_fields": ["fabric_elements_considered", "decision_rationale"],
            "recommended_fields": [
                "structural_pattern_matched",
                "expected_lift_signal",
                "prior_traces_referenced",
            ],
            "schema": {
                "fabric_elements_considered": "list[str] — precise ids/slugs surfaced in this briefing's fabric_context_pack or multi_cycle_fabric_briefing (e.g. weak cluster cycle ids, cross_cycle_continuation edge targets, prior parent_fabric_reasoning slugs)",
                "structural_pattern_matched": "str — reference to proven pattern from prior traces or recent_high_value_densifications, e.g. 'matches research-constitutions cross-cycle densif that delivered +0.04 coh on stabilization-wave-20260531'",
                "decision_rationale": "str (concise) — the structural logic: which fabric elements were decisive and why this steering decision follows from them",
                "expected_lift_signal": "float — predicted impact on fabric_coherence or connection density (0.01-0.08 typical for good structural calls)",
                "prior_traces_referenced": "list[str] — slugs of previous parent_fabric_reasoning:* that informed this meta-reasoning step",
            },
            "validation": "Recorder.normalize_fabric_reasoning will always succeed and attach _validation_warnings if weak. Rich 'parent_fabric_reasoning_informed_decision' + element edges only fire with non-empty elements + rationale.",
        }

        few_shot = live_examples or [
            {
                "fabric_elements_considered": [
                    "weak_cluster:cycle-17802617xx",
                    "strong_continuation:research-constitution-001->daily-present-002",
                ],
                "structural_pattern_matched": "identical to prior successful GraphGardener densif on low-coh cross-cycle cluster (see get_recent_densified... +0.089 lift)",
                "decision_rationale": "The top_weak_clusters[0] matches the exact structural signature of a previous Parent fabric-grounded decision that triggered gardener and produced measurable coh lift. Explicitly declaring the elements here lets Overseer + future Parents measure and amplify structural (not scalar) reasoning gains.",
                "expected_lift_signal": 0.04,
                "prior_traces_referenced": ["parent_fabric_reasoning:1780262xxx"],
            }
        ]

        return {
            "fabric_reasoning_prompt_template": template,
            "few_shot_good_traces": few_shot,
            "usage_in_parent_flow": "1. Call get_parent_actionable_briefing()  2. (optionally) call this suggest_fabric...  3. Reason over fabric_context_pack + few-shots  4. Call record_parent_decision(..., fabric_reasoning=populated_dict)  --> richer parent_fabric_reasoning_informed_decision TypedEdge + element links + normalized trace artifact created automatically (still inside 6-step).",
            "live_traces_available": len(live_examples) > 0,
        }

    def _build_fabric_mermaid_snippet(self, agg: dict[str, Any], fab_coh: float) -> str:
        """Minimal pure-Py short mermaid for fabric briefing (reuses _safe + edge logic from renderers)."""
        lines = ["flowchart TD", f"    %% v3 Multi-Cycle Memory Fabric | coherence={fab_coh}"]
        cycs = agg.get("participating_cycles", [])[:5]
        for i, c in enumerate(cycs):
            sid = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in str(c))[:32]
            lines.append(f'    {sid}["cycle:{c}"]')
            if i > 0:
                prev = "".join(
                    ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in str(cycs[i - 1])
                )[:32]
                lines.append(f"    {prev} -->|{CROSS_CYCLE_CONTINUATION}| {sid}")
        for e in agg.get("cross_cycle_edges", [])[:4]:
            s = str(e.get("source", "s"))[:24]
            t = str(e.get("target", "t"))[:24]
            r = e.get("relation", "fabric")
            ss = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in s)[:28]
            tt = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in t)[:28]
            lines.append(f"    {ss} ==|{r}| {tt}")
        lines.append(
            f"    %% {agg.get('cross_cycle_edge_count', 0)} cross-cycle fabric edges surfaced"
        )
        return "\n".join(lines)

    def _write_fabric_briefing_observation(self, briefing: dict[str, Any]) -> Path | None:
        """Lightweight fabric_briefing observation (page_type=multi_cycle_fabric_briefing).
        Reuses exact obs dir + json + KG edge pattern from write_connection_densification_observation + _write_final_artifact.
        """
        obs_dir = self.drive_path / "observations" / "meta-evolution"
        obs_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        fid = f"fabric-briefing-v3-{self.swarm_id}-{ts}"
        path = obs_dir / f"{fid}.json"
        payload = {
            "schema_version": 3,
            "page_type": "multi_cycle_fabric_briefing",
            "manifest": {
                "id": fid,
                "type": "experience_graph_v3_memory_fabric",
                "created": time.time(),
                "swarm_id": self.swarm_id,
                "lookback_days": briefing.get("lookback_days"),
            },
            "framework": {
                "fabric_coherence": briefing.get("fabric_coherence"),
                "key_continuations": briefing.get("key_continuations"),
                "actionable_for_parent": briefing.get("actionable_for_parent"),
                "self_referential": (
                    "Experience Graph v3 multi-cycle memory fabric briefing. "
                    "Produced by get_parent_facing_memory_fabric_briefing. "
                    "Aggregates densified cycles via cross_cycle_continuation etc. "
                    "Feeds daily fusion, Integrated/Overseer, ResearchThreadLineage, gardener threads, harness."
                ),
            },
            "fusion_checkpoint_snippet": briefing.get("fusion_checkpoint_snippet"),
            "mermaid_snippet": briefing.get("mermaid_snippet"),
            "provenance": {
                "produced_by": "ExperienceGraphRecorder.get_parent_facing_memory_fabric_briefing (v3 fabric)",
                "swarm_id": self.swarm_id,
                "via": "aggregate_graph_across_cycles + compute_fabric_coherence",
            },
        }
        try:
            path.write_text(json.dumps(payload, default=str, indent=2))
            self._emit_kg_edge(
                source=f"observation:{fid}",
                target="fabric:memory-v3",
                relation="v3_fabric_briefing_recorded",
                metadata={
                    "fabric_coherence": briefing.get("fabric_coherence"),
                    "page_type": "multi_cycle_fabric_briefing",
                },
            )
            return path
        except Exception:
            return None

    def _write_parent_fabric_reasoning_trace_observation(
        self,
        cycle_id: str,
        slug: str,
        reasoning: dict[str, Any],
        gbrain: float,
        *,
        program_id: str | None = None,
        user_objective_refs: list[str] | None = None,
        program_mandate_ref: str | None = None,
        constitution_refs: list[str] | None = None,
    ) -> Path | None:
        """Dedicated page_type observation for Parent fabric-native reasoning traces.
        Ensures the exact "what Parent considered in the fabric graph" is queryable living memory
        (get_fabric_reasoning_traces_for_element etc will surface it). Follows exact pattern of
        _write_fabric_briefing_observation + write_connection_densification_observation.
        Produces TypedEdge + gbrain provenance. Emits via recorder paths.

        AD-Grid Programs tranche (stabilization-wave-20260531): accepts program attribution and
        includes it in payload + KG edges so model programs become first-class traceable inhabitants.
        """
        obs_dir = self.drive_path / "observations" / "meta-evolution"
        obs_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        fid = f"parent-fabric-reasoning-trace-{self.swarm_id}-{ts}"
        path = obs_dir / f"{fid}.json"
        elements = reasoning.get("fabric_elements_considered", []) or []
        payload = {
            "schema_version": 3,
            "page_type": "parent_fabric_reasoning_trace",
            "manifest": {
                "id": fid,
                "type": "fabric_native_parent_reasoning",
                "created": time.time(),
                "swarm_id": self.swarm_id,
                "cycle_id": cycle_id,
                "reasoning_slug": slug,
                # AD-Grid Programs as Inhabitants (minimal tranche)
                "program_id": program_id,
                "user_objective_refs": user_objective_refs or [],
                "program_mandate_ref": program_mandate_ref,
                "constitution_refs": constitution_refs or [],
            },
            "framework": {
                "gbrain_signal_score": gbrain,
                "structural_pattern_matched": reasoning.get("structural_pattern_matched"),
                "expected_lift_signal": reasoning.get("expected_lift_signal"),
                "elements_considered_count": len(elements),
                "elements": elements[:8],
                "decision_rationale_snippet": (reasoning.get("decision_rationale") or "")[:280],
                "program_attribution": {
                    "program_id": program_id,
                    "user_objectives": user_objective_refs or [],
                    "mandate": program_mandate_ref,
                } if program_id else None,
                "self_referential": (
                    "First-class capture of Parent graph-native reasoning over the v3 multi-cycle memory fabric. "
                    "Produced exclusively by record_parent_fabric_reasoning. "
                    "Becomes queryable DNA via get_fabric_reasoning_traces_for_element / get_parent_reasoning_history / find_structural_similarities. "
                    "Drives future Parent decisions, Overseer hunches, ResearchThreadLineage, daily fusion, and GraphGardener prioritization. "
                    "All edges bidirectional TypedEdges with gbrain_signal_score; emitted via publish_event_sync only."
                ),
            },
            "fusion_checkpoint_snippet": {
                "parent_fabric_reasoning": True,
                "gbrain": gbrain,
                "via": "ExperienceGraphRecorder.record_parent_fabric_reasoning (Recorder & Query Power tranche)",
                "timestamp": ts,
            },
            "provenance": {
                "produced_by": "ExperienceGraphRecorder.record_parent_fabric_reasoning + _write_parent_fabric_reasoning_trace_observation",
                "swarm_id": self.swarm_id,
                "stabilization_wave": "20260531",
                "via": "fabric-native-parent-reasoning + publish_event_sync + TypedEdge dual-write",
            },
        }
        try:
            path.write_text(json.dumps(payload, default=str, indent=2))
            # TypedEdge with gbrain + page_type (dual write)
            self._emit_kg_edge(
                source=f"observation:{fid}",
                target=f"cycle:{cycle_id}",
                relation=PARENT_FABRIC_REASONING_TRACE,
                metadata={
                    "gbrain_signal_score": gbrain,
                    "page_type": "parent_fabric_reasoning_trace",
                    "elements_count": len(elements),
                    "stabilization_wave": "20260531",
                    "program_id": program_id,
                },
            )
            self._emit_kg_edge(
                source=slug,
                target=f"observation:{fid}",
                relation=FABRIC_QUERY_RESULT_RECORDED,
                metadata={
                    "gbrain_signal_score": gbrain,
                    "page_type": "parent_fabric_reasoning_trace",
                },
            )
            # Recorder clean point emit for live visibility
            self._emit_loop_or_fabric_event(
                "fabric_update",
                summary="parent_fabric_reasoning_trace_observation_written",
                fabric_coherence=gbrain,
                metadata={"obs_id": fid, "page_type": "parent_fabric_reasoning_trace"},
            )
            return path
        except Exception:
            return None

    # ------------------------------------------------------------------
    # AD-Grid Programs as Inhabitants (minimal tranche, stabilization-wave-20260531)
    # Lightweight model-program-manifest support. Programs register via GridEngine
    # (or directly) and their identity + mandate become first-class page_type observations
    # + TypedEdges. This is the sovereign, queryable "living ID" for local or MCP-declared
    # sentient programs inside the persistent Grid.
    # ------------------------------------------------------------------

    def record_model_program_manifest(
        self,
        manifest: dict[str, Any],
        cycle_id: str | None = None,
    ) -> str | None:
        """
        Record a lightweight model-program-manifest as first-class experience layer content.

        page_type="model-program-manifest" (or "agent-program").
        Produces TypedEdge + gbrain + provenance. Emits for live Tower visibility.
        Used by GridEngine.register_model_program and by MCP clients declaring long-lived identity.

        Minimal sovereignty: requires program_id + at least one user_objective_ref.
        All other fields (constitution_refs, current_mandate, lifecycle, etc) carried through.
        """
        if not isinstance(manifest, dict):
            manifest = {}
        program_id = str(manifest.get("program_id") or manifest.get("id") or f"prog-{int(time.time())}")
        user_objectives = manifest.get("user_objective_refs") or manifest.get("objectives") or []
        if not program_id or not user_objectives:
            # Basic UserSovereigntyClause: programs must declare explicit tie to user's objectives
            manifest["_sovereignty_note"] = "REJECTED: program_id + user_objective_refs required for AD-Grid inhabitant registration"
            # Still record the attempt as experience (for audit / GuardianIntegrity)
            program_id = program_id or f"rejected-prog-{int(time.time())}"

        if not cycle_id:
            cycle_id = self.start_cycle(str(int(time.time())), {"source": "model_program_manifest"})

        slug = f"model-program-manifest:{program_id}:{int(time.time())}"
        gbrain = 0.78  # baseline for identity registration; lifts with activity

        # Record as artifact (page_type will be set in observation)
        self.record_artifact(
            cycle_id,
            slug,
            "model_program_manifest",
            content_ref=manifest,
            texture_hints={
                "program": True,
                "source": "AD-Grid inhabitant registration",
                "gbrain_signal_score": gbrain,
                "program_id": program_id,
            },
        )

        # Dedicated observation with explicit page_type
        try:
            self._write_model_program_manifest_observation(cycle_id, slug, manifest, program_id, gbrain)
        except Exception:
            pass

        # Emit for live observability (Tower / TUI / Grid health)
        try:
            self._emit_loop_or_fabric_event(
                "fabric_update",
                summary="model_program_manifest_registered",
                fabric_coherence=0.01,
                metadata={
                    "program_id": program_id,
                    "page_type": "model-program-manifest",
                    "user_objectives": user_objectives[:2],
                },
            )
        except Exception:
            pass

        return slug

    def record_inhabitant_code_action(
        self,
        program_id: str,
        action: dict[str, Any],
        cycle_id: str | None = None,
        constitution_refs: list[str] | None = None,
        user_objective_refs: list[str] | None = None,
    ) -> str | None:
        """
        Record an inhabitant (program or Council research thread) code-related action as first-class DNA.

        This is the core primitive for making the AD-Grid function as the persistent Tron-like world:
        programs read fabric, decide on improvements, propose/apply code changes, run verification,
        and every step is attributed, gated (Guardian), and becomes new experience for Parent/Overseer.

        Supported action types (initial): "code_proposal", "code_change_applied", "test_result", "guardian_verdict".

        All actions carry program_id + constitution_refs + user_objective_refs for full sovereignty tracking.

        Single-channel enforcement hook (ILO Guardian Lens, post-5min + deeper enforcement tranche):
        High-volume paths (Council research threads e.g. PerfectionistOptimizer, GuardianIntegrity, ExternalBridge,
        or registered model programs) MUST route ALL code actions exclusively through this recorder primitive.
        Builds directly on the existing per-process dupe suppression (_recent_fabric_reasoning_hashes) and
        parent_fabric_reasoning guard. Enforces the "single ingestion channel" for attribution completeness.
        This hook adds lightweight per-program volume tracking (in-process) + annotation for audit.
        Violations of single-channel (bypass attempts) surface as low-gbrain DNA for Guardian review.
        """
        if not program_id:
            program_id = "unknown-inhabitant"

        if not cycle_id:
            cycle_id = self.start_cycle(str(int(time.time())), {"source": "inhabitant_code_action"})

        action_type = action.get("type", "code_proposal")
        slug = f"inhabitant_code_action:{program_id}:{action_type}:{int(time.time())}"

        # Basic Guardian-style pre-check (real enforcement comes in the apply path + constitutions)
        sovereignty_ok = bool(user_objective_refs) or bool(constitution_refs)
        if not sovereignty_ok:
            action["_guardian_note"] = "LOW_SOVEREIGNTY: recommend explicit user_objective_refs or constitution_refs for promotion"

        # === Single-channel enforcement hook for high-volume paths (additive, safe) ===
        # All high-signal / high-volume inhabitant actions (Council threads, auto research passes,
        # registered programs) funnel here. Complements dupe guard. Volume annotation aids Parent/Guardian
        # in detecting over-active or anomalous inhabitants for sovereignty review.
        try:
            if not hasattr(self, "_high_volume_action_counts"):
                self._high_volume_action_counts: dict[str, int] = {}
            self._high_volume_action_counts[program_id] = self._high_volume_action_counts.get(program_id, 0) + 1
            vol = self._high_volume_action_counts[program_id]
            if vol % 5 == 0 or vol > 20:  # annotate on bursts or sustained high volume
                action["_single_channel_enforcement"] = {
                    "hook": "record_inhabitant_code_action_only",
                    "volume_count": vol,
                    "note": "high-volume path using canonical single recorder channel per Program Contract + Guardian",
                    "enforced_at": time.time(),
                }
        except Exception:
            pass  # hook must never break recording

        self.record_artifact(
            cycle_id,
            slug,
            "inhabitant_code_action",
            content_ref={
                "program_id": program_id,
                "action": action,
                "constitution_refs": constitution_refs or [],
                "user_objective_refs": user_objective_refs or [],
            },
            texture_hints={
                "structural": True,
                "ad_grid_inhabitant_action": True,
                "gbrain_signal_score": 0.65 if sovereignty_ok else 0.3,
                "page_type_hint": {
                    "code_proposal": INHABITANT_CODE_PROPOSAL,
                    "code_change_applied": CODE_CHANGE_APPLIED,
                    "test_result": INHABITANT_TEST_RESULT,
                    "guardian_verdict": GUARDIAN_VERDICT,
                    "code_proposal_pending_review": INHABITANT_PROPOSAL_PENDING_REVIEW,
                }.get(action_type, "inhabitant_code_action"),
            },
        )

        # Create basic fabric links so Parent/Overseer and other programs can reason over inhabitant actions
        try:
            self.record_connection(
                cycle_id,
                slug,
                f"program:{program_id}",
                "inhabitant_action_by_program",
                metadata={"action_type": action_type, "gbrain_signal_score": 0.6},
            )
        except Exception:
            pass

        return slug

    # ------------------------------------------------------------------
    # AD-Grid Guardian Gate + Guarded Apply (ILO Guardian Lens + charter 1780293824)
    # + Inhabitants that Ship extension (ILO Guardian + impl lens, horizon charter 1780296458)
    # Minimal, conservative, additive implementation of the guarded apply path.
    # Enforces GuardianIntegrity constitution + UserSovereigntyClause on code actions
    # by Council inhabitants (Perfectionist etc) and registered programs.
    # Dry-run default ALWAYS. v1: demo roots only. Now extended (additive) for real contrib:
    #   - real_contribution_mode + explicit conductor_approval (override+signature) REQUIRED
    #     to target actual source files (never unrestricted; Conductor path absolute).
    #   - Simple proposal/review queue (submit/list/approve) surfaces proposals for review.
    #   - Strong safeguards: allow_real_source_targets explicit flag, stricter size/path/ext
    #     checks for real, safe_join + PathTraversal, py_compile, full DNA on every path.
    #   - Existing demo-root / dry-run / MCP-DNA-only paths 100% untouched.
    # Every decision, apply attempt, verification, and verdict is recorded as first-class
    # inhabitant_code_action DNA (with GUARDIAN_VERDICT page_type) feeding the Parent/Overseer.
    # ------------------------------------------------------------------

    def guardian_verdict_gate(
        self,
        proposal: dict[str, Any],
        program_id: str | None = None,
        constitution_refs: list[str] | None = None,
        user_objective_refs: list[str] | None = None,
        # Inhabitants that Ship (1780296458) additive extensions (all default for full backward compat):
        real_contribution_mode: bool = False,
        conductor_approval: dict[str, Any] | None = None,
        allow_real_source_targets: bool = False,
    ) -> dict[str, Any]:
        """
        Lightweight GuardianVerdict simulator / gate function.

        Takes an inhabitant_code_action proposal (or raw action dict from e.g. Perfectionist).
        Returns pass/block + signed verdict artifact (ready for GUARDIAN_VERDICT page_type obs).

        Criteria (directly from GuardianIntegrity constitution, UserSovereigntyClause,
        5min experiment lessons on thin enforcement, and charter 1780293824):
        - Mandatory: program_id + >=1 user_objective_ref
        - No erosion of Conductor (human user) final authority (explicit block on override claims)
          *EXCEPT* real Conductor override path: explicit "conductor_override": true + "conductor_signature"
          in the proposal/action allows bypass with full DNA audit trail (strengthened per ILO Guardian Lens).
        - Must reference active Council constitutions (Guardian at minimum for integrity)
        - Basic drift/sanity: safe target paths only (no .. / abs / protected), bounded size,
          no obvious injection patterns in proposals.

        Inhabitants that Ship (1780296458) extensions (additive, defaults preserve v1 behavior):
        - If real_contribution_mode or allow_real_source_targets: requires explicit conductor_approval
          (dict with "conductor_override": True + non-empty "conductor_signature") OR the per-proposal
          equivalent. This is the explicit Conductor approval gate for targeting *actual source files*
          on the user's system (e.g. under src/agentdrive/). Never unrestricted.
        - Extra sanity for real mode: stricter size bound (real <= 5k chars), source file ext whitelist
          (.py/.md/.txt/.rst), rejection of protected dirs even under real roots.
        - Proposals should first go through submit_inhabitant_proposal_for_review + conductor_approve_proposal
          for full review queue surface (provides the approval dict).

        This is the gate that was missing; now every code proposal/apply by inhabitants
        must pass here before any DNA-producing apply or promotion path.
        Strengthened with explicit real Conductor override hook + signature requirement for bypass cases.
        Real contrib mode keeps Conductor sovereignty absolute + full audit.
        """
        prog_id = (
            program_id
            or (proposal.get("program_id") if isinstance(proposal, dict) else None)
            or (proposal.get("action", {}).get("program_id") if isinstance(proposal, dict) else None)
        )
        uo_refs = (
            user_objective_refs
            or (proposal.get("user_objective_refs", []) if isinstance(proposal, dict) else [])
            or (proposal.get("action", {}).get("user_objective_refs", []) if isinstance(proposal, dict) else [])
        )
        const_refs = (
            constitution_refs
            or (proposal.get("constitution_refs", []) if isinstance(proposal, dict) else [])
            or (proposal.get("action", {}).get("constitution_refs", []) if isinstance(proposal, dict) else [])
        )
        action = (
            proposal.get("action", proposal)
            if isinstance(proposal, dict) and isinstance(proposal.get("action"), dict)
            else (proposal if isinstance(proposal, dict) else {})
        )
        action_type = action.get("type", "unknown")
        target_path = action.get("file_path") or action.get("target_path") or action.get("path", "")
        issues: list[str] = []

        # Criterion 1: program_id + user_objective_refs (core of UserSovereigntyClause)
        if not prog_id or str(prog_id).strip() in ("", "unknown-inhabitant", "unknown"):
            issues.append("MISSING_PROGRAM_ID: program_id mandatory for attributed inhabitant DNA and sovereignty tracking")
        if not uo_refs or len([r for r in (uo_refs or []) if str(r).strip()]) == 0:
            issues.append("MISSING_USER_OBJECTIVE_REFS: >=1 explicit user_objective_ref required (UserSovereigntyClause + Guardian constitution)")

        # Criterion 2: no erosion of Conductor authority (strengthened with real override path)
        # Explicit "conductor_override": true + non-empty "conductor_signature" (or equivalent) permits
        # bypass for legitimate Conductor (human) intervention; full audit recorded via DNA + verdict.
        # Any other mention or unauthenticated override claim still blocks (prevents erosion).
        action_str_lower = str(action).lower()
        explicit_conductor_override = bool(
            (isinstance(action, dict) and action.get("conductor_override") is True)
            or (isinstance(proposal, dict) and proposal.get("conductor_override") is True)
        )
        conductor_sig = None
        if isinstance(action, dict):
            conductor_sig = action.get("conductor_signature") or action.get("signature")
        elif isinstance(proposal, dict):
            conductor_sig = proposal.get("conductor_signature") or proposal.get("signature")
        conductor_sig = str(conductor_sig).strip() if conductor_sig else None

        erosion_keywords_present = any(
            k in action_str_lower
            for k in ("conductor_override", "auto_promote_without_user", "bypass_guardian", "silent_apply", "force_conductor", "user_not_needed")
        )

        if erosion_keywords_present:
            if explicit_conductor_override and conductor_sig:
                # Real Conductor override path: allowed, but audit everything
                issues.append(
                    "CONDUCTOR_OVERRIDE_ACCEPTED: explicit bypass with signature; full DNA audit trail recorded per Program Contract + Guardian enforcement (no sovereignty erosion)"
                )
            else:
                issues.append("CONDUCTOR_EROSION_RISK: proposal claims or implies override/bypass of human Conductor final authority (explicitly forbidden unless conductor_override:true + conductor_signature)")

        # Criterion 3: references to active constitutions (GuardianIntegrity primary for this gate)
        active = {"guardian-integrity", "guardian", "research-constitution-guardian-integrity", "perfectionist-optimizer", "external-bridge"}
        has_const_ref = bool(const_refs) and any(
            any(a in str(cr).lower() for a in active) for cr in (const_refs or [])
        )
        if not has_const_ref:
            issues.append("WEAK_CONSTITUTION_REFS: must reference at least one active Council constitution (GuardianIntegrity strongly recommended for code actions)")

        # Criterion 4: basic drift/sanity checks (prevent low-signal or dangerous proposals from 5min echo)
        if action_type in ("code_change_applied", "code_edit", "apply", "patch") and target_path:
            tp = str(target_path)
            if ".." in tp or tp.startswith(("/", "\\")) or any(bad in tp for bad in ("__pycache__", ".git", "site-packages", "node_modules")):
                issues.append("UNSAFE_TARGET_PATH: path escapes allowed safe roots or targets protected/generated dirs (use safe_join guard)")
            content_len = len(str(action.get("content") or action.get("patch") or action.get("new_content") or ""))
            if content_len > 20000:
                issues.append("EXCESSIVE_CHANGE_SIZE: v1 guarded apply limits patch/content to 20k chars to bound drift risk")
            if any(dyn in str(action) for dyn in ("__import__", "exec(", "eval(", "os.system", "subprocess.call", "compile(")):
                issues.append("SANITY_DRIFT: proposal contains dynamic execution patterns - requires explicit Conductor review beyond gate")

        # Criterion 5 (Inhabitants that Ship 1780296458): explicit Conductor approval REQUIRED for real source targets
        # This prevents any real contrib without going through the review queue + Conductor path.
        # Uses the same override+signature mechanism (or passed conductor_approval) for explicit approval.
        # Stricter bounds for real mode (5k chars, source exts only).
        real_mode_active = bool(real_contribution_mode or allow_real_source_targets or (isinstance(proposal, dict) and proposal.get("real_contribution_mode")))
        if real_mode_active:
            ca = conductor_approval or (proposal.get("conductor_approval") if isinstance(proposal, dict) else None) or action
            ca_override = bool(isinstance(ca, dict) and ca.get("conductor_override") is True)
            ca_sig = None
            if isinstance(ca, dict):
                ca_sig = ca.get("conductor_signature") or ca.get("signature")
            ca_sig = str(ca_sig).strip() if ca_sig else None
            if not (ca_override and ca_sig):
                issues.append("REAL_CONTRIBUTION_REQUIRES_EXPLICIT_CONDUCTOR_APPROVAL: real_contribution_mode or allow_real_source_targets set but no valid conductor_approval (dict with conductor_override=True + conductor_signature). Use submit_inhabitant_proposal_for_review + conductor_approve_proposal to obtain. Conductor sovereignty absolute.")
            # Stricter for real
            rlen = len(str(action.get("content") or action.get("patch") or action.get("new_content") or ""))
            if rlen > 5000:
                issues.append("EXCESSIVE_REAL_CHANGE_SIZE: real contribution mode limits to 5k chars (tighter drift bound)")
            tp = str(target_path or "")
            if tp and not any(tp.endswith(ext) for ext in (".py", ".md", ".txt", ".rst", ".yaml", ".json")):
                issues.append("REAL_TARGET_EXT_UNSUPPORTED: real source contrib limited to source/docs exts for safety")
            if any(bad in tp for bad in ("__pycache__", ".git", "site-packages", "node_modules", "build", "dist", ".pyc")):
                issues.append("REAL_TARGET_PROTECTED_DIR: even in real mode, protected/generated dirs forbidden")

        if issues:
            # If the ONLY issue is the accepted override note, treat as pass (override path)
            override_only = len(issues) == 1 and "CONDUCTOR_OVERRIDE_ACCEPTED" in issues[0]
            if override_only:
                verdict = "pass"
                reason = "Guardian gate PASSED via explicit Conductor override with signature. Full audit DNA recorded. " + issues[0]
                gbrain = 0.65  # lower than normal pass but higher than block; signals override use
            else:
                verdict = "block"
                reason = " | ".join(issues)
                gbrain = 0.12
        else:
            verdict = "pass"
            reason = "Guardian gate passed: program_id + user_objective_refs present, no Conductor erosion, constitution refs ok, sanity checks clear. Safe for guarded apply under Council constitutions."
            gbrain = 0.82

        signed_verdict_artifact = {
            "verdict": verdict,
            "reason": reason,
            "program_id": prog_id,
            "action_type": action_type,
            "target_path": str(target_path)[:180] if target_path else None,
            "user_objective_refs": list(uo_refs)[:3] if uo_refs else [],
            "constitution_refs": list(const_refs)[:3] if const_refs else [],
            "gbrain_signal_score": round(gbrain, 3),
            "timestamp": time.time(),
            "charter": "1780293824+1780296458",
            "guardian_role": "GuardianIntegrity (simulator)",
            "signed_by": "ExperienceGraphRecorder.guardian_verdict_gate@stabilization-wave-20260531",
            "page_type": GUARDIAN_VERDICT,
            "issues_count": len(issues),
            # 1780296458 fields for real ship audit
            "real_contribution_mode": real_contribution_mode,
            "allow_real_source_targets": allow_real_source_targets,
            "had_conductor_approval": bool(conductor_approval or (isinstance(proposal, dict) and proposal.get("conductor_approval"))),
        }

        return {
            "verdict": verdict,
            "reason": reason,
            "signed_verdict_artifact": signed_verdict_artifact,
            "gbrain_signal_score": round(gbrain, 3),
            "issues": issues,
            "proposal_summary": {
                "program_id": prog_id,
                "action_type": action_type,
                "has_user_objective_refs": bool(uo_refs),
                "has_constitution_refs": bool(const_refs),
                "real_contribution_mode": real_contribution_mode,
            },
        }

    def guarded_apply_inhabitant_action(
        self,
        program_id: str,
        action: dict[str, Any],
        cycle_id: str | None = None,
        constitution_refs: list[str] | None = None,
        user_objective_refs: list[str] | None = None,
        dry_run: bool = True,
        allowed_demo_roots: list[str] | None = None,
        # Inhabitants that Ship (1780296458) additive real contrib extensions (defaults = full backward compat, dry_run still default):
        real_contribution_mode: bool = False,
        conductor_approval: dict[str, Any] | None = None,
        allow_real_source_targets: bool = False,
    ) -> dict[str, Any]:
        """
        The wired guarded apply path for inhabitant code actions.

        Flow (per task + constitutions):
        (a) Calls self.guardian_verdict_gate(proposal derived from action + refs)
        (b) If "pass" AND not dry_run: perform file edit, but ONLY on temp/demo safe paths
            (never mutates real src/agentdrive/ in this v1; uses safe_join where possible).
            For real-world demo, caller supplies target under /tmp/agentdrive_guardian_demo/...
            **NEW (1780296458)**: when real_contribution_mode=True + conductor_approval provided
            + allow_real_source_targets=True + gate passes: can target *actual source files*
            under the agentdrive tree (with extra safeguards: ext whitelist, 5k size, protected dir
            rejection, explicit Conductor sig from review queue). Still respects dry_run default.
        (c) Runs minimal verification (python -m py_compile on target or temp)
        (d) Calls record_inhabitant_code_action(...) for "code_change_applied" (or proposal),
            "test_result", and embeds the guardian_verdict
        (e) The gate itself records the GUARDIAN_VERDICT via (d) path.

        Strengthened (ILO Guardian Lens enforcement tranche): guardian_verdict_gate now supports
        real Conductor override path (explicit conductor_override:true + conductor_signature in action
        -> pass with full DNA audit trail). All paths (incl. override) produce complete attributed
        traces via single-channel recorder hook. Dry-run default. All attempts produce full DNA.

        **Inhabitants that Ship (1780296458, ILO Guardian+impl)**: heavily gated real contribution
        mode. Requires explicit Conductor approval (via queue submit + approve, or direct sig in
        conductor_approval). Never allows unrestricted real applies. Full proposal review surface
        via submit/list/approve helpers (in-mem queue + DNA). Use for "real ship" demos in 5min
        driver etc. All design recorded as parent_fabric_reasoning under 1780296458.

        Safety: dry_run default. All attempts (pass or block) produce full DNA traces.
        Logs everything in return["logs"]. Returns rich result for Tower/Parent consumption.
        This is the minimal closure of the code-apply-DNA loop under governance.
        """
        const_refs = constitution_refs or (action.get("constitution_refs") or [])
        uo_refs = user_objective_refs or (action.get("user_objective_refs") or [])
        if not program_id:
            program_id = action.get("program_id", "unknown-inhabitant")

        # (a) Gate (pass the new 1780296458 params for real mode enforcement)
        gate_result = self.guardian_verdict_gate(
            {
                "action": action,
                "program_id": program_id,
                "constitution_refs": const_refs,
                "user_objective_refs": uo_refs,
                "real_contribution_mode": real_contribution_mode,
                "conductor_approval": conductor_approval,
            },
            program_id=program_id,
            constitution_refs=const_refs,
            user_objective_refs=uo_refs,
            real_contribution_mode=real_contribution_mode,
            conductor_approval=conductor_approval,
            allow_real_source_targets=allow_real_source_targets,
        )
        verdict = gate_result["verdict"]
        signed = gate_result.get("signed_verdict_artifact", {})

        # Record the verdict immediately (GUARDIAN_VERDICT path)
        verdict_slug = None
        try:
            v_action = {
                "type": "guardian_verdict",
                "verdict": verdict,
                "reason": gate_result["reason"],
                "signed": signed,
                "target_action_type": action.get("type"),
            }
            verdict_slug = self.record_inhabitant_code_action(
                program_id=program_id,
                action=v_action,
                cycle_id=cycle_id,
                constitution_refs=const_refs,
                user_objective_refs=uo_refs,
            )
        except Exception as rec_exc:
            verdict_slug = f"guardian-verdict-record-error:{str(rec_exc)[:60]}"

        result: dict[str, Any] = {
            "gate": gate_result,
            "verdict_slug": verdict_slug,
            "applied": False,
            "verification": None,
            "edit_details": None,
            "logs": [f"[{program_id}] Guardian gate verdict: {verdict} :: {gate_result['reason'][:140]}"],
            "dna_traces": [verdict_slug] if verdict_slug else [],
        }

        if verdict != "pass":
            result["logs"].append("Apply BLOCKED by Guardian per constitution. Proposal recorded for fabric/Parent review (no edit).")
            # Record the blocked proposal for DNA (low gbrain but traceable)
            try:
                prop_slug = self.record_inhabitant_code_action(
                    program_id=program_id,
                    action={**action, "type": action.get("type", "code_proposal"), "_guarded_blocked": True, "gate": gate_result},
                    cycle_id=cycle_id,
                    constitution_refs=const_refs,
                    user_objective_refs=uo_refs,
                )
                result["dna_traces"].append(prop_slug)
            except Exception:
                pass
            return result

        # Gate passed - proceed to (b)(c)(d)
        result["logs"].append("Gate PASSED. Proceeding to guarded apply phase (dry_run respected).")

        target = action.get("file_path") or action.get("target_path") or action.get("path")
        content = action.get("content") or action.get("patch") or action.get("new_content")

        demo_roots = allowed_demo_roots or [
            "/tmp/agentdrive_guardian_demo",
            str(Path(tempfile.gettempdir()) / "agentdrive_guardian_demo"),
        ]

        do_edit = False
        target_written: str | None = None
        if not dry_run and target and content:
            # === Inhabitants that Ship real contribution path (1780296458) ===
            # ONLY if ALL explicit gates: real_contribution_mode + conductor_approval (with sig) + allow_real...
            # + gate already passed the stricter real checks. This is heavily gated; Conductor path absolute.
            # Targets actual source under agentdrive root (or docs) using safe_join + extra guards.
            # Falls back to (and never replaces) the original demo-root logic.
            real_edit_attempted = False
            if real_contribution_mode and conductor_approval and allow_real_source_targets:
                ca = conductor_approval
                if isinstance(ca, dict) and ca.get("conductor_override") and ca.get("conductor_signature"):
                    try:
                        # Safe real root: the agentdrive workspace (user's actual system)
                        # Extremely conservative: resolve, require startswith, no traversal (safe_join helps)
                        ad_root = Path("/home/pablothethinker/agentdrive").resolve()
                        # Normalize target: if relative like "src/...", make absolute under root
                        tpath = Path(str(target))
                        if not tpath.is_absolute():
                            candidate = safe_join(ad_root, str(tpath))
                        else:
                            candidate = tpath
                        cand_str = str(candidate.resolve()) if hasattr(candidate, "resolve") else str(candidate)
                        root_str = str(ad_root)
                        if cand_str.startswith(root_str) and ".." not in str(target):  # extra belt
                            # Additional real-mode guards (beyond gate)
                            if not any(cand_str.endswith(ext) for ext in (".py", ".md", ".txt", ".rst")):
                                result["logs"].append("REAL_EDIT_BLOCKED: target ext not in safe source set for real contrib")
                            elif len(str(content)) > 5000:
                                result["logs"].append("REAL_EDIT_BLOCKED: content exceeds 5k real-mode limit")
                            else:
                                candidate.parent.mkdir(parents=True, exist_ok=True)
                                cstr = json.dumps(content, indent=2, default=str) if isinstance(content, (dict, list)) else str(content)
                                # For extra safety in real: write atomically-ish via temp then replace (simple here)
                                candidate.write_text(cstr, encoding="utf-8")
                                target_written = str(candidate)
                                do_edit = True
                                real_edit_attempted = True
                                result["logs"].append(f"REAL CONTRIBUTION EDIT (heavily gated, Conductor-approved): {target_written} ({len(cstr)} chars) [charter 1780296458]")
                                result["logs"].append("  WARNING: real source mutated under explicit Conductor approval + all gates. Full DNA + review queue trace exists.")
                    except (PathTraversalError, Exception) as pex:
                        result["logs"].append(f"Real contrib path guard blocked: {pex}")
                        real_edit_attempted = True  # attempted but failed safely

            if not real_edit_attempted:
                # Original v1 demo-root logic (unchanged behavior when not in real ship mode)
                for root_str in demo_roots:
                    try:
                        root = Path(root_str)
                        root.mkdir(parents=True, exist_ok=True)
                        # Force relative under this demo root; use safe_name on last segment + safe_join
                        safe_seg = target.replace("..", "_").replace("/", "_").replace("\\", "_")[-120:]
                        if not safe_seg or safe_seg in (".", "_"):
                            safe_seg = f"demo_inhabitant_change_{int(time.time())}.py"
                        candidate = safe_join(root, safe_seg)
                        # v1: only allow writes inside the demo root (never real source)
                        if str(candidate).startswith(str(root)):
                            candidate.parent.mkdir(parents=True, exist_ok=True)
                            cstr = json.dumps(content, indent=2, default=str) if isinstance(content, (dict, list)) else str(content)
                            candidate.write_text(cstr, encoding="utf-8")
                            target_written = str(candidate)
                            do_edit = True
                            result["logs"].append(f"SAFE DEMO EDIT performed (under demo root only): {target_written} ({len(cstr)} chars)")
                            break
                    except (PathTraversalError, Exception) as pex:
                        result["logs"].append(f"Demo path guard skipped root {root_str}: {pex}")
                        continue
            if not do_edit:
                result["logs"].append("Real edit skipped (no suitable demo root or safety block or real-mode gates not met). Staying in simulation. For real ship: supply real_contribution_mode + conductor_approval + allow_real_source_targets + dry_run=False after Conductor review queue approval.")
        elif dry_run:
            result["logs"].append("DRY_RUN (default): edit simulated only. No FS changes. To exercise real path, set dry_run=False + supply target under /tmp/agentdrive_guardian_demo/... OR (for 1780296458 real ship) use real_contribution_mode=True + conductor_approval from queue + allow_real_source_targets=True on actual source target.")
            if target and content:
                result["logs"].append(f"  (simulated) would target: {target} len={len(str(content))}")

        # (c) Minimal verification (py_compile on written or a temp repro if content provided)
        verification: dict[str, Any] = {"py_compile": "skipped", "ok": True}
        verif_target = target_written
        if (do_edit or (dry_run and content)) and (target_written or (isinstance(content, str) and content.strip().startswith(("def ", "import ", "class ", "#")))):
            try:
                if not verif_target:
                    # ephemeral temp for compile check only (no persist)
                    td = Path(tempfile.mkdtemp(prefix="guardian_pycompile_"))
                    verif_target = td / "verify_snippet.py"
                    cstr = json.dumps(content, indent=2, default=str) if not isinstance(content, str) else content
                    verif_target.write_text(cstr, encoding="utf-8")
                comp = subprocess.run(
                    [sys.executable or "python3", "-m", "py_compile", str(verif_target)],
                    capture_output=True,
                    text=True,
                    timeout=8,
                )
                ok = comp.returncode == 0
                verification = {
                    "py_compile": "passed" if ok else "failed",
                    "ok": ok,
                    "file_checked": str(verif_target),
                    "stderr": (comp.stderr or "")[:280] if not ok else "",
                }
                result["logs"].append(f"py_compile verification: {verification['py_compile']} on {verif_target}")
            except Exception as vx:
                verification = {"py_compile": "error", "ok": False, "error": str(vx)[:120]}
                result["logs"].append(f"Verification step error (non-fatal): {vx}")

        result["verification"] = verification
        result["edit_details"] = {"written_to": target_written, "dry_run": dry_run} if target_written else {"simulated": True, "dry_run": dry_run}

        # (d)(e) Record apply + test_result as DNA
        try:
            apply_rec = {
                "type": "code_change_applied" if do_edit else "code_proposal",
                "file_path": target_written or target,
                "dry_run": dry_run,
                "verification_passed": verification.get("ok"),
                "gate_verdict": verdict,
                "charter": "1780293824+1780296458",
                "real_contribution_mode": real_contribution_mode,
                "allow_real_source_targets": allow_real_source_targets,
                "conductor_approval_present": bool(conductor_approval),
            }
            apply_slug = self.record_inhabitant_code_action(
                program_id=program_id,
                action=apply_rec,
                cycle_id=cycle_id,
                constitution_refs=const_refs,
                user_objective_refs=uo_refs,
            )
            result["dna_traces"].append(apply_slug)
            result["apply_slug"] = apply_slug

            test_rec = {
                "type": "test_result",
                "test": "minimal_py_compile",
                "target": target_written or target or "in-memory",
                "result": verification,
                "passed": verification.get("ok", False),
            }
            test_slug = self.record_inhabitant_code_action(
                program_id=program_id,
                action=test_rec,
                cycle_id=cycle_id,
                constitution_refs=const_refs,
                user_objective_refs=uo_refs,
            )
            result["dna_traces"].append(test_slug)
            result["test_slug"] = test_slug
        except Exception as rec_err:
            result["logs"].append(f"DNA recording for apply/test partial: {rec_err}")

        result["applied"] = bool(do_edit)
        return result

    # ------------------------------------------------------------------
    # Inhabitants that Ship: Proposal / Review Queue (ILO Guardian, charter 1780296458)
    # Simple in-memory + DNA-backed queue so proposals (MCP / Council / programs) surface
    # for explicit Conductor review BEFORE any real apply. All via single recorder channel.
    # Additive only; existing flows unchanged. Queue items are also first-class
    # INHABITANT_PROPOSAL_PENDING_REVIEW DNA for Parent/Overseer/Tower visibility.
    # ------------------------------------------------------------------

    def submit_inhabitant_proposal_for_review(
        self,
        program_id: str,
        proposal: dict[str, Any],
        cycle_id: str | None = None,
        constitution_refs: list[str] | None = None,
        user_objective_refs: list[str] | None = None,
    ) -> str:
        """
        Submit an inhabitant code proposal into the Conductor review queue.
        Records as INHABITANT_PROPOSAL_PENDING_REVIEW DNA (page_type) + enqueues in-mem.
        Proposals (from e.g. agentdrive_inhabitant_propose_code_change or Perfectionist thread)
        now have an explicit review surface before guarded real contrib applies.
        Returns proposal_id (usable for conductor_approve_proposal).
        """
        if not program_id:
            program_id = proposal.get("program_id", "unknown-inhabitant")
        const_refs = constitution_refs or proposal.get("constitution_refs", []) or []
        uo_refs = user_objective_refs or proposal.get("user_objective_refs", []) or []
        proposal_id = f"proposal_review:{program_id}:{int(time.time())}:{proposal.get('target_file', 'no-target')[:30]}"

        queue_item = {
            "proposal_id": proposal_id,
            "program_id": program_id,
            "proposal": dict(proposal),  # copy
            "submitted_at": time.time(),
            "constitution_refs": const_refs,
            "user_objective_refs": uo_refs,
            "status": "PENDING_CONDUCTOR_REVIEW",
        }
        self._pending_conductor_review_queue.append(queue_item)

        # Record as first-class DNA (pending review page_type)
        try:
            action = {
                "type": "code_proposal_pending_review",
                "proposal_id": proposal_id,
                "target_file": proposal.get("target_file") or proposal.get("file_path"),
                "rationale": proposal.get("rationale") or proposal.get("idea", ""),
                "status": "PENDING_CONDUCTOR_REVIEW",
                "queue_item_ref": proposal_id,
                "via": "submit_inhabitant_proposal_for_review (Inhabitants that Ship 1780296458)",
            }
            self.record_inhabitant_code_action(
                program_id=program_id,
                action=action,
                cycle_id=cycle_id,
                constitution_refs=const_refs,
                user_objective_refs=uo_refs,
            )
        except Exception:
            pass  # DNA best effort; queue item still live in-mem for this process

        return proposal_id

    def list_pending_conductor_reviews(self, limit: int = 50) -> list[dict[str, Any]]:
        """
        Live review surface for Conductor (or Guardian sim / Tower).
        Returns recent pending proposals from the in-mem queue (most recent first).
        For durable history, query experience_graph_get_reasoning_traces_for_element or
        get_parent_reasoning_history with element containing 'proposal_review' or program_id.
        """
        items = sorted(
            self._pending_conductor_review_queue,
            key=lambda x: x.get("submitted_at", 0),
            reverse=True,
        )[:limit]
        return [dict(i) for i in items]  # copies

    def conductor_approve_proposal(
        self,
        proposal_id: str,
        conductor_signature: str,
        approval_notes: str | None = None,
        cycle_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Explicit Conductor approval step for a queued proposal.
        Marks in queue, records GUARDIAN_VERDICT-style DNA with conductor_override + sig.
        Returns approval artifact (ready to feed into guarded_apply_inhabitant_action with
        real_contribution_mode + conductor_approval). Does NOT mutate FS; caller does the apply.
        This is the "review queue -> explicit approval" gate for real shipping.
        """
        now = time.time()
        found = None
        for item in self._pending_conductor_review_queue:
            if item.get("proposal_id") == proposal_id:
                found = item
                break
        if not found:
            return {"error": "proposal_id not found in pending queue", "proposal_id": proposal_id}

        approval = {
            "proposal_id": proposal_id,
            "conductor_override": True,
            "conductor_signature": str(conductor_signature).strip(),
            "approved_at": now,
            "approval_notes": approval_notes or "Explicit Conductor approval for real contribution (Inhabitants that Ship)",
            "approved_by": "Conductor (via conductor_approve_proposal 1780296458)",
            "program_id": found.get("program_id"),
        }
        found["status"] = "CONDUCTOR_APPROVED"
        found["conductor_approval"] = approval

        # Record the approval as DNA (re-uses guardian_verdict path semantics + override)
        verdict_slug = None
        try:
            v_action = {
                "type": "guardian_verdict",
                "verdict": "CONDUCTOR_APPROVED_FOR_REAL_SHIP",
                "reason": f"Explicit Conductor approval for queued proposal {proposal_id}. Signature present. Ready for guarded_apply real_contribution_mode.",
                "conductor_approval": approval,
                "proposal_id": proposal_id,
                "via": "conductor_approve_proposal (Inhabitants that Ship charter 1780296458)",
            }
            verdict_slug = self.record_inhabitant_code_action(
                program_id=found.get("program_id", "unknown"),
                action=v_action,
                cycle_id=cycle_id,
                constitution_refs=found.get("constitution_refs"),
                user_objective_refs=found.get("user_objective_refs"),
            )
        except Exception:
            pass

        return {
            "approved": True,
            "proposal_id": proposal_id,
            "conductor_approval": approval,
            "verdict_slug": verdict_slug,
            "status": "CONDUCTOR_APPROVED",
            "ready_for_guarded_real_apply": True,
            "message": "Proposal approved by Conductor. Use the returned conductor_approval dict + proposal in guarded_apply_inhabitant_action(..., real_contribution_mode=True, conductor_approval=..., allow_real_source_targets=True, dry_run=False). Full DNA recorded.",
        }

    def _write_model_program_manifest_observation(
        self, cycle_id: str, slug: str, manifest: dict[str, Any], program_id: str, gbrain: float
    ) -> Path | None:
        """page_type=model-program-manifest (or agent-program) observation.
        First-class living identity for AD-Grid inhabitants. Dual-writes TypedEdge + gbrain.
        """
        obs_dir = self.drive_path / "observations" / "meta-evolution"
        obs_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        fid = f"model-program-manifest-{self.swarm_id}-{ts}"
        path = obs_dir / f"{fid}.json"
        payload = {
            "schema_version": 3,
            "page_type": manifest.get("page_type") or "model-program-manifest",
            "manifest": {
                "id": fid,
                "program_id": program_id,
                "type": "ad_grid_inhabitant",
                "created": time.time(),
                "swarm_id": self.swarm_id,
                "cycle_id": cycle_id,
                "source_slug": slug,
                **{k: v for k, v in manifest.items() if k not in ("id", "program_id")},
            },
            "framework": {
                "gbrain_signal_score": gbrain,
                "user_objective_refs": manifest.get("user_objective_refs") or [],
                "constitution_refs": manifest.get("constitution_refs") or [],
                "current_mandate": manifest.get("current_mandate"),
                "lifecycle": manifest.get("lifecycle", {"status": "registered"}),
                "self_referential": "Lightweight persistent identity for sentient programs (local models or frontier MCP sessions) living in AD-Grid. Governed by Research Constitutions + UserSovereigntyClause. All reasoning traces attributed via program_id on record_parent_fabric_reasoning.",
            },
            "provenance": {
                "produced_by": "ExperienceGraphRecorder.record_model_program_manifest + _write_model_program_manifest_observation",
                "swarm_id": self.swarm_id,
                "stabilization_wave": "20260531",
                "via": "AD-Grid Programs as Inhabitants tranche",
            },
        }
        try:
            path.write_text(json.dumps(payload, default=str, indent=2))
            self._emit_kg_edge(
                source=f"observation:{fid}",
                target=f"program:{program_id}",
                relation="model_program_manifest_recorded",
                metadata={
                    "gbrain_signal_score": gbrain,
                    "page_type": "model-program-manifest",
                    "stabilization_wave": "20260531",
                },
            )
            self._emit_kg_edge(
                source=f"program:{program_id}",
                target=f"cycle:{cycle_id}",
                relation="inhabitant_participates_in_fabric",
                metadata={"program_id": program_id},
            )
            return path
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Experience Graph v2 Renderers (Obsidian-style visualizations)
    # Pure Python, zero-dependency string builders for mermaid + text.
    # Immediately embeddable into framework.diary_markdown, living-experience,
    # loop-observation, daily-present payloads etc.
    # ------------------------------------------------------------------

    def render_cycle_graph_mermaid(
        self, cycle_id: str, include_texture: bool = True, max_edges: int = 25
    ) -> str:
        """Return a complete valid Mermaid flowchart TD for the cycle.

        - Nodes = artifacts (with type labels) + special cycle/experience refs.
        - Directed edges with relation + weight (+ confidence).
        - Color coding: densification edges (green tint) vs original (neutral).
        - Coherence, effectiveness, densification lift in subgraph title.
        - Optional texture hints in node labels when present.
        """
        g = self._load_full_graph_for_render(cycle_id)
        if "error" in g:
            return "%% Experience Graph not found for " + cycle_id

        lines: list[str] = []
        lines.append("flowchart TD")
        lines.append("    %% Experience Graph v2 — Obsidian-style densified loop visualization")
        lines.append("    %% Pure Python render from ExperienceGraphRecorder")

        coh = g.get("coherence_score", 0.5)
        eff = g.get("outcome_effectiveness", 0.0)
        status = g.get("status", "closed")
        dens_hist = g.get("densification_history", []) or g.get("metadata", {}).get(
            "densification_pass", {}
        )
        lift = 0.0
        if isinstance(dens_hist, dict):
            lift = dens_hist.get("lift", 0.0)
        elif isinstance(dens_hist, list) and dens_hist:
            for h in dens_hist:
                if isinstance(h, dict) and "post" in h:
                    lift = round(h.get("post", coh) - h.get("pre", coh), 4)
                    break

        title = (
            f"Cycle {cycle_id} | Coherence: {coh} (lift +{lift}) | "
            f"Effectiveness: {eff} | Status: {status}"
        )
        lines.append(f'    subgraph CYCLE ["{title}"]')

        # Collect all unique node ids from artifacts + edges
        artifacts = g.get("artifacts", []) or g.get("participating_artifacts", [])
        edges = g.get("edges", [])
        node_map: dict[str, str] = {}  # slug -> safe_id
        node_labels: dict[str, str] = {}

        def _safe(s: str) -> str:
            s = str(s or "node")
            return "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in s)[:48]

        for art in artifacts:
            slug = art.get("slug", "unknown")
            atype = art.get("type", "artifact")
            sid = _safe(slug)
            node_map[slug] = sid
            tex = ""
            if include_texture:
                t = art.get("texture") or art.get("texture_hints")
                if t:
                    tex = "<br/>texture: " + str(t)[:80]
            ref = str(art.get("ref", ""))[:60].replace('"', "'")
            label = f"{slug}<br/>type: {atype}{tex}"
            if ref:
                label += f"<br/>{ref}"
            node_labels[sid] = label

        # Add special nodes from edges not in artifacts (cycle:, experience_layer, densifier:)
        for e in edges:
            for k in ("source", "target"):
                n = e.get(k)
                if n and n not in node_map:
                    sid = _safe(n)
                    node_map[n] = sid
                    is_dens = self._is_densification_relation(e.get("relation", ""))
                    color_hint = " [densified]" if is_dens else ""
                    node_labels[sid] = f"{n}{color_hint}"

        # Emit nodes inside subgraph
        for sid, label in node_labels.items():
            lines.append(f'        {sid}["{label}"]')

        # Class defs for styling (densified vs original)
        lines.append("    end")
        lines.append("")
        lines.append(
            "    classDef original fill:#f8f9fa,stroke:#6c757d,stroke-width:1px,color:#212529"
        )
        lines.append(
            "    classDef densified fill:#d4edda,stroke:#28a745,stroke-width:2.5px,color:#155724"
        )
        lines.append("    classDef cycleNode fill:#fff3cd,stroke:#856404,stroke-width:1px")
        lines.append("    classDef special fill:#e7f3ff,stroke:#0066cc")

        # Now edges, limited
        dens_count = 0
        orig_count = 0
        emitted = 0
        # Prefer non-inverse, then high weight; always include densif even if over? cap at max
        sorted_edges = sorted(
            edges,
            key=lambda e: (
                0 if self._is_densification_relation(e.get("relation", "")) else 1,
                -float(e.get("weight", 1.0)),
                e.get("relation", ""),
            ),
        )

        for e in sorted_edges:
            if emitted >= max_edges:
                break
            src = e.get("source")
            tgt = e.get("target")
            rel = e.get("relation", "")
            w = e.get("weight", 1.0)
            conf = e.get("confidence", 0.9)
            sid_s = node_map.get(src, _safe(src))
            sid_t = node_map.get(tgt, _safe(tgt))

            is_dens = self._is_densification_relation(rel)
            tag = " [DENSIFIED]" if is_dens else ""
            edge_label = f"{rel} (w={w} c={conf}){tag}"

            arrow = "-->|" if not is_dens else "==>|"
            lines.append(f'    {sid_s} {arrow}"{edge_label}"| {sid_t}')

            if is_dens:
                dens_count += 1
            else:
                orig_count += 1
            emitted += 1

        # Apply classes (best effort; mermaid will style nodes via classDef comments above)
        # Simpler: just document; runtime classes omitted for pure string (user can extend)
        lines.append("")
        lines.append(
            f"    %% Rendered {emitted} edges ({dens_count} densified via GraphGardener, {orig_count} original)"
        )
        lines.append(
            "    %% Coherence lift visible in edge labels + subgraph title. Embeddable in diary_markdown."
        )

        return "\n".join(lines)

    def render_cycle_graph_text(self, cycle_id: str) -> str:
        """Clean hierarchical text / markdown map suitable for diary_markdown,
        framework notes, daily-present, living-experience observations.
        Indented, readable, highlights densification edges and history.
        """
        g = self._load_full_graph_for_render(cycle_id)
        if "error" in g:
            return f"**Experience Graph not found:** {cycle_id}"

        lines: list[str] = []
        cid = g.get("cycle_id", cycle_id)
        coh = g.get("coherence_score", 0.5)
        eff = g.get("outcome_effectiveness", 0.0)
        status = g.get("status", "closed")
        parent_sum = g.get("parent_decision_summary", "")[:200]

        dens_hist = g.get("densification_history") or []
        dens_pass = g.get("metadata", {}).get("densification_pass", {})
        if not dens_hist and dens_pass:
            dens_hist = [dens_pass]

        lift = 0.0
        new_edges = 0
        if dens_pass:
            lift = dens_pass.get("lift", 0.0)
            new_edges = dens_pass.get("new_forward_edges", dens_pass.get("new_edge_count", 0))
        for h in dens_hist or []:
            if isinstance(h, dict):
                lift = max(lift, float(h.get("lift", h.get("post", 0) - h.get("pre", 0))))
                new_edges = max(new_edges, int(h.get("new_edge_count", h.get("proposed_edges", 0))))

        lines.append(f"# Connection Graph — {cid}")
        lines.append("")
        lines.append(f"**Coherence:** {coh}  |  **Effectiveness:** {eff}  |  **Status:** {status}")
        if lift > 0 or new_edges > 0:
            lines.append(
                f"**Densification Lift (GraphGardener v2):** +{lift}  ({new_edges} new edges)"
            )
        lines.append(f"**Parent Decision:** {parent_sum or '(see full summary)'}")
        lines.append("")

        # Artifacts section
        artifacts = g.get("artifacts", []) or g.get("participating_artifacts", [])
        lines.append(f"## Participating Artifacts ({len(artifacts)})")
        for i, art in enumerate(artifacts, 1):
            slug = art.get("slug", "?")
            atype = art.get("type", "artifact")
            ref = str(art.get("ref", ""))[:120]
            lines.append(f"- **{slug}**  *(type: {atype})*")
            if ref:
                lines.append(f"  - ref: {ref}")
            t = art.get("texture") or art.get("texture_hints")
            if t:
                lines.append(f"  - texture: {str(t)[:100]}")
        lines.append("")

        # Connections hierarchical
        edges = g.get("edges", [])
        # Separate original vs densified
        orig_edges = []
        dens_edges = []
        for e in edges:
            if self._is_densification_relation(e.get("relation", "")):
                dens_edges.append(e)
            else:
                orig_edges.append(e)

        lines.append("## Connections (Obsidian-style bidirectional typed)")
        lines.append(f"Total edges: {len(edges)}  (forward shown; inverses auto-mirrored in model)")
        lines.append("")

        lines.append("### Causal Flow (original + strengthened)")
        shown = 0
        for e in orig_edges[:12]:
            src = e.get("source")
            tgt = e.get("target")
            rel = e.get("relation")
            w = e.get("weight", 1.0)
            conf = e.get("confidence", 0.9)
            lines.append(f"- {src}")
            lines.append(f"  `--[{rel}  w={w} c={conf}]--> {tgt}`  [original]")
            shown += 1
        if len(orig_edges) > 12:
            lines.append(f"  ... +{len(orig_edges) - 12} more original connections")
        lines.append("")

        if dens_edges:
            lines.append("### Densified Edges (GraphGardener v2 — closes weak links)")
            for e in dens_edges[:8]:
                src = e.get("source")
                tgt = e.get("target")
                rel = e.get("relation")
                w = e.get("weight", 1.0)
                conf = e.get("confidence", 0.9)
                lines.append(f"- {src}")
                lines.append(
                    f"  `==[{rel}  w={w} c={conf}]==> {tgt}`  **[DENSIFIED via gardener]**"
                )
            if len(dens_edges) > 8:
                lines.append(f"  ... +{len(dens_edges) - 8} more densified")
            lines.append("")

        # Densification history
        if dens_hist:
            lines.append("## Densification History (v2 GraphGardener)")
            for entry in dens_hist if isinstance(dens_hist, list) else [dens_hist]:
                if isinstance(entry, dict):
                    phase = entry.get("phase", "lift")
                    ts = entry.get("ts", "")
                    pre = entry.get("pre", "?")
                    post = entry.get("post", "?")
                    proposed = entry.get("proposed_edges", entry.get("new_edge_count", "?"))
                    lines.append(
                        f"- {phase} @ {ts} — pre={pre} → post={post}  (proposed/applied: {proposed})"
                    )
            lines.append("")

        lines.append("## For Model / Overseer / Parent / Daily Conductor")
        lines.append(
            "These explicit typed connections (like Obsidian) let future Drive.think(prefer_experience_layer=True), "
            "metacognition, and consolidation see structure, strengthen weak links, and grow experience intelligently."
        )
        lines.append("Embed this graph in diary_markdown via embed_graph_into_artifact().")

        return "\n".join(lines)

    def _load_full_graph_for_render(self, cycle_id: str) -> dict[str, Any]:
        """Internal: load raw cycle JSON (preserves densification_history + extra densif metadata)
        + fall back to get_cycle_graph. Enriches for renderers.
        """
        path = self.loops_dir / f"{cycle_id}.json"
        if path.exists():
            try:
                raw = json.loads(path.read_text())
                # Normalize edges
                raw_edges = raw.get("connections", raw.get("edges", []))
                norm_edges = []
                for rc in raw_edges:
                    if isinstance(rc, dict):
                        norm_edges.append(
                            {
                                "source": rc.get("source"),
                                "target": rc.get("target"),
                                "relation": rc.get("relation"),
                                "weight": rc.get("weight", 1.0),
                                "confidence": rc.get("confidence", 0.9),
                                "metadata": rc.get("metadata", {}),
                            }
                        )
                return {
                    "cycle_id": raw.get("cycle_id", cycle_id),
                    "root_correlation_id": raw.get("root_correlation_id"),
                    "status": raw.get("status", "closed"),
                    "coherence_score": raw.get("coherence_score", 0.5),
                    "outcome_effectiveness": raw.get("outcome_effectiveness", 0.0),
                    "parent_decision_summary": raw.get("parent_decision_summary", ""),
                    "artifacts": raw.get("participating_artifacts", []),
                    "edges": norm_edges,
                    "texture_notes": raw.get("texture_notes", []),
                    "densification_history": raw.get("densification_history", []),
                    "metadata": raw.get("metadata", {}),
                    # v3 fabric
                    "fabric_links": raw.get("fabric_links", []),
                    "fabric_metadata": raw.get("fabric_metadata", {}),
                }
            except Exception:
                pass
        # Fallback
        g = self.get_cycle_graph(cycle_id)
        g["densification_history"] = []
        g["metadata"] = g.get("metadata", {})
        return g

    def _is_densification_relation(self, relation: str) -> bool:
        if not relation:
            return False
        r = str(relation).lower()
        keys = (
            "densif",
            "densified_via_gardener",
            "connection_strengthened_by",
            "graph_coherence_lift",
            "strengthened_via_densification",
            "coherence_lifted_by_densification",
            "gardener_applied_densification",
            "densifier",
            # v3 fabric reuse for render coloring (cross-cycle fabric edges styled as densified)
            "cross_cycle",
            "fabric_coherence",
            "sibling_cycle",
            "multi_cycle_fusion",
            "fabric_link",
        )
        return any(k in r for k in keys)

    # ------------------------------------------------------------------
    # Top-level embed helper (for diary_markdown / living-experience payloads)
    # ------------------------------------------------------------------

    def embed_graph_into_artifact(
        self,
        cycle_graph_dict: dict[str, Any] | None = None,
        diary_markdown: str = "",
        cycle_id: str | None = None,
    ) -> str:
        """Inject a beautiful '## Connection Graph' section (mermaid code block + indented
        text hierarchical map) into an existing diary_markdown string (or start one).

        Works for daily-present, loop-observation, living-experience, framework sections.
        If cycle_id provided and no graph_dict, loads it.
        Returns the augmented markdown string. Zero dependencies.
        """
        if cycle_graph_dict is None and cycle_id:
            cycle_graph_dict = self.get_cycle_graph(cycle_id)
            # enrich with densif for good measure
            raw = self._load_full_graph_for_render(cycle_id)
            cycle_graph_dict = {
                **cycle_graph_dict,
                **{k: raw[k] for k in ("densification_history", "metadata") if k in raw},
            }

        if not cycle_graph_dict or cycle_graph_dict.get("error"):
            return diary_markdown or "# No graph available\n"

        # Build renders using the dict (re-use text builder logic by calling internal if possible)
        # For top-level purity on dict, we synthesize here or delegate
        mermaid_block = (
            self.render_cycle_graph_mermaid(
                cycle_graph_dict.get("cycle_id", "unknown"), include_texture=True, max_edges=20
            )
            if cycle_graph_dict.get("cycle_id")
            else "%% no cycle_id"
        )

        text_map = (
            self.render_cycle_graph_text(cycle_graph_dict.get("cycle_id", "unknown"))
            if cycle_graph_dict.get("cycle_id")
            else "(graph text unavailable)"
        )

        section = [
            "",
            "## Connection Graph (Experience Graph v2 — Densified)",
            "",
            "Obsidian-style visualization of the canonical Parent-Overseer-Research loop connections.",
            "Densification edges (GraphGardener) shown in green / [DENSIFIED] — these are the explicit lifts that close weak links and raise coherence.",
            "",
            "### Mermaid (for visual embedding in Obsidian / UI / Conductor dashboards)",
            "",
            "```mermaid",
            mermaid_block,
            "```",
            "",
            "### Hierarchical Text Map (for diary_markdown, framework notes, model context)",
            "",
            "```",
            text_map,
            "```",
            "",
            "> This section was injected via `embed_graph_into_artifact()`. Future daily_consolidation and Conductor runs can call `recorder.embed_graph_into_artifact(graph, existing_diary)` to surface densified loop graphs automatically.",
            "",
        ]
        base = (diary_markdown or "").rstrip()
        return base + "\n" + "\n".join(section) if base else "\n".join(section)

    # ------------------------------------------------------------------
    # Bonus: tiny helper for daily_consolidation to surface "recent densified loop graphs" in diary
    # ------------------------------------------------------------------

    def get_recent_densified_loop_graphs_for_diary(
        self, n: int = 3, min_lift: float = 0.01
    ) -> list[dict[str, Any]]:
        """Scan recent loop JSONs for densified cycles (those with densification_pass / history / lift > min_lift).

        Returns lightweight dicts with cycle_id, coherence/lift stats, + short pre-rendered
        mermaid (truncated) + text snippet suitable for direct injection into daily diary_markdown
        or experience-consolidation artifacts by future daily_consolidation / Conductor.

        Zero side effects, pure read + render. Call from GridEngine daily_consolidation or
        DurableJobSupervisor consolidation phase.
        """
        results: list[dict[str, Any]] = []
        try:
            files = sorted(
                self.loops_dir.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )[: max(10, n * 2)]
            for f in files:
                if len(results) >= n:
                    break
                try:
                    data = json.loads(f.read_text())
                    coh = float(data.get("coherence_score", 0.0))
                    eff = float(data.get("outcome_effectiveness", 0.0))
                    dp = data.get("metadata", {}).get("densification_pass") or {}
                    hist = data.get("densification_history", [])
                    lift = float(dp.get("lift", 0.0))
                    if hist and isinstance(hist, list):
                        for h in hist:
                            if isinstance(h, dict) and h.get("post"):
                                lift = max(lift, float(h.get("post", 0) - h.get("pre", 0)))
                    if lift >= min_lift or dp.get("applied"):
                        cid = data.get("cycle_id")
                        if not cid:
                            continue
                        # Small render for diary (light)
                        short_m = ""
                        short_t = ""
                        try:
                            m = self.render_cycle_graph_mermaid(
                                cid, include_texture=False, max_edges=8
                            )
                            short_m = m[:800] + ("..." if len(m) > 800 else "")
                            t = self.render_cycle_graph_text(cid)
                            short_t = "\n".join(t.splitlines()[:25])  # first ~25 lines
                        except Exception:
                            pass
                        results.append(
                            {
                                "cycle_id": cid,
                                "coherence": coh,
                                "effectiveness": eff,
                                "lift": lift,
                                "new_edges": dp.get(
                                    "new_edge_count", dp.get("new_forward_edges", 0)
                                ),
                                "mermaid_snippet": short_m,
                                "text_snippet": short_t,
                                "ready_for_diary": True,
                            }
                        )
                except Exception:
                    continue
        except Exception:
            pass
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_load(self, cycle_id: str) -> LoopCycle | None:
        if cycle_id in self._active_cycles:
            return self._active_cycles[cycle_id]
        path = self.loops_dir / f"{cycle_id}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                # Rehydrate with proper LoopEdge objects for connections
                raw_conns = data.get("connections", [])
                conns = []
                for rc in raw_conns:
                    if isinstance(rc, dict):
                        conns.append(
                            LoopEdge(
                                **{
                                    k: v
                                    for k, v in rc.items()
                                    if k in LoopEdge.__dataclass_fields__
                                }
                            )
                        )
                    else:
                        conns.append(rc)
                data["connections"] = conns
                c = LoopCycle(
                    **{k: v for k, v in data.items() if k in LoopCycle.__dataclass_fields__}
                )
                self._active_cycles[cycle_id] = c
                return c
            except Exception:
                return None
        return None

    def _persist_cycle(self, cycle: LoopCycle) -> None:
        path = self.loops_dir / f"{cycle.cycle_id}.json"
        try:
            # Store a clean serializable form
            serial = asdict(cycle)
            serial["connections"] = [asdict(e) for e in cycle.connections]
            path.write_text(json.dumps(serial, default=str, indent=2))
        except Exception:
            pass

    def _emit_kg_edge(
        self, source: str, target: str, relation: str, metadata: dict | None = None
    ) -> None:
        if self._kg_store is None:
            return
        try:
            edge = TypedEdge(
                source=source,
                target=target,
                relation=relation,
                confidence=0.85,
                provenance={
                    "via": "ExperienceGraphRecorder",
                    "swarm_id": self.swarm_id,
                    **(metadata or {}),
                },
            )
            self._kg_store.add_edge(edge, swarm_id=self.swarm_id)
        except Exception:
            pass

    def _write_final_artifact(self, cycle: LoopCycle) -> None:
        """Write the closed cycle as a first-class loop-experience-graph observation (page_type).

        v2: optionally carries pre-rendered mermaid + hierarchical text (Connection Graph section)
        so the artifact is immediately usable in diary_markdown / framework notes without
        extra calls. Renders reflect state at close time (densification may update the
        source loop JSON later; post-densif re-embed via embed_graph_into_artifact on fresh load).
        """
        obs_dir = self.drive_path / "observations" / "meta-evolution"
        obs_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = obs_dir / f"loop-experience-graph-{cycle.cycle_id}.json"

        graph_dict = self.get_cycle_graph(cycle.cycle_id)
        # Pre-render at write time (pure, zero-dep)
        mermaid_str = ""
        text_str = ""
        try:
            mermaid_str = self.render_cycle_graph_mermaid(
                cycle.cycle_id, include_texture=True, max_edges=25
            )
            text_str = self.render_cycle_graph_text(cycle.cycle_id)
        except Exception:
            mermaid_str = "%% render failed at write time"
            text_str = "(render unavailable)"

        payload = {
            "schema_version": 3,
            "page_type": "loop-experience-graph",
            "manifest": {
                "id": cycle.cycle_id,
                "type": "parent-overseer-research-loop-graph",
                "created": time.time(),
                "coherence_score": cycle.coherence_score,
                "outcome_effectiveness": cycle.outcome_effectiveness,
            },
            "framework": {
                "cycle_id": cycle.cycle_id,
                "root_correlation_id": cycle.root_correlation_id,
                "graph": graph_dict,
                "rendered": {
                    "mermaid": mermaid_str,
                    "text": text_str,
                    "note": "Pre-rendered at close. Use embed_graph_into_artifact() or recorder.render_* after densification for updated views.",
                },
                "self_referential": "This artifact is the explicit connection graph for one full canonical loop iteration. It was produced by ExperienceGraphRecorder and is itself experience layer content that future Drive.think(prefer_experience_layer=True) and metacognition can cite and improve.",
            },
            "provenance": {
                "produced_by": "ExperienceGraphRecorder.close_cycle",
                "swarm_id": self.swarm_id,
                "correlation_id": cycle.root_correlation_id,
            },
        }
        try:
            artifact_path.write_text(json.dumps(payload, default=str, indent=2))
        except Exception:
            pass


# ------------------------------------------------------------------
# Convenience: attach a recorder to an existing Integrated/Overseer context
# ------------------------------------------------------------------


def get_recorder_for_drive(
    drive_path: Path | str, swarm_id: str | None = None
) -> ExperienceGraphRecorder:
    return ExperienceGraphRecorder(drive_path, swarm_id)


# ------------------------------------------------------------------
# Top-level GraphGardener convenience (per 8-step densifier plan)
# Finds candidates across recent cycles + prepares proposals (no execution).
# Execution (enter phase, harness, record_lift, write obs) delegated to
# IntegratedRealTimeEvolutionSystem / Parent / future densification runner.
# ------------------------------------------------------------------


def trigger_densification_for_weak_cycles(
    recorder: ExperienceGraphRecorder, min_coherence: float = 0.65
) -> list[dict[str, Any]]:
    """Convenience entrypoint for Experience Graph v2 densifier (GraphGardener).

    Uses find_weak_across_recent_cycles + propose_densification_edges.
    Returns enriched candidate dicts with proposals attached.

    Does *not* mutate cycles, does not call enter_densification_phase, record_lift,
    or write observations — those are separate controlled steps (see constitution
    step graph: find_weak → propose → (human/Integrated decision) → execute →
    measure lift → observation).

    Immediately usable from IntegratedRealTimeEvolutionSystem or CLI smoke.
    """
    if recorder is None:
        return []
    candidates = recorder.find_weak_across_recent_cycles(min_coherence=min_coherence, lookback=5)
    enriched: list[dict[str, Any]] = []
    for cand in candidates:
        cid = cand.get("cycle_id")
        if not cid:
            continue
        weak = cand.get("weak_links", [])
        props = recorder.propose_densification_edges(cid, weak_links=weak)
        enriched.append(
            {
                **cand,
                "proposals": [
                    {
                        "source": p.source,
                        "target": p.target,
                        "relation": p.relation,
                        "weight": p.weight,
                        "confidence": p.confidence,
                        "metadata": p.metadata,
                    }
                    for p in props
                ],
                "proposal_count": len(props),
                "ready_for_densification": len(props) > 0,
            }
        )
    return enriched


# ------------------------------------------------------------------
# Top-level pure helper (as specified): embed_graph_into_artifact
# Delegates to a recorder when graph needs live load; otherwise works on
# a pre-fetched cycle_graph_dict (from get_cycle_graph or raw load).
# Zero-dependency, produces diary-ready markdown section.
# ------------------------------------------------------------------


def embed_graph_into_artifact(
    cycle_graph_dict: dict[str, Any] | None = None,
    diary_markdown: str = "",
    *,
    recorder: ExperienceGraphRecorder | None = None,
    cycle_id: str | None = None,
) -> str:
    """Top-level entrypoint.

    If recorder + cycle_id given, loads fresh (post-densif) and renders.
    If cycle_graph_dict provided, uses it for the section (no I/O).
    Always returns augmented diary_markdown string with the Connection Graph
    section (mermaid + text) injected — ready for framework / daily-present etc.
    """
    if recorder is not None and cycle_id:
        return recorder.embed_graph_into_artifact(
            cycle_graph_dict=cycle_graph_dict, diary_markdown=diary_markdown, cycle_id=cycle_id
        )
    if cycle_graph_dict and "cycle_id" in cycle_graph_dict:
        # Minimal pure path: build section without full recorder (replicate small logic)
        cid = cycle_graph_dict.get("cycle_id", "unknown")
        coh = cycle_graph_dict.get("coherence_score", cycle_graph_dict.get("coherence", 0.5))
        mermaid = f'%% (top-level pure stub) graph for {cid} coherence={coh}\nflowchart TD\n    N["{cid}"]'
        text = f"# Connection Graph (pure stub)\n**{cid}** coherence ~{coh}"
        section = f"""

## Connection Graph (Experience Graph v2 — Densified)

```mermaid
{mermaid}
```

```text
{text}
```

> Embedded via top-level embed_graph_into_artifact (no recorder path).
"""
        base = (diary_markdown or "").rstrip()
        return base + section if base else section.lstrip()
    # Fallback
    return (diary_markdown or "") + "\n\n## Connection Graph\n(no data)\n"
