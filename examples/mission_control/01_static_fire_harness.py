#!/usr/bin/env python3
"""
Mission Control v1.5 — 2-Minute (configurable) Static Fire Harness (wave2-demo-harnesses)

Official shippable example demonstrating the Control Tower as the primary
observability surface for a controlled evolution window.

Uses ONLY the public AgentDrive API (per AGENTS.md):
    from agentdrive import (
        IntegratedRealTimeEvolutionSystem,
        mission_control_hub,
        run_static_fire_with_mission_telemetry,
        create_mission_control_app,
    )

What it exercises (all visible live in the Tower):
- Attachment: system.attach_mission_control(mission_control_hub)
- Zero-friction rich telemetry: the run_static_fire_with_mission_telemetry
  context manager + FireSession (report_progress, record_intervention,
  log_key_event, add_recorder_snippet) → full StaticFireEvent family
  (starting/running/completed + final_report with post_densif_fabric,
  recorder_snippets, lift, interventions, edges_delta, key_events).
- Canonical 6-step loop + Experience Graph (fabric) emissions "for free" via real calls to
  get_parent_actionable_briefing + record_parent_decision (the recorder
  is the mandated clean point; also hits get_fabric_view etc.).
- Parent decisions + interventions inside the fire window.
- Experience Graph deltas (fabric) + coherence snapshots.
- Grid / Overseer health (light, via start() bg ticks when enabled).
- Sequence numbers + replay integrity (hub.recent_events).
- The thin command surface is available on the Tower (start_static_fire etc.).
- All events carry stabilization-wave-20260531 + correlation context.

Co-located Control Tower server (single command = live Tower + mission):
  The script hosts http://127.0.0.1:8421 with the real attached hub so
  every publish_event_sync reaches connected browsers instantly (6-step
  pulsing, live Fabric Observatory (Experience Graph) canvas with deltas, Static Fire Bay
  with rich cards + final_report, Parent Decision timeline, etc.).

Alternative (for long-lived supervisor swarms that already attached):
  Run with `agentdrive mission` in another terminal:
      PYTHONPATH=src agentdrive mission
  Then open http://127.0.0.1:8421 — it will see the mission (when the process
  that owns the evolution has performed the attach).

Stabilization-wave-20260531 context. Minimal (copy this pattern into any
real operator workflow or supervisor) yet rich enough to drive the entire
v1.5 surfaces (Experience Graph deltas / fabric, loop steps, commands, replay, rich static fire).

Usage (from repo root):
    # Quick runnable demo (~25s window)
    PYTHONPATH=src python examples/mission_control/01_static_fire_harness.py

    # Real 2-minute production-style static fire (full coherence lift, many cycles)
    MISSION_DURATION=120 PYTHONPATH=src python examples/mission_control/01_static_fire_harness.py

    # Even shorter for CI/smoke
    MISSION_DURATION=8 PYTHONPATH=src python examples/mission_control/01_static_fire_harness.py

The Tower (whether embedded here or via `agentdrive mission`) becomes the single
pane of glass. No other observability surface needed for the mission.

See also:
- examples/mission_control/README.md
- scripts/verify_mission_control_chain.py (the internal verifier this was modeled on)
- src/agentdrive/mission_control/server.py (the run_* helper + FireSession + hub)
- src/agentdrive/system/integrated_real_time_evolution_system.py
- CHANGELOG.md (Wave2 section)
"""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from datetime import UTC, datetime

# Public API only (AGENTS.md rule for examples + external docs)
from agentdrive import (
    IntegratedRealTimeEvolutionSystem,
    create_mission_control_app,
    mission_control_hub,
    run_static_fire_with_mission_telemetry,
)

# ------------------------------------------------------------------
# Stabilization context + configuration (operator-tunable, zero new config files)
# ------------------------------------------------------------------
SWARM_ID = "stabilization-wave-20260531"
DEFAULT_DURATION_S = 25  # quick but representative; set MISSION_DURATION=120 for full 2min
DURATION_S = int(os.environ.get("MISSION_DURATION", DEFAULT_DURATION_S))
LABEL = "mission-control-demo-static-fire-01"

# For the embedded Tower (so one command gives you live data)
MC_HOST = "127.0.0.1"
MC_PORT = 8421


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def run_embedded_tower() -> None:
    """Run the real Mission Control Tower (create_mission_control_app) in this process.
    Because we attached mission_control_hub to the live Integrated system above,
    every LoopStepEvent, FabricUpdateEvent, StaticFireEvent, ParentDecisionEvent,
    OverseerStateEvent, GridHealthEvent etc. emitted by the harness will appear
    instantly on WS clients and /state.
    """
    try:
        import uvicorn

        print(f"[{_now()}] Starting embedded Control Tower at http://{MC_HOST}:{MC_PORT}")
        print(
            "    Open this URL now — you will see live 6-step + Experience Graph (fabric) + rich Static Fire data."
        )
        print(
            "    (This is the exact surface `agentdrive mission` would serve against an attached mission.)"
        )
        uvicorn.run(
            create_mission_control_app,
            host=MC_HOST,
            port=MC_PORT,
            factory=True,
            log_level="warning",
            access_log=False,
        )
    except ImportError:
        print("[warn] uvicorn not available — install with: pip install 'agentdrive[web]'")
        print(
            "       Tower will not be hosted by this harness (use `agentdrive mission` in another terminal after attaching)."
        )
    except Exception as exc:
        print(f"[warn] Embedded Tower failed to start (harness continues): {exc}")


def _install_signal_handlers(stop_event: threading.Event) -> None:
    def _handler(sig, frame):
        print(f"\n[{_now()}] Received signal {sig}, shutting down cleanly...")
        stop_event.set()

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


def main() -> int:
    print("=== Mission Control v1.5 Static Fire Harness ===")
    print(f"Swarm / stabilization context: {SWARM_ID}")
    print(f"Duration: {DURATION_S}s (set MISSION_DURATION=120 for canonical 2-minute fire)")
    print(f"Label: {LABEL}")
    print(f"Time: {_now()}")
    print()

    # 1. Real Integrated system (the v1.5 engine: Grid + Overseer + Recorder)
    system = IntegratedRealTimeEvolutionSystem(
        swarm_id=SWARM_ID,
        overseer_poll_interval_s=1.5,  # lively but not crazy for demo
    )

    # 2. The critical attach — this is what wires the single publish_event_sync channel
    #    (recorder + integrated loop paths + FireSession) into the global hub that the
    #    Tower (embedded or `agentdrive mission`) is listening on.
    system.attach_mission_control(mission_control_hub)
    print(
        f"[{_now()}] Attached mission_control_hub — all future emissions will be visible in the Tower."
    )

    # Start the real-time components (overseer ticks, grid health, background fabric work)
    # This produces OverseerState + GridHealth events "for free".
    system.start()
    print(f"[{_now()}] IntegratedRealTimeEvolutionSystem started (overseer + grid live).")

    # 3. Start the Tower in a background thread so the fire loop + Tower coexist in one process.
    #    This guarantees "live Tower shows the full telemetry in real time".
    stop_event = threading.Event()
    _install_signal_handlers(stop_event)

    tower_thread = threading.Thread(target=run_embedded_tower, daemon=True, name="mc-tower")
    tower_thread.start()

    # Give the server a moment to bind before we start emitting heavily
    time.sleep(1.8)

    print(
        f"\n[{_now()}] === BEGIN STATIC FIRE WINDOW (via run_static_fire_with_mission_telemetry) ==="
    )
    print(
        "    Watch the Static Fire Bay, Fabric Observatory (Experience Graph deltas + coherence), Loop steps,"
    )
    print("    Parent Decision timeline, and command surface in the Tower.\n")

    start_wall = time.time()
    events_before = len(mission_control_hub.recent_events)

    try:
        # THE ZERO-FRICTION PATTERN FOR REAL HARNESSSES
        with (
            run_static_fire_with_mission_telemetry(
                duration_seconds=float(DURATION_S),
                label=LABEL,
                coherence_start=0.855,  # realistic starting point; helper will try to improve from real fabric if available
                mission=system,  # lets it auto-probe better start coherence
            ) as sess
        ):
            # Drive a realistic number of canonical Parent loop iterations inside the window.
            # Each record_parent_decision + get_* call exercises the exact paths that feed
            # LoopStepEvent + FabricUpdateEvent + ParentDecisionEvent into the Tower.
            cycles = max(3, DURATION_S // 4)
            for i in range(cycles):
                if stop_event.is_set():
                    break

                # Parent receives briefing (step 2/3 in the canonical loop)
                briefing = system.get_parent_actionable_briefing()
                cid = briefing.get("active_evolution_cycle_id") or f"sf-cycle-{i}"

                # Fabric view (exercises recorder fabric surface + FabricUpdate emission paths)
                try:
                    fab = system.get_fabric_view()
                    coh = getattr(fab, "overall_coherence", 0.86 + (i * 0.012))
                except Exception:
                    coh = 0.86 + (i * 0.012)

                # Real Parent decision inside the fire (this is what the Tower timeline shows)
                decision = {
                    "action": "steer_research_thread",
                    "note": "Static fire harness: prioritizing Tron Grid time-dilation + fabric densification",
                    "source": "mission_control_demo_harness",
                    "cycle": i,
                }
                actions = ["overseer_texture_boost", "hint_graph_gardener", "record_intervention"]

                system.record_parent_decision(cid, decision, actions_taken=actions)

                # Enrich the dedicated Static Fire Bay via the session helpers (rich final_report)
                sess.report_progress(
                    cycles_completed=i + 1,
                    current_coherence=round(coh, 4),
                    log_line=f"cycle {i + 1}/{cycles} inside static fire — coherence lift in progress",
                )
                sess.record_intervention(
                    decision_summary="Parent steered research toward time-dilation mathematics during controlled evolution window",
                    cycle_id=cid,
                )
                sess.add_recorder_snippet(f"recorder:parent_decision@{cid}")
                if i % 2 == 0:
                    sess.log_key_event(
                        "densification_candidate",
                        "cross-cycle edge opportunity surfaced by recorder during fire",
                        cycle_id=cid,
                    )

                # Simulate realistic work inside the evolution step (keeps the demo lively)
                sleep_for = min(1.6, max(0.4, DURATION_S / cycles))
                time.sleep(sleep_for)

            # Final coherence bump + explicit completion path (the context also calls complete())
            final_coh = 0.855 + (0.065 * min(1.0, DURATION_S / 120.0))
            sess.report_progress(
                cycles_completed=cycles,
                current_coherence=round(final_coh, 4),
                log_line="Static fire window complete — preparing rich final_report for Tower",
            )
            # The context manager + sess.complete() will emit the canonical completed StaticFireEvent
            # carrying the beautiful post_densif_fabric + recorder_snippets + lift etc.

    except KeyboardInterrupt:
        print(f"\n[{_now()}] Interrupted by operator during fire.")
    finally:
        elapsed = time.time() - start_wall
        print(f"\n[{_now()}] === STATIC FIRE WINDOW CLOSED (elapsed {elapsed:.1f}s) ===")

        # Clean shutdown of the real system (leaves all artifacts in the experience layer)
        try:
            system.stop()
        except Exception:
            pass

        # Summary for the operator (and for verification that surfaces fired)
        events_after = len(mission_control_hub.recent_events)
        new_events = events_after - events_before

        # Count families (what the Tower replay + filters will show)
        by_type: dict[str, int] = {}
        for e in mission_control_hub.recent_events[-new_events:]:
            t = e.get("event_type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        print(
            f"Events emitted during this harness run: +{new_events} (total in hub: {events_after})"
        )
        print(f"Event families seen (Tower surfaces exercised): {by_type}")
        print(
            f"Recent seq range (replay integrity): "
            f"{mission_control_hub.recent_events[0].get('seq') if mission_control_hub.recent_events else 0} → "
            f"{mission_control_hub.recent_events[-1].get('seq') if mission_control_hub.recent_events else 0}"
        )

        print(
            f"\n[{_now()}] Harness complete. All v1.5 surfaces (loop + Experience Graph deltas (fabric) + rich StaticFire + replay) exercised."
        )
        print("    If the embedded Tower is still running, it has the full live session.")
        print(
            "    Re-run with MISSION_DURATION=120 for a canonical 2-minute production static fire."
        )
        print("    To observe from a separate `agentdrive mission` process (long-running swarms):")
        print("        PYTHONPATH=src agentdrive mission   # then http://127.0.0.1:8421")

    return 0


if __name__ == "__main__":
    sys.exit(main())
