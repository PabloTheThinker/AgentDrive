"""Discover and load SKILL.md files from ~/.agentdrive/skills."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentdrive.constants import get_agentdrive_home
from agentdrive.utils.safe_paths import safe_name


@dataclass(frozen=True)
class SkillEntry:
    """One skill from a SKILL.md frontmatter + body."""

    name: str
    description: str
    path: Path
    operation: str | None = None
    argument: str | None = None
    body: str = ""
    tags: tuple[str, ...] = ()
    role: str = ""  # arisen | pawn | orchestrator | shared | bench
    category: str = ""
    harness: str = ""  # universal | agentdrive | grok | claude | codex
    requires: str = ""  # human-readable harness/tool requirements
    source: str = ""
    when_to_call: str = ""


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def _skills_roots() -> list[Path]:
    home = get_agentdrive_home()
    return [
        home / "skills",
        Path(__file__).resolve().parents[3] / "examples" / "skills",
    ]


def _parse_skill_file(path: Path, *, skills_root: Path | None = None) -> SkillEntry | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None

    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return None

    if not isinstance(meta, dict):
        return None

    name = str(meta.get("name") or path.parent.name).strip()
    if not name:
        return None

    description = str(meta.get("description") or "").strip()
    operation = meta.get("agentdrive_operation") or meta.get("operation")
    argument = meta.get("argument") or meta.get("arg")
    body = match.group(2).strip()

    raw_tags = meta.get("tags") or []
    if isinstance(raw_tags, str):
        tags = tuple(t.strip() for t in raw_tags.split(",") if t.strip())
    elif isinstance(raw_tags, list):
        tags = tuple(str(t).strip() for t in raw_tags if str(t).strip())
    else:
        tags = ()

    role = str(meta.get("role") or meta.get("pawn_role") or "").strip()
    category = str(meta.get("category") or "").strip()
    harness = str(meta.get("harness") or "").strip()
    requires = str(meta.get("requires") or "").strip()
    if not category and skills_root is not None:
        try:
            rel = path.parent.relative_to(skills_root)
            parts = rel.parts
            if parts[0] == "vendors" and len(parts) > 1:
                category = "vendors"
                harness = harness or parts[1]
            elif len(parts) > 1:
                category = parts[0]
            elif len(parts) == 1:
                category = parts[0]
        except ValueError:
            category = ""
    if not harness:
        if category in ("core", "hive", "agentdrives"):
            harness = "agentdrive"
        elif category == "universal":
            harness = "universal"
        elif category in ("think", "golden-path-verify") or path.parent.name in (
            "think",
            "golden-path-verify",
        ):
            harness = "agentdrive"
        else:
            harness = "universal" if category == "universal" else "agentdrive"
    source = str(meta.get("source") or "").strip()
    when_to_call = str(meta.get("when_to_call") or "").strip()

    return SkillEntry(
        name=name,
        description=description,
        path=path,
        operation=str(operation).strip() if operation else None,
        argument=str(argument).strip() if argument else None,
        body=body,
        tags=tags,
        role=role,
        category=category,
        harness=harness,
        requires=requires,
        source=source,
        when_to_call=when_to_call,
    )


def discover_skills() -> list[SkillEntry]:
    """All skills from user + bundled example directories."""
    seen: set[str] = set()
    out: list[SkillEntry] = []

    for root in _skills_roots():
        if not root.is_dir():
            continue
        for skill_md in sorted(root.glob("**/SKILL.md")):
            entry = _parse_skill_file(skill_md, skills_root=root)
            if entry is None or entry.name in seen:
                continue
            seen.add(entry.name)
            out.append(entry)

    return sorted(out, key=lambda e: e.name)


def list_skills(*, harness: str | None = None) -> list[SkillEntry]:
    entries = discover_skills()
    if not harness:
        return entries
    needle = harness.strip().lower()
    return [e for e in entries if e.harness.lower() == needle]


def list_skills_by_tier() -> dict[str, list[SkillEntry]]:
    """Group skills for catalog display: agentdrive, universal, vendors."""
    tiers: dict[str, list[SkillEntry]] = {
        "agentdrive": [],
        "universal": [],
        "grok": [],
        "claude": [],
        "codex": [],
    }
    for entry in discover_skills():
        h = entry.harness.lower() if entry.harness else "agentdrive"
        if h in tiers:
            tiers[h].append(entry)
        elif entry.category == "vendors":
            tiers.setdefault(h, []).append(entry)
        elif h == "agentdrive" or entry.category in ("core", "hive", "agentdrives"):
            tiers["agentdrive"].append(entry)
        else:
            tiers["universal"].append(entry)
    return {k: sorted(v, key=lambda e: e.name) for k, v in tiers.items() if v}


def get_skill(name: str) -> SkillEntry | None:
    needle = name.strip().lower()
    for entry in discover_skills():
        if entry.name.lower() == needle:
            return entry
    return None


_SKILL_TEMPLATE = """---
name: {name}
description: "{description}"
# agentdrive_operation: optional_operation_name
# argument: optional_arg_key
---

# {title}

Describe what this skill does and when to use it.

**Usage:** `/skill {name}` or `agentdrive skills run {name}`
"""


def _normalize_skill_name(name: str) -> str:
    cleaned = name.strip().lower().replace(" ", "-")
    cleaned = re.sub(r"[^a-z0-9_-]+", "", cleaned)
    if not cleaned:
        raise ValueError("Skill name must contain letters or numbers")
    return cleaned


def init_skill(name: str, *, description: str = "", force: bool = False) -> Path:
    """Scaffold ``~/.agentdrive/skills/<name>/SKILL.md`` with frontmatter template."""
    slug = _normalize_skill_name(name)
    skill_dir = get_agentdrive_home() / "skills" / safe_name(slug)
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists() and not force:
        raise FileExistsError(f"Skill already exists: {skill_md}")

    desc = description.strip() or f"Custom skill — {slug}"
    title = slug.replace("-", " ").title()
    skill_dir.mkdir(parents=True, exist_ok=True)
    # Quote description so colons in generated text stay valid YAML.
    skill_md.write_text(
        _SKILL_TEMPLATE.format(
            name=slug,
            description=desc.replace('"', '\\"'),
            title=title,
        ),
        encoding="utf-8",
    )
    return skill_md


def skill_operation_kwargs(entry: SkillEntry, arg: str) -> dict[str, Any]:
    """Map slash/CLI args to operation kwargs for a skill."""
    kwargs: dict[str, Any] = {}
    key = entry.argument or "input"
    if entry.operation == "think":
        kwargs["question"] = arg.strip() or "What should I know about my AgentDrive?"
    elif entry.operation == "learnings_log":
        parts = arg.split(maxsplit=1)
        if len(parts) >= 2:
            kwargs["key"], kwargs["insight"] = parts[0], parts[1]
        else:
            kwargs["key"] = parts[0] if parts else "skill"
            kwargs["insight"] = entry.description or "skill invocation"
    elif entry.operation in ("learnings_list", "pool_status", "pool_stats"):
        pass
    elif entry.operation == "pool_query":
        kwargs["task"] = arg.strip() or "semantic search"
    else:
        if arg.strip():
            kwargs[key] = arg.strip()
    return kwargs