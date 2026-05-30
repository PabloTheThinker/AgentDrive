"""
Typed link / entity extraction for AgentDrive.

Modeled after GBrain's link-extraction (pure functions, zero LLM for graph wiring).

Goals:
- Extract entities (people, companies, genomes, agents, deals, etc.) from text/genomes.
- Emit typed edges with provenance.
- Cheap enough to run on every ingest.
- Complements (does not replace) the existing Genome manifest provenance and DNA lineages.

Initial edge types (will expand):
- authored_by, contributed_to
- depends_on (genome dependencies)
- executes (agent ran this genome)
- references (citation-style)
- related_to (weaker)

This is the foundation for future multi-hop graph queries and richer synthesis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from agentdrive.genome.models import Genome

# Simple entity patterns (start conservative; expand with schema packs later)
# Matches [[type/slug]] or [[type/slug|Display]] style + markdown links
ENTITY_REF_RE = re.compile(
    r"\[\[([a-z0-9_-]+/[^|\]#]+?)(?:#[^|\]]*?)?(?:\|([^]]+?))?\]\]|\[([^\]]+)\]\(([^)]+?)\)",
    re.IGNORECASE,
)

# Known top-level dirs for now (will become schema-driven)
KNOWN_DIRS = {
    "people",
    "companies",
    "genomes",
    "agents",
    "deals",
    "meetings",
    "projects",
    "concepts",
    "sources",
    "security",
    "architecture",
}


@dataclass(frozen=True)
class EntityRef:
    name: str
    slug: str
    dir: str
    source_id: str | None = None


@dataclass(frozen=True)
class TypedEdge:
    source: str  # slug or genome id
    target: str
    relation: str  # "authored_by", "depends_on", "references", etc.
    confidence: float = 1.0
    provenance: dict[str, Any] | None = None


def _normalize_slug(raw: str) -> str:
    raw = raw.strip().lower().strip("/")
    if raw.endswith(".md"):
        raw = raw[:-3]
    return raw


def extract_entities_and_edges(
    text: str,
    source_slug: str,
    source_type: str = "genome",
) -> tuple[list[EntityRef], list[TypedEdge]]:
    """
    Pure function. Extract entities and typed edges from free text or genome content.

    Returns (entities, edges).
    No DB side effects — caller decides persistence.
    """
    entities: dict[str, EntityRef] = {}
    edges: list[TypedEdge] = []

    for match in ENTITY_REF_RE.finditer(text or ""):
        if match.group(1):  # [[dir/slug|name]] or [[dir/slug]]
            slug = _normalize_slug(match.group(1))
            name = match.group(2) or slug.split("/")[-1]
        elif match.group(3) and match.group(4):  # [name](path)
            name = match.group(3)
            slug = _normalize_slug(match.group(4))
        else:
            continue

        if "/" not in slug:
            continue

        dir_part, _ = slug.split("/", 1)
        if dir_part not in KNOWN_DIRS:
            continue

        entity = EntityRef(name=name, slug=slug, dir=dir_part)
        entities[slug] = entity

        # Simple heuristic relations
        relation = "references"
        if "authored" in text.lower() or "by " in text.lower():
            relation = "authored_by"
        elif "depends" in text.lower() or "requires" in text.lower():
            relation = "depends_on"

        edges.append(
            TypedEdge(
                source=source_slug,
                target=slug,
                relation=relation,
                provenance={"source_type": source_type, "extractor": "link_extraction_v1"},
            )
        )

    return list(entities.values()), edges


def extract_from_genome(genome: Genome) -> tuple[list[EntityRef], list[TypedEdge]]:
    """
    Convenience wrapper for Genome objects.
    Pulls from manifest, framework steps, and any associated markdown.
    """
    parts: list[str] = []

    if genome.manifest:
        parts.append(genome.manifest.id or "")
        if hasattr(genome.manifest, "authors"):
            for a in getattr(genome.manifest, "authors", []):
                parts.append(str(a))

    if genome.framework:
        for step in genome.framework.get("steps", []):
            parts.append(str(step))

    # Add reasoning patterns if present
    if hasattr(genome, "reasoning_patterns"):
        parts.append(str(getattr(genome, "reasoning_patterns", {})))

    text = "\n".join(parts)
    source_slug = (
        f"genomes/{genome.manifest.id}@{genome.manifest.version}" if genome.manifest else "unknown"
    )

    return extract_entities_and_edges(text, source_slug, source_type="genome")
