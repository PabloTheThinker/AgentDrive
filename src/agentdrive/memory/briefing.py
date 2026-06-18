"""Memory Bank briefings — dense recall packs for the AI."""

from __future__ import annotations

from typing import Any

from agentdrive.memory.store import MemoryBankStore


def build_memory_briefing(
    swarm_id: str,
    *,
    query: str = "",
    limit: int = 12,
    program_id: str | None = None,
    max_chars: int = 4000,
) -> dict[str, Any]:
    """Return a LLM-optimized memory briefing for session grounding."""
    store = MemoryBankStore(swarm_id)
    if query.strip():
        memories = store.search(query, limit=limit, program_id=program_id)
    else:
        memories = store.list_recent(limit=limit)

    if not memories:
        return {
            "swarm_id": swarm_id,
            "memory_count": 0,
            "briefing": "No memories stored yet. AgentDrive will grow this bank as you work.",
            "memories": [],
            "stats": store.stats(),
        }

    lines = [
        f"# Memory Bank — {swarm_id}",
        "",
        f"**{store.count()}** active memories. This is your deep personal databank —",
        "experience, decisions, patterns, born skills, and learnings merged for recall.",
        "",
    ]

    by_kind: dict[str, list] = {}
    for mem in memories:
        by_kind.setdefault(mem.kind, []).append(mem)

    for kind, group in sorted(by_kind.items()):
        lines.append(f"## {kind.replace('_', ' ').title()}")
        for mem in group:
            conf = f"{mem.confidence:.0%}"
            lines.append(f"### {mem.title} ({conf})")
            body = mem.content.strip()
            if len(body) > 500:
                body = body[:499] + "…"
            lines.append(body)
            if mem.links:
                link_str = ", ".join(f"{l.get('type')}:{l.get('id')}" for l in mem.links[:3])
                lines.append(f"_Links: {link_str}_")
            lines.append("")

    briefing = "\n".join(lines)
    if len(briefing) > max_chars:
        briefing = briefing[: max_chars - 1] + "…"

    return {
        "swarm_id": swarm_id,
        "memory_count": store.count(),
        "recalled": len(memories),
        "briefing": briefing,
        "memories": [m.to_dict() for m in memories],
        "stats": store.stats(),
        "integrated_layers": [
            "experience_graph",
            "skills",
            "learnings",
            "codebase_patterns",
            "auto_absorb",
            "skill_fusion",
        ],
    }


def build_deep_briefing(
    swarm_id: str,
    *,
    query: str = "",
    reasoning_style: str = "balanced",
    lookback_days: int = 7,
    memory_limit: int = 10,
    max_tokens: int = 1800,
) -> dict[str, Any]:
    """Unified briefing: Experience Graph fabric pack + Memory Bank."""
    from agentdrive.operations.registry import _integrated_recorder

    _, recorder = _integrated_recorder(swarm_id)
    fabric_pack = recorder.get_fabric_context_pack(
        reasoning_style=reasoning_style,
        lookback_days=lookback_days,
        max_tokens=max_tokens,
    )
    memory_pack = build_memory_briefing(swarm_id, query=query, limit=memory_limit)

    return {
        "swarm_id": swarm_id,
        "fabric_context_pack": fabric_pack,
        "memory_bank": memory_pack,
        "deep_briefing": (
            "## Structural memory (Experience Graph)\n"
            f"{fabric_pack.get('compact_graph_summary', '')}\n\n"
            "## Deep memory bank (personal databank)\n"
            f"{memory_pack.get('briefing', '')}"
        )[:6000],
        "memory_count": memory_pack.get("memory_count", 0),
    }
