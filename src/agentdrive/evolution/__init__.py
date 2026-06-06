"""
Agent Drive Evolutionary Engine — scanning, mutation, merging, selection, and improvement of Genomes.

This package includes LineageDNAEvolver + DNACycleResult (native Research → Evaluate → Evolve
cycles with immune/fitness awareness via agentdrive.evolution.lineage_dna).
Implementation is defensive and uses AgentDrive-native sources primarily.
"""

from .experience_graph import (
    CONNECTION_STRENGTHENED_BY,
    # Experience Graph v3 Multi-Cycle Memory Fabric relations (Grid-native GraphGardener + daily fusion)
    CROSS_CYCLE_CONTINUATION,
    CYCLE_FABRIC_PARTICIPATION,
    DENSIFIED_FROM_SIBLING_CYCLE,
    DENSIFIED_VIA_GARDENER,
    FABRIC_COHERENCE_CONTRIBUTED,
    FABRIC_LINK,
    GRAPH_COHERENCE_LIFT,
    MULTI_CYCLE_FUSION_EDGE,
    ExperienceGraphRecorder,
    LoopCycle,
    LoopEdge,
    embed_graph_into_artifact,
    get_recorder_for_drive,
    trigger_densification_for_weak_cycles,
)
from .lineage_dna import DNACycleResult, LineageDNAEvolver, evolve_genome_with_lineage
from .real_time_evolution_overseer import (
    EpisodicTrace,
    IntuitionEngine,
    MetaAdaptationSignal,
    RealTimeEvolutionOverseer,
    TextureVector,
)

__all__ = [
    "LineageDNAEvolver",
    "DNACycleResult",
    "evolve_genome_with_lineage",
    "RealTimeEvolutionOverseer",
    "MetaAdaptationSignal",
    "IntuitionEngine",
    "TextureVector",
    "EpisodicTrace",
    # Experience Graph (clean loop ingestion + Obsidian-style connection graphs)
    "ExperienceGraphRecorder",
    "LoopCycle",
    "LoopEdge",
    "get_recorder_for_drive",
    # GraphGardener v2 densifier (Experience Graph connection densification)
    "DENSIFIED_VIA_GARDENER",
    "CONNECTION_STRENGTHENED_BY",
    "GRAPH_COHERENCE_LIFT",
    "trigger_densification_for_weak_cycles",
    # Experience Graph v3 Multi-Cycle Memory Fabric (Grid-native GraphGardener + daily fusion + ResearchThreadLineage)
    "CROSS_CYCLE_CONTINUATION",
    "FABRIC_COHERENCE_CONTRIBUTED",
    "DENSIFIED_FROM_SIBLING_CYCLE",
    "MULTI_CYCLE_FUSION_EDGE",
    "FABRIC_LINK",
    "CYCLE_FABRIC_PARTICIPATION",
    # v2/v3 Renderers + Fusion Operator (mermaid/text + embed for diary/densified cycles + fabric briefings)
    "embed_graph_into_artifact",
]
