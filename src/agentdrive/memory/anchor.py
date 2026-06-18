"""
Session anchor — compact grounding pack when a swarm session opens.

Tier 1: agent brief (~/.agentdrive/identity.txt)
Tier 2: essential memories (high-confidence, recent)
Tier 3: task-scoped recall (optional query)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentdrive.constants import get_agentdrive_home
from agentdrive.memory.store import MemoryBankStore


def load_agent_brief(path: Path | None = None) -> str:
    brief_path = path or (get_agentdrive_home() / "identity.txt")
    if brief_path.is_file():
        return brief_path.read_text(encoding="utf-8").strip()
    return (
        "## Agent brief\n"
        "No brief configured. Create ~/.agentdrive/identity.txt with the agent role, "
        "active projects, and operator preferences."
    )


def build_essential_memories(
    swarm_id: str,
    *,
    vault: str | None = None,
    limit: int = 12,
    max_chars: int = 3200,
) -> str:
    store = MemoryBankStore(swarm_id)
    entries = store.list_recent(limit=limit * 2)
    if vault:
        entries = [entry for entry in entries if entry.vault == vault or vault in entry.tags]
    entries.sort(key=lambda entry: (entry.confidence, entry.created_at), reverse=True)
    entries = entries[:limit]

    if not entries:
        return "## Essential memories\nThe bank is empty — memories accumulate as AgentDrive work completes."

    lines = ["## Essential memories"]
    used = 0
    for entry in entries:
        vault_label = f" [{entry.vault}]" if entry.vault else ""
        body = entry.content.strip()
        if len(body) > 400:
            body = body[:399] + "…"
        block = f"\n### {entry.title}{vault_label} ({entry.kind})\n{body}"
        if used + len(block) > max_chars:
            break
        lines.append(block)
        used += len(block)
    return "\n".join(lines)


def build_session_anchor(
    swarm_id: str,
    *,
    vault: str | None = None,
    query: str = "",
) -> dict[str, Any]:
    """Produce the session-opening anchor text and structured tiers."""
    tier_agent = load_agent_brief()
    tier_essential = build_essential_memories(swarm_id, vault=vault)
    tier_scoped = ""
    scoped_hits: list[dict[str, Any]] = []

    if query.strip():
        hits = MemoryBankStore(swarm_id).search(query, limit=5, vault=vault)
        if hits:
            lines = ["## Scoped recall"]
            for hit in hits:
                lines.append(f"- **{hit.title}**: {hit.content[:200]}")
            tier_scoped = "\n".join(lines)
            scoped_hits = [hit.to_dict() for hit in hits]

    anchor_text = f"{tier_agent}\n\n{tier_essential}"
    if tier_scoped:
        anchor_text = f"{anchor_text}\n\n{tier_scoped}"

    return {
        "swarm_id": swarm_id,
        "vault": vault,
        "tiers": {
            "agent_brief": tier_agent,
            "essential": tier_essential,
            "scoped": tier_scoped or None,
        },
        "anchor_text": anchor_text[:8000],
        "token_estimate": len(anchor_text) // 4,
        "scoped_memories": scoped_hits,
    }