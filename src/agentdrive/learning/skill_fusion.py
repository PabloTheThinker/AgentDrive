"""
Skill fusion — experience + skills + patterns → a completely new skill.

When an MCP/CLI session accumulates structural experience (graph traces),
distilled playbooks, and codebase pattern signals, this module merges them
into one born skill — not a copy of any parent, but a synthesis of the
session's lived AgentDrive work.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agentdrive.learning.auto_absorb import LearningSession

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_MAX_SKILL_NAME = 64

_EXPERIENCE_OPS = frozenset(
    {
        "experience_graph_context_pack",
        "experience_graph_record_reasoning",
        "think",
        "external_parent_decision",
        "multiverse_parent_decision",
        "multiverse_run_full",
        "record_outcome",
        "learnings_log",
    }
)

_PATTERN_OPS = frozenset(
    {
        "codebase_observe_file",
        "codebase_patterns_profile",
        "codebase_mimic",
        "codebase_transform_style",
        "codebase_mirror_resonance",
        "codebase_patterns_match",
    }
)


def _flag(name: str, default: str = "1") -> bool:
    raw = os.environ.get(name, default).strip().lower()
    return raw not in {"0", "false", "no", "off"}


def auto_fuse_skills_enabled() -> bool:
    return _flag("AGENTDRIVE_AUTO_FUSE_SKILLS", "1") and _flag("AGENTDRIVE_AUTO_LEARN", "1")


def _slugify(text: str, *, max_len: int = 32) -> str:
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or "session"


@dataclass
class FusionLineage:
    """Provenance for a born skill — what merged to create it."""

    trigger: str
    swarm_id: str
    program_id: str
    operations: list[str] = field(default_factory=list)
    experience_traces: list[str] = field(default_factory=list)
    source_skills: list[str] = field(default_factory=list)
    pattern_projects: list[str] = field(default_factory=list)

    def axes_present(self) -> set[str]:
        axes: set[str] = set()
        if self.experience_traces or any(op in _EXPERIENCE_OPS for op in self.operations):
            axes.add("experience")
        if self.source_skills:
            axes.add("skills")
        if self.pattern_projects or any(op in _PATTERN_OPS for op in self.operations):
            axes.add("patterns")
        return axes

    def fusion_ready(self) -> bool:
        return len(self.axes_present()) >= 2 and len(self.operations) >= 2


def lineage_from_session(session: LearningSession, trigger: str) -> FusionLineage:
    ops = [op for op, _ in session.ops]
    return FusionLineage(
        trigger=trigger,
        swarm_id=session.swarm_id,
        program_id=session.program_id,
        operations=ops,
        experience_traces=list(session.experience_traces),
        source_skills=list(dict.fromkeys(session.distilled_skills + session.referenced_skills)),
        pattern_projects=list(dict.fromkeys(session.pattern_projects)),
    )


def _fused_skill_name(lineage: FusionLineage) -> str:
    from agentdrive.learning.skill_naming import fused_skill_name

    return fused_skill_name(
        trigger=lineage.trigger,
        pattern_projects=lineage.pattern_projects,
        axes=lineage.axes_present(),
    )


def _load_skill_excerpts(skill_names: list[str], *, limit: int = 3) -> list[dict[str, str]]:
    from agentdrive.skills.registry import get_skill

    excerpts: list[dict[str, str]] = []
    for name in skill_names[:limit]:
        entry = get_skill(name)
        if entry is None:
            continue
        body = entry.body.strip()
        if len(body) > 600:
            body = body[:599] + "…"
        excerpts.append(
            {
                "name": entry.name,
                "description": entry.description[:200],
                "body": body,
            }
        )
    return excerpts


def _load_pattern_excerpts(project_ids: list[str], *, limit: int = 2) -> list[dict[str, Any]]:
    from agentdrive.codebase.framework import get_writing_guide

    excerpts: list[dict[str, Any]] = []
    for pid in project_ids[:limit]:
        try:
            framework = get_writing_guide(pid)
        except Exception:
            logger.debug("Failed to load framework for %s", pid, exc_info=True)
            continue
        patterns = framework.get("patterns") or []
        excerpts.append(
            {
                "project_id": pid,
                "patterns": [
                    {"category": p.get("category"), "rule": p.get("rule")}
                    for p in patterns[:5]
                    if isinstance(p, dict)
                ],
                "summary": framework.get("summary") or {},
            }
        )
    return excerpts


def build_fused_skill_body(lineage: FusionLineage) -> tuple[str, str]:
    """Return (description, markdown body) for a born skill."""
    title = lineage.trigger[:80] if lineage.trigger else "AgentDrive fused playbook"
    axes = sorted(lineage.axes_present())
    description = (
        f"Born skill — fused from AgentDrive {', '.join(axes)} "
        f"({len(lineage.operations)} ops in session)"
    )[:1024]

    lines = [
        f"# {title}",
        "",
        "A **born skill** — not copied from any single parent. Experience traces,",
        "distilled playbooks, and codebase patterns from this AgentDrive session were",
        "merged into one integrated playbook.",
        "",
        "## Lineage",
        f"- **Axes merged:** {', '.join(axes)}",
        f"- **Operations:** {', '.join(lineage.operations[:12])}",
    ]
    if lineage.experience_traces:
        lines.append(f"- **Experience traces:** {', '.join(lineage.experience_traces[:5])}")
    if lineage.source_skills:
        lines.append(f"- **Parent skills merged:** {', '.join(lineage.source_skills)}")
    if lineage.pattern_projects:
        lines.append(f"- **Pattern projects:** {', '.join(lineage.pattern_projects)}")

    lines.extend(["", "## When to use"])
    if lineage.trigger:
        lines.append(f"- Task resembles: {lineage.trigger[:240]}")
    lines.append("- You need the combined grounding from experience + skills + repo patterns.")
    lines.append("- Prior session work on this swarm already proved the path.")

    lines.extend(["", "## Synthesized playbook"])

    if "experience" in axes:
        lines.append("### From experience (Experience Graph)")
        lines.append("1. Call `experience_graph_get_context_pack` — inherit structural memory.")
        if lineage.experience_traces:
            lines.append(f"2. Ground in traces: `{lineage.experience_traces[0]}`.")
        if any(op.startswith("multiverse") or op == "external_parent_decision" for op in lineage.operations):
            lines.append(
                "3. For competing paths, use `external_parent_decision` or `multiverse_parent_decision`."
            )
        else:
            lines.append("3. Record non-trivial forks with `experience_graph_record_reasoning`.")

    skill_excerpts = _load_skill_excerpts(lineage.source_skills)
    if skill_excerpts:
        lines.append("")
        lines.append("### From merged skills")
        for ex in skill_excerpts:
            lines.append(f"**{ex['name']}** — {ex['description']}")
            if ex["body"]:
                snippet = ex["body"].split("\n")[0][:120]
                lines.append(f"> {snippet}")

    pattern_excerpts = _load_pattern_excerpts(lineage.pattern_projects)
    if pattern_excerpts:
        lines.append("")
        lines.append("### From codebase patterns (mirror neurons)")
        for ex in pattern_excerpts:
            lines.append(f"**Project `{ex['project_id']}`**")
            for pat in ex.get("patterns") or []:
                lines.append(f"- [{pat.get('category')}] {pat.get('rule')}")
        lines.append("- Use `codebase_mimic` before writing; `codebase_transform_style` after drafting.")

    lines.extend(
        [
            "",
            "### Integrated execution",
            "1. Pull graph context → match fused lineage above.",
            "2. Invoke merged skill steps where they apply; do not treat them as isolated.",
            "3. Write code through project patterns when a repo is in scope.",
            "4. Close the loop: `record_outcome` or `experience_graph_record_reasoning`.",
            "",
            "## Verification",
            "- Contradictions checked against latest context pack.",
            "- Born skill supersedes individual parent skills for this trigger class.",
        ]
    )

    return description, "\n".join(lines)


def synthesize_fused_skill(
    lineage: FusionLineage,
    *,
    promote: bool = False,
) -> dict[str, Any]:
    """Install a born skill from fusion lineage. Returns install metadata."""
    if not lineage.fusion_ready():
        raise ValueError(
            "Fusion requires at least two axes (experience, skills, patterns) "
            f"and 2+ operations; got axes={lineage.axes_present()}, "
            f"ops={len(lineage.operations)}"
        )

    from agentdrive.skills.registry import install_inherited_skill

    name = _fused_skill_name(lineage)
    description, body = build_fused_skill_body(lineage)
    tags = [
        "fused",
        "born-skill",
        "auto-learned",
        *sorted(lineage.axes_present()),
    ]
    if lineage.program_id:
        tags.append(lineage.program_id)

    path = install_inherited_skill(
        name=name,
        description=description,
        body=body,
        tags=tags,
        operation="synthesize_fused_skill",
        swarm_id=lineage.swarm_id,
        source_subagent_id="skill-fusion",
        update_existing=True,
    )

    lineage_path = path.parent / "fusion-lineage.json"
    lineage_path.write_text(
        json.dumps(
            {
                "name": name,
                "trigger": lineage.trigger,
                "axes": sorted(lineage.axes_present()),
                "operations": lineage.operations,
                "experience_traces": lineage.experience_traces,
                "source_skills": lineage.source_skills,
                "pattern_projects": lineage.pattern_projects,
                "program_id": lineage.program_id,
                "swarm_id": lineage.swarm_id,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    promoted = False
    genome_id: str | None = None
    if promote:
        try:
            from agentdrive.drive.drive import get_default_drive
            from agentdrive.skills.curation import ingest_skill_as_dna, promote_inherited_skill

            promote_inherited_skill(name)
            export = ingest_skill_as_dna(name, target_drive=get_default_drive())
            promoted = export.accepted
            genome_id = export.genome_id
        except Exception:
            logger.debug("Fused skill promote/ingest failed for %s", name, exc_info=True)

    fused_meta = {
        "name": name,
        "path": str(path),
        "axes": sorted(lineage.axes_present()),
        "source_skills": lineage.source_skills,
        "pattern_projects": lineage.pattern_projects,
        "promoted": promoted,
        "genome_id": genome_id,
        "born": True,
    }

    try:
        from agentdrive.memory.ingest import ingest_from_fused_skill

        mem = ingest_from_fused_skill(
            fused_meta,
            swarm_id=lineage.swarm_id,
            program_id=lineage.program_id,
            trigger=lineage.trigger,
        )
        if mem:
            fused_meta["memory"] = mem
    except Exception:
        logger.debug("memory bank ingest for fused skill failed", exc_info=True)

    return fused_meta


def maybe_fuse_session(
    session: LearningSession,
    *,
    trigger: str,
    last_operation: str,
) -> dict[str, Any] | None:
    """After absorb, attempt to birth a fused skill when lineage is rich enough."""
    if not auto_fuse_skills_enabled():
        return None
    lineage = lineage_from_session(session, trigger)
    if not lineage.fusion_ready():
        return None
    # Avoid re-fusing on every op — fuse on high-signal terminal ops or explicit synthesis.
    terminal = last_operation in {
        "external_parent_decision",
        "multiverse_parent_decision",
        "codebase_mimic",
        "think",
        "record_outcome",
        "experience_graph_record_reasoning",
        "synthesize_fused_skill",
    }
    if not terminal and len(session.ops) < 3:
        return None
    try:
        return synthesize_fused_skill(lineage)
    except Exception:
        logger.debug("Session skill fusion failed", exc_info=True)
        return None


def synthesize_from_inputs(
    *,
    trigger: str,
    swarm_id: str,
    program_id: str = "skill-fusion",
    operations: list[str] | None = None,
    experience_traces: list[str] | None = None,
    source_skills: list[str] | None = None,
    pattern_projects: list[str] | None = None,
    promote: bool = False,
) -> dict[str, Any]:
    """Explicit fusion API for MCP/CLI (manual or session-exported lineage)."""
    lineage = FusionLineage(
        trigger=trigger,
        swarm_id=swarm_id,
        program_id=program_id,
        operations=list(operations or []),
        experience_traces=list(experience_traces or []),
        source_skills=list(source_skills or []),
        pattern_projects=list(pattern_projects or []),
    )
    return synthesize_fused_skill(lineage, promote=promote)