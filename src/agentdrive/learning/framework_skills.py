"""
Framework skill playbook — how AI agents use AgentDrive + learned skills on any task.

When AgentDrive is the framework, models route work through:
  1. Session briefing (anchor + growth + skill matches)
  2. Matched learned/fused playbooks for the current task
  3. Skill invocation (read body or run bound operation)
  4. Write-back (auto-learning grows the bench)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from agentdrive.skills.compose import _score_skill
from agentdrive.skills.registry import SkillEntry, discover_skills, get_skill
from agentdrive.skills.runner import run_skill
from agentdrive.skills.usage import record_skill_match

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]{2,}")

_LEARNED_PREFIXES = ("learned-", "fused-")

_FRAMEWORK_WORKFLOW = """## AgentDrive framework loop (use on every task)

1. **Brief** — `framework_session_start` or `growth_merge_briefing` + `framework_skill_route`
2. **Route** — pick matched `learned-*` / `fused-*` skills for this task (below)
3. **Ground** — `experience_graph_get_context_pack` + apply skill playbook steps
4. **Execute** — run bound ops via `framework_skill_run` or follow SKILL.md body
5. **Write-back** — `experience_graph_record_reasoning` + `record_outcome` on completion

Learned skills compound automatically — check `auto_learning` on every `run_operation` result.
"""


@dataclass
class FrameworkSkillMatch:
    name: str
    description: str
    score: float
    kind: str  # learned | fused | inherited | bundled
    project: str
    when_to_call: str
    has_operation: bool
    operation: str | None
    excerpt: str
    invoke_hint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "score": self.score,
            "kind": self.kind,
            "project": self.project,
            "when_to_call": self.when_to_call,
            "has_operation": self.has_operation,
            "operation": self.operation,
            "excerpt": self.excerpt,
            "invoke_hint": self.invoke_hint,
        }


def _skill_kind(name: str, tags: tuple[str, ...]) -> str:
    if name.startswith("fused-"):
        return "fused"
    if name.startswith("learned-"):
        return "learned"
    if "fused" in tags:
        return "fused"
    if "learned" in tags or "auto-learned" in tags:
        return "learned"
    if "inherited" in tags:
        return "inherited"
    return "bundled"


def _project_from_skill(entry: SkillEntry) -> str:
    for tag in entry.tags:
        if tag and not tag.startswith(("auto-", "mcp-", "learned", "fused", "inherited")):
            if "-" in tag or tag.isalnum():
                return tag
    parts = entry.name.split("-")
    if entry.name.startswith("learned-") and len(parts) >= 2:
        return parts[1]
    if entry.name.startswith("fused-") and len(parts) >= 2:
        return parts[1]
    return ""


def _framework_boost(
    entry: SkillEntry,
    *,
    swarm_id: str,
    project_id: str,
) -> float:
    boost = 0.0
    kind = _skill_kind(entry.name, entry.tags)
    if kind == "fused":
        boost += 8.0
    elif kind == "learned":
        boost += 5.0
    elif kind == "inherited":
        boost += 2.0

    skill_project = _project_from_skill(entry)
    if project_id and (project_id in entry.name or project_id in entry.tags or skill_project == project_id):
        boost += 6.0
    if swarm_id and swarm_id in str(entry.path):
        boost += 3.0
    if entry.operation:
        boost += 1.5
    return boost


def _invoke_hint(entry: SkillEntry) -> str:
    if entry.operation:
        arg = f' arg="{entry.argument}"' if entry.argument else ""
        return f"framework_skill_run(name={entry.name!r}{arg}) or run_operation({entry.operation!r})"
    return f"Read SKILL.md body for `{entry.name}` and follow the playbook steps."


def _excerpt(body: str, *, limit: int = 420) -> str:
    text = body.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def list_framework_skills(
    *,
    swarm_id: str = "",
    learned_only: bool = False,
) -> list[SkillEntry]:
    entries: list[SkillEntry] = []
    for entry in discover_skills():
        kind = _skill_kind(entry.name, entry.tags)
        if learned_only and kind not in ("learned", "fused"):
            continue
        if swarm_id and swarm_id not in str(entry.path) and kind == "bundled":
            continue
        entries.append(entry)
    return sorted(entries, key=lambda item: item.name)


def route_skills_for_task(
    task: str,
    *,
    swarm_id: str = "",
    project_id: str = "",
    limit: int = 5,
    learned_only: bool = False,
    record_matches: bool = True,
) -> list[FrameworkSkillMatch]:
    """Rank skills for the current task — prioritizes learned/fused playbooks."""
    query = task.strip()
    if not query:
        query = project_id or "agentdrive session"

    scored: list[tuple[float, SkillEntry]] = []
    for entry in discover_skills():
        kind = _skill_kind(entry.name, entry.tags)
        if learned_only and kind not in ("learned", "fused"):
            continue
        if entry.harness not in ("agentdrive", "universal", ""):
            continue
        total = _score_skill(entry, query, role=None) + _framework_boost(
            entry, swarm_id=swarm_id, project_id=project_id
        )
        if total > 0:
            scored.append((total, entry))

    scored.sort(key=lambda pair: (-pair[0], pair[1].name))
    results: list[FrameworkSkillMatch] = []
    for score, entry in scored[:limit]:
        kind = _skill_kind(entry.name, entry.tags)
        match = FrameworkSkillMatch(
            name=entry.name,
            description=entry.description,
            score=round(score, 2),
            kind=kind,
            project=_project_from_skill(entry),
            when_to_call=entry.when_to_call or entry.description,
            has_operation=bool(entry.operation),
            operation=entry.operation,
            excerpt=_excerpt(entry.body),
            invoke_hint=_invoke_hint(entry),
        )
        results.append(match)
        if record_matches:
            try:
                record_skill_match(entry.name, score=score)
            except Exception:
                pass
    return results


def format_skill_playbook(matches: list[FrameworkSkillMatch]) -> str:
    if not matches:
        return "No learned skills matched this task yet. AgentDrive will grow skills as you work."

    lines = ["## Matched skills for this task"]
    for match in matches:
        lines.append(
            f"\n### {match.name} ({match.kind}, score {match.score})\n"
            f"**When:** {match.when_to_call}\n"
            f"**Invoke:** {match.invoke_hint}\n"
            f"{match.excerpt}"
        )
    return "\n".join(lines)


def build_framework_session_pack(
    task: str = "",
    *,
    swarm_id: str,
    project_id: str = "",
    skill_limit: int = 5,
) -> dict[str, Any]:
    """Unified framework opening pack for any AgentDrive session."""
    from agentdrive.learning.growth_merge import build_growth_briefing
    from agentdrive.memory.anchor import build_session_anchor

    vault = project_id or None
    anchor = build_session_anchor(swarm_id, vault=vault, query=task)
    growth = build_growth_briefing(swarm_id, query=task, limit=skill_limit)
    matches = route_skills_for_task(
        task,
        swarm_id=swarm_id,
        project_id=project_id,
        limit=skill_limit,
    )
    learned_bench = list_framework_skills(swarm_id=swarm_id, learned_only=True)

    playbook = format_skill_playbook(matches)
    framework_briefing = (
        f"{_FRAMEWORK_WORKFLOW}\n\n"
        f"{anchor.get('anchor_text', '')}\n\n"
        f"{playbook}\n\n"
        f"## Growth context\n"
        f"{growth.get('growth_briefing', '')[:2500]}"
    )[:8000]

    return {
        "swarm_id": swarm_id,
        "task": task,
        "project_id": project_id,
        "framework_workflow": _FRAMEWORK_WORKFLOW,
        "anchor": anchor,
        "growth_briefing": growth,
        "matched_skills": [m.to_dict() for m in matches],
        "learned_skill_count": len(learned_bench),
        "learned_skills": [
            {"name": e.name, "description": e.description[:120], "kind": _skill_kind(e.name, e.tags)}
            for e in learned_bench[:20]
        ],
        "framework_briefing": framework_briefing,
    }


def run_framework_skill(
    name: str,
    *,
    arg: str = "",
    swarm_id: str = "",
) -> dict[str, Any]:
    """Run a matched skill and attach swarm context to bound operations."""
    entry = get_skill(name)
    if entry is None:
        return {"success": False, "error": f"Unknown skill: {name}", "operation": "framework_skill_run"}

    result = run_skill(name, arg, swarm_id=swarm_id)
    payload = {
        "success": bool(result.get("success")),
        "operation": "framework_skill_run",
        "skill": name,
        "result": result,
    }
    if entry.operation:
        payload["bound_operation"] = entry.operation
    return payload