#!/usr/bin/env python3
"""
Mission Control v1.5 — Tron Grid / Full Integrated Cycle Swarm Harness (wave2-demo-harnesses)

Official shippable example for a longer "mission" under the full
IntegratedRealTimeEvolutionSystem (GridEngine + RealTimeEvolutionOverseer with
metacognition + embodied intuition + on-the-fly adaptation).

The Control Tower is the single pane:

- Attaches via the public mission_control_hub.
- All canonical emissions (LoopStep, FabricUpdate with Experience Graph deltas, ParentDecision,
  OverseerState, GridHealth) flow "for free" through the recorder + integrated
  instrumentation once attach_mission_control is called.
- Demonstrates both the thin static fire entrypoint (system.start_static_fire)
  and the rich run_static_fire_with_mission_telemetry helper inside the mission.
- Real research thread formation on the Grid (Tron Grid time-dilation objective
  from the stabilization background runs).
- Parent Conductor adaptation loop using live overseer briefings.
- Every surface the Tower renders (6-step, Fabric Observatory (Experience Graph) canvas + coherence
  deltas, Static Fire Bay, Parent timeline, Grid deck, Overseer console, command
  dispatch for densify/parent_decision/start_static_fire) receives live typed events
  with seq numbers and stabilization-wave-20260531 context.

Exactly like 01_ but for a multi-phase swarm mission rather than a bounded static fire.

Co-located Tower or "run `agentdrive mission` in another terminal" (see README).

Stabilization-wave-20260531. Minimal copyable pattern for real operator
long-running swarms / research orgs. Rich enough to drive replay, Experience Graph deltas (fabric),
commands, and the full live experience layer growth visible in one UI.

Usage (repo root):
    PYTHONPATH=src python examples/mission_control/02_tron_grid_swarm.py

    # 90-second mission (full representative length)
    MISSION_DURATION=90 PYTHONPATH=src python examples/mission_control/02_tron_grid_swarm.py

    # Quick smoke of the integrated surfaces
    MISSION_DURATION=20 PYTHONPATH=src python examples/mission_control/02_tron_grid_swarm.py

Open http://127.0.0.1:8421 (script hosts it) or run with `agentdrive mission` in another terminal
against a process that has performed the attach. The Tower shows the entire mission
unified — no other dashboard required.

See the companion 01_static_fire_harness.py and examples/mission_control/README.md.
"""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from datetime import UTC, datetime

# Public API only (never submodule imports in examples)
from agentdrive import (
    IntegratedRealTimeEvolutionSystem,
    create_mission_control_app,
    mission_control_hub,
    publish_static_fire_telemetry,
    run_static_fire_with_mission_telemetry,
    # RealTimeEvolutionOverseer also public (used internally by the Integrated system we attach)
)

SWARM_ID = "stabilization-wave-20260531"
DEFAULT_DURATION_S = 45
DURATION_S = int(os.environ.get("MISSION_DURATION", DEFAULT_DURATION_S))
LABEL = "tron-grid-full-integrated-mission-02"

MC_HOST = "127.0.0.1"
MC_PORT = 8421


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def run_embedded_tower() -> None:
    """Embedded real Tower (same process = live data from this swarm)."""
    try:
        import uvicorn

        print(f"[{_now()}] Embedded Control Tower live at http://{MC_HOST}:{MC_PORT}")
        print("    This is the unified pane for the entire Tron Grid swarm mission.")
        uvicorn.run(
            create_mission_control_app,
            host=MC_HOST,
            port=MC_PORT,
            factory=True,
            log_level="warning",
            access_log=False,
        )
    except ImportError:
        print("[warn] uvicorn missing — pip install 'agentdrive[web]' for embedded Tower.")
        print("       Use separate `agentdrive mission` terminal against an attached process.")
    except Exception as exc:
        print(f"[warn] Tower thread: {exc}")


def _install_signal_handlers(stop_event: threading.Event) -> None:
    def _h(sig, frame):
        print(f"\n[{_now()}] Signal {sig} — graceful shutdown of swarm mission...")
        stop_event.set()

    signal.signal(signal.SIGINT, _h)
    signal.signal(signal.SIGTERM, _h)


def main() -> int:
    print("=== Mission Control v1.5 — Tron Grid Full Integrated Cycle Swarm ===")
    print(f"Stabilization context: {SWARM_ID}")
    print(
        "Objective: Tron Grid time dilation mathematics + real-time parent-swarm-overseer adaptation"
    )
    print(f"Mission duration: {DURATION_S}s (env MISSION_DURATION=90 for longer run)")
    print(f"Time: {_now()}\n")

    # The full v1.5 engine (exactly as used in background stabilization static fires / Tron runs)
    system = IntegratedRealTimeEvolutionSystem(
        swarm_id=SWARM_ID,
        overseer_poll_interval_s=2.0,  # realistic metacognition cadence
    )

    # THE ATTACH — everything the Tower needs (loop, Experience Graph (fabric), static fire, overseer, grid) now flows here
    system.attach_mission_control(mission_control_hub)
    print(
        f"[{_now()}] mission_control_hub attached. All 6-step + Experience Graph (fabric) + Grid + Overseer events → Tower."
    )

    system.start()
    print(
        f"[{_now()}] Full Integrated system started (GridEngine + RealTimeEvolutionOverseer with embodied intuition)."
    )

    stop_event = threading.Event()
    _install_signal_handlers(stop_event)

    tower_thread = threading.Thread(target=run_embedded_tower, daemon=True)
    tower_thread.start()
    time.sleep(1.6)

    print(f"\n[{_now()}] === TRON GRID SWARM MISSION ACTIVE ===")
    print("    Forming specialized research threads on the Grid...")
    print("    Parent Conductor will adapt in real time from Overseer metacognitive briefings.")
    print("    All of it (plus optional rich static fire windows) visible in the Tower.\n")

    events_before = len(mission_control_hub.recent_events)
    start_t = time.time()

    # Form the multi-role research swarm (modeled on the exact stabilization background runs)
    try:
        if system.grid is not None and hasattr(system.grid, "form_autonomous_research_thread"):
            roles = [
                (
                    "Mathematician",
                    "Develop mathematical models for Grid time dilation and cycle-rate acceleration",
                ),
                (
                    "SystemsArchitect",
                    "Design the cycle system architecture for faster subjective time inside the Grid",
                ),
                (
                    "IntuitionResearcher",
                    "Explore embodied intuition + texture resonance for cycle discovery",
                ),
                (
                    "AdaptationMonitor",
                    "Track parent-swarm-overseer loops and surface real-time improvements",
                ),
            ]
            for role, objective in roles:
                if stop_event.is_set():
                    break
                try:
                    tid = system.grid.form_autonomous_research_thread(
                        objective=objective,
                        budget={
                            "token_budget": 420,
                            "time_budget_seconds": max(30, DURATION_S // 2),
                            "max_experiments": 2,
                        },
                        parent_context=f"tron_swarm_role_{role}",
                    )
                    print(f"  + Spawned {role} thread: {tid}")
                    # This path also emits GridHealth + Experience Graph (fabric) updates via the attached wiring
                except Exception as e:
                    print(f"  (role {role} note: {e})")
    except Exception as e:
        print(f"Grid thread formation note (continuing): {e}")

    # Main Parent adaptation + mission loop (the heart of the "full integrated cycle")
    print(
        f"\n[{_now()}] Parent Conductor receiving live metacognitive briefings and making decisions...\n"
    )

    cycle = 0
    fire_window_opened = False
    try:
        while (time.time() - start_t) < DURATION_S and not stop_event.is_set():
            cycle += 1
            time.sleep(3.5 if DURATION_S > 30 else 1.2)

            # === Core Parent-facing surfaces (all emit to Tower) ===
            briefing = system.get_parent_actionable_briefing()
            understanding = (
                system.get_overseer_current_understanding()
                if hasattr(system, "get_overseer_current_understanding")
                else {}
            )

            print(f"[{_now()}] PARENT CYCLE {cycle}")
            print(f"  Overseer understanding (texture): {str(understanding)[:110]}...")
            print(
                f"  Adaptation effectiveness: {briefing.get('briefing', {}).get('adaptation_effectiveness', 0):.3f}"
            )
            print(f"  Plateau: {briefing.get('briefing', {}).get('plateau_detected', False)}")

            # Real Parent decision (exercises record_parent_decision + Experience Graph (fabric) + loop step paths)
            cid = briefing.get("active_evolution_cycle_id") or f"tron-cycle-{cycle}"
            decision = {
                "action": "adapt_tron_cycle_guidance",
                "note": "Inject sharper time-dilation assumptions based on overseer texture",
                "mission": LABEL,
                "cycle": cycle,
            }
            system.record_parent_decision(
                cid, decision, actions_taken=["briefing_ingest", "overseer_recommendation"]
            )

            # Occasionally surface an Experience Graph densification steer (exercises trigger path via command surface too)
            if cycle % 3 == 0:
                try:
                    system.trigger_graph_densification(cid)
                    print(
                        "  → triggered graph densification (Experience Graph delta will appear in Tower)"
                    )
                except Exception:
                    pass

            # === Inside the longer mission, demonstrate rich static fire surfaces ===
            # (a) Thin entrypoint (what MC command "start_static_fire" calls)
            if not fire_window_opened and cycle >= 2 and DURATION_S > 15:
                print(
                    "  → Opening short rich static fire sub-window via thin entrypoint (Tower Static Fire Bay lights up)"
                )
                try:
                    system.start_static_fire(duration_seconds=12.0, label=f"{LABEL}-subfire-thin")
                except Exception as e:
                    print(f"     (thin entrypoint note: {e})")
                fire_window_opened = True

            # (b) Or the full zero-friction helper for a beautiful completed card (used here for a mid-mission burst)
            if cycle == 4 and DURATION_S > 25:
                print(
                    "  → Mid-mission rich static fire via run_static_fire_with_mission_telemetry (full final_report)"
                )
                try:
                    with run_static_fire_with_mission_telemetry(
                        duration_seconds=8.0,
                        label=f"{LABEL}-mid-burst",
                        coherence_start=0.87,
                        mission=system,
                    ) as sess:
                        sess.report_progress(
                            cycles_completed=2,
                            current_coherence=0.895,
                            log_line="mid-mission burst: 2 cycles, densify +1 intervention",
                        )
                        sess.record_intervention(
                            "Parent injected adversarial time-dilation challenge inside burst", cid
                        )
                        sess.log_key_event(
                            "texture_resonance",
                            "overseer reported strong embodied signal on cycle math",
                        )
                        time.sleep(1.5)
                except Exception as e:
                    print(f"     (run_* burst note: {e})")

            # Direct publish example (what internal durable/daily paths also do)
            if cycle % 5 == 0:
                publish_static_fire_telemetry(
                    phase="running",
                    duration_seconds=20,
                    cycles_completed=cycle,
                    current_fabric_coherence=0.89 + (cycle % 5) * 0.003,
                    coherence_start=0.87,
                    log_line=f"Tron swarm telemetry publish (cycle {cycle})",
                    parent_interventions=1,
                    fabric_edges_delta=2,
                )

            state = (
                system.get_full_system_state() if hasattr(system, "get_full_system_state") else {}
            )
            grid_h = state.get("grid_health", {}) if isinstance(state, dict) else {}
            print(
                f"  Grid: active_research={grid_h.get('active_research_threads', 0)}, resilience_lift={grid_h.get('resilience_lift_total', 0):.3f}"
            )

    except KeyboardInterrupt:
        print("\nOperator interrupt — ending mission early.")
    finally:
        elapsed = time.time() - start_t
        print(
            f"\n[{_now()}] === TRON GRID SWARM MISSION COMPLETE ({elapsed:.1f}s, {cycle} parent cycles) ==="
        )

        try:
            system.stop()
        except Exception:
            pass

        # Verification summary — exactly what an operator sees in the Tower replay / event log
        events_after = len(mission_control_hub.recent_events)
        delta = events_after - events_before

        by_type: dict[str, int] = {}
        for e in mission_control_hub.recent_events[-delta:]:
            t = e.get("event_type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        print(f"Total new events emitted to Mission Control hub: +{delta}")
        print(f"Surface coverage (Tower filters + replay will contain all of these): {by_type}")
        if mission_control_hub.recent_events:
            print(
                f"Replay seq integrity: {mission_control_hub.recent_events[0]['seq']} → {mission_control_hub.recent_events[-1]['seq']}"
            )

        print(
            f"\n[{_now()}] All v1.5 surfaces exercised under one attached hub (Experience Graph deltas (fabric), loop steps,"
        )
        print(
            "    rich static fire via both thin + run_* helpers, parent adaptation, grid threads, overseer)."
        )
        print(
            "    The live Control Tower (embedded or via `agentdrive mission` in another terminal) is the"
        )
        print(
            "    single pane for the entire mission. Artifacts + adaptation traces remain in the experience layer."
        )
        print(
            "\n    Re-run with MISSION_DURATION=120 for a full-length Tron Grid research org evolution."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
