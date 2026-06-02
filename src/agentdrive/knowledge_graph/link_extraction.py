"""
Typed link / entity extraction for AgentDrive.

Pure functions for extracting entities and typed relationships from genome
content and free text. Zero-LLM heuristics for wiring the knowledge graph
on every ingest and during densification passes.

Capabilities:
- Extract entities (people, companies, genomes, agents, deals, observations,
  swarms, etc.) from text and manifests using [[dir/slug]] and markdown links.
- Emit typed edges with provenance: authored_by, dispatched_by, implements_spec,
  executes, depends_on, implements, references, cross_swarm_references,
  coordinates_with, builds_on, closes_gap, simulates_workflow, temporal_predecessor,
  related_to, mentions, indexes.
- Rich extraction from Genome manifests (applicability, keywords, domains,
  swarms, dependencies, framework charters, reasoning patterns, evaluations).
- Supports cross-swarm coordination patterns, workflow simulations,
  temporal/version evolution relationships, and gap closure signals.
- Cheap and deterministic — suitable for every drive ingest and batch passes.

This complements (does not replace) Genome manifest provenance and DNA lineages.
It is the foundation for multi-hop graph queries and richer synthesis.
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
    "knowledge",  # for the typed graph edges / nodes themselves
    "synthesis",
    "dreams",
    "notes",
    "observations",  # fused experience + dream observations (high-signal for experience layer boosts)
    "milestones",
    "coordination",
    "primitives",
    "fabric",
    "phase-artifacts",
    "usability",
    "swarms",  # cross-swarm refs
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

        # Improved heuristic relations (keyword proximity + context aware, still zero-LLM)
        # Cross-swarm, temporal, gap-closure, and workflow simulation signals for rich KG wiring.
        text_lower = (text or "").lower()
        relation = "references"
        conf = 0.7

        # Priority 1: Cross-swarm coordination patterns
        cross_swarm_markers = [
            "cross-swarm",
            "swarm coordination",
            "multi-swarm",
            "family consolidation",
            "central drive",
            "experience layer",
            "living-experience",
        ]
        if any(m in text_lower for m in cross_swarm_markers):
            if any(
                k in text_lower
                for k in ("coordinates with", "coordinates_with", "parallel with", "collaborates")
            ):
                relation = "coordinates_with"
                conf = 0.88
            elif any(
                k in text_lower
                for k in ("cross-swarm-knowledge-fabric", "knowledge fabric", "graph fabric")
            ):
                relation = "builds_on"
                conf = 0.91
            else:
                relation = "cross_swarm_references"
                conf = 0.82

        # Priority 2: simulates_workflow (workflow simulation and verification genomes)
        if any(
            k in text_lower
            for k in (
                "simulates_workflow",
                "simulates the workflow",
                "workflow simulation",
                "daily-workflow-simulation",
                "usability-simulator",
                "workflow-verification-observation",
                "simulation completion",
                "verifies workflow",
            )
        ):
            relation = "simulates_workflow"
            conf = 0.93

        # Priority 3: closes_gap / gap closure (synthesis gaps, densification, experience layer)
        # High-confidence bridge edges for graph connectivity and gap resolution.
        if any(
            k in text_lower
            for k in (
                "closes_gap",
                "closes gap",
                "gap closer",
                "resolves gap",
                "fills the gap",
                "addresses gap",
                "gap analysis",
                "from synthesis gap",
                "smart-gap",
                "densif",
                "densification pass",
                "cellular map",
                "engine abstraction",
                "experience layer imperfection",
                "graph sparse",
                "isolated cluster",
                "graph connectivity low",
                "densification gap",
                "fused experience gap",
            )
        ):
            relation = "closes_gap"
            conf = 0.97  # higher confidence on direct gap closures

        # Priority 4: builds_on + temporal (version evolution, consolidation, predecessors)
        if any(
            k in text_lower
            for k in (
                "builds_on",
                "builds on",
                "builds upon",
                "improves upon",
                "extends the",
                "based on prior",
                "evolves from",
                "successor to",
                "follows ",
                "after the ",
                "master consolidation",
            )
        ):
            relation = "builds_on"
            conf = 0.91
        elif any(
            k in text_lower
            for k in (
                "temporal",
                "precedes",
                "predecessor",
                "version evolution",
                "supersedes",
                "last_improved after",
            )
        ):
            relation = (
                "temporal_predecessor"
                if "predecessor" in text_lower or "precedes" in text_lower
                else "builds_on"
            )
            conf = 0.85

        # Priority 5: explicit references / citations (stronger for [[ ]] and docs)
        if relation == "references" and any(
            k in text_lower
            for k in ("references", "cites", "see ", "cf. ", "documented in", "per ", "from the ")
        ):
            conf = max(conf, 0.82)

        # Explicit role-swarm and dispatch signals (preserve + integrate)
        if any(
            k in text_lower
            for k in (
                "dispatched by",
                "dispatched_by",
                "submitted via supervisor",
                "minions dispatcher",
            )
        ):
            relation = "dispatched_by"
            conf = 0.95
        elif any(
            k in text_lower
            for k in ("implements spec", "implements_spec", "spec compliance", "genome-ready spec")
        ):
            relation = "implements_spec"
            conf = 0.93
        elif any(
            k in text_lower for k in ("executes", "executed via", "runs via DurableJobSupervisor")
        ):
            relation = "executes"
            conf = 0.9
        elif any(k in text_lower for k in ("authored by", "written by", "by [[", "author:")):
            relation = "authored_by"
            conf = 0.85
        elif any(
            k in text_lower
            for k in ("depends on", "requires", "built on", "uses [[", "extends [[", "fork of")
        ):
            relation = "depends_on"
            conf = 0.9
        elif any(k in text_lower for k in ("implements", "provides", "executes", "runs")):
            relation = "implements"
            conf = 0.8
        elif any(k in text_lower for k in ("related to", "see also", "cf.", "similar")):
            relation = "related_to"
            conf = 0.65
        elif "mentions" in text_lower or "notes/" in slug or "concepts/" in slug:
            relation = "mentions"
            conf = 0.6
        elif "knowledge/" in slug or source_type == "knowledge" or "fabric/" in slug:
            relation = "indexes"
            conf = 0.78

        # Fallback boost for genome<->genome or usability<->graph links (densification target)
        if (
            "genomes/" in slug
            and source_type == "genome"
            and relation in ("references", "related_to")
        ):
            conf = max(conf, 0.75)

        edges.append(
            TypedEdge(
                source=source_slug,
                target=slug,
                relation=relation,
                confidence=conf,
                provenance={
                    "source_type": source_type,
                    "extractor": "link_extraction_v3",
                    "heuristic": relation,
                },
            )
        )

    return list(entities.values()), edges


def extract_from_genome(
    genome: Genome, *, extra_text: str = ""
) -> tuple[list[EntityRef], list[TypedEdge]]:
    """
    Convenience wrapper for Genome objects.
    Pulls from manifest, framework steps, reasoning, provenance, evaluations,
    plus optional caller-supplied extra_text (e.g. README.md content at ingest time).
    This produces richer typed edges for the knowledge graph.
    """
    parts: list[str] = []

    if genome.manifest:
        parts.append(genome.manifest.id or "")
        parts.append(genome.manifest.version or "")
        if hasattr(genome.manifest, "authors"):
            for a in getattr(genome.manifest, "authors", []):
                parts.append(str(a))
        if hasattr(genome.manifest, "applicability"):
            app = getattr(genome.manifest, "applicability", {})
            parts.append(str(app))
            # Explicit keywords/domains/swarms for cross-swarm + temporal heuristics
            for k in ("domains", "keywords", "swarms", "problem_signatures"):
                if k in app:
                    parts.append(" ".join(str(x) for x in (app.get(k) or [])))
        if hasattr(genome.manifest, "dependencies"):
            deps = getattr(genome.manifest, "dependencies", {})
            parts.append(str(deps))
            if "genomes" in deps:
                parts.append(" ".join(str(x) for x in (deps.get("genomes") or [])))
        if hasattr(genome.manifest, "evaluation_score"):
            parts.append(str(getattr(genome.manifest, "evaluation_score", {})))

    if genome.framework:
        for step in genome.framework.get("steps", []):
            parts.append(str(step))
        if "title" in genome.framework:
            parts.append(str(genome.framework.get("title", "")))
        if "charter_executed" in genome.framework:
            parts.append(str(genome.framework.get("charter_executed", "")))

    # Richer content for graph wiring (simulation, verification, and densification fields)
    if hasattr(genome, "reasoning_patterns"):
        parts.append(str(getattr(genome, "reasoning_patterns", {})))
    if hasattr(genome, "evaluations"):
        parts.append(str(getattr(genome, "evaluations", {})))
    if hasattr(genome, "provenance"):
        parts.append(str(getattr(genome, "provenance", {})))
    if hasattr(genome, "tool_compositions"):
        parts.append(str(getattr(genome, "tool_compositions", {})))
    # Additional common attrs on real genomes
    for extra_attr in ("framework", "reasoning", "notes", "content"):
        if hasattr(genome, extra_attr):
            try:
                parts.append(str(getattr(genome, extra_attr, {})))
            except Exception:
                pass

    if extra_text:
        parts.append(extra_text)

    text = "\n".join(parts)
    source_slug = (
        f"genomes/{genome.manifest.id}@{genome.manifest.version}" if genome.manifest else "unknown"
    )

    edges_out = extract_entities_and_edges(text, source_slug, source_type="genome")
    # Also emit a self-referential "authored" edge if authors present (strong signal)
    if genome.manifest and getattr(genome.manifest, "authors", None):
        for author in genome.manifest.authors:
            aid = getattr(author, "id", None) or getattr(author, "name", None)
            if aid:
                edges_out[1].append(
                    TypedEdge(
                        source=source_slug,
                        target=f"people/{str(aid).lower().replace(' ', '_')}",
                        relation="authored_by",
                        confidence=0.95,
                        provenance={
                            "source_type": "genome",
                            "extractor": "link_extraction_v3",
                            "field": "manifest.authors",
                        },
                    )
                )
    return edges_out[0], edges_out[1]
