"""Review, promote, and prune inherited skills using local evidence."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from agentdrive.genome.models import Genome
from agentdrive.skills.registry import SkillEntry, discover_skills, get_skill
from agentdrive.skills.usage import SkillUsage, get_skill_usage

if TYPE_CHECKING:
    from agentdrive.drive.drive import AgentDrive, DriveIngestResult

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)
_GENOME_ID_RE = re.compile(r"[^a-z0-9._-]+")


@dataclass(frozen=True)
class SkillReview:
    """Curation recommendation for one inherited skill candidate."""

    name: str
    recommendation: str
    reason: str
    path: str
    category: str
    source: str
    matches: int = 0
    runs: int = 0
    successes: int = 0
    failures: int = 0
    success_rate: float = 0.0
    promoted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SkillDNAExport:
    """Result of turning a curated skill into pool DNA."""

    skill_name: str
    genome_id: str
    accepted: bool
    reason: str
    path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SkillAssimilationReport:
    """Result of a gated inherited-skill assimilation pass."""

    reviewed: int
    promoted: list[SkillReview]
    dna_exports: list[SkillDNAExport]
    pruned: list[dict[str, str]]
    watched: list[SkillReview]
    errors: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "reviewed": self.reviewed,
            "promoted": [item.to_dict() for item in self.promoted],
            "dna_exports": [item.to_dict() for item in self.dna_exports],
            "pruned": list(self.pruned),
            "watched": [item.to_dict() for item in self.watched],
            "errors": list(self.errors),
        }


def review_inherited_skills(*, include_promoted: bool = True) -> list[SkillReview]:
    """Review inherited skill candidates and return promote/watch/prune advice."""
    reviews: list[SkillReview] = []
    for entry in discover_skills():
        if entry.category not in ("inherited", "promoted"):
            continue
        if entry.category == "promoted" and not include_promoted:
            continue
        usage = get_skill_usage(entry.name)
        recommendation, reason = _recommend(entry, usage)
        reviews.append(
            SkillReview(
                name=entry.name,
                recommendation=recommendation,
                reason=reason,
                path=str(entry.path),
                category=entry.category,
                source=entry.source,
                matches=usage.matches,
                runs=usage.runs,
                successes=usage.successes,
                failures=usage.failures,
                success_rate=usage.success_rate,
                promoted=entry.category == "promoted",
            )
        )
    return sorted(
        reviews,
        key=lambda item: (
            _recommendation_rank(item.recommendation),
            -item.successes,
            -item.matches,
            item.failures,
            item.name,
        ),
    )


def assimilate_inherited_skills(
    *,
    target_drive: AgentDrive | None = None,
    ingest_dna: bool = True,
    prune: bool = False,
    include_promoted: bool = False,
) -> SkillAssimilationReport:
    """Apply gated curation recommendations to inherited sub-agent skills.

    This is the parent-bench assimilation pass: promote candidates that already
    meet the evidence threshold, optionally ingest promoted skills into DNA, and
    only prune weak candidates when explicitly requested.
    """
    reviews = review_inherited_skills(include_promoted=include_promoted)
    promoted: list[SkillReview] = []
    dna_exports: list[SkillDNAExport] = []
    pruned: list[dict[str, str]] = []
    watched: list[SkillReview] = []
    errors: list[dict[str, str]] = []

    for review in reviews:
        if review.recommendation == "promote" and not review.promoted:
            try:
                promoted_review = promote_inherited_skill(review.name)
                promoted.append(promoted_review)
                if ingest_dna:
                    dna_exports.append(
                        ingest_skill_as_dna(promoted_review.name, target_drive=target_drive)
                    )
            except Exception as exc:
                errors.append({"skill_name": review.name, "action": "promote", "error": str(exc)})
            continue

        if review.recommendation == "promoted":
            if ingest_dna and include_promoted:
                try:
                    dna_exports.append(ingest_skill_as_dna(review.name, target_drive=target_drive))
                except Exception as exc:
                    errors.append({"skill_name": review.name, "action": "dna", "error": str(exc)})
            watched.append(review)
            continue

        if review.recommendation == "prune" and prune:
            try:
                path = prune_inherited_skill(review.name, reason=review.reason)
                pruned.append({"skill_name": review.name, "path": str(path), "reason": review.reason})
            except Exception as exc:
                errors.append({"skill_name": review.name, "action": "prune", "error": str(exc)})
            continue

        watched.append(review)

    return SkillAssimilationReport(
        reviewed=len(reviews),
        promoted=promoted,
        dna_exports=dna_exports,
        pruned=pruned,
        watched=watched,
        errors=errors,
    )


def promote_inherited_skill(name: str) -> SkillReview:
    """Mark an inherited skill as promoted parent bench knowledge."""
    entry = _require_skill(name)
    if entry.category not in ("inherited", "promoted"):
        raise ValueError(f"Skill is not inherited: {name}")
    meta, body = _read_skill_doc(entry.path)
    tags = _normalize_tags(meta.get("tags"))
    if "promoted" not in tags:
        tags.append("promoted")
    if "inherited" not in tags:
        tags.append("inherited")
    meta.update(
        {
            "category": "promoted",
            "role": meta.get("role") or "shared",
            "harness": meta.get("harness") or "agentdrive",
            "tags": tags,
            "promotion": {
                "status": "promoted",
                "source": "agentdrive skills promote",
                "usage": _usage_payload(entry.name),
            },
        }
    )
    _write_skill_doc(entry.path, meta, body)
    promoted = get_skill(entry.name)
    if promoted is None:
        promoted = entry
    usage = get_skill_usage(entry.name)
    recommendation, reason = _recommend(promoted, usage)
    return SkillReview(
        name=promoted.name,
        recommendation=recommendation,
        reason=reason,
        path=str(promoted.path),
        category=promoted.category,
        source=promoted.source,
        matches=usage.matches,
        runs=usage.runs,
        successes=usage.successes,
        failures=usage.failures,
        success_rate=usage.success_rate,
        promoted=True,
    )


def prune_inherited_skill(name: str, *, reason: str = "") -> Path:
    """Disable a weak inherited skill without deleting its file."""
    entry = _require_skill(name)
    if entry.category not in ("inherited", "promoted"):
        raise ValueError(f"Skill is not inherited/promoted: {name}")
    meta, body = _read_skill_doc(entry.path)
    tags = _normalize_tags(meta.get("tags"))
    if "pruned" not in tags:
        tags.append("pruned")
    meta.update(
        {
            "disabled": True,
            "category": "pruned",
            "tags": tags,
            "promotion": {
                "status": "pruned",
                "reason": reason or "pruned by agentdrive skills prune",
                "source": "agentdrive skills prune",
                "usage": _usage_payload(entry.name),
            },
        }
    )
    _write_skill_doc(entry.path, meta, body)
    return entry.path


def skill_to_genome(entry: SkillEntry) -> Genome:
    """Convert a promoted/inherited skill into a durable Genome."""
    if entry.category not in ("inherited", "promoted"):
        raise ValueError(f"Skill is not inherited/promoted: {entry.name}")
    usage = get_skill_usage(entry.name)
    genome_id = _skill_genome_id(entry.name)
    tags = list(entry.tags)
    source_parts = [p for p in entry.source.split(":") if p]
    swarm_id = source_parts[1] if len(source_parts) >= 3 else ""
    subagent_id = source_parts[2] if len(source_parts) >= 3 else ""
    body_steps = _body_steps(entry.body)
    framework = {
        "type": "inherited_skill",
        "skill_name": entry.name,
        "description": entry.description,
        "source": entry.source,
        "body": entry.body,
        "steps": body_steps,
        "usage": _usage_payload(entry.name),
    }
    applicability = {
        "domains": sorted(set(["agent-skills", "inherited-skills", *tags])),
        "problem_signatures": [
            entry.name,
            entry.description,
            entry.when_to_call,
            *tags,
        ],
        "source_skill": entry.name,
        "source_subagent_id": subagent_id,
        "swarm_id": swarm_id,
    }
    evaluation_score = {
        "skill_success_rate": usage.success_rate,
        "skill_successes": float(usage.successes),
        "skill_matches": float(usage.matches),
    }
    reasoning_patterns = {
        "skill_body": entry.body,
        "when_to_call": entry.when_to_call,
        "patterns_recognized": [
            {
                "framework_id": entry.name,
                "intents": [entry.name, *tags],
                "fields": ["skill", "subagent", "inheritance", "promotion"],
            }
        ],
    }
    provenance = {
        "lineage": [
            {
                "parent": entry.source or str(entry.path),
                "relation": "skill-to-dna",
                "timestamp": datetime.now(UTC).isoformat(),
                "notes": f"Promoted inherited skill {entry.name} into AgentDrive DNA",
            }
        ]
    }
    authors: list[dict[str, str]] = [
        {"type": "agent", "id": "agentdrive-skills", "name": "AgentDrive skills"}
    ]
    if subagent_id:
        authors.append({"type": "agent", "id": f"sub:{subagent_id}", "name": subagent_id})
    return Genome.create(
        id=genome_id,
        version="1.0.0",
        framework=framework,
        authors=authors,
        applicability=applicability,
        dependencies={"genomes": [], "agent_capabilities": ["skill-reuse", "inheritance"]},
        evaluation_score=evaluation_score,
        reasoning_patterns=reasoning_patterns,
        provenance=provenance,
    )


def ingest_skill_as_dna(
    name: str,
    *,
    target_drive: AgentDrive | None = None,
) -> SkillDNAExport:
    """Ingest a promoted/inherited skill into the AgentDrive DNA pool."""
    entry = _require_skill(name)
    if entry.category not in ("inherited", "promoted"):
        raise ValueError(f"Skill is not inherited/promoted: {name}")
    if target_drive is None:
        from agentdrive.drive.drive import get_default_drive

        target_drive = get_default_drive()

    genome = skill_to_genome(entry)
    result: DriveIngestResult = target_drive.ingest(
        genome,
        source="skill-promotion",
        actor="agentdrive-skills",
    )
    meta, body = _read_skill_doc(entry.path)
    meta["dna"] = {
        "status": "ingested",
        "genome_id": result.genome_id,
        "accepted": result.accepted,
        "reason": result.reason,
        "source": "agentdrive skills dna",
    }
    _write_skill_doc(entry.path, meta, body)
    return SkillDNAExport(
        skill_name=entry.name,
        genome_id=result.genome_id,
        accepted=result.accepted,
        reason=result.reason,
        path=str(entry.path),
    )


def _recommend(entry: SkillEntry, usage: SkillUsage) -> tuple[str, str]:
    if entry.category == "promoted":
        return "promoted", "already promoted into the parent skill bench"
    if usage.failures >= 2 and usage.failures > usage.successes:
        return "prune", "failures outnumber successful outcomes"
    if usage.runs >= 2 and usage.success_rate >= 0.75:
        return "promote", "outcome evidence shows reliable success"
    if usage.successes >= 1 and usage.matches >= 3 and usage.failures == 0:
        return "promote", "matched repeatedly and has successful outcome evidence"
    if usage.matches >= 3 and usage.failures == 0:
        return "watch", "retrieved repeatedly; needs success outcome evidence"
    return "watch", "not enough outcome evidence yet"


def _recommendation_rank(value: str) -> int:
    order = {"promote": 0, "prune": 1, "watch": 2, "promoted": 3}
    return order.get(value, 9)


def _usage_payload(name: str) -> dict[str, Any]:
    usage = get_skill_usage(name)
    return {
        "matches": usage.matches,
        "runs": usage.runs,
        "successes": usage.successes,
        "failures": usage.failures,
        "success_rate": usage.success_rate,
        "last_matched_at": usage.last_matched_at,
        "last_run_at": usage.last_run_at,
    }


def _skill_genome_id(name: str) -> str:
    cleaned = _GENOME_ID_RE.sub("-", name.strip().lower()).strip("-._")
    if not cleaned:
        cleaned = "skill"
    return f"skill-{cleaned}"[:120].strip("-._")


def _body_steps(body: str) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        stripped = re.sub(r"^#{1,6}\s*", "", stripped)
        stripped = re.sub(r"^(?:[-*]|\d+[.)])\s*", "", stripped)
        if not stripped:
            continue
        steps.append(
            {
                "id": str(len(steps) + 1),
                "name": stripped[:90],
                "description": stripped,
            }
        )
        if len(steps) >= 12:
            break
    if not steps:
        steps.append({"id": "1", "name": "Apply skill", "description": body[:500]})
    return steps


def _require_skill(name: str) -> SkillEntry:
    entry = get_skill(name)
    if entry is None:
        raise ValueError(f"Unknown skill: {name}")
    return entry


def _read_skill_doc(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"Skill file has no frontmatter: {path}")
    meta = yaml.safe_load(match.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError(f"Skill frontmatter is not a mapping: {path}")
    return meta, match.group(2).strip()


def _write_skill_doc(path: Path, meta: dict[str, Any], body: str) -> None:
    path.write_text(
        "---\n"
        + yaml.safe_dump(meta, sort_keys=False).strip()
        + "\n---\n\n"
        + body.strip()
        + "\n",
        encoding="utf-8",
    )


def _normalize_tags(raw: Any) -> list[str]:
    if isinstance(raw, str):
        return [t.strip() for t in raw.split(",") if t.strip()]
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if str(t).strip()]
    if isinstance(raw, tuple):
        return [str(t).strip() for t in raw if str(t).strip()]
    return []
