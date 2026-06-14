"""Ingest gstack-style learnings JSONL into the Drive living-experience layer."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentdrive.learnings.store import LearningsStore

if TYPE_CHECKING:
    from agentdrive.drive.drive import AgentDrive


def _entry_hash(entry: dict[str, Any]) -> str:
    """Stable short hash for idempotent observation ids."""
    payload = {
        "key": entry.get("key"),
        "type": entry.get("type"),
        "insight": entry.get("insight"),
        "ts": entry.get("ts"),
        "skill": entry.get("skill"),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def _observation_from_learning(entry: dict[str, Any], *, slug: str, obs_id: str) -> dict[str, Any]:
    return {
        "schema_version": 3,
        "page_type": "living-experience",
        "type": "learning",
        "id": obs_id,
        "version": "1.0.0",
        "created": str(entry.get("ts") or datetime.now(UTC).isoformat()),
        "content": {
            "title": f"Project learning: {entry.get('key')}",
            "summary": str(entry.get("insight") or ""),
            "learning_type": entry.get("type"),
            "skill": entry.get("skill"),
            "key": entry.get("key"),
            "confidence": entry.get("confidence"),
            "source": entry.get("source"),
            "project_slug": slug,
            "files": list(entry.get("files") or []),
        },
        "provenance": {
            "source": "agentdrive.learnings.ingest_learnings_to_experience",
            "project_slug": slug,
            "ingest_kind": "gstack-style-learnings-jsonl",
        },
    }


def ingest_learnings_to_experience(drive: "AgentDrive", slug: str) -> int:
    """Materialize learnings as living-experience observations (idempotent).

    Skips entries whose observation id ``learnings-<slug>-<hash>`` already exists
    under ``<drive>/living-experience/``.
    """
    store = LearningsStore(slug=slug)
    entries = store._entries()  # noqa: SLF001 — intentional shared dedupe semantics
    if not entries:
        return 0

    obs_dir = Path(drive.drive_path) / "living-experience"
    obs_dir.mkdir(parents=True, exist_ok=True)

    ingested = 0
    for entry in entries:
        digest = _entry_hash(entry)
        obs_id = f"learnings-{store.slug}-{digest}"
        obs_path = obs_dir / f"{obs_id}.json"
        if obs_path.exists():
            continue
        observation = _observation_from_learning(entry, slug=store.slug, obs_id=obs_id)
        obs_path.write_text(json.dumps(observation, indent=2, default=str), encoding="utf-8")
        ingested += 1
    return ingested
