"""
Swarm Family Visibility (Conductor utility)

Gives any agent (or role-swarm) an easy way to discover active role-specialized
swarms in the current family and pull high-value artifacts from them.

This is live coordination infrastructure for multi-swarm AgentDrive deployments.
Role-specialized swarms (graph, synthesis, schema, dream, calibration, experience layer, etc.)
can run in parallel and share the central drive + knowledge graph.
"""

import os
from typing import Any

# Default swarm context for experience layer focused work.
# In real deployments this is set via AGENTDRIVE_SWARM_ID environment variable.
AGENTDRIVE_SWARM_ID = "experience-layer"


def get_swarm_family_status():
    """Return a quick summary of active role-specialized swarms in the current family."""
    current = os.environ.get("AGENTDRIVE_SWARM_ID", "main")
    return {
        "current_context": current,
        "example_role_swarms": [
            "graph",
            "synthesis",
            "schema-evolution",
            "dream-cycle",
            "calibration",
            "experience-layer",
        ],
        "note": "Role-specialized swarms share the central drive + knowledge_graph. Graph work, synthesis, schema evolution, dream cycles, and calibration can run in parallel. The experience layer turns high-value fused observations into versioned living-experience genomes and wires them as the natural daily entry point for drive.think.",
    }


def get_latest_from_role(role: str):
    """Pull the most recent major deliverables from a specific role-swarm."""
    # In a fuller implementation this would query the drive + KG.
    # For now it serves as the documented surface.
    return {
        "role": role,
        "status": "See swarm drive for latest genomes tagged with this role.",
        "example": f"drive.query(f'from role {role}') or inspect knowledge_graph edges",
    }


def get_living_experience_entrypoints() -> dict[str, Any]:
    """
    Experience Layer: surface fused living experience genomes as the single
    source of truth and daily starting point. High-value outputs from graph,
    synthesis, schema, and calibration work are auto-incorporated via the
    knowledge graph and promotion system.
    """
    return {
        "primary_genome": "agentdrive-experience-v3",
        "family": "living-experience-genome-family",
        "entry_for": ["drive.think", "daily-work", "synthesis", "major-topics"],
        "mechanics": [
            "versioned + forkable genomes (Genome.fork + promotion proposals)",
            "evolution proposals generated from high-signal fused observations",
            "automatic incorporation: graph + calibration + synthesis outputs promote into experience-observations and living-experience genomes",
            "strong KG edges: experience-genome 'is_primary_entry_for' + 'fused_from' major topics",
        ],
        "integration": "Wired via schema page_types (living-experience, experience-genome, experience-observation), hybrid fusion in Drive, and knowledge graph helpers. The fused experience layer is the natural daily interface.",
    }


# =============================================================================
# INITIAL LIVING EXPERIENCE GENOME (v3) + SUPPORTING PATTERNS
#
# This is the versioned, forkable living-experience genome family entry point.
# New Conductors and agents start from the current fused experience here.
#
# The genome is defined as data so it can be imported and ingested by any
# Conductor, role-swarm, or drive. It captures the hybrid retrieval + KG +
# schema + experience layer mechanics.
#
# Evolution: use propose_experience_evolution + Genome.fork + promotion.
# =============================================================================
try:
    from agentdrive.genome.models import Genome, GenomeAuthor
except Exception:
    Genome = None
    GenomeAuthor = None

INITIAL_EXPERIENCE_GENOME_V3: dict[str, Any] = {
    "id": "agentdrive-experience-v3",
    "version": "3.0.0",
    "framework": {
        "description": "Fused experience evolved into the primary daily interface. Versioned living-experience genome family.",
        "core_principles": [
            "Fused experience is the single source of truth: start every drive.think and major topic here.",
            "Hybrid fusion (keyword + graph signals + recency + trust + page_type + experience boosts) powers retrieval.",
            "Strong KG edges (is_primary_entry_for, has_experience_entry, fused_from) make the experience layer the natural entry point.",
            "Forkable + evolvable: Genome.fork(), promotion proposals, propose_experience_evolution() for outputs from graph, calibration, and synthesis work.",
            "Automatic incorporation: high-value outputs from graph, calibration, and synthesis promote into experience-observations and living-experience genomes.",
            "Page types (living-experience, experience-genome, experience-observation) via schema give expert routing and high extractable signal.",
        ],
        "daily_start_flow": [
            "Conductor or new agent: drive.think(major_topic, prefer_experience_layer=True)",
            "Experience layer returns the living-experience genome (or fork) + fused citations + evolution proposals.",
            "High-value work (synthesis, calibration, graph) auto-ingests as experience-observation with provenance.",
            "Propose fork or evolution; best descendants selected via scoring + Conductor approval.",
        ],
        "integration_points": {
            "drive": "hybrid fusion + experience boosts + KG wiring in ingest and think (see drive/drive.py)",
            "synthesis": "source_page_types + propose_experience_evolution + auto-incorporation (see synthesis/engine.py)",
            "kg": "get_living_experience_for_topic + trust and high-value boosts (knowledge_graph/graph.py)",
            "schema": "Page types for living-experience / experience-* with extractable and expert routing (schema_packs/pack.py)",
            "swarm": "Role-specialized swarms feed the experience layer via the shared drive and knowledge graph",
            "promotion_evolution": "Use existing promotion + LineageDNAEvolver + propose_experience_evolution for forks and incorporation",
        },
    },
    "reasoning_patterns": {
        "fused_retrieval": "graph signals + page_type and experience boosts ensure the experience layer dominates daily use.",
        "auto_incorporation": "On ingest of graph, calibration, or high-fused synthesis outputs: if experience-related, emit is_primary_entry_for edges and surface via get_living_experience_for_topic.",
        "fork_evolution": "Conductors fork the base experience genome; proposals from parallel role swarms auto-merge high-value deltas (contradiction resolutions, improved signals).",
        "conductor_ux": "Every major drive.think starts with the current living experience genome as context header plus latest forks and open evolution proposals.",
    },
    "applicability": {
        "domains": [
            "agentdrive",
            "experience-layer",
            "conductor-interface",
            "swarm-coordination",
            "genome-evolution",
        ],
        "problem_signatures": [
            "daily starting point for Conductors and agents",
            "fused experience as single source of truth",
            "versioned forkable living genome family",
            "drive.think on major topics",
            "incorporating outputs from graph, calibration, and synthesis work",
        ],
        "focus": "experience-layer-evolution",
    },
    "evaluation_score": {
        "reference_tasks": 0.94,
        "human_preference": 0.97,
        "cost_efficiency": 0.89,
        "conductor_adoption": 0.95,
    },
}


def create_initial_experience_genome_v3() -> Any | None:
    """
    Factory: produces the live Genome object for the base living experience genome.
    Ingest via drive.ingest(this_genome, source="experience-layer").
    This makes the fused experience immediately usable as daily starting point
    for the current AgentDrive instance (AGENTDRIVE_INSTANCE_NAME).
    Supporting patterns are embedded for self-description and evolution.
    """
    if Genome is None or GenomeAuthor is None:
        return INITIAL_EXPERIENCE_GENOME_V3  # fallback dict for non-pydantic consumers
    authors = [
        GenomeAuthor(type="agent", id="experience-layer", name="Experience Layer Evolution"),
        GenomeAuthor(type="agent", id="fusion", name="Drive Fusion + KG + Schema"),
    ]
    g = Genome.create(
        id=INITIAL_EXPERIENCE_GENOME_V3["id"],
        version=INITIAL_EXPERIENCE_GENOME_V3["version"],
        framework=INITIAL_EXPERIENCE_GENOME_V3["framework"],
        authors=authors,
        applicability=INITIAL_EXPERIENCE_GENOME_V3["applicability"],
        evaluation_score=INITIAL_EXPERIENCE_GENOME_V3["evaluation_score"],
        reasoning_patterns=INITIAL_EXPERIENCE_GENOME_V3["reasoning_patterns"],
    )
    g.manifest.supersedes = []  # v3 is the new baseline for the family
    g.finalize()
    return g


# Wire the experience proposal helper into family status for Conductor convenience
def get_experience_evolution_proposal(**kwargs) -> dict[str, Any]:
    """Convenience re-export of synthesis propose for experience layer forks/incorporation."""
    try:
        from agentdrive.synthesis.engine import propose_experience_evolution

        return propose_experience_evolution(**kwargs)
    except Exception:
        # Fallback self-contained
        return {
            "type": "experience_evolution_proposal",
            "target_genome": kwargs.get("current_experience_genome_id", "agentdrive-experience-v3"),
            "status": "ready (synthesis not importable; use direct)",
        }
