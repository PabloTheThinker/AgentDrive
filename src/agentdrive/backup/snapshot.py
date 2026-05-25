"""Point-in-time Snapshot Backup for AgentDrive.

A snapshot is a pointer-only manifest naming the content hashes that
make up an agent's Drive at one moment in time. The content bytes live
in the Milestone-1 content store and are shared across snapshots — so
adding a snapshot of an unchanged Drive costs basically nothing.

Layout on disk:

```
~/.agentdrive/backups/
└── <agent_id>/
    ├── 2026-05-24T18:00:00Z/
    │   └── manifest.json    # { hashes: [...], cadence_id, taken_at, ... }
    ├── 2026-05-25T00:00:00Z/
    └── _retention.json      # rolling policy
```

Cadence (default 6h) is enforced by ``snapshot_if_due()``; callers wire
that to a cron / scheduler / loop / whatever fits their runtime. The
``SnapshotManager`` itself is sleep-free and side-effect-bounded so it's
testable.

Restore is a read operation: ``restore(snapshot_id)`` returns the list
of content hashes from that snapshot, and the caller decides what to
rebuild. We do NOT mutate Drive state during restore — destroying live
data is the operator's call, not ours.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from agentdrive.drive.content_store import ContentStore

logger = logging.getLogger(__name__)


DEFAULT_CADENCE_SECONDS = 6 * 60 * 60  # 6 hours
"""Default time between automatic snapshots. Configurable per agent."""

DEFAULT_RETENTION = {
    "keep_hourly": 6,  # last 6 hourly snapshots
    "keep_daily": 7,  # last 7 daily snapshots
    "keep_weekly": 4,  # last 4 weekly snapshots
}


class SnapshotError(Exception):
    """Raised on snapshot integrity failures (missing manifest, hash drift)."""


@dataclass(frozen=True)
class SnapshotEntry:
    """One snapshot, as returned by ``list_snapshots()`` / ``get()``."""

    snapshot_id: str  # ISO-8601 UTC of taken_at, used as the dir name
    agent_id: str
    taken_at: float  # unix epoch
    hashes: list[str]  # content hashes captured at this point
    drive_path: str  # the on-disk Drive path snapshotted (for restore context)
    cadence_id: str  # "scheduled" | "on-demand" | "test"
    pinned: bool = False  # if True, retention policy will not evict


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


import re as _re

# Identifiers that flow into filesystem paths from the web UI must match
# this whitelist — letters, digits, dot, underscore, dash, colon. No
# slashes, no '..', no NULs. Path-traversal defense per the security audit.
_SAFE_ID_RE = _re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _validate_id(label: str, value: str) -> str:
    """Reject any agent_id / snapshot_id that could escape its parent dir.
    Raises ValueError so the HTTP layer can return a clean 400.
    """
    if not isinstance(value, str) or not _SAFE_ID_RE.match(value):
        raise ValueError(f"{label} must match [A-Za-z0-9._:-]{{1,128}} — got {value!r}")
    if value in (".", ".."):
        raise ValueError(f"{label} cannot be a directory traversal segment")
    return value


class SnapshotManager:
    """Per-agent snapshot store. Cheap to instantiate.

    Pass ``drive_path`` pointing at the Drive root you want to snapshot
    (this is whatever contains an ``objects/`` directory the content
    store wrote into — Personal Drive, DNA Drive, or a swarm Drive).

    **Security note.** ``agent_id`` and any caller-supplied ``snapshot_id``
    are passed through ``_validate_id`` because they end up joined into
    filesystem paths under ``backup_root``. A malicious value like
    ``../../etc`` could otherwise escape the backup tree.
    """

    def __init__(
        self,
        agent_id: str,
        drive_path: Path,
        backup_root: Path,
        *,
        cadence_seconds: int = DEFAULT_CADENCE_SECONDS,
    ):
        self.agent_id = _validate_id("agent_id", agent_id)
        self.drive_path = Path(drive_path)
        self.backup_root = Path(backup_root)
        self.agent_backups = self.backup_root / self.agent_id
        # After joining, double-check the resolved path is genuinely a
        # descendant of backup_root. Defends against future regressions
        # in the validator and surfaces symlink escapes.
        resolved = self.agent_backups.resolve()
        if not str(resolved).startswith(str(self.backup_root.resolve())):
            raise ValueError(
                f"agent_id {agent_id!r} resolved outside backup_root — "
                f"path traversal attempt blocked"
            )
        self.agent_backups.mkdir(parents=True, exist_ok=True)
        self.cadence_seconds = cadence_seconds
        self._content_store = ContentStore(self.drive_path)

    # ── public API ──────────────────────────────────────────────────────────

    def take(self, *, cadence_id: str = "on-demand") -> SnapshotEntry:
        """Capture an immediate snapshot. Returns the SnapshotEntry.

        Snapshots are pointer-only — we write a manifest of hashes, NOT a
        copy of the object bytes. Cheap, idempotent across unchanged
        Drives, and the cost is bounded by the number of hashes not by
        their size.
        """
        ts = time.time()
        sid = _iso(ts)
        snap_dir = self.agent_backups / sid
        snap_dir.mkdir(parents=True, exist_ok=True)

        hashes = sorted(self._content_store.iter_hashes())

        entry = SnapshotEntry(
            snapshot_id=sid,
            agent_id=self.agent_id,
            taken_at=ts,
            hashes=hashes,
            drive_path=str(self.drive_path),
            cadence_id=cadence_id,
            pinned=False,
        )
        (snap_dir / "manifest.json").write_text(
            json.dumps(asdict(entry), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        logger.info(
            "Snapshot taken",
            extra={
                "agent_id": self.agent_id,
                "snapshot_id": sid,
                "hash_count": len(hashes),
                "cadence_id": cadence_id,
            },
        )
        return entry

    def snapshot_if_due(self, *, now: float | None = None) -> SnapshotEntry | None:
        """Take a snapshot only if more than ``cadence_seconds`` have passed
        since the last one. Returns the new entry or None if nothing was
        due. This is the function a scheduler should call on a tick.
        """
        ts = now if now is not None else time.time()
        last = self.last_snapshot()
        if last is not None and ts - last.taken_at < self.cadence_seconds:
            return None
        return self.take(cadence_id="scheduled")

    def list_snapshots(self) -> list[SnapshotEntry]:
        """All snapshots for this agent, sorted newest first."""
        snaps: list[SnapshotEntry] = []
        for child in self.agent_backups.iterdir():
            if not child.is_dir():
                continue
            manifest = child / "manifest.json"
            if not manifest.exists():
                continue
            try:
                d = json.loads(manifest.read_text(encoding="utf-8"))
                snaps.append(SnapshotEntry(**d))
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning(
                    "Skipping corrupt snapshot manifest at %s: %s",
                    manifest,
                    exc,
                )
        snaps.sort(key=lambda s: s.taken_at, reverse=True)
        return snaps

    def last_snapshot(self) -> SnapshotEntry | None:
        snaps = self.list_snapshots()
        return snaps[0] if snaps else None

    def get(self, snapshot_id: str) -> SnapshotEntry:
        # Path-traversal defense — same whitelist as agent_id.
        try:
            snapshot_id = _validate_id("snapshot_id", snapshot_id)
        except ValueError as exc:
            raise SnapshotError(str(exc)) from exc
        manifest = self.agent_backups / snapshot_id / "manifest.json"
        if not manifest.exists():
            raise SnapshotError(f"snapshot {snapshot_id!r} not found")
        d = json.loads(manifest.read_text(encoding="utf-8"))
        return SnapshotEntry(**d)

    def restore(self, snapshot_id: str) -> list[str]:
        """Return the list of content hashes a snapshot captured.

        Deliberately read-only: we don't mutate Drive state because that's
        an operator decision. Caller composes the restore by walking the
        hashes and re-materializing whatever surface they need.
        """
        entry = self.get(snapshot_id)
        # Integrity check — every hash should still be in the content store
        # (snapshots are pointer-only; if the underlying object is gone,
        # restore can't reconstitute it).
        missing = [h for h in entry.hashes if not self._content_store.has(h)]
        if missing:
            raise SnapshotError(
                f"snapshot {snapshot_id} references {len(missing)} content "
                f"hashes that are no longer in the content store"
            )
        return entry.hashes

    def pin(self, snapshot_id: str, pinned: bool = True) -> SnapshotEntry:
        """Pin or unpin a snapshot. Pinned snapshots survive retention GC."""
        entry = self.get(snapshot_id)
        updated = SnapshotEntry(
            snapshot_id=entry.snapshot_id,
            agent_id=entry.agent_id,
            taken_at=entry.taken_at,
            hashes=entry.hashes,
            drive_path=entry.drive_path,
            cadence_id=entry.cadence_id,
            pinned=pinned,
        )
        (self.agent_backups / snapshot_id / "manifest.json").write_text(
            json.dumps(asdict(updated), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return updated

    def delete(self, snapshot_id: str) -> bool:
        """Remove a snapshot manifest (its referenced content bytes stay
        in the content store — they may be referenced by other snapshots
        or live Drive entries). Refuses to delete pinned snapshots."""
        try:
            entry = self.get(snapshot_id)
        except SnapshotError:
            return False
        if entry.pinned:
            raise SnapshotError(f"snapshot {snapshot_id} is pinned; unpin first")

        snap_dir = self.agent_backups / snapshot_id
        for p in snap_dir.iterdir():
            p.unlink()
        snap_dir.rmdir()
        return True

    def stats(self) -> dict:
        snaps = self.list_snapshots()
        return {
            "agent_id": self.agent_id,
            "snapshot_count": len(snaps),
            "newest": snaps[0].snapshot_id if snaps else None,
            "oldest": snaps[-1].snapshot_id if snaps else None,
            "cadence_seconds": self.cadence_seconds,
            "drive_path": str(self.drive_path),
            "backup_root": str(self.backup_root),
        }
