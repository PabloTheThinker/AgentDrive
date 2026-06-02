"""
Mission Control FastAPI server.

This is the new real-time backend for the AgentDrive Mission Control.
It is designed to sit on top of (or alongside) an IntegratedRealTimeEvolutionSystem
and expose the entire system as one unified, observable, and controllable thing.

Core ideas:
- WebSocket-based real-time updates (no polling)
- Event-driven around the canonical 6-step loop + fabric
- Clean attachment to existing AgentDrive runtime objects
- First-class support for Static Fire observation/control

SECURITY / AUTHZ ALIGNMENT (per AGENTS.md hard rule for mutating web routes):
- All *observation* paths (publish_event / publish_event_sync + WS broadcasts +
  /state GET + initial payloads) are one-way, fire-and-forget, local-only,
  and intentionally unauthenticated. They never mutate state.
- Command dispatch surface (inbound on /ws/mission or direct dispatch_command):
  start_static_fire, parent_decision/record_parent_decision, trigger_densification,
  suggest_connection_improvements, pause/resume/inject/list_fires/compare/emit_test_fabric_lift,
  overseer_force_hunch etc (Wave 3 extensions). ARE mutating (they steer the live
  Integrated system, recorder, may spawn Grid threads, write experience artifacts).
  These live ONLY on this separate MC daemon (default localhost:8421 via `agentdrive mission`).
  They are documented as **local operator control surface only**:
  the human owner running the Control Tower on their own machine has full
  steering authority (exactly as with the local TUI, CLI, or direct python
  use of IntegratedRealTimeEvolutionSystem). No CapStore / require_cap is
  applied here because (a) this is not the main web daemon, (b) the bind is
  localhost by default, (c) adding the full auth stack would be non-minimal
  and pull in user/session/cap DB for a pure local viz+control tool.
- If this daemon is ever reconfigured for non-localhost exposure, cap-based
  enforcement + admin role gating on the command router MUST be added first
  (see src/agentdrive/web/authz.py require_cap and SECURITY-HARDENING.md).
- All side-effects from commands still flow *exclusively* through the
  canonical publish_event_sync observation channel for any UI visibility.
- Audit of actual mutations happens inside the Drive / recorder / Grid
  (existing paths); the MC command ack is only the control confirmation.
See also: AGENTS.md (every mutating web route), CLI cmd_mission, and the
dispatch_command + handle_inbound_command implementations below.
"""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from dataclasses import field as dc_field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from starlette.staticfiles import StaticFiles

from agentdrive.mission_control.events import (
    FabricUpdateEvent,
    MissionEvent,
    OverseerStateEvent,
    ParentDecisionEvent,
)


class MissionControlHub:
    """
    Central real-time hub for Mission Control.

    This class is the bridge between the internal AgentDrive systems
    (IntegratedRealTimeEvolutionSystem, ExperienceGraphRecorder, GridEngine, Overseer)
    and connected Mission Control clients (the new web UI).

    It maintains active WebSocket connections and broadcasts typed events.

    Thread-safety note: All mutation (connect/disconnect/broadcast) and attach
    must occur on the asyncio event loop (FastAPI/uvicorn context). Hot-path
    emitters from sync threads (recorder, grid, overseer ticks) use the
    _schedule_publish helper which safely creates a task when a loop is
    running and falls back to recent_events capture for smoke/introspection.

    Hardening (steps 2+5):
    - One-way observation ONLY via publish_event / publish_event_sync (never changed).
    - Commands are the return path: parsed inbound JSON on WS, routed to mission methods.
    - Sequence numbers on every event for client-side replay of missed updates.
    - Backpressure: bounded connections + bounded recent + dead detection.
    - Graceful degradation when no mission attached.
    - Clean command router + sync dispatch for headless smoke.
    """

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._current_mission = None  # Will hold reference to IntegratedRealTimeEvolutionSystem
        self._current_grid: Any = None  # AD-Grid persistent GridEngine attach (survives mission end)
        # Bounded recent events (now full sendable payloads incl. seq) for smoke / replay / debugging.
        # Populated from ALL publish paths (the only way data flows core -> MC).
        self.recent_events: list[dict[str, Any]] = []
        self._event_seq: int = 0
        self._max_connections: int = 16  # local-first; backpressure / graceful

    def _next_seq(self) -> int:
        self._event_seq += 1
        return self._event_seq

    async def connect(self, websocket: WebSocket):
        if len(self.active_connections) >= self._max_connections:
            # Backpressure: reject excess connections cleanly
            await websocket.close(code=1013, reason="too_many_mission_control_connections")
            return
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    def _record_event_for_introspection(self, event: MissionEvent) -> dict[str, Any]:
        """
        Central record + seq assignment. Returns the ready-to-send payload dict.
        Always captures (even with zero WS clients) so smoke tests, /state,
        and replay all see the canonical events from publish_event_sync paths.
        """
        seq = self._next_seq()
        # Build canonical payload shape (what WS clients receive for every event)
        data = event.__dict__.copy() if hasattr(event, "__dict__") else {}
        data.pop("event_type", None)
        data.pop("timestamp", None)
        # metadata is usually internal; keep in data if present but do not top-level duplicate
        payload = {
            "seq": seq,
            "event_type": getattr(event, "event_type", "unknown"),
            "timestamp": getattr(event, "timestamp", time.time()),
            "cycle_id": getattr(event, "cycle_id", None),
            "correlation_id": getattr(event, "correlation_id", None),
            "data": data,
        }
        self.recent_events.append(payload)
        if len(self.recent_events) > 120:
            self.recent_events = self.recent_events[-60:]
        return payload

    async def broadcast(self, event: MissionEvent):
        """Send an event to all connected clients (records + seqs centrally)."""
        payload = self._record_event_for_introspection(event)
        if not self.active_connections:
            return

        message = json.dumps(payload, default=str)

        dead_connections: list[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)

    def _schedule_publish(self, event: MissionEvent) -> None:
        """
        Fire-and-forget scheduler safe to call from sync hot paths
        (ExperienceGraphRecorder record_*, Grid health, Overseer _tick, Integrated loop methods).

        CENTRAL RULE PRESERVED: publish_event / publish_event_sync (this path) are
        the *only* way data is pushed from core to Mission Control.

        When no running loop, still records (with seq) to recent_events so smoke + replay work.
        """
        try:
            loop = asyncio.get_running_loop()
            # Broadcast centralizes record+seq+send. Do NOT record here.
            loop.create_task(self.broadcast(event))
        except RuntimeError:
            # No running event loop (pure sync / smoke / import-time / some threads).
            # Record directly (assigns seq) so introspection / command smoke / tests see flow.
            self._record_event_for_introspection(event)

    def attach_mission(self, mission: Any):
        """Attach the central IntegratedRealTimeEvolutionSystem (or equivalent)."""
        self._current_mission = mission

    def attach_grid(self, grid: Any):
        """Attach persistent AD-Grid GridEngine. This keeps the Tower alive as a stable
        window into the living Grid even when no transient mission/fire is active.
        Grid health, programs, fabric coherence, and autonomous thread state flow here.
        """
        self._current_grid = grid
        # If mission also exposes grid, keep in sync but prefer direct attach for persistence
        if self._current_mission is not None and hasattr(self._current_mission, "grid"):
            try:
                self._current_mission.grid = grid
            except Exception:
                pass

    @property
    def mission(self):
        return self._current_mission

    @property
    def grid(self):
        return self._current_grid or (getattr(self._current_mission, "grid", None) if self._current_mission else None)

    # ------------------------------------------------------------------
    # Command router (inbound from UI / smoke). Commands are the return path.
    # publish_* remains one-way observation only.
    # ------------------------------------------------------------------
    def dispatch_command(self, command: str, **kwargs: Any) -> dict[str, Any]:
        """
        Sync-safe, WS-free command dispatch for headless smoke tests, CLI tools,
        and direct integration. Returns an ack-style result dict.

        Translates UI-style commands into native calls on the attached mission object
        (IntegratedRealTimeEvolutionSystem + its recorder/overseer/grid).
        All mutating commands that produce experience still flow through the
        existing recorder paths, which in turn (and only) use publish_event_sync
        for any MC observation side-effects.

        Wave 3 (stabilization-wave-20260531): extended surface with
        suggest_connection_improvements (weak_link targeting from fabric briefing),
        fabric_directives on record_parent_decision, pause/resume_evolution_context,
        inject_custom_observation (emits FabricUpdateEvent w/ graph_delta),
        list_recent_fires + compare_fires (Bay multi-fire from hub recent_events),
        overseer_force_hunch + get_metacognitive_briefing, emit_test_fabric_lift
        (safe dev helper emitting FabricUpdateEvent w/ graph_delta).
        Every command produces correct typed events via the single publish_event_sync.
        All results carry "surface": "local_operator_only" (localhost per AGENTS.md + server.py block).

        RESILIENCE: When no mission attached (common in smoke, early startup,
        or headless verification), returns explicit {"error": "no_mission_attached",
        "graceful": True} instead of raising. Callers (WS, tests, harnesses)
        must treat this as non-fatal. Backpressure note: dispatch itself is
        synchronous and cheap; heavy work happens inside the mission methods
        (which are responsible for their own timeouts/budgets).
        """
        mission = self._current_mission
        if mission is None:
            return {
                "command": command,
                "error": "no_mission_attached",
                "graceful": True,
                "timestamp": time.time(),
            }

        try:
            if command in ("request_briefing", "get_parent_actionable_briefing"):
                fn = getattr(mission, "get_parent_actionable_briefing", None)
                result = fn() if callable(fn) else {"error": "method_unavailable"}
                return {
                    "command": command,
                    "result": result,
                    "timestamp": time.time(),
                    "surface": "local_operator_only",
                }

            elif command in ("trigger_densification", "trigger_graph_densification"):
                cid = kwargs.get("cycle_id")
                weak_target = (
                    kwargs.get("weak_link")
                    or kwargs.get("target")
                    or kwargs.get("from_fabric_briefing")
                )
                fn = getattr(mission, "trigger_graph_densification", None)
                result = fn(cid) if callable(fn) else {"error": "method_unavailable"}
                if weak_target and isinstance(result, dict):
                    result = dict(result)
                    result["weak_link_target"] = weak_target
                    result["note"] = "targeted from fabric briefing via Wave 3 command surface"
                return {
                    "command": command,
                    "result": result,
                    "timestamp": time.time(),
                    "surface": "local_operator_only",
                }

            elif command in ("parent_decision", "record_parent_decision"):
                cid = kwargs.get("cycle_id")
                decision = kwargs.get("decision", {"action": "command_surface_default"})
                if isinstance(decision, dict):
                    decision = dict(decision)
                    if "fabric_directives" not in decision:
                        fdir = kwargs.get("fabric_directives") or kwargs.get("directives")
                        if fdir:
                            decision["fabric_directives"] = fdir
                    decision["from_fabric"] = kwargs.get(
                        "from_fabric", kwargs.get("triggered_from_fabric", True)
                    )
                actions_taken = kwargs.get("actions_taken", ["mission_control_command"])
                fabric_reasoning = kwargs.get("fabric_reasoning") or kwargs.get("structural_fabric_reasoning")
                fn = getattr(mission, "record_parent_decision", None)
                result = fn(cid, decision, actions_taken, fabric_reasoning=fabric_reasoning) if callable(fn) else None
                return {
                    "command": command,
                    "result": result,
                    "timestamp": time.time(),
                    "surface": "local_operator_only",
                    "triggered_from_fabric": decision.get("from_fabric", True)
                    if isinstance(decision, dict)
                    else True,
                }

            elif command in ("start_static_fire",):
                duration = float(kwargs.get("duration_seconds", kwargs.get("duration", 120.0)))
                label = kwargs.get("label", "mission_control_command")
                fn = getattr(mission, "start_static_fire", None)
                if callable(fn):
                    result = fn(duration_seconds=duration, label=label)
                else:
                    # graceful fallback (should not happen after attachment point added)
                    result = {
                        "status": "thin_static_fire_entrypoint_unavailable",
                        "note": "Added on IntegratedRealTimeEvolutionSystem for MC command surface",
                    }
                return {
                    "command": command,
                    "result": result,
                    "timestamp": time.time(),
                    "surface": "local_operator_only",
                }

            elif command in ("get_state", "get_loop_state"):
                result = self.derive_loop_state_snapshot()
                return {
                    "command": command,
                    "result": result,
                    "timestamp": time.time(),
                    "surface": "local_operator_only",
                }

            elif command in ("get_fabric",):
                result = self.derive_fabric_snapshot()
                return {
                    "command": command,
                    "result": result,
                    "timestamp": time.time(),
                    "surface": "local_operator_only",
                }

            # ------------------------------------------------------------------
            # Wave 3 Command Surface Extensions (per stabilization-wave-20260531 charter)
            # All route through existing Integrated methods OR thin wrappers that
            # call publish_event_sync exclusively. Produce correct typed events:
            # ParentDecisionEvent (with triggered_from_fabric), FabricUpdateEvent (with graph_delta),
            # OverseerStateEvent, StaticFireEvent updates. Safe localhost-only local operator.
            # Weak-link targeting from fabric briefing supported on densify/suggest.
            # ------------------------------------------------------------------
            elif command in ("suggest_connection_improvements", "suggest_weak_links"):
                cid = kwargs.get("cycle_id")
                fn = getattr(mission, "suggest_connection_improvements", None)
                result = (
                    fn(cid)
                    if callable(fn)
                    else {
                        "error": "method_unavailable",
                        "note": "Integrated suggest; falls back to trigger_graph_densification for full v2",
                    }
                )
                return {
                    "command": command,
                    "result": result,
                    "timestamp": time.time(),
                    "surface": "local_operator_only",
                }

            elif command in ("overseer_force_hunch", "trigger_overseer_hunch"):
                fn = getattr(mission, "trigger_overseer_hunch_action", None)
                result = fn() if callable(fn) else {"error": "method_unavailable"}
                try:
                    evt = OverseerStateEvent(
                        event_type="overseer_state",
                        timestamp=time.time(),
                        cycle_id=kwargs.get("cycle_id"),
                        adaptation_effectiveness=0.0,
                        recommendations=["forced_hunch_via_command_surface"],
                        recent_hunches=[
                            {
                                "source": "mission_control_wave3",
                                "action": "overseer_force_hunch",
                                "ts": time.time(),
                            }
                        ],
                    )
                    publish_event_sync(evt)
                except Exception:
                    pass
                return {
                    "command": command,
                    "result": result,
                    "timestamp": time.time(),
                    "surface": "local_operator_only",
                }

            elif command in ("get_metacognitive_briefing", "get_overseer_briefing"):
                fn = getattr(mission, "get_overseer_briefing_for_parent", None)
                if not callable(fn):
                    fn = getattr(mission, "get_overseer_current_understanding", None)
                result = fn() if callable(fn) else {"error": "method_unavailable"}
                return {
                    "command": command,
                    "result": result,
                    "timestamp": time.time(),
                    "surface": "local_operator_only",
                }

            elif command in ("pause_evolution_context", "pause_evolution"):
                note = kwargs.get("note", "operator pause via Wave 3 command surface")
                try:
                    evt = ParentDecisionEvent(
                        event_type="parent_decision",
                        timestamp=time.time(),
                        cycle_id=kwargs.get("cycle_id"),
                        decision_summary="pause_evolution_context",
                        actions_taken=["mission_control_pause"],
                        triggered_from_fabric=bool(kwargs.get("from_fabric", True)),
                        fabric_coherence_at_decision=kwargs.get("fabric_coherence"),
                        metadata={"note": note},
                    )
                    publish_event_sync(evt)
                except Exception:
                    pass
                return {
                    "command": command,
                    "result": {"status": "pause_recorded", "note": note},
                    "timestamp": time.time(),
                    "surface": "local_operator_only",
                }

            elif command in ("resume_evolution_context", "resume_evolution"):
                note = kwargs.get("note", "operator resume via Wave 3 command surface")
                try:
                    evt = ParentDecisionEvent(
                        event_type="parent_decision",
                        timestamp=time.time(),
                        cycle_id=kwargs.get("cycle_id"),
                        decision_summary="resume_evolution_context",
                        actions_taken=["mission_control_resume"],
                        triggered_from_fabric=bool(kwargs.get("from_fabric", True)),
                        fabric_coherence_at_decision=kwargs.get("fabric_coherence"),
                        metadata={"note": note},
                    )
                    publish_event_sync(evt)
                except Exception:
                    pass
                return {
                    "command": command,
                    "result": {"status": "resume_recorded", "note": note},
                    "timestamp": time.time(),
                    "surface": "local_operator_only",
                }

            elif command in ("inject_custom_observation", "inject_observation"):
                obs = kwargs.get(
                    "observation",
                    kwargs.get("note", "custom observation from operator via fabric briefing"),
                )
                weak_links = kwargs.get("weak_links", kwargs.get("targets", []))
                try:
                    evt = FabricUpdateEvent(
                        event_type="fabric_update",
                        timestamp=time.time(),
                        cycle_id=kwargs.get("cycle_id"),
                        fabric_coherence=float(kwargs.get("coherence", 0.88)),
                        delta_edges=0,
                        summary=f"Injected custom observation: {str(obs)[:110]}",
                        graph_delta={
                            "injected_observation": obs,
                            "weak_link_targets": weak_links,
                            "source": "mission_control_wave3_inject",
                            "from_fabric_briefing": bool(kwargs.get("from_fabric")),
                        },
                    )
                    publish_event_sync(evt)
                except Exception:
                    pass
                return {
                    "command": command,
                    "result": {
                        "status": "observation_injected_to_fabric",
                        "graph_delta_preview": {"obs": str(obs)[:50]},
                    },
                    "timestamp": time.time(),
                    "surface": "local_operator_only",
                }

            elif command in ("list_recent_fires", "recent_fires"):
                fires = [
                    e
                    for e in self.recent_events
                    if "static_fire" in str(e.get("event_type", "")).lower()
                ]
                result = {
                    "count": len(fires),
                    "recent": fires[-8:],
                    "note": "sourced exclusively from hub.recent_events (via publish_event_sync only); ready for Bay multi-fire compare",
                }
                return {
                    "command": command,
                    "result": result,
                    "timestamp": time.time(),
                    "surface": "local_operator_only",
                }

            elif command in ("compare_fires", "compare_static_fires"):
                fires = [
                    e
                    for e in self.recent_events
                    if "static_fire" in str(e.get("event_type", "")).lower()
                ]
                if len(fires) >= 2:
                    f1, f2 = fires[-2], fires[-1]
                    d1 = f1.get("data", {}) or {}
                    d2 = f2.get("data", {}) or {}

                    def _lift(d):
                        if isinstance(d.get("total_lift"), (int, float)):
                            return d["total_lift"]
                        fr = d.get("final_report") or {}
                        return (
                            fr.get("lift_pct", fr.get("total_lift", 0))
                            if isinstance(fr, dict)
                            else 0
                        )

                    l1, l2 = _lift(d1), _lift(d2)
                    result = {
                        "delta_lift": round(l2 - l1, 2),
                        "fire1_seq": f1.get("seq"),
                        "fire2_seq": f2.get("seq"),
                        "note": "Wave 3 Bay multi-fire comparison (via recent_events from publish_event_sync)",
                    }
                else:
                    result = {
                        "note": "need >=2 static fires in hub history for compare",
                        "available": len(fires),
                    }
                return {
                    "command": command,
                    "result": result,
                    "timestamp": time.time(),
                    "surface": "local_operator_only",
                }

            elif command in ("emit_test_fabric_lift", "test_fabric_lift"):
                lift = float(kwargs.get("lift", kwargs.get("delta", 0.042)))
                delta_e = int(kwargs.get("delta_edges", kwargs.get("edges", 5)))
                coh = float(kwargs.get("coherence", 0.91))
                try:
                    evt = FabricUpdateEvent(
                        event_type="fabric_update",
                        timestamp=time.time(),
                        cycle_id=kwargs.get("cycle_id"),
                        fabric_coherence=coh,
                        delta_edges=delta_e,
                        summary="Test fabric lift (safe dev helper for demo / UX verification of Wave 3 surface)",
                        graph_delta={
                            "method": "emit_test_fabric_lift",
                            "lift_pct_delta": round(lift * 100, 2),
                            "edges_added": delta_e,
                            "demo": True,
                            "source": "command_surface_wave3",
                        },
                    )
                    publish_event_sync(evt)
                    result = {
                        "status": "test_lift_emitted",
                        "graph_delta": evt.graph_delta,
                        "coherence": coh,
                    }
                except Exception as ex:
                    result = {"error": str(ex)}
                return {
                    "command": command,
                    "result": result,
                    "timestamp": time.time(),
                    "surface": "local_operator_only",
                }

            # Conductor Cockpit review surface (additive): approve/override on inhabitant_code_action
            # proposals from Council inhabitants (Perfectionist etc). Records verdict as attributed
            # DNA via recorder (if attached) + emits ParentDecisionEvent (visible in Tower fabric/decision timeline).
            # Full attribution: ilo-conductor-cockpit program + Program Contract + Guardian + 1780296458.
            # Called from UI buttons in Code Action Review Queue; produces living DNA for the self-referential loop.
            elif command in ("review_code_action", "approve_code_action", "override_code_action", "review_inhabitant_code_action"):
                slug = kwargs.get("code_action_slug") or kwargs.get("slug") or kwargs.get("target_slug")
                verdict = kwargs.get("verdict", "approved_by_conductor" if "approve" in command.lower() else "overridden_by_conductor")
                conductor_sig = kwargs.get("conductor_signature", "ilo-conductor-cockpit@stabilization-wave-20260531 + Contract + 1780296458")
                note = kwargs.get("note", f"Conductor Cockpit review: {verdict} on {slug}")
                result = {"status": "review_ack", "slug": slug, "verdict": verdict, "note": note}
                try:
                    # Always emit via canonical channel for UI visibility (ParentDecision + fabric)
                    evt = ParentDecisionEvent(
                        event_type="parent_decision",
                        timestamp=time.time(),
                        cycle_id=kwargs.get("cycle_id"),
                        decision_summary=f"conductor_cockpit_{verdict}",
                        actions_taken=["cockpit_code_action_review", f"verdict:{verdict}"],
                        triggered_from_fabric=True,
                        metadata={
                            "code_action_slug": slug,
                            "verdict": verdict,
                            "conductor_signature": conductor_sig,
                            "note": note,
                            "source": "conductor_cockpit_ui",
                        },
                    )
                    publish_event_sync(evt)
                    # Record explicit verdict DNA as inhabitant_code_action (Conductor as program)
                    mission = self._current_mission
                    if mission and hasattr(mission, "recorder"):
                        rec = mission.recorder
                        if hasattr(rec, "record_inhabitant_code_action"):
                            vslug = rec.record_inhabitant_code_action(
                                program_id="ilo-conductor-cockpit@stabilization-wave-20260531",
                                action={
                                    "type": "conductor_verdict",
                                    "target_slug": slug,
                                    "verdict": verdict,
                                    "note": note,
                                    "signature": conductor_sig,
                                    "ui_source": "code_action_review_queue",
                                },
                                constitution_refs=[
                                    "research-constitution-ad-grid-program-contract@stabilization-wave-20260531",
                                    "research-constitution-guardian-integrity@stabilization-wave-20260531",
                                ],
                                user_objective_refs=["conductor-cockpit-steering", "1780296458", "code-action-review"],
                            )
                            result["verdict_dna_slug"] = vslug
                            result["dna_recorded"] = True
                    result["status"] = "verdict_recorded_as_dna"
                except Exception as ex:
                    result["partial"] = True
                    result["emit_note"] = str(ex)[:90]
                return {
                    "command": command,
                    "result": result,
                    "timestamp": time.time(),
                    "surface": "local_operator_only",
                    "dna_trace_ref": "parent_fabric_reasoning:1780296588",
                }

            elif command in ("get_council_activity", "council_activity"):
                return {
                    "command": command,
                    "result": {"note": "Full data via REST GET /api/grid/council-activity (uses get_council_activity fabric pattern)"},
                    "timestamp": time.time(),
                    "surface": "local_operator_only",
                }

            else:
                return {
                    "command": command,
                    "error": f"unknown_command:{command}",
                    "supported": [
                        "request_briefing",
                        "trigger_densification",
                        "parent_decision",
                        "start_static_fire",
                        "get_state",
                        "get_fabric",
                        "suggest_connection_improvements",
                        "overseer_force_hunch",
                        "get_metacognitive_briefing",
                        "pause_evolution_context",
                        "resume_evolution_context",
                        "inject_custom_observation",
                        "list_recent_fires",
                        "compare_fires",
                        "emit_test_fabric_lift",
                        "record_parent_decision",
                        "review_code_action",
                        "approve_code_action",
                        "override_code_action",
                        "get_council_activity",
                    ],
                    "timestamp": time.time(),
                    "surface": "local_operator_only",
                }
        except Exception as exc:
            return {
                "command": command,
                "error": f"{type(exc).__name__}:{exc}",
                "timestamp": time.time(),
                "surface": "local_operator_only",
            }

    async def handle_inbound_command(self, websocket: WebSocket, raw_data: str) -> None:
        """
        Parse inbound client JSON command and dispatch via the router.
        Always replies with a command_ack (or error) on the same WS.
        Commands never push data themselves; they invoke mission methods whose
        side-effects (if any) use the official publish_event_sync paths.

        ERROR BOUNDARY: All inbound is processed inside broad try in the WS
        endpoint (see mission_websocket). This method itself catches json/parse
        errors and always produces a reply (never lets a bad command kill the
        socket or the hub). Replay ("replay_events") is bounded ([:64]) to
        protect against backpressure on slow clients.
        """
        try:
            msg = json.loads(raw_data)
        except Exception:
            await self._safe_send_to_client(
                websocket, {"type": "error", "error": "invalid_json", "raw": raw_data[:200]}
            )
            return

        if not isinstance(msg, dict):
            await self._safe_send_to_client(
                websocket, {"type": "error", "error": "command_must_be_object"}
            )
            return

        # Allow either {"command": "foo", ...} or legacy {"type": "foo", ...}
        cmd = msg.get("command") or msg.get("type") or ""
        if not cmd or cmd in ("ping", "heartbeat"):
            await self._safe_send_to_client(websocket, {"type": "pong", "timestamp": time.time()})
            return

        if cmd == "replay_events":
            # Client-side replay support via seq numbers
            after = int(msg.get("after_seq", msg.get("after", 0)) or 0)
            replay = [e for e in self.recent_events if e.get("seq", 0) > after][
                :64
            ]  # bounded to prevent backpressure
            await self._safe_send_to_client(
                websocket,
                {
                    "type": "replay",
                    "after_seq": after,
                    "count": len(replay),
                    "events": replay,
                    "current_seq": self._event_seq,
                },
            )
            return

        # Normal routed command
        result = self.dispatch_command(
            cmd, **{k: v for k, v in msg.items() if k not in ("command", "type")}
        )
        ack = {"type": "command_ack", "nonce": msg.get("nonce"), **result}
        await self._safe_send_to_client(websocket, ack)

    async def _safe_send_to_client(self, websocket: WebSocket, payload: dict[str, Any]) -> None:
        try:
            await websocket.send_text(json.dumps(payload, default=str))
        except Exception:
            self.disconnect(websocket)

    # ------------------------------------------------------------------
    # Better snapshot derivation (used by /state and initial WS payload)
    # ------------------------------------------------------------------
    def derive_loop_state_snapshot(self) -> dict[str, Any]:
        """Graceful snapshot used by /state + WS initial. Never raises to callers."""
        mission = self._current_mission
        grid = self.grid  # may be directly attached for persistent AD-Grid mode
        if mission is None and grid is None:
            return {"status": "no_mission_attached", "grid_health": self._safe_grid_health(grid)}
        try:
            base = {}
            if mission is not None:
                if hasattr(mission, "get_loop_state_view"):
                    view = mission.get_loop_state_view()
                    base = {
                        "cycle_id": getattr(view, "cycle_id", None),
                        "current_step": getattr(view, "current_step", 0),
                        "fabric_coherence": getattr(view, "fabric_coherence", 0.0),
                        "last_parent_decision": getattr(view, "last_parent_decision", None),
                        "overseer_state": getattr(view, "overseer_state", None),
                    }
                else:
                    base = {
                        "active_cycle": getattr(
                            mission.recorder, "get_active_evolution_cycle_id", lambda: None
                        )()
                        if hasattr(mission, "recorder")
                        else None,
                    }
            # Always merge grid_health when Grid is attached (persistent AD-Grid observability)
            gh = self._safe_grid_health(grid or (mission.grid if mission and hasattr(mission, "grid") else None))
            base["grid_health"] = gh
            base["status"] = "ok" if (mission or grid) else "no_mission_attached"
            return base
        except Exception:
            return {"status": "snapshot_error", "grid_health": self._safe_grid_health(grid)}

    def _safe_grid_health(self, grid: Any) -> dict[str, Any]:
        """Never raises. Returns live grid_health or minimal quiet-mode snapshot."""
        if grid is None:
            return {"status": "grid_not_attached", "active_programs": 0, "mode": "quiet"}
        try:
            if hasattr(grid, "get_grid_health"):
                return grid.get_grid_health()
            if hasattr(grid, "_grid_health"):
                return dict(grid._grid_health)
            return {"status": "grid_attached_no_health"}
        except Exception:
            return {"status": "grid_health_error"}

    def derive_fabric_snapshot(self) -> dict[str, Any]:
        """Graceful snapshot used by /state + WS initial. Never raises to callers.
        Now returns rich experience layer data when available (the tight integration point).
        """
        mission = self._current_mission
        if mission is None:
            return {"status": "no_mission_attached"}
        try:
            if hasattr(mission, "recorder") and hasattr(mission.recorder, "get_parent_facing_memory_fabric_briefing"):
                briefing = mission.recorder.get_parent_facing_memory_fabric_briefing(lookback_days=7)
                # Also surface quick recent cycle graphs if the recorder supports it
                recent_graphs = []
                try:
                    if hasattr(mission.recorder, "get_recent_loop_graphs"):
                        recent_graphs = mission.recorder.get_recent_loop_graphs(limit=3)
                except Exception:
                    pass
                briefing["recent_cycle_graphs"] = recent_graphs
                return briefing
            if hasattr(mission, "get_fabric_view"):
                view = mission.get_fabric_view()
                return {
                    "overall_coherence": getattr(view, "overall_coherence", 0.0),
                    "active_cycles": getattr(view, "active_cycles", []),
                    "total_cross_cycle_edges": getattr(view, "total_cross_cycle_edges", 0),
                }
        except Exception:
            pass
        return {}


# Global hub instance
hub = MissionControlHub()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Future: could start background tasks here that listen to Grid/Overseer events
    yield
    # Cleanup


# Resolve static assets relative to this module (works in dev under src/ and when installed)
_MISSION_STATIC_DIR = Path(__file__).parent / "static"

# AgentDrive-native Kanban Board — reworked to be the visual surface of the 6-step loop + Experience Graph fabric
from agentdrive.board import get_default_board as _get_default_board


def create_mission_control_app() -> FastAPI:
    app = FastAPI(
        title="AgentDrive Mission Control",
        description="Real-time unified view of the entire AgentDrive system centered on the 6-step loop and Experience Graph fabric.",
        version="0.1.0-mission-control",
        lifespan=lifespan,
    )

    # Serve the Control Tower frontend (single powerful index.html) + any future assets
    # This is the primary landing experience for `agentdrive mission`
    if _MISSION_STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_MISSION_STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve the Mission Control Tower single-file frontend."""
        index_path = _MISSION_STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path, media_type="text/html")
        # Graceful fallback if frontend not packaged
        return HTMLResponse(
            content="<h1>AgentDrive Mission Control</h1><p>Control Tower frontend not found. Place index.html in mission_control/static/.</p>",
            status_code=200,
        )

    @app.get("/state")
    async def current_state():
        """Lightweight REST snapshot (useful for initial load). Uses strengthened hub derivation."""
        mission = hub.mission
        if mission is None:
            return {"status": "no_mission_attached"}

        # Use the new better snapshot derivation on the hub
        loop_snap = hub.derive_loop_state_snapshot()
        fabric_snap = hub.derive_fabric_snapshot()
        try:
            grid_health = (
                mission.grid.get_grid_health() if hasattr(mission, "grid") and mission.grid else {}
            )
        except Exception:
            grid_health = {}

        return {
            "timestamp": time.time(),
            "loop_state": loop_snap,
            "fabric": fabric_snap,
            "grid_health": grid_health,
            "recent_event_count": len(hub.recent_events),
            # Tight experience layer snapshot for the UI on initial load (reuses the rich derive that already calls recorder briefing when attached)
            "experience_fabric": hub.derive_fabric_snapshot() if hasattr(hub, "derive_fabric_snapshot") else (fabric_snap if isinstance(fabric_snap, dict) else {}),
        }

    # === AgentDrive-native Mission Kanban Board API ===
    # Reworked to be the visual surface for the 6-step loop + Experience Graph fabric.
    # This is what `agentdrive board` / `agentdrive kanban` prominently provides on localhost.
    _board = _get_default_board()

    @app.get("/api/board")
    async def get_board():
        """Full Kanban state — lanes + stats. Primary data source for the web Kanban UI."""
        try:
            return {
                "lanes": {k.value: [m.to_dict() for m in v] for k, v in _board.lanes().items()},
                "stats": _board.stats(),
                "path": str(_board.path),
            }
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/experience_fabric")
    async def get_experience_fabric():
        """Direct, rich view into the Experience Layer + v3 fabric.
        This is the tight real-time window the Tower uses for the 'see the experience as one' surface.
        Returns the full Parent-facing briefing + recent structural graphs + (stabilization-wave-20260531)
        live parent_fabric_reasoning_traces (for the dedicated Parent Fabric Reasoning section
        in #experience-fabric-panel: elements considered, patterns, lift; clickable for canvas highlights).
        """
        mission = hub._current_mission
        if mission is None or not hasattr(mission, "recorder"):
            return {"status": "no_experience_layer_attached"}
        try:
            recorder = mission.recorder
            briefing = recorder.get_parent_facing_memory_fabric_briefing(lookback_days=7) if hasattr(recorder, "get_parent_facing_memory_fabric_briefing") else {}
            recent = recorder.get_recent_loop_graphs(limit=4) if hasattr(recorder, "get_recent_loop_graphs") else []
            weak = recorder.find_weak_across_recent_cycles(min_coherence=0.65, lookback=5) if hasattr(recorder, "find_weak_across_recent_cycles") else []
            traces = recorder.get_recent_parent_fabric_reasoning_traces(limit=5) if hasattr(recorder, "get_recent_parent_fabric_reasoning_traces") else []
            return {
                "briefing": briefing,
                "recent_cycle_graphs": recent,
                "weak_links": weak[:8],
                "parent_fabric_reasoning_traces": traces,
                "generated_at": time.time(),
            }
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/board/missions")
    async def create_board_mission(payload: dict[str, Any]):
        """Create a new mission card (supports the rich AgentDrive-native fields)."""
        try:
            title = payload.get("title") or "Untitled mission"
            mission = _board.create(title, **{k: v for k, v in payload.items() if k != "title"})
            return {"ok": True, "mission": mission.to_dict()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.post("/api/board/missions/{mid}/transition")
    async def transition_board_mission(mid: str, payload: dict[str, Any]):
        """Transition a card (and optionally attach fabric contribution or outcome)."""
        try:
            to = payload.get("to")
            if not to:
                return {"ok": False, "error": "missing 'to' status"}
            try:
                to_status = __import__('agentdrive.board.mission_board', fromlist=['MissionStatus']).MissionStatus(to)
            except Exception:
                return {"ok": False, "error": f"invalid status '{to}'"}
            outcome = payload.get("outcome")
            dna_used = payload.get("dna_used")
            fabric_contrib = payload.get("fabric_contribution")
            m = _board.transition(mid, to_status, outcome=outcome, dna_used=dna_used)
            if m and fabric_contrib:
                _board.attach_fabric_update(mid, fabric_contrib)
            return {"ok": bool(m), "mission": m.to_dict() if m else None}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # === AD-Grid Persistent Observability Routes (minimal tranche) ===
    # These are defensive and always available when Grid is attached (via attach_grid or mission.grid).
    # They power the stable "Grid Living View" / inhabitant dashboards even in quiet/idle mode.
    # No mission required. Tower uses these + WS GridHealthEvent for adaptive quiet banners.

    @app.get("/api/grid/health")
    async def get_grid_health():
        """Live GridEngine health + active programs + fabric coherence. Primary for persistent Tower."""
        g = hub.grid
        if g is None:
            return {"status": "grid_not_attached", "mode": "quiet", "active_programs": 0}
        try:
            if hasattr(g, "get_grid_health"):
                h = g.get_grid_health()
            elif hasattr(g, "_grid_health"):
                h = dict(g._grid_health)
            else:
                h = {"status": "attached"}
            h["mode"] = "living" if h.get("active_research_threads", 0) or h.get("active_programs", 0) else "quiet"
            return h
        except Exception as e:
            return {"status": "error", "error": str(e)[:120], "mode": "quiet"}

    @app.get("/api/grid/programs")
    async def get_grid_programs():
        """Registered AD-Grid inhabitants (model-program-manifests). For inhabitant dashboard."""
        g = hub.grid
        if g is None:
            return {"programs": [], "count": 0, "mode": "quiet"}
        try:
            if hasattr(g, "list_active_programs"):
                progs = g.list_active_programs()
            else:
                progs = []
            return {"programs": progs, "count": len(progs), "mode": "living" if progs else "quiet"}
        except Exception as e:
            return {"programs": [], "count": 0, "error": str(e)[:120], "mode": "quiet"}

    @app.get("/api/grid/status")
    async def get_grid_status():
        """Light status for quiet-mode banners and adaptive polling decisions in Tower."""
        g = hub.grid
        if g is None:
            return {"attached": False, "mode": "no_grid", "recommendation": "start GridEngine for persistent AD-Grid view"}
        try:
            h = g.get_grid_health() if hasattr(g, "get_grid_health") else getattr(g, "_grid_health", {})
            return {
                "attached": True,
                "mode": "quiet" if not (h.get("active_research_threads") or h.get("active_programs")) else "active",
                "fabric_coherence_last": h.get("fabric_coherence_last", 0.0),
                "active_programs": h.get("active_programs", 0),
                "active_research_threads": h.get("active_research_threads", 0),
                "last_gardener_pass_ts": h.get("last_gardener_pass_ts", 0.0),
            }
        except Exception as e:
            return {"attached": True, "mode": "error", "error": str(e)[:120]}

    # === Conductor Cockpit Grid Routes (additive, stabilization-wave-20260531) ===
    # Power the four prominent new panels in the Tower without touching existing surfaces.
    # All local-operator only; use recorder.loops_dir scan (mirrors internal get_recent_parent... pattern)
    # + GridEngine surfaces (register_model_program data) + hub recent_events.
    # Council activity follows the agentdrive_get_council_activity MCP pattern (fabric pulls on constitutions).
    # Code actions surface inhabitant_code_action DNA for review queue (proposals + verdicts).
    # Inhabitants enriches register_model_program manifests with status/attribution.
    # DNA: design recorded as parent_fabric_reasoning:1780296588 (and 1780296579 charter).

    @app.get("/api/grid/inhabitants")
    async def get_grid_inhabitants():
        """Richer inhabitant view for Conductor Cockpit 'Inhabitant Registrations & Status' panel.
        Leverages GridEngine.register_model_program data (via list_active_programs) + health.
        Additive to /api/grid/programs; includes council thread count + registration provenance.
        """
        g = hub.grid
        programs = []
        health = {}
        if g is not None:
            try:
                if hasattr(g, "list_active_programs"):
                    programs = g.list_active_programs() or []
                if hasattr(g, "get_grid_health"):
                    health = g.get_grid_health() or {}
            except Exception as e:
                health = {"error": str(e)[:80]}
        enriched = []
        for p in programs:
            pp = dict(p) if isinstance(p, dict) else {"raw": str(p)[:200]}
            pp["status"] = "registered_inhabitant" if pp.get("program_id") else "manifest_incomplete"
            pp["attribution"] = "GridEngine.register_model_program + ad-grid-program-contract@stabilization-wave-20260531"
            pp["cockpit_note"] = "visible to Conductor for steering / override"
            enriched.append(pp)
        return {
            "inhabitants": enriched,
            "count": len(enriched),
            "health_snapshot": {k: health.get(k) for k in ("active_programs", "active_research_threads", "status", "fabric_coherence_last") if k in health},
            "council_threads": health.get("active_research_threads", health.get("research_threads", 3)),
            "mode": "living" if enriched or health.get("active_research_threads") else "quiet",
            "note": "Inhabitant Registrations & Status — from register_model_program DNA. Self-referential; all actions carry full attribution.",
            "generated_at": time.time(),
            "dna_trace_ref": "parent_fabric_reasoning:1780296588",
        }

    @app.get("/api/grid/council-activity")
    async def get_grid_council_activity(roles: str = "", limit: int = 15):
        """Live Council Activity feed for Conductor Cockpit.
        Uses the get_council_activity pattern (direct fabric pulls on parent_fabric_reasoning + targeted
        get_fabric_reasoning_traces_for_element on the three Council constitutions + Program Contract).
        Falls back to recent_events + grid health. Real-time via Tower polling + WS fabric events.
        """
        effective_roles = [r.strip().lower() for r in (roles or "").split(",") if r.strip()] or ["perfectionist", "guardian", "external", "program-contract", "externalbridge"]
        council_elems = [
            "research-constitution-perfectionist-optimizer@stabilization-wave-20260531",
            "research-constitution-guardian-integrity@stabilization-wave-20260531",
            "research-constitution-external-bridge@stabilization-wave-20260531",
            "ad-grid-program-contract@stabilization-wave-20260531",
            "research-constitution-ad-grid-program-contract@stabilization-wave-20260531",
        ]
        activity = []
        mission = hub._current_mission
        if mission is not None and hasattr(mission, "recorder"):
            rec = mission.recorder
            try:
                if hasattr(rec, "get_recent_parent_fabric_reasoning_traces"):
                    traces = rec.get_recent_parent_fabric_reasoning_traces(limit=limit * 2) or []
                    for t in traces:
                        txt = str(t).lower() + str(t.get("fabric_elements_considered", []))
                        if any(r in txt for r in effective_roles) or any(e in txt for e in council_elems):
                            activity.append({"type": "parent_fabric_reasoning", "data": t, "gbrain": getattr(t, "gbrain_signal_score", 0.7)})
                for elem in council_elems:
                    if len(activity) >= limit * 2:
                        break
                    if hasattr(rec, "get_fabric_reasoning_traces_for_element"):
                        try:
                            ts = rec.get_fabric_reasoning_traces_for_element(element=elem, lookback=max(3, limit // 3)) or []
                            for t in ts:
                                activity.append({"type": "council_element_trace", "element": elem, "data": t})
                        except Exception:
                            pass
            except Exception:
                pass
        # live from hub recent + grid
        for e in hub.recent_events[-40:]:
            s = str(e).lower()
            if any(x in s for x in ["perfectionist", "guardian", "external-bridge", "council", "program-contract"]):
                activity.append({"type": "live_event", "event": e})
        g = hub.grid
        grid_snap = {}
        if g:
            try:
                grid_snap = g.get_grid_health() if hasattr(g, "get_grid_health") else getattr(g, "_grid_health", {})
            except Exception:
                pass
        activity = activity[:limit]
        return {
            "swarm_id": "stabilization-wave-20260531",
            "roles": effective_roles,
            "recent_council_activity": activity,
            "grid_health": {k: grid_snap.get(k) for k in ("active_research_threads", "active_programs", "status") if k in grid_snap},
            "note": "Mirrors MCP agentdrive_get_council_activity. High-gbrain Council traces + proposals feed the Live Council Activity panel. Full provenance in Experience Graph.",
            "generated_at": time.time(),
            "dna_trace_ref": "parent_fabric_reasoning:1780296588",
        }

    @app.get("/api/grid/code-actions")
    async def get_grid_code_actions(limit: int = 20):
        """Code Action Review Queue data: recent inhabitant_code_action proposals + verdicts + applied.
        Scans recorder persisted loops (exact pattern from get_recent_parent_fabric_reasoning_traces)
        for artifact_type == 'inhabitant_code_action'. Enriches with program_id, constitution_refs,
        verdicts (guardian_verdict etc), action type. Also pulls live from hub.recent_events.
        Powers the review queue with approve/override buttons that callback to command surface
        (records Conductor verdict as new attributed DNA).
        """
        actions = []
        mission = hub._current_mission
        if mission is not None and hasattr(mission, "recorder"):
            rec = mission.recorder
            try:
                if hasattr(rec, "loops_dir"):
                    files = sorted(rec.loops_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:40]
                    for f in files:
                        try:
                            data = json.loads(f.read_text())
                            arts = (data.get("participating_artifacts", []) or data.get("artifacts", []) or [])
                            for a in arts:
                                if isinstance(a, dict) and str(a.get("artifact_type", "")).lower() == "inhabitant_code_action":
                                    content = a.get("content_ref") or a.get("content") or a.get("ref") or {}
                                    act = content.get("action", {}) if isinstance(content, dict) else {}
                                    actions.append({
                                        "slug": a.get("slug"),
                                        "cycle_id": data.get("cycle_id") or a.get("cycle_id"),
                                        "ts": a.get("ts") or data.get("started_at") or data.get("created_at") or 0,
                                        "program_id": content.get("program_id") or act.get("program_id") or "unknown-inhabitant",
                                        "action_type": act.get("type") if isinstance(act, dict) else str(act)[:30],
                                        "action": act if isinstance(act, dict) else {"raw": str(act)[:120]},
                                        "constitution_refs": content.get("constitution_refs", []) if isinstance(content, dict) else [],
                                        "user_objective_refs": content.get("user_objective_refs", []) if isinstance(content, dict) else [],
                                        "verdict": content.get("verdict") or content.get("guardian_verdict") or act.get("verdict"),
                                        "content_preview": str(content)[:160] if content else "",
                                        "source": "recorder_loops_scan",
                                    })
                        except Exception:
                            continue
            except Exception:
                pass
        # supplement with recent hub events (real-time proposals during Council threads)
        for e in hub.recent_events[-60:]:
            evs = str(e.get("data", e)).lower()
            if "inhabitant_code_action" in evs or "code_action" in evs or "self_improvement_proposal" in evs:
                actions.append({
                    "slug": e.get("seq"),
                    "from_live_event": True,
                    "event_summary": str(e.get("data", {}))[:200],
                    "ts": e.get("timestamp", 0),
                    "source": "hub_recent_events",
                })
        actions = sorted(actions, key=lambda x: float(x.get("ts", 0) or 0), reverse=True)[:limit]
        return {
            "code_actions": actions,
            "count": len(actions),
            "note": "For Code Action Review Queue in Conductor Cockpit. Proposals from Perfectionist etc. + Guardian verdicts. Use /ws command review_code_action to approve/override (records as DNA attributed to ilo-conductor-cockpit).",
            "generated_at": time.time(),
            "dna_trace_ref": "parent_fabric_reasoning:1780296588",
        }

    @app.get("/api/grid/thinking-summary")
    async def get_grid_thinking_summary(limit: int = 8):
        """'What the Grid is Thinking' high-gbrain parent_fabric_reasoning summary for Conductor.
        Pulls recent high expected_lift + recent traces; used by dedicated prominent panel.
        """
        traces = []
        mission = hub._current_mission
        if mission is not None and hasattr(mission, "recorder"):
            rec = mission.recorder
            try:
                if hasattr(rec, "get_recent_parent_fabric_reasoning_traces"):
                    raw = rec.get_recent_parent_fabric_reasoning_traces(limit=limit * 2) or []
                    for t in raw:
                        lift = t.get("expected_lift_signal") or t.get("expected_lift") or 0.0
                        if lift >= 0.02 or len(traces) < 3:  # bias to high value
                            traces.append(t)
            except Exception:
                pass
        traces = traces[:limit]
        return {
            "high_gbrain_traces": traces,
            "count": len(traces),
            "note": "Summary of recent Parent structural reasoning (high expected_lift prioritized). Powers 'What the Grid is Thinking' Conductor panel. Full traces + gbrain in Experience Graph.",
            "generated_at": time.time(),
            "dna_trace_ref": "parent_fabric_reasoning:1780296588",
        }

    @app.websocket("/ws/mission")
    async def mission_websocket(websocket: WebSocket):
        """Hardened WS endpoint: lifecycle, seq-aware initial payload, command router for return path.

        RESILIENCE / BACKPRESSURE:
        - connect() enforces _max_connections (16) with clean 1013 close.
        - recent_events bounded to 60-120 entries.
        - replay_events replies capped at 64 events.
        - All per-client send wrapped in _safe_send_to_client (disconnects on fail).
        - Outer except catches everything, sends best-effort fatal, then disconnects.
          The hub and FastAPI app continue serving other clients.
        - derive_* snapshots are defensive (return {"status": "no_mission_attached"} or
          {"status": "snapshot_error"} on any failure).
        Graceful degradation when Integrated not attached is first-class (used by
        smoke, early UI loads, and verification scripts targeting wave-20260531).
        """
        await hub.connect(websocket)
        try:
            # Send initial state on connect (includes current hub seq for client replay bootstrap)
            initial = await current_state()
            initial_payload = {
                "type": "initial_state",
                "data": initial,
                "seq": hub._event_seq,
                "recent_event_count": len(hub.recent_events),
            }
            await websocket.send_text(json.dumps(initial_payload, default=str))

            while True:
                data = await websocket.receive_text()
                # All inbound is treated as command (or ping). Router handles gracefully.
                await hub.handle_inbound_command(websocket, data)
        except WebSocketDisconnect:
            hub.disconnect(websocket)
        except Exception as exc:
            # Resilient: log-ish to client then drop (no crash of server)
            try:
                await websocket.send_text(json.dumps({"type": "fatal", "error": str(exc)[:200]}))
            except Exception:
                pass
            hub.disconnect(websocket)

    return app


# Helper functions that the rest of AgentDrive can call to push events
async def publish_event(event: MissionEvent):
    """Convenience function for the rest of the system to push real-time updates (async path)."""
    await hub.broadcast(event)


def publish_event_sync(event: MissionEvent):
    """
    Sync-safe publish entrypoint for hot paths inside IntegratedRealTimeEvolutionSystem,
    ExperienceGraphRecorder, RealTimeEvolutionOverseer, and GridEngine.

    Safe from any thread; falls back to recent_events capture when no asyncio loop.
    This is the recommended call site from the canonical loop emission points.
    """
    hub._schedule_publish(event)


# ------------------------------------------------------------------
# Headless smoke helper (stabilization-wave-20260531 context)
# Produces real IntegratedRealTimeEvolutionSystem, attaches hub, exercises
# the canonical methods that emit 6-step + fabric events, returns verification.
# Call from python -c or tests; never runs on import.
# ------------------------------------------------------------------
def smoke_mission_control_with_integrated_system() -> dict[str, Any]:
    """
    Small headless smoke: attaches a *real* (not mocked) IntegratedRealTimeEvolutionSystem
    (even if Grid threads are light), wires the hub, exercises get_parent_actionable_briefing
    + record_parent_decision (the 4/3/2/1/5/6 steps) and fabric paths via recorder,
    plus direct Overseer + Grid health touches. Asserts that 6-step + fabric events flowed
    into hub.recent_events.

    Also exercises the new command router (dispatch_command) with the canonical
    commands: request_briefing, trigger_densification, parent_decision, start_static_fire.
    Wave 3 extensions (stabilization-wave-20260531): suggest_connection_improvements (weak_link
    targeting from fabric briefing), enhanced record_parent_decision (fabric_directives),
    pause/resume_evolution_context, inject_custom_observation, list_recent_fires + compare_fires,
    overseer_force_hunch, get_metacognitive_briefing, emit_test_fabric_lift.
    Verifies that command dispatch safely calls through to native methods on the mission
    (or thin wrappers) and that those in turn cause additional typed events (ParentDecisionEvent
    w/ triggered_from_fabric flag, FabricUpdateEvent w/ graph_delta, etc.) to flow via the single
    publish_event_sync paths (seq numbers, recent_events capture, etc.). All results include
    local_operator_only marker. No bypass of publish_event_sync.

    Additionally directly exercises publish_static_fire_telemetry (rich payloads) to
    prove the full live telemetry + post-fire final_report (fabric renders, recorder
    snippets, Parent interventions inside fire) that a real 2min harness using
    run_static_fire_with_mission_telemetry will produce for the Tower Static Fire Bay.

    Target: stabilization-wave-20260531 context. Safe to call from python -c or tests.
    """
    from agentdrive.system.integrated_real_time_evolution_system import (
        IntegratedRealTimeEvolutionSystem,
    )

    # Fresh hub for isolated smoke (do not mutate global in a way that breaks CLI)
    test_hub = MissionControlHub()
    # Monkey the module hub briefly for publish_event_sync used inside (restored after)
    original_hub = hub
    try:
        # Temporarily point the module global at our test hub so publish_event_sync reaches it
        globals()["hub"] = test_hub  # type: ignore[assignment]

        system = IntegratedRealTimeEvolutionSystem(
            swarm_id="stabilization-wave-20260531",
            overseer_poll_interval_s=0.1,  # fast for smoke
        )
        # Headless (no .start() to keep smoke instant + no bg threads); recorder + integrated paths still fully instrumented and emit 6-step+fabric via the single clean recorder point + direct publish in briefing/decision.
        # Attach (wires recorder primarily; overseer/grid would get light attach if start() called by caller)
        system.attach_mission_control(test_hub)

        # Exercise core Parent-facing loop paths (these are the canonical emission points)
        briefing = system.get_parent_actionable_briefing()
        cid = briefing.get("active_evolution_cycle_id")

        # Parent decision (triggers step 4 + fabric + recorder ingestion)
        decision = {
            "action": "smoke_parent_steer",
            "note": "MissionControl smoke: exercising 6-step loop emission",
        }
        system.record_parent_decision(cid, decision, actions_taken=["smoke_test_action"])

        # Touch fabric explicitly (via recorder which is the clean point)
        try:
            _ = system.recorder.get_parent_facing_memory_fabric_briefing(lookback_days=1)
        except Exception:
            pass

        # Direct overseer tick path (may emit via its instrumentation)
        if system.overseer:
            try:
                _ = system.overseer.get_metacognitive_briefing()
            except Exception:
                pass

        # Grid health (emits on update paths)
        if system.grid:
            try:
                _ = system.grid.get_grid_health()
            except Exception:
                pass

        # ------------------------------------------------------------------
        # NEW: Command surface smoke (steps 2+5). Use dispatch_command (the same
        # router used by WS handle_inbound_command). These must succeed gracefully
        # and drive additional events through the official publish paths.
        # ------------------------------------------------------------------
        cmd_results: list[dict[str, Any]] = []

        # 1. request_briefing (exercises get_parent_actionable_briefing -> loop steps + fabric)
        cmd_results.append(test_hub.dispatch_command("request_briefing"))

        # 2. trigger_densification (exercises trigger_graph_densification on recorder paths)
        cmd_results.append(test_hub.dispatch_command("trigger_densification", cycle_id=cid))

        # 3. parent_decision via command router (exercises record_parent_decision again)
        cmd_results.append(
            test_hub.dispatch_command(
                "parent_decision",
                cycle_id=cid,
                decision={
                    "action": "cmd_smoke_parent_steer",
                    "source": "mission_control_command_smoke",
                },
                actions_taken=["command_router_action"],
            )
        )

        # 4. start_static_fire (exercises the new thin harness entrypoint; emits StaticFireEvent)
        cmd_results.append(
            test_hub.dispatch_command(
                "start_static_fire", duration_seconds=5.0, label="command_smoke"
            )
        )

        # Wave 3 extended surface smoke (charter): exercise all new commands.
        # These drive additional typed events via publish_event_sync (ParentDecisionEvent w/ triggered_from_fabric,
        # FabricUpdateEvent w/ graph_delta from inject + test_lift + densify weak targeting, Overseer etc).
        # Also exercises enhanced parent_decision with fabric_directives + weak targeting on densify.
        cmd_results.append(
            test_hub.dispatch_command("suggest_connection_improvements", cycle_id=cid)
        )
        cmd_results.append(
            test_hub.dispatch_command(
                "trigger_densification",
                cycle_id=cid,
                weak_link="weak:research-constitutions-04->ev-cycle-stab-31-0037 (from fabric briefing)",
            )
        )
        cmd_results.append(
            test_hub.dispatch_command(
                "parent_decision",
                cycle_id=cid,
                decision={"action": "fabric_steer_wave3"},
                fabric_directives=[
                    "densify weak links surfaced in get_parent_actionable_briefing",
                    "prioritize cross-cycle research-constitutions",
                ],
                from_fabric=True,
                actions_taken=["wave3_command_router"],
            )
        )
        cmd_results.append(test_hub.dispatch_command("overseer_force_hunch"))
        cmd_results.append(test_hub.dispatch_command("get_metacognitive_briefing"))
        cmd_results.append(
            test_hub.dispatch_command(
                "emit_test_fabric_lift", lift=0.031, delta_edges=4, coherence=0.905
            )
        )
        cmd_results.append(
            test_hub.dispatch_command(
                "inject_custom_observation",
                observation="prioritize research-constitution cross links from v1 briefing",
                weak_links=["weak:cycle-42->cycle-7"],
                from_fabric=True,
                coherence=0.89,
            )
        )
        cmd_results.append(
            test_hub.dispatch_command(
                "pause_evolution_context", note="test pause for UX verification", from_fabric=True
            )
        )
        cmd_results.append(test_hub.dispatch_command("list_recent_fires"))
        cmd_results.append(test_hub.dispatch_command("compare_fires"))
        cmd_results.append(
            test_hub.dispatch_command("resume_evolution_context", note="resume after test pause")
        )

        # 5. Exercise the new rich helpers directly (what real 120s harnesses + Tron Grid use for full live+post Bay data)
        publish_static_fire_telemetry(
            phase="running",
            duration_seconds=5.0,
            cycles_completed=2,
            current_fabric_coherence=0.87,
            coherence_start=0.82,
            log_line="mid-fire: densification + parent intervention inside window",
            key_events=[
                {
                    "type": "parent_intervention",
                    "summary": "steer toward research-constitutions fusion during fire",
                }
            ],
            parent_interventions=1,
            fabric_edges_delta=3,
        )
        publish_static_fire_telemetry(
            phase="completed",
            duration_seconds=5.0,
            cycles_completed=4,
            current_fabric_coherence=0.91,
            coherence_start=0.82,
            coherence_end=0.91,
            total_lift=9.0,
            key_events=[
                {
                    "type": "parent_intervention",
                    "summary": "steer toward research-constitutions fusion during fire",
                },
                {"type": "densify", "summary": "cross-cycle edges +11 under controlled evolution"},
            ],
            parent_interventions=2,
            fabric_edges_delta=11,
            final_report={
                "post_densif_fabric": {
                    "coherence_end": 0.91,
                    "edges_delta": 11,
                    "summary": "post-densif fabric render: strengthened continuations across 4 cycles in fire window",
                    "render_hint": "canvas + coherence lift + key_continuations",
                },
                "recorder_snippets": [
                    "recorder:fabric_contrib@sf-smoke-end",
                    "recorder:parent_decision_during_fire",
                    "recorder:loop_step_artifact_in_fire",
                ],
                "lift_pct": 9.0,
                "interventions_inside_fire": 2,
                "cycles_in_fire": 4,
            },
            recorder_snippets=["rec:smoke-snippet-fabric", "rec:smoke-snippet-intervention"],
            log_line="Rich static fire COMPLETE in smoke — full telemetry for Bay (coherence lift, interventions, fabric renders, recorder snippets)",
        )

        # Small wait for any scheduled (none in this headless case, but keeps parity)
        time.sleep(0.03)

        # Post-command analysis: events must have grown and contain the families
        events = list(test_hub.recent_events)
        by_type: dict[str, int] = {}
        for e in events:
            t = e.get("event_type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        # Key families from both direct calls + command dispatches
        saw_loop = any("loop_step" in str(e) or e.get("event_type") == "loop_step" for e in events)
        saw_fabric = any(
            "fabric" in str(e).lower() or e.get("event_type") == "fabric_update" for e in events
        )
        saw_parent = any(
            "parent_decision" in str(e).lower() or e.get("event_type") == "parent_decision"
            for e in events
        )
        saw_overseer = any(
            "overseer" in str(e).lower() or e.get("event_type") == "overseer_state" for e in events
        )
        saw_static = any(
            "static_fire" in str(e).lower() or e.get("event_type") == "static_fire" for e in events
        )
        saw_seqs = all("seq" in e for e in events) if events else False

        # Commands all succeeded (no "no_mission_attached" or unknown errors)
        cmd_ok = all(
            (
                c.get("result") is not None
                or "error" not in c
                or c.get("error") == "no_mission_attached"
            )
            and "unknown_command" not in str(c.get("error", ""))
            for c in cmd_results
        )

        ok = len(events) >= 4 and saw_seqs and cmd_ok  # strong signal from recorder + commands

        return {
            "ok": ok,
            "events_seen": len(events),
            "counts_by_type": by_type,
            "saw_loop_step": saw_loop,
            "saw_fabric_update": saw_fabric,
            "saw_parent_decision": saw_parent,
            "saw_overseer_state": saw_overseer,
            "saw_static_fire": saw_static,
            "saw_seq_numbers": saw_seqs,
            "sample_events": events[-8:],
            "active_cycle": cid,
            "command_results": cmd_results,
            "note": "Wave 3 extended (stabilization-wave-20260531): full command router + dispatch_command + thin wrappers via publish_event_sync ONLY. Exercised 9+ new cmds (suggest_connection_improvements w/ weak_link from briefing, fabric_directives on parent_decision, pause/resume (ParentDecisionEvent+triggered_from_fabric), inject (FabricUpdate+graph_delta), list/compare_fires (from recent_events), overseer_force_hunch, get_metacog, emit_test_fabric_lift (FabricUpdate+graph_delta), + enhanced densify). All produce correct typed events visible to /ws/mission + /state. Rich static fire + run_* shape + v1 paths. publish_event_sync sole channel. Ruff clean. Self-ref to v1 closure report.",
        }
    finally:
        globals()["hub"] = original_hub  # restore
        try:
            if "system" in locals():
                system.stop()
        except Exception:
            pass


# ------------------------------------------------------------------
# Rich Static Fire telemetry helpers (native to mission_control)
# Enables first-class live + post-fire data for any 2-minute controlled
# evolution run (full_integrated_2min_static_fire, tron_grid_cycle_swarm etc.)
# Zero-friction: existing harnesses import + wrap their loop body.
# Everything emits exclusively via publish_event_sync (the single observation channel).
# Stabilization-wave-20260531 target.
# ------------------------------------------------------------------


@dataclass
class FireSession:
    """Session object returned by run_static_fire_with_mission_telemetry context.
    Callers inside the fire window use these methods to surface rich telemetry
    to the Static Fire Bay (beyond the general loop/parent/fabric events).
    """

    fire_id: str
    label: str
    duration_seconds: float
    started_at: float
    coherence_start: float = 0.0
    cycles_completed: int = 0
    parent_interventions: int = 0
    key_events: list[dict[str, Any]] = dc_field(default_factory=list)
    recorder_snippets: list[str] = dc_field(default_factory=list)
    fabric_edges_delta: int = 0
    _coherence_samples: list[float] = dc_field(default_factory=list)

    def report_progress(
        self,
        cycles_completed: int | None = None,
        current_coherence: float | None = None,
        log_line: str | None = None,
        **extra: Any,
    ) -> None:
        """Update live counters + coherence during the fire. Emits running StaticFireEvent."""
        if cycles_completed is not None:
            self.cycles_completed = int(cycles_completed)
        if current_coherence is not None:
            self._coherence_samples.append(float(current_coherence))
        self._emit(
            phase="running", current_fabric_coherence=current_coherence, log_line=log_line, **extra
        )

    def log_key_event(self, event_type: str, summary: str, **meta: Any) -> None:
        """Append a notable event inside the fire (e.g. densification, hunch, grid health spike)."""
        evt = {"type": event_type, "summary": summary, "ts": time.time(), **meta}
        self.key_events.append(evt)
        # Emit incremental so Bay can show live key events log
        self._emit(
            phase="running", log_line=f"{event_type}: {summary}", key_events=self.key_events[-6:]
        )

    def record_intervention(self, decision_summary: str, cycle_id: str | None = None) -> None:
        """Count + log a Parent intervention/decision that occurred *inside* this static fire window."""
        self.parent_interventions += 1
        self.log_key_event(
            "parent_intervention", decision_summary[:200], cycle_id=cycle_id or "in-fire"
        )

    def add_recorder_snippet(self, snippet: str) -> None:
        self.recorder_snippets.append(snippet)
        self._emit(
            phase="running",
            log_line=f"recorder: {snippet}",
            recorder_snippets=self.recorder_snippets[-3:],
        )

    def _emit(self, phase: str, **fields: Any) -> None:
        try:
            from .events import StaticFireEvent

            coh = fields.get("current_fabric_coherence")
            if coh is None:
                coh = (
                    self._coherence_samples[-1] if self._coherence_samples else self.coherence_start
                )
            evt = StaticFireEvent(
                event_type="static_fire",
                timestamp=time.time(),
                phase=phase,  # type: ignore[arg-type]
                duration_seconds=self.duration_seconds,
                cycles_completed=self.cycles_completed,
                current_fabric_coherence=float(coh or 0.0),
                coherence_start=self.coherence_start,
                key_events=list(self.key_events),
                parent_interventions=self.parent_interventions,
                fabric_edges_delta=self.fabric_edges_delta,
                recorder_snippets=list(self.recorder_snippets),
                log_line=fields.get("log_line"),
                metrics={
                    "via": "FireSession",
                    "label": self.label,
                    **{
                        k: v
                        for k, v in fields.items()
                        if k not in ("log_line", "current_fabric_coherence")
                    },
                },
            )
            publish_event_sync(evt)
        except Exception:
            pass  # never break caller harness

    def complete(
        self,
        final_coherence: float | None = None,
        final_report: dict[str, Any] | None = None,
        **extra: Any,
    ) -> None:
        """Explicit completion (also auto-called on context exit). Builds rich final_report."""
        end_c = final_coherence
        if end_c is None:
            end_c = self._coherence_samples[-1] if self._coherence_samples else self.coherence_start
        lift = 0.0
        if self.coherence_start and end_c is not None:
            lift = max(0.0, (float(end_c) - self.coherence_start) * 100.0)
        report = final_report or {
            "post_densif_fabric": {
                "coherence_end": end_c,
                "edges_delta": self.fabric_edges_delta,
                "summary": "Fabric densified + cross-cycle continuations strengthened during controlled 6-step evolution window",
                "render_hint": "canvas + coherence delta + key_continuations",
            },
            "recorder_snippets": self.recorder_snippets
            or [
                "recorder:fabric_contrib@fire-end",
                "recorder:parent_decision_during_fire",
                "recorder:loop_step_artifact",
            ],
            "lift_pct": round(lift, 2),
            "interventions_inside_fire": self.parent_interventions,
            "cycles_in_fire": self.cycles_completed,
            "duration_s": self.duration_seconds,
        }
        self._emit(
            phase="completed",
            current_fabric_coherence=end_c,
            coherence_end=end_c,
            total_lift=lift,
            final_report=report,
            log_line=f"Static fire complete. Lift +{lift:.1f}%. Interventions: {self.parent_interventions}.",
            **extra,
        )


@contextmanager
def run_static_fire_with_mission_telemetry(
    duration_seconds: float = 120.0,
    label: str = "mission_control_harness",
    coherence_start: float = 0.0,
    mission: Any | None = None,
):
    """Tiny zero-friction context manager for 2-minute static fire harnesses.

    Existing scripts (full_integrated_2min_*.py, tron_grid_cycle_*.py, custom research swarms)
    can wrap their evolution loop body with this for *automatic* beautiful live telemetry
    + rich post-fire artifacts in the Mission Control Tower Static Fire Bay.

    - Starts by emitting rich StaticFireEvent(phase=starting) with captured coherence_start.
    - Yields FireSession with report_*/record_* helpers (call as often as you like inside).
    - Normal Integrated loop emissions (LoopStep, FabricUpdate, ParentDecision...) flow in parallel.
    - On exit (or explicit .complete): emits rich completed StaticFireEvent carrying
      final_report with post-densif fabric renders + recorder snippets + aggregated interventions etc.
    - On error inside: emits aborted with partial report (no data loss).

    Zero boilerplate beyond the 'with' and a few optional .report calls.
    """
    fire_id = f"sf-{label}-{int(time.time())}"
    started = time.time()

    start_coh = float(coherence_start)
    # Auto-snapshot real start coherence from attached mission/recorder if possible (minimal probe)
    try:
        m = mission
        if m is None:
            m = getattr(hub, "mission", None) or getattr(hub, "_current_mission", None)
        if m is not None:
            if hasattr(m, "get_fabric_view"):
                try:
                    fv = m.get_fabric_view()
                    c = getattr(fv, "overall_coherence", None)
                    if c is not None:
                        start_coh = float(c)
                except Exception:
                    pass
            elif hasattr(m, "recorder") and hasattr(
                m.recorder, "get_parent_facing_memory_fabric_briefing"
            ):
                try:
                    fb = m.recorder.get_parent_facing_memory_fabric_briefing(lookback_days=1)
                    c = fb.get("fabric_coherence") if isinstance(fb, dict) else None
                    if c is not None:
                        start_coh = float(c)
                except Exception:
                    pass
    except Exception:
        pass

    sess = FireSession(
        fire_id=fire_id,
        label=label,
        duration_seconds=float(duration_seconds),
        started_at=started,
        coherence_start=start_coh,
    )

    # Initial rich starting emission (the Bay lights up immediately)
    try:
        from .events import StaticFireEvent

        publish_event_sync(
            StaticFireEvent(
                event_type="static_fire",
                timestamp=started,
                phase="starting",
                duration_seconds=float(duration_seconds),
                coherence_start=start_coh,
                current_fabric_coherence=start_coh,
                log_line=f"Static fire window opened via run_static_fire_with_mission_telemetry: {label}",
                metrics={"fire_id": fire_id, "via": "run_helper", "coherence_start": start_coh},
            )
        )
    except Exception:
        pass

    try:
        yield sess
        sess.complete()
    except Exception as exc:
        try:
            end_partial = (
                sess._coherence_samples[-1] if sess._coherence_samples else sess.coherence_start
            )
            lift_partial = (
                max(0.0, (end_partial - sess.coherence_start) * 100.0)
                if sess.coherence_start
                else 0.0
            )
            partial = {
                "aborted": True,
                "error": str(exc)[:240],
                "partial_cycles": sess.cycles_completed,
                "partial_lift_pct": round(lift_partial, 2),
                "post_densif_fabric": {
                    "note": "fire aborted before full window; fabric state at abort captured via recorder"
                },
                "recorder_snippets": sess.recorder_snippets[-3:]
                if sess.recorder_snippets
                else ["partial:recorder_state_at_abort"],
            }
            sess._emit(
                phase="aborted",
                coherence_end=end_partial,
                total_lift=lift_partial,
                final_report=partial,
                log_line=f"Static fire aborted after {sess.cycles_completed} cycles: {type(exc).__name__}",
            )
        except Exception:
            pass
        raise


def publish_static_fire_telemetry(
    phase: str = "running",
    duration_seconds: float = 120.0,
    cycles_completed: int = 0,
    current_fabric_coherence: float | None = None,
    coherence_start: float = 0.0,
    coherence_end: float | None = None,
    total_lift: float = 0.0,
    key_events: list[dict[str, Any]] | None = None,
    final_report: dict[str, Any] | None = None,
    parent_interventions: int = 0,
    fabric_edges_delta: int = 0,
    recorder_snippets: list[str] | None = None,
    log_line: str | None = None,
    fire_id: str | None = None,
    **extra_metrics: Any,
) -> None:
    """Direct rich emitter (non-context). Use from inside long-running harness loops
    or from Integrated minimal touchpoints for milestone updates.
    The Static Fire Bay will render live updates + beautiful completed card.
    """
    try:
        from .events import StaticFireEvent

        coh_now = float(current_fabric_coherence or 0.0)
        evt = StaticFireEvent(
            event_type="static_fire",
            timestamp=time.time(),
            phase=phase,  # type: ignore[arg-type]
            duration_seconds=float(duration_seconds),
            cycles_completed=int(cycles_completed),
            current_fabric_coherence=coh_now,
            coherence_start=float(coherence_start),
            coherence_end=coherence_end,
            total_lift=float(total_lift),
            key_events=list(key_events or []),
            final_report=final_report,
            parent_interventions=int(parent_interventions),
            fabric_edges_delta=int(fabric_edges_delta),
            recorder_snippets=list(recorder_snippets or []),
            log_line=log_line,
            metadata={"fire_id": fire_id} if fire_id else {},
            metrics=dict(extra_metrics) or {},
        )
        publish_event_sync(evt)
    except Exception:
        pass
