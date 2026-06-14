"""
Typed real-time events for the Mission Control.

These events are the canonical way the system pushes state to the UI.
They are deliberately centered on the 6-step loop and the Experience Graph fabric
so the operator sees the system as one unified process instead of scattered files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# Base event all real-time messages inherit from
@dataclass
class MissionEvent:
    event_type: str
    timestamp: float
    cycle_id: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# === Core Loop Events (the 6-step canonical loop) ===


@dataclass
class LoopStepEvent(MissionEvent):
    """Represents progress through one of the 6 canonical loop steps."""

    step: Literal[1, 2, 3, 4, 5, 6] = 1
    description: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class FabricUpdateEvent(MissionEvent):
    """A change in the multi-cycle memory fabric or per-cycle connection graph.

    stabilization-wave-20260531: now carries optional parent_fabric_reasoning
    (full structural trace from ExperienceGraphRecorder.record_parent_fabric_reasoning)
    so the Tower Experience Layer panel can live-show what the Parent actually
    considered (elements, pattern, expected lift) and allow clickable highlights
    on the fabric canvas.
    """

    fabric_coherence: float = 0.0
    delta_edges: int = 0
    affected_cycles: list[str] = field(default_factory=list)
    summary: str = ""
    graph_delta: dict[str, Any] | None = None  # For partial graph updates
    parent_fabric_reasoning: dict[str, Any] | None = (
        None  # Parent's explicit graph-native reasoning trace (elements_considered, structural_pattern, expected_lift, rationale)
    )


@dataclass
class ParentDecisionEvent(MissionEvent):
    """A decision made by the Parent Conductor."""

    decision_summary: str = ""
    actions_taken: list[str] = field(default_factory=list)
    triggered_from_fabric: bool = False
    fabric_coherence_at_decision: float | None = None


@dataclass
class OverseerStateEvent(MissionEvent):
    """The Overseer's current metacognitive understanding (step 2 of the loop)."""

    adaptation_effectiveness: float = 0.0
    plateau_detected: bool = False
    fabric_coherence: float = 0.0
    recommendations: list[str] = field(default_factory=list)
    recent_hunches: list[dict[str, Any]] = field(default_factory=list)


# === Static Fire Specific ===


@dataclass
class StaticFireEvent(MissionEvent):
    """Telemetry and state for a Static Fire run (controlled evolution window).

    Rich surface for Mission Control Static Fire Bay (stabilization-wave-20260531):
    - Live: phase, cycles, current coherence, accumulating key_events (Parent interventions,
      densif steps, loop milestones inside the fire window).
    - Post-fire: coherence_start/end + computed total_lift, full final_report (includes
      post-densification fabric renders/summaries + recorder snippet refs), parent_interventions
      count, fabric_edges_delta, recorder_snippets.
    Emitted on start (via thin entrypoint or helper), at milestones (via publish helper),
    and on completion by harness using run_static_fire_with_mission_telemetry or direct calls.
    All via the single publish_event_sync path; never bypasses quarantine or auth.
    """

    phase: Literal["starting", "running", "densifying", "measuring", "completed", "aborted"] = (
        "idle"
    )
    duration_seconds: float = 0.0
    cycles_completed: int = 0
    current_fabric_coherence: float = 0.0
    coherence_start: float = 0.0
    coherence_end: float | None = None
    total_lift: float = 0.0
    key_events: list[dict[str, Any]] = field(default_factory=list)
    final_report: dict[str, Any] | None = None
    parent_interventions: int = 0
    fabric_edges_delta: int = 0
    recorder_snippets: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    log_line: str | None = None


# === System-level ===


@dataclass
class GridHealthEvent(MissionEvent):
    """Snapshot of GridEngine health surfaced in Mission Control."""

    health: dict[str, Any] = field(default_factory=dict)


@dataclass
class DreamPhaseEvent(MissionEvent):
    """Telemetry for one phased dream maintenance cycle step."""

    phase_id: str = ""
    phase_name: str = ""
    success: bool = True
    dry_run: bool = False
    duration_ms: int = 0
    stop_gate: bool = False
    run_id: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


# Convenience type for all events the frontend might receive
MissionEventType = (
    LoopStepEvent
    | FabricUpdateEvent
    | ParentDecisionEvent
    | OverseerStateEvent
    | StaticFireEvent
    | GridHealthEvent
    | DreamPhaseEvent
)
