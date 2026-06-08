"""Discover and load SKILL.md files from ~/.agentdrive/skills."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentdrive.constants import get_agentdrive_home


@dataclass(frozen=True)
class SkillEntry:
    """One skill from a SKILL.md frontmatter + body."""

    name: str
    description: str
    path: Path
    operation: str | None = None
    argument: str | None = None
    body: str = ""


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def _skills_roots() -> list[Path]:
    home = get_agentdrive_home()
    return [
        home / "skills",
        Path(__file__).resolve().parents[3] / "examples" / "skills",
    ]


def _parse_skill_file(path: Path) -> SkillEntry | None:
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

    return SkillEntry(
        name=name,
        description=description,
        path=path,
        operation=str(operation).strip() if operation else None,
        argument=str(argument).strip() if argument else None,
        body=body,
    )


def discover_skills() -> list[SkillEntry]:
    """All skills from user + bundled example directories."""
    seen: set[str] = set()
    out: list[SkillEntry] = []

    for root in _skills_roots():
        if not root.is_dir():
            continue
        for skill_md in sorted(root.glob("*/SKILL.md")):
            entry = _parse_skill_file(skill_md)
            if entry is None or entry.name in seen:
                continue
            seen.add(entry.name)
            out.append(entry)

    return sorted(out, key=lambda e: e.name)


def list_skills() -> list[SkillEntry]:
    return discover_skills()


def get_skill(name: str) -> SkillEntry | None:
    needle = name.strip().lower()
    for entry in discover_skills():
        if entry.name.lower() == needle:
            return entry
    return None


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