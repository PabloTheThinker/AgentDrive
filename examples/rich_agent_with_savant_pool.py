#!/usr/bin/env python3
"""
Rich External Agent using SavantHarness + Pool

This is a concrete, runnable example showing how a rich external agent
can participate in the Savant ecosystem using the harness for DNA.

It demonstrates:
- Pulling relevant DNA from the central pool for a task
- Adapting its behavior (prompt + reasoning) using the harness
- Performing work
- Recording the outcome so the pool learns

Run:
    PYTHONPATH=src python examples/rich_agent_with_savant_pool.py \
        --task "Perform a deep codebase architecture review"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from savant import SavantHarness, get_default_pool

def simulate_rich_work(task: str, enriched_prompt: str, dna_packets: list) -> dict:
    """Simulates a high-quality rich external agent doing real work with pool DNA."""
    print(f"\n[RICH AGENT WORKER] Task: {task}")
    print(f"[RICH AGENT WORKER] Using {len(dna_packets)} genomes from Savant Pool for adaptation...\n")

    # In reality this would call the actual external agent with the enriched context
    # Here we just simulate high-quality output informed by the pool
    result = {
        "status": "success",
        "quality": 0.93,
        "used_genomes": [p["genome_id"] for p in dna_packets],
        "key_insights": [
            "Applied causal analysis pattern from security-postmortem genome",
            "Used architecture map framework steps for structure",
            "Added contradiction detection from savant reasoning primitives",
        ],
        "artifact_summary": f"High-quality structured analysis for: {task}",
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="Perform a thorough security incident postmortem on a production breach")
    args = parser.parse_args()

    print("=== Rich Agent + Savant Harness Demo ===\n")

    harness = SavantHarness(agent_id="rich-agent-demo-042")

    with harness.task_context(args.task):
        dna = harness.pull_relevant_dna()

        base = f"You are a senior systems analyst with deep security and architecture expertise.\nTask: {args.task}"
        enriched = harness.inject_into_context(base, "Be rigorous, use the frameworks from the pool, cite patterns.", use_framework_steps=True)

        print("Enriched prompt sent to worker (excerpt):")
        print(enriched[:450] + "...\n")

        result = simulate_rich_work(args.task, enriched, dna)

        harness.record_outcome(result)

    print("\n[RESULT] Work completed with pool assistance.")
    print(f"[RESULT] Quality: {result['quality']}")
    print(f"[RESULT] This outcome was recorded — the Savant Pool can now evolve from it.\n")

    stats = get_default_pool().get_pool_stats()
    print(f"Pool now has {stats.get('ingest_events', 0)} recorded contributions (including this run).")


if __name__ == "__main__":
    main()