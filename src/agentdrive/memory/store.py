"""
AgentDrive Memory Bank — deep persistent memory for the AI.

Append-only atomic memories per swarm, queryable across sessions.
Complements the Experience Graph (structure) and learnings (operational)
with a unified knowledge databank the model can always grow and recall.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentdrive.drive.drive import get_swarm_drive_path

_MEMORY_KINDS = frozenset(
    {
        "fact",
        "procedure",
        "insight",
        "decision",
        "pattern",
        "relationship",
        "preference",
        "episode",
        "born_skill",
        "learning",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]{2,}")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _memory_bank_dir(swarm_id: str) -> Path:
    path = get_swarm_drive_path(swarm_id) / "memory_bank"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class MemoryEntry:
    memory_id: str
    kind: str
    title: str
    content: str
    confidence: float = 0.75
    source: str = "user"
    program_id: str = ""
    swarm_id: str = ""
    tags: list[str] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)
    created_at: str = ""
    last_accessed_at: str = ""
    access_count: int = 0
    active: bool = True
    supersedes: str | None = None
    vault: str = ""
    topic: str = ""
    origin_path: str = ""
    shard_index: int | None = None
    preserves_source: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        shard_index = data.get("shard_index")
        return cls(
            memory_id=str(data.get("memory_id") or ""),
            kind=str(data.get("kind") or "insight"),
            title=str(data.get("title") or ""),
            content=str(data.get("content") or ""),
            confidence=float(data.get("confidence") or 0.75),
            source=str(data.get("source") or "user"),
            program_id=str(data.get("program_id") or ""),
            swarm_id=str(data.get("swarm_id") or ""),
            tags=[str(t) for t in (data.get("tags") or [])],
            links=[dict(link) for link in (data.get("links") or []) if isinstance(link, dict)],
            created_at=str(data.get("created_at") or ""),
            last_accessed_at=str(data.get("last_accessed_at") or ""),
            access_count=int(data.get("access_count") or 0),
            active=bool(data.get("active", True)),
            supersedes=data.get("supersedes"),
            vault=str(data.get("vault") or ""),
            topic=str(data.get("topic") or ""),
            origin_path=str(data.get("origin_path") or ""),
            shard_index=int(shard_index) if shard_index is not None else None,
            preserves_source=bool(data.get("preserves_source", True)),
        )


class MemoryBankStore:
    """Swarm-scoped append-only memory databank."""

    def __init__(self, swarm_id: str) -> None:
        self.swarm_id = swarm_id
        self.root = _memory_bank_dir(swarm_id)
        self.memories_path = self.root / "memories.jsonl"
        self.stats_path = self.root / "stats.json"

    def _load_all(self) -> list[MemoryEntry]:
        if not self.memories_path.is_file():
            return []
        entries: list[MemoryEntry] = []
        for line in self.memories_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                entries.append(MemoryEntry.from_dict(data))
        return entries

    def _active_entries(self) -> list[MemoryEntry]:
        return [entry for entry in self._load_all() if entry.active]

    def _dedupe_by_title(self, entries: list[MemoryEntry]) -> list[MemoryEntry]:
        seen: dict[str, MemoryEntry] = {}
        for entry in sorted(entries, key=lambda item: item.created_at):
            key = f"{entry.kind}|{entry.title.strip().lower()}"
            if entry.active:
                seen[key] = entry
        return list(seen.values())

    def _write_entry(self, entry: MemoryEntry) -> MemoryEntry:
        if entry.kind not in _MEMORY_KINDS:
            raise ValueError(f"invalid memory kind {entry.kind!r}")
        if not entry.title.strip():
            raise ValueError("title is required")
        if not entry.content.strip():
            raise ValueError("content is required")
        if not entry.memory_id:
            entry.memory_id = f"mem-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        if not entry.created_at:
            entry.created_at = _utc_now()
        if not entry.swarm_id:
            entry.swarm_id = self.swarm_id
        entry.confidence = max(0.0, min(1.0, float(entry.confidence)))

        with self.memories_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

        self._bump_stats(kind=entry.kind, source=entry.source)
        return entry

    def _bump_stats(self, *, kind: str, source: str) -> None:
        stats: dict[str, Any] = {
            "total_writes": 0,
            "by_kind": {},
            "by_source": {},
            "updated_at": _utc_now(),
        }
        if self.stats_path.is_file():
            try:
                stats = json.loads(self.stats_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        stats["total_writes"] = int(stats.get("total_writes") or 0) + 1
        stats.setdefault("by_kind", {})
        stats.setdefault("by_source", {})
        stats["by_kind"][kind] = int(stats["by_kind"].get(kind) or 0) + 1
        stats["by_source"][source] = int(stats["by_source"].get(source) or 0) + 1
        stats["updated_at"] = _utc_now()
        self.stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    def store(
        self,
        *,
        kind: str,
        title: str,
        content: str,
        confidence: float = 0.75,
        source: str = "user",
        program_id: str = "",
        tags: list[str] | None = None,
        links: list[dict[str, str]] | None = None,
        supersedes: str | None = None,
        vault: str = "",
        topic: str = "",
        origin_path: str = "",
        shard_index: int | None = None,
        preserves_source: bool = True,
    ) -> MemoryEntry:
        entry = MemoryEntry(
            memory_id="",
            kind=kind,
            title=title.strip(),
            content=content.strip(),
            confidence=confidence,
            source=source,
            program_id=program_id,
            swarm_id=self.swarm_id,
            tags=list(tags or []),
            links=list(links or []),
            supersedes=supersedes,
            vault=vault,
            topic=topic,
            origin_path=origin_path,
            shard_index=shard_index,
            preserves_source=preserves_source,
        )
        return self._write_entry(entry)

    def recall(self, memory_id: str) -> MemoryEntry | None:
        for entry in reversed(self._load_all()):
            if entry.memory_id == memory_id and entry.active:
                return entry
        return None

    def _signal_score(self, entry: MemoryEntry, query_tokens: set[str]) -> float:
        haystack = " ".join(
            [entry.title, entry.content, entry.kind, entry.source, " ".join(entry.tags)]
        ).lower()
        haystack_tokens = set(_TOKEN_RE.findall(haystack))
        overlap = len(query_tokens & haystack_tokens) if query_tokens else 0
        score = overlap * 3.0
        score += entry.confidence * 2.0
        score += min(entry.access_count, 10) * 0.15
        try:
            created = datetime.fromisoformat(entry.created_at.replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            age_days = max(0, (datetime.now(UTC) - created.astimezone(UTC)).days)
            score += max(0, 1.5 - age_days * 0.05)
        except ValueError:
            pass
        for tag in entry.tags:
            if tag.lower() in query_tokens:
                score += 2.0
        return score

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        kind: str | None = None,
        program_id: str | None = None,
        vault: str | None = None,
        topic: str | None = None,
        ranked: bool = True,
    ) -> list[MemoryEntry]:
        tokens = set(_TOKEN_RE.findall(query.lower()))
        candidates = self._dedupe_by_title(self._active_entries())
        if kind:
            candidates = [entry for entry in candidates if entry.kind == kind]
        if program_id:
            candidates = [
                entry
                for entry in candidates
                if entry.program_id == program_id or not entry.program_id
            ]
        if vault:
            candidates = [
                entry
                for entry in candidates
                if entry.vault == vault or vault in entry.tags or not entry.vault
            ]
        if topic:
            candidates = [
                entry
                for entry in candidates
                if entry.topic == topic or topic in entry.tags or not entry.topic
            ]

        if ranked and query.strip():
            from agentdrive.memory.ranking import rank_memory_candidates

            payload = [
                {
                    "entry": entry,
                    "text": f"{entry.title}\n{entry.content}",
                    "signal_score": self._signal_score(entry, tokens),
                }
                for entry in candidates
            ]
            ordered = rank_memory_candidates(payload, query)
            return [item[1]["entry"] for item in ordered[:limit]]

        ordered = sorted(
            ((self._signal_score(entry, tokens), entry) for entry in candidates),
            key=lambda item: (-item[0], item[1].created_at),
        )
        return [entry for score, entry in ordered[:limit] if score > 0 or not query.strip()]

    def list_recent(self, *, limit: int = 20, kind: str | None = None) -> list[MemoryEntry]:
        entries = self._dedupe_by_title(self._active_entries())
        if kind:
            entries = [entry for entry in entries if entry.kind == kind]
        entries.sort(key=lambda entry: entry.created_at, reverse=True)
        return entries[:limit]

    def count(self) -> int:
        return len(self._dedupe_by_title(self._active_entries()))

    def stats(self) -> dict[str, Any]:
        base = {
            "swarm_id": self.swarm_id,
            "active_memories": self.count(),
            "path": str(self.memories_path),
        }
        if self.stats_path.is_file():
            try:
                base.update(json.loads(self.stats_path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                pass
        by_kind: dict[str, int] = {}
        for entry in self._dedupe_by_title(self._active_entries()):
            by_kind[entry.kind] = by_kind.get(entry.kind, 0) + 1
        base["active_by_kind"] = by_kind
        return base

    def content_hash(self, title: str, content: str) -> str:
        raw = f"{title.strip().lower()}|{content.strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    def has_similar(self, title: str, content: str) -> bool:
        digest = self.content_hash(title, content)
        for entry in self._active_entries():
            if self.content_hash(entry.title, entry.content) == digest:
                return True
        return False
