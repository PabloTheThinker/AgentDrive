"""AgentDrive Snapshot Backup — the recovery layer.

Per the v2 design (``docs/AGENTDRIVE-V2-INHERITANCE.md``), every agent's
Drive state is captured as a point-in-time snapshot every 6 hours by
default. Snapshots are **pointer-only** — they reference object hashes
in the shared content store from Milestone 1, so cost is just the delta.

The localhost UI at ``http://localhost:8420/`` is a tiny stdlib-only
web app (no Flask / FastAPI dep) for restore / cadence control /
on-demand snapshots. Loopback-only by default.
"""

from .snapshot import (
    DEFAULT_CADENCE_SECONDS,
    SnapshotEntry,
    SnapshotError,
    SnapshotManager,
)

__all__ = [
    "SnapshotManager",
    "SnapshotEntry",
    "SnapshotError",
    "DEFAULT_CADENCE_SECONDS",
]
