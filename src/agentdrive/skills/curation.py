"""Review, promote, and prune inherited skills using local evidence."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from agentdrive.skills.registry import SkillEntry, discover_skills, get_skill
from agentdrive.skills.usage import SkillUsage, get_skill_usage

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


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


def _recommend(entry: SkillEntry, usage: SkillUsage) -> tuple[str, str]:
    if entry.category == "promoted":
        return "promoted", "already promoted into the parent skill bench"
    if usage.failures >= 2 and usage.failures > usage.successes:
        return "prune", "failures outnumber successful runs"
    if usage.runs >= 2 and usage.success_rate >= 0.75:
        return "promote", "explicit runs show reliable success"
    if usage.successes >= 1 and usage.matches >= 3 and usage.failures == 0:
        return "promote", "matched repeatedly and has successful run evidence"
    if usage.matches >= 3 and usage.failures == 0:
        return "watch", "retrieved repeatedly; needs explicit success evidence"
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
