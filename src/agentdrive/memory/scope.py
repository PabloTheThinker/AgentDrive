"""
Memory Bank scoping — vault (workspace) and topic (thematic lane).

AgentDrive organizes recall by where work lives (vault) and what it is about (topic).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MemoryScope:
    """Filter memories by workspace vault and/or topic lane."""

    vault: str = ""
    topic: str = ""

    def matches(self, entry_vault: str, entry_topic: str) -> bool:
        if self.vault and entry_vault and self.vault != entry_vault:
            return False
        if self.topic and entry_topic and self.topic != entry_topic:
            return False
        return True

    def to_dict(self) -> dict[str, str]:
        return {"vault": self.vault, "topic": self.topic}


def resolve_topic(kind: str, tags: list[str] | None = None) -> str:
    """Pick a topic lane from kind or the first meaningful tag."""
    if tags:
        for tag in tags:
            if tag and not tag.startswith("auto-"):
                return tag
    return kind or "general"


def scope_metadata(
    *,
    vault: str = "",
    topic: str = "",
    origin_path: str = "",
    shard_index: int | None = None,
    preserves_source: bool = True,
) -> dict[str, Any]:
    return {
        "vault": vault,
        "topic": topic or "general",
        "origin_path": origin_path,
        "shard_index": shard_index,
        "preserves_source": preserves_source,
    }