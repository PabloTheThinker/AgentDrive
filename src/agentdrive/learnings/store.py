"""gstack-style append-only project learnings (JSONL per repo slug).

Operational memory across sessions — lightweight companion to the heavier
Experience Graph / genome layer. Stored at::

    ~/.agentdrive/learnings/<slug>.jsonl

Each line is a JSON object with schema::

    {skill, type, key, insight, confidence, source, ts}
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentdrive.constants import get_learnings_dir

ALLOWED_TYPES = frozenset(
    {
        "pattern",
        "pitfall",
        "preference",
        "architecture",
        "tool",
        "operational",
        "investigation",
    }
)
ALLOWED_SOURCES = frozenset({"observed", "user-stated", "inferred", "cross-model"})
_KEY_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_SLUG_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _sanitize_slug(raw: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "-", raw.strip())
    return cleaned or "default"


def _git_repo_root(path: Path) -> Path | None:
    for parent in [path, *path.parents]:
        if (parent / ".git").is_dir():
            return parent
    return None


def resolve_learnings_slug(cwd: Path | str | None = None) -> str:
    """Derive slug from git repo basename, else ``default``."""
    start = Path(cwd or Path.cwd()).resolve()
    root = _git_repo_root(start)
    if root is not None:
        return _sanitize_slug(root.name)
    return "default"


def _effective_confidence(entry: dict[str, Any], *, now: datetime | None = None) -> int:
    conf = int(entry.get("confidence") or 5)
    source = str(entry.get("source") or "")
    if source not in ("observed", "inferred"):
        return conf
    ts_raw = entry.get("ts")
    if not ts_raw:
        return conf
    try:
        ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
    except ValueError:
        return conf
    now = now or datetime.now(UTC)
    days = max(0, (now - ts.astimezone(UTC)).days)
    return max(0, conf - days // 30)


def _parse_ts(entry: dict[str, Any]) -> datetime:
    ts_raw = entry.get("ts")
    if not ts_raw:
        return datetime.min.replace(tzinfo=UTC)
    try:
        ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return ts.astimezone(UTC)
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)


def _dedupe_latest(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Latest winner per key+type (gstack read-time dedup semantics)."""
    seen: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = str(entry.get("key") or "")
        typ = str(entry.get("type") or "")
        if not key or not typ:
            continue
        dk = f"{key}|{typ}"
        existing = seen.get(dk)
        if existing is None or _parse_ts(entry) > _parse_ts(existing):
            seen[dk] = entry
    return list(seen.values())


class LearningsStore:
    """Append-only JSONL store for cross-session operational learnings."""

    def __init__(self, slug: str | None = None, *, path: Path | None = None) -> None:
        self.slug = _sanitize_slug(slug) if slug else resolve_learnings_slug()
        if path is not None:
            self.path = Path(path)
        else:
            learnings_dir = get_learnings_dir()
            learnings_dir.mkdir(parents=True, exist_ok=True)
            self.path = learnings_dir / f"{self.slug}.jsonl"

    def _load_raw(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict):
                    out.append(data)
        return out

    def _entries(self) -> list[dict[str, Any]]:
        return _dedupe_latest(self._load_raw())

    def log(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Append one learning entry. Returns the normalized record written."""
        typ = str(entry.get("type") or "")
        if typ not in ALLOWED_TYPES:
            raise ValueError(
                f"invalid learning type {typ!r}; must be one of: {sorted(ALLOWED_TYPES)}"
            )

        key = str(entry.get("key") or "")
        if not key or not _KEY_RE.match(key):
            raise ValueError("key must be alphanumeric with hyphens/underscores only")

        insight = str(entry.get("insight") or "").strip()
        if not insight:
            raise ValueError("insight is required")

        conf = entry.get("confidence", 5)
        if not isinstance(conf, int) or conf < 1 or conf > 10:
            raise ValueError("confidence must be an integer from 1 to 10")

        source = str(entry.get("source") or "observed")
        if source not in ALLOWED_SOURCES:
            raise ValueError(
                f"invalid source {source!r}; must be one of: {sorted(ALLOWED_SOURCES)}"
            )

        record: dict[str, Any] = {
            "skill": str(entry.get("skill") or "harness"),
            "type": typ,
            "key": key,
            "insight": insight,
            "confidence": conf,
            "source": source,
            "ts": str(entry.get("ts") or _utc_now_iso()),
        }
        if entry.get("files"):
            record["files"] = list(entry["files"])

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        return record

    def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        """Token-OR search over key/insight/files; sort by confidence then recency."""
        tokens = [t.lower() for t in query.split() if t.strip()]
        results = self._entries()
        if tokens:
            filtered: list[dict[str, Any]] = []
            for entry in results:
                haystacks = [
                    str(entry.get("key") or "").lower(),
                    str(entry.get("insight") or "").lower(),
                    *[str(f).lower() for f in (entry.get("files") or [])],
                ]
                if any(tok in h for h in haystacks for tok in tokens):
                    filtered.append(entry)
            results = filtered

        now = datetime.now(UTC)

        def sort_key(entry: dict[str, Any]) -> tuple[int, float]:
            return (_effective_confidence(entry, now=now), _parse_ts(entry).timestamp())

        results.sort(key=sort_key, reverse=True)
        return results[: max(0, limit)]

    def list_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        """Most recent deduplicated entries."""
        entries = self._entries()
        entries.sort(key=_parse_ts, reverse=True)
        return entries[: max(0, limit)]

    def count(self) -> int:
        """Count deduplicated learnings."""
        return len(self._entries())
