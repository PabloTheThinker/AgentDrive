"""Compose skills into the agent system prompt (Pattern 5 + hive bench)."""

from __future__ import annotations

import logging
import os
import re

from agentdrive.skills.registry import SkillEntry, discover_skills, list_skills_by_tier
from agentdrive.skills.usage import record_skill_match, skill_usage_boost

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]{1,}")

_TIER_LABELS = {
    "agentdrive": "AgentDrive + hive (MCP operations & pawns)",
    "universal": "Universal (any model via MCP or plain tools)",
    "grok": "Grok harness (native Grok CLI tools)",
    "claude": "Claude Code harness",
    "codex": "Codex CLI harness",
}


def active_harness() -> str | None:
    """Optional filter from env or config — AGENTDRIVE_HARNESS=grok|claude|codex."""
    return (os.environ.get("AGENTDRIVE_HARNESS") or "").strip().lower() or None


def _tokenize(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 2}


def _include_in_prompt(entry: SkillEntry, *, active: str | None) -> bool:
    h = (entry.harness or "agentdrive").lower()
    if h in ("agentdrive", "universal"):
        return True
    if active and h == active:
        return True
    return False


def _score_skill(entry: SkillEntry, message: str, *, role: str | None) -> float:
    msg_tokens = _tokenize(message)
    if not msg_tokens:
        return 0.0

    score = 0.0
    haystack = " ".join(
        [
            entry.name,
            entry.description,
            entry.when_to_call,
            " ".join(entry.tags),
            entry.category,
        ]
    ).lower()
    skill_tokens = _tokenize(haystack)
    overlap = msg_tokens & skill_tokens
    score += len(overlap) * 2.0

    for tag in entry.tags:
        if tag.lower() in message.lower():
            score += 3.0

    if entry.when_to_call and any(
        w in message.lower() for w in entry.when_to_call.lower().split()[:6]
    ):
        score += 1.5

    if role:
        if entry.role == role:
            score += 4.0
        elif entry.role in ("shared", "bench"):
            score += 1.0
        elif entry.role and entry.role != role:
            score -= 2.0

    score += skill_usage_boost(entry.name, inherited=entry.category == "inherited")
    return score


def match_skills_for_turn(
    message: str,
    *,
    top_k: int = 3,
    role: str | None = None,
    harness: str | None = None,
    record_matches: bool = True,
) -> list[SkillEntry]:
    """Rank skills by keyword/tag overlap with the user message."""
    active = harness or active_harness()
    ranked: list[tuple[float, SkillEntry]] = []
    for entry in discover_skills():
        if not _include_in_prompt(entry, active=active):
            continue
        score = _score_skill(entry, message, role=role)
        if score > 0:
            ranked.append((score, entry))
    ranked.sort(key=lambda item: (-item[0], item[1].name))
    selected = ranked[:top_k]
    if record_matches:
        for score, entry in selected:
            try:
                record_skill_match(entry.name, score=score)
            except Exception:
                logger.debug("Failed to record skill match for %s", entry.name, exc_info=True)
    return [entry for _, entry in selected]


def format_skills_catalog(*, per_tier: int = 8, harness: str | None = None) -> str:
    """Tiered bench list for the system prompt."""
    active = harness or active_harness()
    tiers = list_skills_by_tier()
    if not any(tiers.values()):
        return ""

    lines = ["\n## Skills on your bench (invoke with /skill <name>)"]
    order = ["agentdrive", "universal", "grok", "claude", "codex"]
    for tier in order:
        entries = tiers.get(tier, [])
        if not entries:
            continue
        if tier not in ("agentdrive", "universal") and tier != active:
            lines.append(
                f"\n### {_TIER_LABELS[tier]} "
                f"({len(entries)} skills — set AGENTDRIVE_HARNESS={tier} to inject)"
            )
            continue
        lines.append(f"\n### {_TIER_LABELS[tier]}")
        shown = entries[:per_tier]
        for entry in shown:
            role_note = f" [{entry.role}]" if entry.role else ""
            lines.append(f"  - {entry.name}{role_note}: {entry.description[:90]}")
        if len(entries) > len(shown):
            lines.append(f"  - … +{len(entries) - len(shown)} more")
    return "\n".join(lines)


def format_matched_skill_bodies(
    entries: list[SkillEntry],
    *,
    body_limit: int = 900,
) -> str:
    """Inject truncated skill bodies for top matches this turn."""
    if not entries:
        return ""

    lines = ["\n## Skills matched for this turn"]
    for entry in entries:
        body = entry.body.strip()
        if len(body) > body_limit:
            body = body[: body_limit - 1] + "…"
        harness_note = f" ({entry.harness})" if entry.harness else ""
        lines.append(f"\n### {entry.name}{harness_note}\n{body}")
    return "\n".join(lines)


def compose_skills_block(
    user_message: str,
    *,
    role: str | None = None,
    harness: str | None = None,
    include_catalog: bool = True,
    top_k: int = 2,
) -> str:
    """Full skills section for build_system_prompt."""
    active = harness or active_harness()
    matched = match_skills_for_turn(user_message, top_k=top_k, role=role, harness=active)
    parts: list[str] = []
    if include_catalog:
        catalog = format_skills_catalog(harness=active)
        if catalog:
            parts.append(catalog)
    if matched:
        parts.append(format_matched_skill_bodies(matched))
    return "\n".join(parts)
