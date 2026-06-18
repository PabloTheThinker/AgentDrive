#!/usr/bin/env python3
"""
Multiverse Cognition Loop — runnable smoke against real Experience Graph recorder.

Runs the full multiverse pipeline (spawn → simulate → invariants → stress-test →
collapse) and writes fabric DNA via record_parent_fabric_reasoning.

Usage:
    cd "Vektra Industries/Software/AgentDrive"
    PYTHONPATH=src python examples/12_multiverse_cognition_loop.py \\
        --trigger "How should we ship multiverse cognition MVP?"

Writes observations to:
    ~/.agentdrive/swarms/<swarm_id>/drive/observations/meta-evolution/multiverse/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentdrive.drive.drive import get_swarm_drive_path
from agentdrive.system.integrated_real_time_evolution_system import (
    IntegratedRealTimeEvolutionSystem,
)

SWARM_ID = "stabilization-wave-20260531"


def main() -> int:
    parser = argparse.ArgumentParser(description="Multiverse Cognition smoke loop")
    parser.add_argument(
        "--trigger",
        default="How should we integrate multiverse cognition into AgentDrive?",
        help="Decision question to run through multiverse superposition",
    )
    parser.add_argument("--branches", type=int, default=7, help="Number of parallel branches")
    parser.add_argument("--swarm-id", default=SWARM_ID, help="AgentDrive swarm id")
    parser.add_argument(
        "--program-id",
        default="multiverse-cognition-demo@stabilization-wave-20260531",
        help="AD-Grid program attribution",
    )
    args = parser.parse_args()

    drive_path = get_swarm_drive_path(args.swarm_id)
    integrated = IntegratedRealTimeEvolutionSystem(swarm_id=args.swarm_id)

    print(f"Trigger: {args.trigger}")
    print(f"Swarm:   {args.swarm_id}")
    print(f"Drive:   {drive_path}")
    print()

    result = integrated.run_multiverse_parent_decision(
        args.trigger,
        n_branches=args.branches,
        program_id=args.program_id,
        user_objective_refs=["multiverse-cognition-deep-integration"],
    )
    session = result.get("session") or {}
    session_id = result.get("session_id")

    print("=== Multiverse Session ===")
    print(f"  session_id:          {session_id}")
    print(f"  status:              {result.get('status')}")
    print(f"  branches:            {session.get('branch_count')}")
    print(f"  invariants:          {result.get('invariant_count')}")
    print(f"  collapsed_branch_id: {result.get('collapsed_branch_id')}")
    print(f"  collapse_policy:     {result.get('collapse_policy')}")
    print(f"  parent_decision:     {result.get('parent_decision_slug')}")
    print()

    collapsed_id = result.get("collapsed_branch_id")
    for b in session.get("branches") or []:
        if b.get("branch_id") == collapsed_id:
            print(f"Collapsed path ({b.get('role')}): {b.get('path_summary')}")
            break
    print()

    print("Robust invariants:")
    for inv in session.get("invariants") or []:
        if inv.get("kind") == "robust":
            cov = float(inv.get("branch_coverage", 0))
            print(f"  - [{cov:.0%}] {inv.get('statement')}")
    print()

    out_dir = Path(drive_path) / "observations" / "meta-evolution" / "multiverse"
    print(f"Observations written to: {out_dir}")
    if out_dir.exists():
        recent = sorted(out_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)[-3:]
        for p in recent:
            print(f"  {p.name}")

    summary_path = out_dir / f"{session_id}-summary.json"
    summary_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"Summary: {summary_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
