"""Local usage ledger for SKILL.md candidates.

Inherited sub-agent skills should not be static prompt text forever. This
ledger tracks whether a skill is being retrieved and whether explicit runs
succeed, giving the matcher a small feedback signal without mutating SKILL.md.
"""

from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentdrive.constants import get_agentdrive_home

logger = logging.getLogger(__name__)

USAGE_FILE_NAME = "usage.json"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _usage_path() -> Path:
    return get_agentdrive_home() / "skills" / USAGE_FILE_NAME


@dataclass
class SkillUsage:
    """Usage and outcome summary for one skill."""

    name: str
    matches: int = 0
    runs: int = 0
    successes: int = 0
    failures: int = 0
    last_score: float = 0.0
    last_matched_at: str = ""
    last_run_at: str = ""
    sources: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, name: str, raw: Any) -> SkillUsage:
        if not isinstance(raw, dict):
            return cls(name=name)
        sources = raw.get("sources") or {}
        if not isinstance(sources, dict):
            sources = {}
        return cls(
            name=str(raw.get("name") or name),
            matches=int(raw.get("matches") or 0),
            runs=int(raw.get("runs") or 0),
            successes=int(raw.get("successes") or 0),
            failures=int(raw.get("failures") or 0),
            last_score=float(raw.get("last_score") or 0.0),
            last_matched_at=str(raw.get("last_matched_at") or ""),
            last_run_at=str(raw.get("last_run_at") or ""),
            sources={str(k): int(v or 0) for k, v in sources.items()},
        )

    @property
    def success_rate(self) -> float:
        if self.runs <= 0:
            return 0.0
        return self.successes / max(1, self.runs)


def _load_all() -> dict[str, SkillUsage]:
    path = _usage_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("Failed to read skill usage ledger %s", path, exc_info=True)
        return {}
    skills = raw.get("skills") if isinstance(raw, dict) else {}
    if not isinstance(skills, dict):
        return {}
    return {
        str(name): SkillUsage.from_raw(str(name), value)
        for name, value in skills.items()
    }


def _save_all(items: dict[str, SkillUsage]) -> None:
    path = _usage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_at": _utc_now_iso(),
        "skills": {name: asdict(item) for name, item in sorted(items.items())},
    }
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{USAGE_FILE_NAME}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    try:
        with open(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
        Path(tmp_name).replace(path)
    except Exception:
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except Exception:
            pass
        raise


def get_skill_usage(name: str) -> SkillUsage:
    """Return current usage for a skill, or a zero record."""
    key = name.strip()
    if not key:
        return SkillUsage(name="")
    return _load_all().get(key, SkillUsage(name=key))


def list_skill_usage() -> list[SkillUsage]:
    """Return usage records sorted by strongest evidence first."""
    return sorted(
        _load_all().values(),
        key=lambda item: (-item.successes, -item.matches, item.failures, item.name),
    )


def record_skill_match(name: str, *, score: float = 0.0, source: str = "compose") -> SkillUsage:
    """Record that a skill was selected for a turn."""
    key = name.strip()
    if not key:
        return SkillUsage(name="")
    items = _load_all()
    usage = items.get(key, SkillUsage(name=key))
    usage.matches += 1
    usage.last_score = float(score)
    usage.last_matched_at = _utc_now_iso()
    usage.sources[source] = usage.sources.get(source, 0) + 1
    items[key] = usage
    _save_all(items)
    return usage


def record_skill_run(name: str, *, success: bool, source: str = "run") -> SkillUsage:
    """Record a skill execution or task-outcome evidence point."""
    key = name.strip()
    if not key:
        return SkillUsage(name="")
    items = _load_all()
    usage = items.get(key, SkillUsage(name=key))
    usage.runs += 1
    if success:
        usage.successes += 1
    else:
        usage.failures += 1
    usage.last_run_at = _utc_now_iso()
    usage.sources[source] = usage.sources.get(source, 0) + 1
    items[key] = usage
    _save_all(items)
    return usage


def skill_usage_boost(name: str, *, inherited: bool = False) -> float:
    """Small ranking adjustment from local evidence.

    The boost is deliberately bounded. Keyword relevance still dominates, but
    repeated successful inherited skills rise above equally relevant unproven
    siblings, and failing ones stop crowding the parent prompt.
    """
    usage = get_skill_usage(name)
    boost = min(1.5, usage.matches * 0.05)
    boost += min(4.0, usage.successes * 1.0)
    boost -= min(4.0, usage.failures * 1.25)
    if inherited:
        boost += min(1.0, usage.matches * 0.05)
        if usage.runs and usage.success_rate >= 0.75:
            boost += 1.0
        if usage.failures > usage.successes:
            boost -= 1.5
    return boost
