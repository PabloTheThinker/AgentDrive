"""
Agent Drive Evolutionary Engine — scanning, mutation, merging, selection, and improvement of Genomes.

This package includes LineageDNAEvolver + DNACycleResult (native Research → Evaluate → Evolve
cycles with immune/fitness awareness via agentdrive.evolution.lineage_dna).
Implementation is defensive and uses AgentDrive-native sources primarily.
"""

from .lineage_dna import DNACycleResult, LineageDNAEvolver, evolve_genome_with_lineage

__all__ = [
    "LineageDNAEvolver",
    "DNACycleResult",
    "evolve_genome_with_lineage",
]
