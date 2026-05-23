"""
Savant Pool + Harness End-to-End Demo

This script demonstrates the core vision:
1. An agent uses the SavantHarness to pull DNA from the central pool.
2. It adapts its work using the pulled knowledge.
3. It records the outcome, which can feed improvements back.
4. The pool grows smarter over time.

Run with:
    PYTHONPATH=src python examples/savant_pool_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make sure we can import from src during early dev
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from savant import (
    SavantHarness,
    get_default_pool,
    Genome,
    GenomeRegistry,
)

def main():
    print("=== Savant Pool + Harness Demo ===\n")

    pool = get_default_pool()
    print(f"Using pool: {pool.name}")
    print(f"Current pool size: {pool.get_pool_stats()['total_genomes']} genomes\n")

    # Simulate a worker agent using the harness
    harness = SavantHarness(agent_id="demo-worker-001")

    task = "Analyze a recent production security incident and produce a high-quality postmortem"

    print(f"Task: {task}\n")

    with harness.task_context(task):
        print("→ Harness pulled relevant DNA from the Savant Pool:")
        dna = harness.pulled_dna
        for packet in dna[:3]:
            print(f"   • {packet['genome_id']} (score={packet.get('score', 0):.2f})")

        # Simulate the agent using the DNA
        base_prompt = f"You are an expert security analyst. Task: {task}"
        enriched_prompt = harness.inject_into_context(base_prompt, "Focus on causal chains and actionable recommendations.")

        print("\n→ Enriched prompt (first 300 chars):")
        print(enriched_prompt[:300] + "...\n")

        # Simulate doing the work
        print("→ Performing work with pool-augmented context...")
        simulated_result = {
            "quality": 0.91,
            "new_patterns_discovered": ["timeline_synthesis_guard", "blameless_causal_tagging"],
            "used_genomes": [p["genome_id"] for p in dna[:2]],
        }

        # Record outcome → this can later drive automatic improvement proposals
        harness.record_outcome(simulated_result)
        print("→ Outcome recorded. The pool can now learn from this run.\n")

    print("Demo complete. The harness allowed the agent to dynamically use and contribute to the shared Savant Pool.")
    print("In a real system, this loop runs continuously across many agents, causing the collective intelligence to compound.")


if __name__ == "__main__":
    main()