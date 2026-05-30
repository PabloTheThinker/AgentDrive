"""Knowledge Graph layer for AgentDrive.

Inspired by GBrain's self-wiring typed graph (zero-LLM edge extraction on ingest).

Provides:
- Pure link/entity extraction from genome manifests, frameworks, and markdown content.
- Typed edges (authored_by, depends_on, executes, references, etc.).
- Pluggable for future page-level extraction in the drive.

This complements AgentDrive's existing strong provenance (GenomeManifest, DNA lineages)
with a richer, queryable relationship graph.
"""

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
]
