"""
RealTimeEvolutionOverseer (fully wired version)

The persistent metacognitive meta-layer whose primary purpose is to serve the Parent Agent / Main Conductor.

Exact role and order in the architecture (as specified):

1. Ingests raw signals from the Experience Layer + Runtime (GridEngine + research threads / swarms) in real time.
2. Processes them through metacognition (monitoring, evaluation, regulation) and embodied intuition (texture resonance over rich episodic memory).
3. Develops a higher-order, real-time understanding of the adaptation process itself.
4. Delivers this understanding primarily and explicitly to the Parent Conductor (via get_metacognitive_briefing(), get_current_understanding(), etc.) so the Parent can make on-the-fly real-time decisions and improvements.
5. The Parent then drives concrete changes back into the runtime (Grid + swarms), generating new experience.
6. New experience flows back to the Overseer for deeper metacognitive processing.

The Overseer is the metacognitive processor and intuition engine that equips the Parent with richer, faster understanding. The Parent remains the central decision-maker and source of strategic adaptation for the sub-agents / swarms.

All outputs are first-class experience layer content for full traceability.

DEEP EXPERIENCE GRAPH v3 INTEGRATION (multi-cycle memory fabric in the exact canonical loop)
The Overseer deeply ingests the multi-cycle fabric as a core signal:
- get_metacognitive_briefing now always includes the full fabric briefing (fabric_coherence, key cross-cycle continuations, densification opportunities).
- Fabric coherence directly influences meta_gaps, recommendations, and regulation logic.
- process_embodied_synthesis + EpisodicTrace record fabric ingestion and fabric-driven hunches.
- This ensures step 2 of the user's exact 6-step loop (Overseer understands experience and adapts) operates on rich relational structure, not just flat health/synthesis signals.

DEEP PARENT FABRIC REASONING CONSUMPTION (Overseer now builds directly on Parent's graph-native traces)
- get_metacognitive_briefing (and get_current_understanding) pull recent parent_fabric_reasoning traces from the recorder (new get_recent_parent_fabric_reasoning_traces helper on ExperienceGraphRecorder).
- Explicit references to prior Parent structural reasoning appear in meta_gaps_identified, metacognitive_recommendations_for_parent, and recent_embodied_hunches (example form: "Parent previously strengthened similar continuation between X and Y with +0.04 lift").
- Every such reference records an "overseer_referenced_parent_fabric_reasoning" TypedEdge (via recorder.record_connection + dual KG write) for full traceability and fabric growth.
- Fabric reasoning history participates in the embodied intuition / texture system: structural resonances from prior Parent traces are surfaced as additional felt hunches alongside texture-based episodic memory.
- All of the above happens strictly inside step 2 (Overseer ingests + understands); the enriched briefing is delivered in step 3 for the Parent to act on in step 4. Overseer never decides or steers — it only equips the Parent with deeper, history-aware structural context.

The fabric (including Parent's explicit reasoning traces over it) is not an observer — it is active substrate for the Overseer's metacognition and the Parent's decisions.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentdrive.drive.drive import AgentDrive
from agentdrive.grid.engine import GridEngine

# Experience Graph support (optional; passed from Integrated system)
try:
    from agentdrive.evolution.experience_graph import (
        ExperienceGraphRecorder,
        trigger_densification_for_weak_cycles,
    )
except Exception:
    ExperienceGraphRecorder = None  # type: ignore
    trigger_densification_for_weak_cycles = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class MetaAdaptationSignal:
    timestamp: float
    adaptation_effectiveness: float
    plateau_detected: bool
    recommended_actions: list[str] = field(default_factory=list)
    meta_gaps: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class TextureVector:
    contradiction_roughness: float = 0.0
    coherence_smoothness: float = 0.0
    urgency_pressure: float = 0.0
    novelty_surprise: float = 0.0
    stagnation_flavor: float = 0.0

    def as_tuple(self):
        return (
            self.contradiction_roughness,
            self.coherence_smoothness,
            self.urgency_pressure,
            self.novelty_surprise,
            self.stagnation_flavor,
        )

    def similarity(self, other: "TextureVector") -> float:
        a = self.as_tuple()
        b = other.as_tuple()
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5 or 1.0
        mag_b = sum(y * y for y in b) ** 0.5 or 1.0
        return dot / (mag_a * mag_b)


def extract_texture_from_synthesis(
    synthesis_result: Any, health_snapshot: dict | None = None
) -> TextureVector:
    contradictions = getattr(synthesis_result, "contradictions", []) or []
    gaps = getattr(synthesis_result, "gaps", []) or []
    kg = getattr(synthesis_result, "kg_fusion_signals", {}) or {}

    contradiction_roughness = min(
        1.0,
        len(contradictions) * 0.15
        + sum((g.get("severity", 0.5) if isinstance(g, dict) else 0.5) for g in contradictions)
        * 0.1,
    )
    coherence_smoothness = max(0.0, 1.0 - contradiction_roughness * 0.8)
    urgency_pressure = min(
        1.0,
        sum(
            0.9
            if (
                getattr(g, "severity", "medium")
                if hasattr(g, "severity")
                else (g.get("severity", "medium") if isinstance(g, dict) else "medium")
            )
            in ("high", "critical")
            else 0.5
            for g in gaps
        )
        / max(1, len(gaps)),
    )
    novelty_surprise = max(0.0, 1.0 - (kg.get("composite", 0.5) if isinstance(kg, dict) else 0.5))
    stagnation = (health_snapshot or {}).get("recent_adaptation_velocity", 0.0)
    stagnation_flavor = max(0.0, 1.0 - stagnation * 5.0) if stagnation < 0.2 else 0.0

    return TextureVector(
        contradiction_roughness,
        coherence_smoothness,
        urgency_pressure,
        novelty_surprise,
        stagnation_flavor,
    )


@dataclass
class EpisodicTrace:
    timestamp: float
    context_snapshot: dict
    action_taken: list[str]
    outcome_effectiveness: float
    felt_notes: str = ""
    texture: TextureVector | None = None
    linked_observation_ids: list[str] = field(default_factory=list)
    parent_guidance_snapshot: str = ""
    # Experience Graph additions (clean loop ingestion + Obsidian-style connections)
    cycle_id: str | None = None
    synthesis_texture_notes: str = ""
    connection_deltas: list[str] = field(
        default_factory=list
    )  # e.g. "strengthened 'briefing_informed_decision' edge +0.18 coherence"


class IntuitionEngine:
    def __init__(self, drive: AgentDrive, max_traces: int = 200):
        self.drive = drive
        self.episodic_memory: list[EpisodicTrace] = []
        self.max_traces = max_traces

    def remember(self, trace: EpisodicTrace):
        self.episodic_memory.append(trace)
        if len(self.episodic_memory) > self.max_traces:
            self.episodic_memory.pop(0)
        # Future: when recorder is attached, it will also call record_artifact + record_connection for the cycle graph.

    def generate_embodied_hunch(
        self, current_synthesis: Any, current_context: dict, recent_signals: list
    ) -> dict:
        current_texture = extract_texture_from_synthesis(current_synthesis, current_context)
        best_resonance = 0.0
        best_trace = None
        for trace in self.episodic_memory[-30:]:
            if trace.texture:
                res = current_texture.similarity(trace.texture)
                if res > best_resonance:
                    best_resonance = res
                    best_trace = trace

        hunch = {
            "hunch_type": "embodied_texture_resonance",
            "confidence": min(0.9, best_resonance * 1.1),
            "felt_texture": current_texture.as_tuple(),
            "resonance_with_past": best_resonance,
            "felt_resemblance": "",
            "suggested_focus": None,
            "partial_reasoning": [
                f"Current synthesis feels {self._describe_texture(current_texture)}"
            ],
            "cycle_id": getattr(best_trace, "cycle_id", None) if best_trace else None,
        }

        if best_trace and best_resonance > 0.55:
            hunch["felt_resemblance"] = (
                best_trace.felt_notes or "Resonates with a previous similar texture."
            )
            if "aggressive" in " ".join(best_trace.action_taken).lower():
                hunch["suggested_focus"] = (
                    "Texture matches past stall where pushing harder worked — spawn adversarial thread."
                )
            else:
                hunch["suggested_focus"] = (
                    "Texture matches situation where giving swarm more space helped."
                )

        return hunch

    def _describe_texture(self, tv: TextureVector) -> str:
        parts = []
        if tv.contradiction_roughness > 0.6:
            parts.append("jagged")
        if tv.urgency_pressure > 0.7:
            parts.append("urgent")
        if tv.stagnation_flavor > 0.6:
            parts.append("stagnant")
        return ", ".join(parts) if parts else "balanced"


class RealTimeEvolutionOverseer:
    def __init__(
        self,
        grid: GridEngine,
        drive: AgentDrive,
        poll_interval_s: float = 3.0,
        state_path: Path | None = None,
        recorder: "ExperienceGraphRecorder | None" = None,
    ):
        self.grid = grid
        self.drive = drive
        self.poll_interval_s = poll_interval_s
        self.recorder = recorder  # Clean loop ingestion + connection graph surface (when present)
        self._mission_hub: Any = (
            None  # wired via Integrated or direct attach (for OverseerStateEvent)
        )

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._adaptation_history: list[MetaAdaptationSignal] = []
        self._intervention_success_history: list[float] = []
        self.intuition_engine = IntuitionEngine(drive=drive)
        self._episodic_traces: list[EpisodicTrace] = []
        self._current_window_textures: list[TextureVector] = []

        if state_path is None:
            state_path = (
                Path(drive.drive_path) / "meta_evolution_state" / f"overseer-{grid.swarm_id}.jsonl"
            )
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_persistent_state()

        logger.info("real_time_evolution_overseer_initialized", extra={"swarm_id": grid.swarm_id})

    def attach_mission_control(self, hub: Any) -> None:
        """Light attach for emitting OverseerStateEvent on hot paths."""
        self._mission_hub = hub

    def _load_persistent_state(self):
        if not self.state_path.exists():
            return
        try:
            with open(self.state_path) as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if "adaptation_effectiveness" in data:
                        self._adaptation_history.append(
                            MetaAdaptationSignal(
                                **{
                                    k: v
                                    for k, v in data.items()
                                    if k in MetaAdaptationSignal.__annotations__
                                }
                            )
                        )
                    elif "intervention_success" in data:
                        self._intervention_success_history.append(data["intervention_success"])
        except Exception:
            pass

    def _persist_signal(self, signal: MetaAdaptationSignal):
        try:
            with open(self.state_path, "a") as f:
                f.write(
                    json.dumps(
                        {
                            "adaptation_effectiveness": signal.adaptation_effectiveness,
                            "plateau_detected": signal.plateau_detected,
                            "confidence": signal.confidence,
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="real-time-evolution-overseer", daemon=True
        )
        self._thread.start()
        logger.info("real_time_evolution_overseer_started")

    def stop(self, timeout: float = 5.0):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                logger.exception("overseer_tick_error")
            time.sleep(self.poll_interval_s)

    def _tick(self):
        health = self.grid.get_grid_health() if hasattr(self.grid, "get_grid_health") else {}
        active_threads = (
            self.grid.get_active_research_threads()
            if hasattr(self.grid, "get_active_research_threads")
            else []
        )

        context = {
            "health": health,
            "active_thread_count": len(active_threads),
            "recent_adaptation_velocity": self._compute_adaptation_velocity(health),
            "plateau_risk": self._detect_plateau(health),
        }

        signal = self._run_meta_synthesis(context)
        self._adaptation_history.append(signal)
        if len(self._adaptation_history) > 50:
            self._adaptation_history.pop(0)

        if signal.confidence > 0.6 and signal.recommended_actions:
            self._inject_meta_guidance(signal)
            self._persist_signal(signal)

        # Mission Control: emit OverseerStateEvent on every _tick (step 2 metacog heartbeat)
        if getattr(self, "_mission_hub", None):
            try:
                from agentdrive.mission_control.events import OverseerStateEvent
                from agentdrive.mission_control.server import publish_event_sync

                publish_event_sync(
                    OverseerStateEvent(
                        event_type="overseer_state",
                        timestamp=time.time(),
                        adaptation_effectiveness=signal.adaptation_effectiveness,
                        plateau_detected=signal.plateau_detected,
                        fabric_coherence=0.0,
                        recommendations=signal.recommended_actions,
                    )
                )
            except Exception:
                pass

        # Embodied intuition on recent high-signal synthesis (if available)
        # In a live system this would be fed via wire_embodied_feedback
        self._last_health_snapshot = dict(health)

    def _compute_adaptation_velocity(self, health: dict) -> float:
        if not self._adaptation_history:
            return 0.0
        recent = self._adaptation_history[-5:]
        if len(recent) < 2:
            return 0.0
        deltas = [
            b.adaptation_effectiveness - a.adaptation_effectiveness
            for a, b in zip(recent, recent[1:])
        ]
        return sum(deltas) / len(deltas)

    def _detect_plateau(self, health: dict) -> bool:
        velocity = self._compute_adaptation_velocity(health)
        lift = health.get("resilience_lift_total", 0.0)
        return velocity < 0.01 and lift > 0.15

    def _run_meta_synthesis(self, context: dict) -> MetaAdaptationSignal:
        velocity = context.get("recent_adaptation_velocity", 0.0)
        plateau = context.get("plateau_risk", False)
        lift = context.get("health", {}).get("resilience_lift_total", 0.0)
        effectiveness = min(1.0, max(0.0, (lift * 0.6) + (velocity * 4.0)))
        avg_success = (
            sum(self._intervention_success_history[-10:])
            / max(1, len(self._intervention_success_history[-10:]))
            if self._intervention_success_history
            else 0.5
        )

        recs, gaps = [], []
        if plateau:
            if avg_success < 0.4:
                recs.append("Shift to higher-variance interventions (past gentle ones failed)")
            else:
                recs.append("Inject sharper parent guidance on current plateau")
            gaps.append("No measurable adaptation velocity")
        if effectiveness < 0.4:
            recs.append("Reallocate away from low-yield directions")
            gaps.append("Adaptation effectiveness below threshold")

        return MetaAdaptationSignal(
            time.time(),
            effectiveness,
            plateau,
            recs,
            gaps,
            0.8 if plateau or effectiveness < 0.45 else 0.6,
        )

    def _inject_meta_guidance(self, signal: MetaAdaptationSignal):
        logger.info(
            "meta_guidance",
            extra={
                "effectiveness": signal.adaptation_effectiveness,
                "actions": signal.recommended_actions,
            },
        )
        self._persist_signal(signal)

    # Embodied intuition entry point (called from Integrated system via wire_embodied_feedback)
    # Now also creates real EpisodicTrace + records into Experience Graph for clean loop connections.
    def process_embodied_synthesis(self, synthesis_result: Any, context: dict | None = None):
        if not hasattr(self, "intuition_engine"):
            return
        ctx = context or {"health": getattr(self, "_last_health_snapshot", {})}
        hunch = self.intuition_engine.generate_embodied_hunch(
            synthesis_result, ctx, self._adaptation_history[-3:]
        )

        # Create a proper EpisodicTrace (was never instantiated before)
        trace = EpisodicTrace(
            timestamp=time.time(),
            context_snapshot=ctx,
            action_taken=["embodied_hunch_generated"],
            outcome_effectiveness=hunch.get("confidence", 0.5),
            felt_notes=hunch.get("felt_resemblance", "") or hunch.get("partial_reasoning", [""])[0],
            texture=extract_texture_from_synthesis(synthesis_result, ctx),
            cycle_id=hunch.get("cycle_id"),
            synthesis_texture_notes=str(getattr(synthesis_result, "gaps", []))[:300],
        )
        self.intuition_engine.remember(trace)
        self._episodic_traces.append(trace)

        if hunch.get("confidence", 0) > 0.6:
            self._apply_embodied_hunch(hunch)

        # If we have a recorder (from Integrated), record the trace + texture connection into the current cycle graph
        if self.recorder and hasattr(self.recorder, "record_artifact"):
            cid = getattr(self, "_current_evolution_cycle_id", None) or (
                hunch.get("cycle_id") if isinstance(hunch, dict) else None
            )
            if cid:
                self.recorder.record_artifact(
                    cid,
                    f"episodic_trace:{int(trace.timestamp)}",
                    "episodic_trace",
                    trace.felt_notes,
                    {"texture": trace.texture.as_tuple() if trace.texture else None},
                )
                if hunch.get("resonance_with_past", 0) > 0.5:
                    self.recorder.record_connection(
                        cid,
                        f"episodic_trace:{int(trace.timestamp)}",
                        "synthesis_result",
                        "texture_resonance_to_episodic_trace",
                        {"resonance": hunch.get("resonance_with_past")},
                    )

    def _apply_embodied_hunch(self, hunch: dict):
        logger.info("embodied_hunch_applied", extra=hunch)
        # Real actions can be added here (e.g. form threads on the grid)
        # For the 2min static fire this will be exercised via the IntegratedSystem wiring

    def get_recent_meta_signals(self, n: int = 5):
        return self._adaptation_history[-n:]

    # ------------------------------------------------------------------
    # Primary interface for the Parent Conductor
    # ------------------------------------------------------------------

    def get_metacognitive_briefing(self) -> dict:
        """
        Returns a structured, real-time briefing intended for the Parent Conductor.

        This is the main way the overseer delivers its metacognitive understanding
        so the Parent can make on-the-fly adaptive decisions.

        Contains:
        - Current assessment of adaptation effectiveness
        - Whether a plateau or acceleration is detected
        - High-confidence recommendations specifically for the Parent
        - Recent embodied intuitions / hunches with their felt texture
        - Suggested next actions the Parent should consider
        - (NEW) recent_parent_fabric_reasoning_traces + explicit references in gaps/recs/hunches
          to prior Parent graph-native structural reasoning over the fabric.
        """
        latest = self._adaptation_history[-1] if self._adaptation_history else None

        briefing = {
            "timestamp": time.time(),
            "adaptation_effectiveness": latest.adaptation_effectiveness if latest else 0.0,
            "plateau_detected": latest.plateau_detected if latest else False,
            "confidence_in_assessment": latest.confidence if latest else 0.0,
            "recent_velocity": self._compute_adaptation_velocity(self._last_health_snapshot),
            "metacognitive_recommendations_for_parent": latest.recommended_actions
            if latest
            else [],
            "meta_gaps_identified": latest.meta_gaps if latest else [],
            "recent_embodied_hunches": [],
            "suggested_parent_actions": [],
        }

        # Pull recent high-confidence embodied hunches for the Parent
        if hasattr(self, "intuition_engine"):
            for trace in self.intuition_engine.episodic_memory[-5:]:
                if trace.felt_notes or trace.action_taken:
                    briefing["recent_embodied_hunches"].append(
                        {
                            "felt": trace.felt_notes,
                            "actions_taken": trace.action_taken,
                            "effectiveness": trace.outcome_effectiveness,
                        }
                    )

        # Explicitly format suggestions for the Parent Conductor
        if briefing["metacognitive_recommendations_for_parent"]:
            briefing["suggested_parent_actions"] = [
                f"Consider: {rec}" for rec in briefing["metacognitive_recommendations_for_parent"]
            ]

        # Deep v3 fabric integration into metacognition (core of step 2 in the exact canonical loop)
        # The Overseer now ingests multi-cycle memory fabric as first-class input for its understanding and regulation.
        if self.recorder is not None:
            try:
                # Pull the full multi-cycle fabric briefing (the highest-order relational view of recent loops)
                fabric = self.recorder.get_parent_facing_memory_fabric_briefing(lookback_days=7)
                briefing["multi_cycle_fabric"] = fabric
                briefing["fabric_coherence"] = fabric.get("fabric_coherence", 0.0)

                # Use fabric coherence as a signal in metacognitive assessment
                fab_coh = fabric.get("fabric_coherence", 0.5)
                if fab_coh < 0.65:
                    briefing["meta_gaps_identified"].append(
                        "Multi-cycle memory fabric coherence below threshold — weak cross-loop connections detected"
                    )
                    if "Inject sharper parent guidance" not in " ".join(
                        briefing.get("metacognitive_recommendations_for_parent", [])
                    ):
                        briefing["metacognitive_recommendations_for_parent"].append(
                            "Request fabric-driven GraphGardener thread to strengthen cross-cycle connections"
                        )

                # Surface densification opportunities (v2) + new fabric-specific recommendations
                densif_cands = self.recorder.find_weak_across_recent_cycles(
                    min_coherence=0.60, lookback=3
                )
                briefing["densification_opportunities"] = densif_cands
                briefing["graph_gardener_recommendation"] = (
                    f"Multi-cycle fabric coherence {fab_coh:.2f}. Weak links present. Parent should act via record_parent_decision + Grid gardener dispatch."
                    if densif_cands or fab_coh < 0.72
                    else "Fabric and recent loops show healthy connection density."
                )

                # Keep the Parent engaged even when the fabric is healthy: above the
                # weak-link threshold the loop would otherwise hand back zero
                # recommendations and effectively go silent. Surface a maintenance /
                # consolidation steer so the real-time loop keeps compounding instead
                # of plateauing.
                if not briefing.get("metacognitive_recommendations_for_parent"):
                    if densif_cands:
                        briefing["metacognitive_recommendations_for_parent"].append(
                            "Fabric healthy — opportunistically densify the strongest remaining weak "
                            f"cluster ({densif_cands[0].get('cycle_id', 'recent')}) to push coherence higher"
                        )
                    else:
                        briefing["metacognitive_recommendations_for_parent"].append(
                            "Fabric coherence healthy — consolidate strong cross-cycle continuations "
                            "(daily fusion) to lock in gains and guard against regression"
                        )

                # Record the fabric ingestion itself into the active cycle graph (deep loop closure)
                cid = getattr(self, "_current_evolution_cycle_id", None) or (
                    densif_cands[0].get("cycle_id") if densif_cands else None
                )
                if cid and hasattr(self.recorder, "record_artifact"):
                    self.recorder.record_artifact(
                        cid,
                        f"overseer_fabric_ingestion:{int(time.time())}",
                        "overseer_fabric_ingestion",
                        {
                            "fabric_coherence": fab_coh,
                            "key_continuations": len(fabric.get("key_continuations", [])),
                        },
                        {"source": "RealTimeEvolutionOverseer metacognition"},
                    )
                    if fab_coh < 0.72:
                        self.recorder.record_connection(
                            cid,
                            f"overseer_fabric_ingestion:{int(time.time())}",
                            "fabric:weak_cross_cycle",
                            "overseer_fabric_coherence_gap",
                            {
                                "note": "Overseer detected low fabric coherence during metacognitive synthesis and surfaced it to Parent."
                            },
                        )

                # NEW: Deep Overseer consumption of Parent's explicit fabric reasoning traces (stabilization-wave-20260531 tranche)
                # Pulls the structural DNA Parent declared via record_parent_fabric_reasoning.
                # References appear in meta_gaps, recommendations, and hunches. Records TypedEdges.
                # Fits embodied intuition by surfacing "structural resonance" hunches.
                # Strictly step-2 ingestion only; all value flows to Parent in step 3 for step-4 decisions.
                try:
                    pfr_traces = self.recorder.get_recent_parent_fabric_reasoning_traces(lookback=5)
                    briefing["recent_parent_fabric_reasoning_traces"] = pfr_traces[:3]
                    for tr in pfr_traces[:3]:
                        pat = tr.get("structural_pattern_matched") or "fabric_continuation"
                        lift = tr.get("expected_lift_signal") or 0.0
                        elems = (tr.get("elements_considered") or [])[:2]
                        cid_for_ref = tr.get("cycle_id") or getattr(
                            self, "_current_evolution_cycle_id", None
                        )
                        ref_note = f"Parent previously strengthened similar {pat} between {', '.join(map(str, elems)) or 'nodes'} with +{float(lift):.2f} lift (trace {tr.get('slug')})"
                        # Reference in gaps (awareness of history)
                        if "Parent fabric reasoning history" not in " ".join(
                            briefing.get("meta_gaps_identified", [])
                        ):
                            briefing["meta_gaps_identified"].append(
                                f"Structural memory available: {ref_note}"
                            )
                        # Reference in recommendations (Parent can choose to extend proven lifts)
                        if lift and float(lift) > 0.02:
                            rec = f"Extend proven Parent fabric pattern: {ref_note}"
                            if rec not in briefing.get(
                                "metacognitive_recommendations_for_parent", []
                            ):
                                briefing["metacognitive_recommendations_for_parent"].append(rec)
                        else:
                            briefing["meta_gaps_identified"].append(
                                f"Review prior Parent reasoning for gaps: {ref_note}"
                            )
                        # Reference in hunches (embodied + structural texture resonance)
                        briefing["recent_embodied_hunches"].append(
                            {
                                "felt": f"structural_fabric_resonance: {ref_note}",
                                "actions_taken": ["reference_parent_fabric_reasoning_history"],
                                "effectiveness": min(0.85, 0.6 + abs(float(lift)) * 2.0),
                                "parent_fabric_trace_slug": tr.get("slug"),
                                "cycle_id": tr.get("cycle_id"),
                            }
                        )
                        # Record "overseer_referenced_parent_fabric_reasoning" TypedEdge (via recorder -> _emit_kg_edge)
                        # This grows the fabric with the act of metacognitive consumption itself.
                        if cid_for_ref and tr.get("slug"):
                            try:
                                self.recorder.record_connection(
                                    cid_for_ref,
                                    f"overseer_briefing:{int(time.time())}",
                                    tr["slug"],
                                    "overseer_referenced_parent_fabric_reasoning",
                                    {
                                        "structural_pattern": pat,
                                        "lift_signal": lift,
                                        "elements": elems,
                                        "source": "RealTimeEvolutionOverseer.get_metacognitive_briefing (deep Parent fabric consumption)",
                                    },
                                )
                            except Exception:
                                pass
                except Exception:
                    pass
            except Exception:
                pass

        # Mission Control: after fabric ingestion (core of step 2), emit OverseerState
        if getattr(self, "_mission_hub", None) or self.recorder:
            try:
                from agentdrive.mission_control.events import OverseerStateEvent
                from agentdrive.mission_control.server import publish_event_sync

                fab_coh = briefing.get("fabric_coherence", 0.0)
                publish_event_sync(
                    OverseerStateEvent(
                        event_type="overseer_state",
                        timestamp=time.time(),
                        cycle_id=getattr(self, "_current_evolution_cycle_id", None),
                        adaptation_effectiveness=briefing.get("adaptation_effectiveness", 0.0),
                        plateau_detected=briefing.get("plateau_detected", False),
                        fabric_coherence=fab_coh,
                        recommendations=briefing.get(
                            "metacognitive_recommendations_for_parent", []
                        ),
                        recent_hunches=briefing.get("recent_embodied_hunches", []),
                    )
                )
            except Exception:
                pass

        return briefing

    def get_current_understanding(self) -> str:
        """Returns a concise, human-readable summary of the overseer's current metacognitive understanding.
        v2: includes densification opportunity summary when recorder is wired (Experience Graph Gardener visibility).
        v3 fabric-reasoning tranche: surfaces count of recent Parent fabric reasoning traces consumed.
        """
        briefing = self.get_metacognitive_briefing()
        parts = [
            f"Adaptation effectiveness: {briefing['adaptation_effectiveness']:.2f}",
            f"Plateau detected: {briefing['plateau_detected']}",
        ]
        if briefing["recent_embodied_hunches"]:
            parts.append(
                f"Recent intuitive sense: {briefing['recent_embodied_hunches'][-1].get('felt', '')}"
            )
        if briefing["suggested_parent_actions"]:
            parts.append("Top suggestion: " + briefing["suggested_parent_actions"][0])
        # v2 densif surface (light)
        dops = briefing.get("densification_opportunities") or []
        if dops:
            lowest = dops[0].get("coherence", 0.0) if dops else 0.0
            parts.append(
                f"Densification opportunities: {len(dops)} (lowest coh ~{lowest:.2f}; GraphGardener ready)"
            )
        elif "densification_opportunities" in briefing:
            parts.append("Graph coherence healthy (no immediate densif candidates)")
        # NEW: Parent fabric reasoning history consumption (structural substrate now in intuition)
        pfr = briefing.get("recent_parent_fabric_reasoning_traces") or []
        if pfr:
            parts.append(
                f"Parent fabric reasoning traces consumed: {len(pfr)} (structural history in metacog + hunches)"
            )
        return " | ".join(parts)
