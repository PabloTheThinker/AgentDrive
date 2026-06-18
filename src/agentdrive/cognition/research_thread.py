"""
Durable multiverse superposition as research-thread manifests (M4).

Links open multiverse sessions to GridEngine research-thread lifecycle.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from agentdrive.cognition.multiverse import MultiverseSession, SessionStatus


def write_durable_research_thread_manifest(
    drive_path: Path,
    session: MultiverseSession,
    *,
    reopen_after_hours: float = 24.0,
) -> Path:
    """Write research-thread-manifest observation linked to a multiverse session."""
    obs_dir = (
        Path(drive_path) / "observations" / "meta-evolution" / "multiverse" / "research-threads"
    )
    obs_dir.mkdir(parents=True, exist_ok=True)
    slug = f"multiverse-research-thread-{session.session_id}"
    path = obs_dir / f"{slug}.json"

    payload = {
        "page_type": "research-thread-manifest",
        "id": slug,
        "multiverse_session_id": session.session_id,
        "trigger": session.trigger,
        "status": session.status.value,
        "correlation_id": session.correlation_id,
        "cycle_id": session.cycle_id,
        "branch_count": len(session.branches),
        "durable": True,
        "reopen_after_hours": reopen_after_hours,
        "constitution_ref": "research-constitution-multiverse-cognition@stabilization-wave-20260531",
        "created_at": session.created_at,
        "timestamp": time.time(),
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def list_durable_manifests(drive_path: Path, *, limit: int = 20) -> list[dict[str, Any]]:
    d = Path(drive_path) / "observations" / "meta-evolution" / "multiverse" / "research-threads"
    if not d.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(d.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def find_stale_open_sessions(
    drive_path: Path,
    *,
    max_age_hours: float = 24.0,
) -> list[str]:
    """Return session ids that are open and older than max_age_hours."""
    from agentdrive.cognition.store import MultiverseSessionStore

    store = MultiverseSessionStore(Path(drive_path))
    cutoff = time.time() - (max_age_hours * 3600)
    stale: list[str] = []
    for session in store.list_recent(limit=50):
        if session.status == SessionStatus.OPEN and session.created_at < cutoff:
            stale.append(session.session_id)
    return stale
