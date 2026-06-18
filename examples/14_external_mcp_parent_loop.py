#!/usr/bin/env python3
"""
External MCP Parent loop — Grok / Claude / Codex submit multiverse reasoning.

The connected chat model performs branch analysis; AgentDrive persists collapse.

Usage:
    cd "Vektra Industries/Software/AgentDrive"
    PYTHONPATH=src python examples/14_external_mcp_parent_loop.py
"""

from __future__ import annotations

import json
import sys

from agentdrive.system.integrated_real_time_evolution_system import (
    IntegratedRealTimeEvolutionSystem,
)

SWARM = "stabilization-wave-20260531"
TRIGGER = "Interegy: what should Pablo do before launch?"


def main() -> int:
    system = IntegratedRealTimeEvolutionSystem(swarm_id=SWARM)

    # Simulates what Grok/Claude/Codex submit after reasoning in MCP session
    branches = [
        {
            "branch_id": "branch:architect-0",
            "role": "architect",
            "path_summary": "Map ingest→cycle→Gate; intervention is upstream model funding",
            "robustness_score": 0.82,
            "stress_test_passed": True,
        },
        {
            "branch_id": "branch:adversary-1",
            "role": "adversary",
            "path_summary": "VPS-first ships demo floor to paying customers",
            "robustness_score": 0.78,
            "stress_test_passed": False,
            "fatal_flaws": ["Launch before draft quality proof"],
        },
        {
            "branch_id": "branch:operator-2",
            "role": "operator",
            "path_summary": "48h: fund xAI → real brand cycle → judge Gate → then VPS",
            "robustness_score": 0.9,
            "stress_test_passed": True,
        },
    ]

    result = system.run_external_parent_decision(
        TRIGGER,
        branches,
        collapsed_branch_id="branch:operator-2",
        collapse_reason="Scout+Operator convergence on reversible quality proof",
        reasoning_provider="grok-mcp-example",
        program_id="grok-interegy-web@stabilization-wave-20260531",
        fabric_reasoning={
            "fabric_elements_considered": ["interegy-web/HANDOFF.md", "xAI-credits-blocker"],
            "decision_rationale": "Fund model before distribution; Gate draft quality is unproven",
            "expected_lift_signal": 0.12,
            "llm_mode": "external",
        },
    )

    print("=== External Parent Decision ===")
    print(f"  session_id:          {result.get('session_id')}")
    print(f"  llm_mode:            {result.get('llm_mode')}")
    print(f"  reasoning_provider:  {result.get('reasoning_provider')}")
    print(f"  collapsed:           {result.get('collapsed_branch_id')}")
    print(f"  parent_decision:     {result.get('parent_decision_slug')}")
    print()
    print(json.dumps(result, indent=2, default=str)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
