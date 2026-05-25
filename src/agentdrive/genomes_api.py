"""
savant.genomes_api — Pattern 5: one code path for genome operations.

Pure-logic layer that returns typed data structures. No console.print, no Rich,
no UI. Both the CLI subcommands (`savant genomes ...`) and the chat slash
commands (`/genomes`, `/genome <id>`, etc.) route through here so the *logic*
stays single-sourced while each surface owns its own *presentation*.

If you find yourself reaching for `rich.console.Console` inside this file —
stop. That's the cli/tui layer's job.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentdrive.drive.drive import DriveQuery, get_default_drive
from agentdrive.registry import GenomeRegistry

# ─────────────────────────────────────────────────────────────────────
# Data structures (the contract between logic and presentation)
# ─────────────────────────────────────────────────────────────────────


@dataclass
class GenomeListEntry:
    """One row in a genome listing. Mirrors the fields the existing UIs render."""

    id: str  # stable manifest id (e.g. "security-incident-postmortem")
    genome_id: str  # full id, often "id@version"
    dir_name: str  # on-disk dir under registry root
    version: str
    path: Path | None
    domains: list[str] = field(default_factory=list)
    score: float = 0.0
    num_steps: int = 0
    authors: list[str] = field(default_factory=list)
    is_ultimate: bool = False
    ultimate_version: str | None = None
    confidence_stars: int = 0
    encounter_count: int = 0


@dataclass
class GenomeInfo:
    """Full info for a single genome, surface-agnostic."""

    id: str
    genome_id: str
    version: str
    path: Path | None
    created: str  # iso string (presentation-friendly)
    last_improved: str | None  # iso string or None — closest thing to "last_used"
    authors: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    problem_signatures: list[str] = field(default_factory=list)
    applicability: dict[str, Any] = field(default_factory=dict)
    evaluation_score: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    framework_id: str | None = None
    framework_inputs: list[str] = field(default_factory=list)
    num_steps: int = 0
    step_previews: list[dict[str, str]] = field(default_factory=list)  # [{name, description}]
    reasoning_pattern_keys: list[str] = field(default_factory=list)
    tool_composition_keys: list[str] = field(default_factory=list)


@dataclass
class GenomeMatch:
    """A single result row from a pool/registry search."""

    id: str
    genome_id: str
    version: str
    score: float
    domains: list[str] = field(default_factory=list)
    path: Path | None = None


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────


def list_genomes(registry: GenomeRegistry | None = None) -> list[GenomeListEntry]:
    """Return every registered genome as a list of GenomeListEntry.

    The registry is the source of truth; we lean on its existing
    `list_genome_details()` helper so we don't drift from what the
    TUI browser shows.
    """
    from agentdrive.confidence import get_rating
    from agentdrive.ultimate import get_ultimate_info

    reg = registry or GenomeRegistry()
    out: list[GenomeListEntry] = []
    for d in reg.list_genome_details():
        dir_name = d.get("dir_name", "")
        gid = d.get("genome_id", dir_name)
        path = reg.get_genome_path(dir_name) or (reg.root / dir_name if dir_name else None)
        ult = get_ultimate_info(gid, reg) or get_ultimate_info(dir_name, reg)
        conf = get_rating(gid, reg) or get_rating(dir_name, reg)
        out.append(
            GenomeListEntry(
                id=d.get("id", gid),
                genome_id=gid,
                dir_name=dir_name,
                version=str(d.get("version", "?")),
                path=path,
                domains=list(d.get("domains", []) or []),
                score=float(d.get("score", 0.0) or 0.0),
                num_steps=int(d.get("num_steps", 0) or 0),
                authors=list(d.get("authors", []) or []),
                is_ultimate=ult is not None,
                ultimate_version=ult.ultimate_version if ult is not None else None,
                confidence_stars=conf.stars if conf is not None else 0,
                encounter_count=conf.encounters if conf is not None else 0,
            )
        )
    return out


def get_genome(genome_id: str, registry: GenomeRegistry | None = None) -> GenomeInfo | None:
    """Load full info for one genome. Returns None if not found."""
    reg = registry or GenomeRegistry()
    g = reg.get_genome(genome_id)
    if g is None:
        return None

    m = g.manifest
    path = reg.get_genome_path(g.genome_id)

    # Manifest-derived
    authors = [(a.name or a.id or "unknown") for a in (m.authors or [])]
    domains = list(m.applicability.get("domains", []) if isinstance(m.applicability, dict) else [])
    sigs = list(
        m.applicability.get("problem_signatures", []) if isinstance(m.applicability, dict) else []
    )
    score = (
        float(m.evaluation_score.get("reference_tasks", 0.0))
        if isinstance(m.evaluation_score, dict)
        else 0.0
    )

    # Framework-derived
    fw = g.framework or {}
    steps = fw.get("steps", []) or []
    step_previews = [
        {"name": str(s.get("name", "step")), "description": str(s.get("description", "") or "")}
        for s in steps
    ]

    return GenomeInfo(
        id=m.id,
        genome_id=g.genome_id,
        version=str(m.version),
        path=path,
        created=m.created.isoformat() if hasattr(m.created, "isoformat") else str(m.created),
        last_improved=(
            m.last_improved.isoformat()
            if m.last_improved and hasattr(m.last_improved, "isoformat")
            else None
        ),
        authors=authors,
        domains=domains,
        problem_signatures=sigs,
        applicability=dict(m.applicability or {}),
        evaluation_score=dict(m.evaluation_score or {}),
        score=score,
        framework_id=fw.get("id") if isinstance(fw, dict) else None,
        framework_inputs=list(fw.get("inputs", []) or []) if isinstance(fw, dict) else [],
        num_steps=len(steps),
        step_previews=step_previews,
        reasoning_pattern_keys=list((g.reasoning_patterns or {}).keys()),
        tool_composition_keys=list((g.tool_compositions or {}).keys()),
    )


def search_genomes(
    query: str,
    limit: int = 5,
    min_score: float = 0.0,
    pool: Any = None,
) -> list[GenomeMatch]:
    """Run a pool query and return typed matches.

    Wraps `AgentDrive.query(DriveQuery(...))`. Both the CLI's
    `savant pool query` and the chat `/genome-search` (future) go through here.
    """
    q = DriveQuery(
        task_description=query or "",
        limit=int(limit),
        min_score=float(min_score) or 0.0,
    )
    pool = pool or get_default_drive()
    genomes = pool.query(q)

    out: list[GenomeMatch] = []
    for g in genomes:
        m = g.manifest
        score = (
            m.evaluation_score.get("reference_tasks", 0.0)
            if isinstance(m.evaluation_score, dict)
            else 0.0
        )
        doms = list(m.applicability.get("domains", []) if isinstance(m.applicability, dict) else [])
        p = pool.registry.get_genome_path(g.genome_id) if hasattr(pool, "registry") else None
        out.append(
            GenomeMatch(
                id=m.id,
                genome_id=g.genome_id,
                version=str(m.version),
                score=float(score),
                domains=doms,
                path=p,
            )
        )
    return out


def list_inheritance_manifests(swarm_id: str | None = None) -> list[InheritanceManifest]:
    """Return every inheritance manifest on disk, optionally filtered by swarm.

    Thin wrapper around ``savant.inheritance.list_manifests`` so UI layers
    have a single typed entry point through ``genomes_api``.
    """
    from agentdrive.inheritance import InheritanceManifest, list_manifests  # noqa: F401

    return list_manifests(swarm_id=swarm_id)


__all__ = [
    "GenomeListEntry",
    "GenomeInfo",
    "GenomeMatch",
    "list_genomes",
    "get_genome",
    "search_genomes",
    "list_inheritance_manifests",
]
