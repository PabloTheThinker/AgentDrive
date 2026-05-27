"""
Lineage-enhanced features smoke test (see the runnable demos).

Demos of the lineage extensions (immune, evolver, grants, bridge):
    examples/04_quarantine_workflow.py   — Quarantine + LineageImmuneRule end-to-end
    examples/05_lineage_dna_grants.py    — DNADrive, Ancestry, LineageShareGrant,
                                           pull_via_grant, LineageImmuneSystem,
                                           LineageDNAEvolver, Harness DNA methods
    examples/11_high_continuity_bridge_demo.py — GrokPatternLineageBridge full flows

Run the above for concrete usage. They exercise public surfaces used by CLI/TUI/web.

This is a minimal import+smoke of LineageImmuneSystem + LineageDNAEvolver.
See docs/CLEANLINESS_AND_STABILITY_REPORT.md and source for current implementation
status (native, defensive; not full external-Lineage depth).
"""

from agentdrive.dna.lineage_immune import LineageImmuneSystem
from agentdrive.evolution.lineage_dna import LineageDNAEvolver
from agentdrive.genome.models import Genome


def main():
    print("Lineage smoke (see 04_ and 05_ for the real demos)")
    immune = LineageImmuneSystem()
    g = Genome.create(
        id="smoke-genome",
        version="1.0.0",
        framework={"steps": [{"name": "be excellent"}]},
        evaluation_score={"ref": 0.8},
    )
    a = immune.assess_genome(g.model_dump(mode="json"), source_agent="demo")
    print(f"  Immune: {a.threat_level} (conf {a.confidence:.2f})")

    ev = LineageDNAEvolver(g)
    r = ev.run_full_cycle(dry_run=True)
    print(f"  Evolver: delta={r.fitness_delta:.3f}, findings={len(r.research_findings)}")

    print("\nFull lineage story is in examples/04_quarantine_workflow.py and 05_lineage_dna_grants.py")


if __name__ == "__main__":
    main()
