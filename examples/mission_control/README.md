# Mission Control v1.5 Demo Harnesses

Official, shippable example harnesses demonstrating the Control Tower (`agentdrive mission` / embedded) as the **primary observability surface** for AgentDrive v1.5.

**Stabilization wave context:** stabilization-wave-20260531

## The Two Harnesses

1. `01_static_fire_harness.py`
   - Configurable 2-minute (default) static fire.
   - Uses the zero-friction public `run_static_fire_with_mission_telemetry` context manager + `FireSession` helpers.
   - Attaches `mission_control_hub` so **all** 6-step loop, Experience Graph (fabric) deltas, parent decisions, overseer signals + rich StaticFire telemetry (starting/running/completed with final_report, post-densif fabric, recorder snippets, interventions, lift) flow live.
   - Co-located lightweight Control Tower server for true real-time view (or pair with separate `agentdrive mission`).

2. `02_tron_grid_swarm.py`
   - Longer "full integrated cycle swarm" mission (Tron Grid time-cycle mathematics objective).
   - Full `IntegratedRealTimeEvolutionSystem` + overseer + grid research threads + parent adaptation loop.
   - Attaches hub; exercises Experience Graph (fabric), loop steps, grid health, parent decisions "for free".
   - Optional rich static fire window via thin entrypoint or the run_* helper.
   - Same Tower attachment story.

## How to Run (live Tower data guaranteed)

```bash
# From repo root. Requires the web extra for uvicorn/FastAPI if not already installed:
#   pip install 'agentdrive[web]'

PYTHONPATH=src python examples/mission_control/01_static_fire_harness.py
# or with custom duration (seconds):
#   MISSION_DURATION=45 PYTHONPATH=src python examples/mission_control/01_static_fire_harness.py

# Open the live Control Tower:
#   http://127.0.0.1:8421
# Watch 6-step pulsing, Fabric Observatory (Experience Graph canvas + deltas + coherence), Static Fire Bay (rich live + final_report), Overseer console, Parent timeline, Grid deck, command surface (all real events from the running harness).
```

In a separate terminal (for long-running / supervisor-attached missions):

```bash
PYTHONPATH=src agentdrive mission
# (connects to the hub of any process that called attach_mission_control on the shared global; for these standalone examples the harness itself hosts the Tower).
# For long-running swarms: run with `agentdrive mission` in another terminal to view the Tower against the attached mission.
```

The scripts are intentionally minimal (copy-paste into real workflows) yet rich enough to exercise every v1.5 surface: Experience Graph deltas (fabric), loop steps, commands, replay (seqs), rich static fire, daily/dream-style emissions via the same paths, etc.

All emissions go exclusively through the hardened `publish_event_sync` + `mission_control_hub` (never bypass). Stabilization-wave-20260531 context + correlation carried on every event.

## Verification

These were modeled directly on:
- `scripts/verify_mission_control_chain.py`
- `tests/mission_control/test_v15_surfaces.py`
- `src/agentdrive/mission_control/server.py` (run_* + FireSession + attach)
- `src/agentdrive/system/integrated_real_time_evolution_system.py` (thin entrypoints + wiring)
- The exact temp harnesses used in stabilization background static fires / Tron swarms.

Run cleanly under PYTHONPATH=src. Produce hundreds of typed events visible in the Tower (live when co-hosted, representative rich demo data otherwise).

See also: CHANGELOG (Wave2 Daily + Dream + Mission Control v1.5), src/agentdrive/mission_control/server.py (SECURITY note for the local command surface), AGENTS.md.

Built for operators. The Tower is now the single pane of glass.

## Wave 3: Rich TUI + Hardened Cross-Process Client (Full System Visibility)

The complete "see the whole system" experience combines:
- Web Control Tower (`agentdrive mission` or co-hosted in harnesses) — professional single-file observability.
- **Native TUI** (`agentdrive tui` or `agentdrive tui --mission ws://127.0.0.1:8421`): rich interactive interface (genome registry, chat, pool, dedicated `mc` view) that mirrors every 6-step / Fabric Observatory (Experience Graph) / Static Fire Bay / Parent timeline / Overseer surface.

The TUI uses the hardened `MissionControlClient` (src/agentdrive/tui/app.py, Wave 3):
- Always-available HTTP /state snapshots + optional true WS (`/ws/mission`) when `websocket-client` is installed.
- Resilient auto-reconnect with seq-aware replay (`replay_events` after last known seq).
- Nonce-correlated `command_ack` for all dispatches (trigger_densification, parent_decision, start_static_fire, replay).
- Graceful degradation + duck-typing so TUI mc view works identically whether wired to in-process hub or remote Tower.
- All events carry stabilization-wave-20260531 context + full seq integrity.

```bash
# Run a harness (hosts Tower + hub)
PYTHONPATH=src python examples/mission_control/01_static_fire_harness.py

# In another terminal: native TUI client against it (Wave 3 hardened path)
PYTHONPATH=src agentdrive tui --mission ws://127.0.0.1:8421
# Inside TUI: navigate to mc section — live renders, reconnect simulation, command acks all visible.
```

The Wave 3 living-experience ingest artifacts (this README's context) + enriched capture JSON document exactly these dual-pane sessions (Tower + TUI client with reconnect/replay/ack traces) as first-class DNA on the drive. Every harness and real swarm now has zero-friction visibility in both surfaces.

This closes the Mission Control observability arc on stabilization-wave-20260531. The mission is one living Experience Graph (fabric), visible everywhere the operator is.
