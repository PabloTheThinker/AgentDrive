"""
Descriptive names for auto-learned and born (fused) skills.

Skill slugs should tell you what was learned at a glance:
  learned-openmangos-mimic-growth-merge-briefing
  fused-openmangos-experience-patterns-skills
"""

from __future__ import annotations

import re
from typing import Iterable

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_MAX_SKILL_NAME = 64

_OPERATION_VERBS: dict[str, str] = {
    "codebase_mimic": "mimic",
    "codebase_patterns_profile": "patterns",
    "codebase_observe_file": "observe",
    "codebase_patterns_match": "match-style",
    "codebase_transform_style": "transform-style",
    "codebase_mirror_resonance": "mirror-resonance",
    "codebase_register_project": "register-project",
    "external_parent_decision": "parent-decision",
    "multiverse_parent_decision": "multiverse-decision",
    "experience_graph_record_reasoning": "fabric-reasoning",
    "experience_graph_context_pack": "context-pack",
    "think": "synthesis",
    "record_outcome": "outcome",
    "learnings_log": "learning",
    "synthesize_fused_skill": "skill-fusion",
    "growth_merge_briefing": "growth-merge",
    "memory_bank_store": "memory-store",
}


def slugify(text: str, *, max_len: int = 32) -> str:
    slug = _SLUG_RE.sub("-", str(text).lower()).strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or "session"


def _trim_name(parts: Iterable[str]) -> str:
    name = "-".join(part for part in parts if part)
    return name[:_MAX_SKILL_NAME] or "learned-session"


def learned_skill_name(
    operation: str,
    *,
    trigger: str = "",
    project_id: str = "",
    intent: str = "",
) -> str:
    """
    Human-readable slug for a single auto-distilled playbook.

    Pattern: learned-{project?}-{verb}-{focus?}
    """
    verb = _OPERATION_VERBS.get(operation) or slugify(operation.replace("_", "-"), max_len=18)
    subject = slugify(project_id, max_len=22) if project_id else ""
    raw_focus = (intent or trigger or "").strip()
    focus = slugify(raw_focus, max_len=30) if raw_focus else ""
    if focus in {subject, verb, "session"}:
        focus = ""

    parts = ["learned"]
    if subject:
        parts.append(subject)
    parts.append(verb)
    if focus:
        parts.append(focus)
    return _trim_name(parts)


def fused_skill_name(
    *,
    trigger: str = "",
    pattern_projects: Iterable[str] | None = None,
    axes: Iterable[str] | None = None,
) -> str:
    """
    Human-readable slug for a born skill merged from multiple surfaces.

    Pattern: fused-{subject}-{axis1-axis2-...}
    """
    projects = [slugify(p, max_len=18) for p in (pattern_projects or []) if p]
    subject = projects[0] if projects else slugify(trigger, max_len=26)
    axis_list = sorted({slugify(a, max_len=12) for a in (axes or []) if a})
    axis_part = "-".join(axis_list) if axis_list else "merged"

    parts = ["fused", subject or "session", axis_part]
    return _trim_name(parts)


def learned_skill_title(
    operation: str,
    *,
    trigger: str = "",
    project_id: str = "",
    intent: str = "",
) -> str:
    """Display title for SKILL.md header (not the slug)."""
    verb = _OPERATION_VERBS.get(operation, operation.replace("_", " "))
    focus = (intent or trigger or "").strip()
    if project_id and focus:
        return f"{project_id}: {verb} — {focus[:80]}"
    if project_id:
        return f"{project_id}: {verb}"
    if focus:
        return f"{verb}: {focus[:80]}"
    return verb.replace("-", " ").title()
