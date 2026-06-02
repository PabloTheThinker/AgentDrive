"""Knowledge Graph layer for AgentDrive.

Provides persistent typed edges, graph signals (degree, recency, swarm trust, source_boost from schema page types), temporal freshness scoring, contradiction candidates, high-centrality, and living experience layer helpers. Used for drive.think hybrid fusion, synthesis, calibration loops, and experience layer boosts.
"""

from .graph import (
    GraphEdge,
    GraphPath,
    KnowledgeGraphStore,
    SimpleGraph,
    compute_graph_signals,
    edges_to_drive_events,
    find_contradictions_candidates,
    fuse_for_synthesis,
    fuse_graph_signals_into_scores,
    get_high_centrality_genomes,
    get_knowledge_graph_for_swarm,
    get_living_experience_for_topic,  # experience layer: high-signal entry point for drive.think on major topics (wired via graph signals + page types)
    get_stale_entities,
    load_graph_from_drive_events,
    recency_boost,
    source_boost,
    swarm_trust_tier,
    temporal_freshness_score,
)
from .link_extraction import (
    EntityRef,
    TypedEdge,
    extract_entities_and_edges,
    extract_from_genome,
)

__all__ = [
    "EntityRef",
    "TypedEdge",
    "extract_entities_and_edges",
    "extract_from_genome",
    "SimpleGraph",
    "GraphEdge",
    "GraphPath",
    "KnowledgeGraphStore",
    "edges_to_drive_events",
    "load_graph_from_drive_events",
    "get_knowledge_graph_for_swarm",
    "compute_graph_signals",
    "fuse_graph_signals_into_scores",
    "fuse_for_synthesis",
    "recency_boost",
    "swarm_trust_tier",
    "source_boost",
    "find_contradictions_candidates",
    "get_stale_entities",
    "get_high_centrality_genomes",
    "temporal_freshness_score",
    "get_living_experience_for_topic",
]
