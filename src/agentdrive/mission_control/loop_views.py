"""
Loop-centric and fabric-centric views for Mission Control.

These classes turn the raw internals (Experience Graph, Overseer, Grid, etc.)
into clean, UI-friendly representations that make the entire AgentDrive system
feel like one unified mission instead of a pile of files and objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LoopStateView:
    """
    A live snapshot of the canonical 6-step Parent-Overseer-Research loop.
    This is the primary "single pane of glass" view.
    """

    cycle_id: str
    current_step: int  # 1-6
    step_descriptions: dict[int, str] = field(
        default_factory=lambda: {
            1: "Experience Layer + Runtime generating signals",
            2: "Overseer ingesting experience + multi-cycle fabric",
            3: "Overseer feeding understanding to Parent",
            4: "Parent making real-time decisions",
            5: "Decisions executing back into runtime",
            6: "New experience + updated fabric flowing back to Overseer",
        }
    )
    fabric_coherence: float = 0.0
    last_parent_decision: dict[str, Any] | None = None
    overseer_state: dict[str, Any] | None = None
    recent_events: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FabricView:
    """
    Multi-cycle memory fabric view.
    This is what makes the user see "the whole system as one" across iterations.
    """

    overall_coherence: float
    active_cycles: list[str]
    total_cross_cycle_edges: int
    recent_continuations: list[dict[str, Any]]
    key_weak_links: list[dict[str, Any]]
    graph_summary: dict[str, Any]  # Could include mermaid snippet or node/edge counts


@dataclass
class MultiverseView:
    """Live multiverse superposition snapshot for Mission Control."""

    active_session_id: str | None = None
    status: str = "idle"
    branch_count: int = 0
    collapsed_branch_id: str | None = None
    top_invariants: list[str] = field(default_factory=list)
    branches: list[dict[str, Any]] = field(default_factory=list)
    recent_collapses: list[dict[str, Any]] = field(default_factory=list)
    llm_mode: str = "heuristic"  # llm | heuristic


@dataclass
class StaticFireTelemetry:
    """
    Real-time and historical view of a Static Fire run.
    First-class support for the controlled evolution tests the user cares about.

    Mirrors the rich payload in StaticFireEvent for the Mission Control Tower
    Static Fire Bay (live telemetry + post-densif fabric renders + recorder snippets).
    Populated by Integrated.get_static_fire_telemetry() and by harnesses via
    the run_* helper or direct publish_static_fire_telemetry.
    """

    fire_id: str
    status: str  # "idle", "running", "completed", "aborted"
    started_at: float | None = None
    duration_seconds: float = 0.0
    cycles_executed: int = 0
    fabric_coherence_start: float = 0.0
    fabric_coherence_end: float | None = None
    total_lift: float = 0.0
    key_events: list[dict[str, Any]] = field(default_factory=list)
    final_report: dict[str, Any] | None = None
    parent_interventions: int = 0
    fabric_edges_delta: int = 0
    recorder_snippets: list[str] = field(default_factory=list)
    current_fabric_coherence: float = 0.0
    phase: str = "idle"
    label: str | None = None


# These can later be turned into proper "live" objects that the WebSocket hub updates.
# For now they serve as the canonical data shapes the frontend will consume.
