#!/usr/bin/env python3
"""
AgentDrive full-stack smoke test — exercises core surfaces end-to-end.

Usage:
    cd "Vektra Industries/Software/AgentDrive"
    PYTHONPATH=src python examples/13_agentdrive_full_smoke_test.py
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

SWARM = "stabilization-wave-20260531"
TRIGGER = "Full AgentDrive smoke test: should we ship multiverse cognition as default Parent mode?"


def check(name: str, fn) -> dict[str, Any]:
    t0 = time.time()
    try:
        result = fn()
        ok = True if result is not False else False
        if isinstance(result, dict) and result.get("success") is False:
            ok = False
        return {
            "name": name,
            "ok": ok,
            "elapsed_ms": int((time.time() - t0) * 1000),
            "result": result,
        }
    except Exception as exc:
        return {
            "name": name,
            "ok": False,
            "elapsed_ms": int((time.time() - t0) * 1000),
            "error": str(exc),
        }


def main() -> int:
    results: list[dict[str, Any]] = []

    from agentdrive.operations import run_operation

    results.append(
        check(
            "doctor",
            lambda: run_operation("doctor"),
        )
    )

    results.append(
        check(
            "pool_status",
            lambda: run_operation("pool_status"),
        )
    )

    results.append(
        check(
            "experience_graph_context_pack",
            lambda: run_operation(
                "experience_graph_context_pack",
                swarm_id=SWARM,
                max_tokens=600,
            ),
        )
    )

    results.append(
        check(
            "experience_graph_suggest_reasoning",
            lambda: run_operation("experience_graph_suggest_reasoning", swarm_id=SWARM),
        )
    )

    results.append(
        check(
            "multiverse_list_sessions",
            lambda: run_operation("multiverse_list_sessions", swarm_id=SWARM, limit=5),
        )
    )

    results.append(
        check(
            "multiverse_parent_decision",
            lambda: run_operation(
                "multiverse_parent_decision",
                swarm_id=SWARM,
                trigger=TRIGGER,
                n_branches=5,
                heuristic_only=True,
            ),
        )
    )

    mv = results[-1].get("result") or {}
    session_id = (mv.get("result") or {}).get("session_id")

    if session_id:
        results.append(
            check(
                "multiverse_get_session",
                lambda: run_operation(
                    "multiverse_get_session",
                    swarm_id=SWARM,
                    session_id=session_id,
                ),
            )
        )
        results.append(
            check(
                "multiverse_densify",
                lambda: run_operation(
                    "multiverse_densify",
                    swarm_id=SWARM,
                    session_id=session_id,
                ),
            )
        )

    from agentdrive.system.integrated_real_time_evolution_system import (
        IntegratedRealTimeEvolutionSystem,
    )

    def briefing():
        system = IntegratedRealTimeEvolutionSystem(swarm_id=SWARM)
        b = system.get_parent_actionable_briefing()
        return {
            "has_fabric_context_pack": "fabric_context_pack" in b,
            "has_multiverse_context": "multiverse_context" in b,
            "fabric_coherence": b.get("fabric_coherence"),
            "multiverse_recent": (b.get("multiverse_context") or {}).get("session_count_recent"),
            "cycle_id": b.get("active_evolution_cycle_id"),
        }

    results.append(check("parent_actionable_briefing", briefing))

    def tower_snapshot():
        from agentdrive.mission_control.server import hub

        system = IntegratedRealTimeEvolutionSystem(swarm_id=SWARM)
        hub._current_mission = system
        return hub.derive_multiverse_snapshot()

    results.append(check("mission_control_multiverse_snapshot", tower_snapshot))

    results.append(
        check(
            "think",
            lambda: run_operation(
                "think",
                question="What is multiverse cognition in AgentDrive?",
                prefer_experience_layer=True,
            ),
        )
    )

    passed = sum(1 for r in results if r.get("ok"))
    total = len(results)

    print("=" * 60)
    print("AGENTDRIVE FULL SMOKE TEST")
    print("=" * 60)
    for r in results:
        status = "PASS" if r.get("ok") else "FAIL"
        line = f"[{status}] {r['name']} ({r.get('elapsed_ms', 0)}ms)"
        if not r.get("ok"):
            line += f" — {r.get('error') or (r.get('result') or {}).get('error', '')}"
        print(line)
    print("-" * 60)
    print(f"Result: {passed}/{total} passed")
    print()

    # Highlight multiverse run
    mv_result = next((r for r in results if r["name"] == "multiverse_parent_decision"), None)
    if mv_result and mv_result.get("ok"):
        payload = (mv_result.get("result") or {}).get("result") or {}
        print("Multiverse collapse:")
        print(f"  session_id:    {payload.get('session_id')}")
        print(f"  llm_mode:      {payload.get('llm_mode')}")
        print(f"  collapsed:     {payload.get('collapsed_branch_id')}")
        print(f"  policy:        {payload.get('collapse_policy')}")
        print(f"  invariants:    {payload.get('invariant_count')}")
        session = payload.get("session") or {}
        for b in (session.get("branches") or [])[:5]:
            print(f"  branch {b.get('role')}: {str(b.get('path_summary', ''))[:70]}…")

    print()
    print(
        json.dumps({"passed": passed, "total": total, "results": results}, indent=2, default=str)[
            :8000
        ]
    )

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
