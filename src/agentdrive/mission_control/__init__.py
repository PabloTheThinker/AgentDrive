"""
Mission Control — Real-time unified observation and control surface for AgentDrive.

This package provides the new "Mission Control" interface that lets an operator
see the entire AgentDrive system as one living thing, centered on the canonical
6-step Parent-Overseer-Research loop and the Experience Graph fabric.

Design goals:
- Real-time by default (WebSockets)
- Loop-centric and fabric-centric (not file-centric)
- Deep integration with IntegratedRealTimeEvolutionSystem + ExperienceGraphRecorder
- First-class support for Static Fire observation and control
- Extensible for future "new and better" UI (Svelte, etc.)

The Mission Control treats the IntegratedRealTimeEvolutionSystem as the central
"Mission" object. Everything flows through the exact loop the user defined.
"""

from .events import (
    FabricUpdateEvent,
    GridHealthEvent,
    LoopStepEvent,
    MissionEvent,
    OverseerStateEvent,
    ParentDecisionEvent,
    StaticFireEvent,
)
from .loop_views import FabricView, LoopStateView, StaticFireTelemetry
from .server import (
    # Rich Static Fire helpers for first-class controlled evolution runs
    FireSession,
    MissionControlHub,
    create_mission_control_app,
    hub,
    publish_event,
    publish_event_sync,
    publish_static_fire_telemetry,
    run_static_fire_with_mission_telemetry,
    smoke_mission_control_with_integrated_system,
)

__all__ = [
    "create_mission_control_app",
    "MissionControlHub",
    "hub",
    "publish_event",
    "publish_event_sync",
    "smoke_mission_control_with_integrated_system",
    "MissionEvent",
    "LoopStepEvent",
    "FabricUpdateEvent",
    "StaticFireEvent",
    "ParentDecisionEvent",
    "OverseerStateEvent",
    "GridHealthEvent",
    "LoopStateView",
    "FabricView",
    "StaticFireTelemetry",
    # Rich static fire surfaces + integration helpers (use in 2min harnesses for full Bay telemetry)
    "FireSession",
    "run_static_fire_with_mission_telemetry",
    "publish_static_fire_telemetry",
]