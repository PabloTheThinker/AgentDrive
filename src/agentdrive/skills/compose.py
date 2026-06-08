"""Compose skills into the agent system prompt (Pattern 5 + hive bench)."""

from __future__ import annotations

import re

from agentdrive.skills.registry import SkillEntry, discover_skills

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]{1,}")


def _tokenize(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 2}


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

    if entry.when_to_call and any(w in message.lower() for w in entry.when_to_call.lower().split()[:6]):
        score += 1.5

    if role:
        if entry.role == role:
            score += 4.0
        elif entry.role in ("shared", "bench"):
            score += 1.0
        elif entry.role and entry.role != role:
            score -= 2.0

    return score


def match_skills_for_turn(
    message: str,
    *,
    top_k: int = 3,
    role: str | None = None,
) -> list[SkillEntry]:
    """Rank skills by keyword/tag overlap with the user message."""
    ranked: list[tuple[float, SkillEntry]] = []
    for entry in discover_skills():
        score = _score_skill(entry, message, role=role)
        if score > 0:
            ranked.append((score, entry))
    ranked.sort(key=lambda item: (-item[0], item[1].name))
    return [entry for _, entry in ranked[:top_k]]


def format_skills_catalog(*, limit: int = 24) -> str:
    """Compact bench list for the system prompt."""
    entries = discover_skills()
    if not entries:
        return ""

    lines = ["\n## Skills on your bench (invoke with /skill <name>)"]
    for entry in entries[:limit]:
        role_note = f" [{entry.role}]" if entry.role else ""
        lines.append(f"  - {entry.name}{role_note}: {entry.description[:100]}")
    if len(entries) > limit:
        lines.append(f"  - … +{len(entries) - limit} more (`agentdrive skills list`)")
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
        lines.append(f"\n### {entry.name}\n{body}")
    return "\n".join(lines)


def compose_skills_block(
    user_message: str,
    *,
    role: str | None = None,
    include_catalog: bool = True,
    top_k: int = 2,
) -> str:
    """Full skills section for build_system_prompt."""
    matched = match_skills_for_turn(user_message, top_k=top_k, role=role)
    parts: list[str] = []
    if include_catalog:
        catalog = format_skills_catalog()
        if catalog:
            parts.append(catalog)
    if matched:
        parts.append(format_matched_skill_bodies(matched))
    return "\n".join(parts)