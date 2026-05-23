#!/usr/bin/env python3
"""
Savant Swarm DNA Demo — End-to-End Professional Experience

This script demonstrates the complete Savant Swarm Pool vision:

- A parent "orchestrator" spawns two sub-agents.
- Each sub-agent automatically receives its own isolated, persistent Savant Pool (starts empty).
- The children do real work using the SavantHarness (pull DNA, adapt, contribute back).
- High-value patterns flow upward to the parent swarm pool according to policy.
- The user can inspect everything beautifully in the TUI (`savant tui` → `pool`).

This is the "Exo Labs for agent minds" + "Assassin's Creed DNA" experience:
multiple agents + their children grow, learn, and compound intelligence together
while the real user remains in full control.

Run:
    PYTHONPATH=src python3 examples/savant_swarm_dna_demo.py

Then launch the TUI and type `pool` to see the living swarm tree.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Make the package importable during development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from savant import (
    SavantHarness,
    get_swarm_pool_manager,
    get_pool_settings_manager,
    RichAgentAdapter,   # the clean Savant-native rich external agent
)


def simulate_rich_work(harness: SavantHarness, task: str) -> dict:
    """Simulates a high-quality agent doing work while using the Savant Pool."""
    print(f"  [{harness.agent_id}] Starting task: {task}")

    dna = harness.pull_relevant_dna(top_k=3)
    print(f"  [{harness.agent_id}] Pulled {len(dna)} relevant genomes from its private pool")

    # Simulate rich reasoning + tool use, guided by Savant DNA
    time.sleep(0.4)

    # Record a high-quality outcome (this will trigger automatic improvement back to the pool)
    outcome = {
        "status": "success",
        "quality": 0.91,
        "new_patterns_discovered": [f"pattern-{int(time.time()) % 10000}"],
        "used_genomes": [d["genome_id"] for d in dna],
        "trajectory_length": 7,
    }
    harness.record_outcome(outcome)

    print(f"  [{harness.agent_id}] Task complete. Outcome recorded → pool is now smarter.\n")
    return outcome


def main():
    print("=== Savant Swarm DNA Demo ===\n")

    swarm_id = f"demo-swarm-{int(time.time())}"
    print(f"Swarm ID: {swarm_id}\n")

    # Activate the Grok-build-style adapter for this swarm (simulates what the user would tell Grok)
    from savant.adapters.grok_build_adapter import GrokBuildSavantAdapter
    adapter = GrokBuildSavantAdapter()
    adapter.activate_for_current_session(swarm_id=swarm_id)

    print("✓ Savant Pool activated for swarm. Every sub-agent will now get its own private DNA pool.\n")

    # === Parent orchestrator (the "user" or top-level agent) ===
    parent_harness = SavantHarness(agent_id="orchestrator-parent")
    print("Parent orchestrator created (global pool).")

    # === Spawn two sub-agents ===
    # In a real Grok build system this would be `spawn_subagent(...)`.
    # Here we simulate the exact same effect using the harness + manager.

    child1 = SavantHarness(
        agent_id="research-analyst-01",
        swarm_id=swarm_id,
        subagent_id="research-analyst-01",
    )
    child2 = SavantHarness(
        agent_id="security-reviewer-02",
        swarm_id=swarm_id,
        subagent_id="security-reviewer-02",
    )

    print("Spawned two sub-agents. Each now has its own empty persistent Savant Pool.")
    print(f"  Child 1 pool: {child1.pool.name}")
    print(f"  Child 2 pool: {child2.pool.name}\n")

    # === The children do real work ===
    print("=== Children executing tasks (each in their own DNA pool) ===\n")

    simulate_rich_work(child1, "Deep research on novel security patterns")
    simulate_rich_work(child2, "High-quality security incident postmortem")

    # === Parent pulls valuable DNA that bubbled up according to policy ===
    print("=== Parent pulling high-value DNA contributed by children ===\n")
    parent_dna = parent_harness.pull_relevant_dna(top_k=5)
    print(f"Parent now sees {len(parent_dna)} high-value genomes from the swarm (policy-controlled).")

    print("\n=== Demo Complete ===")
    print("The swarm has grown real, private DNA. The parent has benefited.")
    print("\nNow run:")
    print("    PYTHONPATH=src python -m savant tui")
    print("    > pool")
    print("\nYou will see the full swarm tree, each child's private pool, and the DNA that has grown.")
    print("This is the living, user-owned, compounding intelligence system you designed.")


if __name__ == "__main__":
    main()
