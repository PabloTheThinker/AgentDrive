"""
storage — run layout, checkpoints, locks, and staged promotion artifacts for dreaming.

Design goals:
- Keep dream writes isolated under ~/.agentdrive/dreams/ until explicit commit.
- Make every phase replayable, auditable, and reversible by dream_run_id.
- No new magic — just disciplined composition + Agent Drive / Genome idioms.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from agentdrive.dreaming.candidate import DreamCandidate
from agentdrive.dreaming.dilation import SleepWindow
from agentdrive.genome.models import Genome


@dataclass
class DreamPaths:
    """Filesystem layout for dream runs and staged artifacts."""

    root: Path = field(default_factory=lambda: Path.home() / ".agentdrive" / "dreams")
    runs: Path = field(default_factory=lambda: Path.home() / ".agentdrive" / "dreams" / "runs")
    checkpoints: Path = field(
        default_factory=lambda: Path.home() / ".agentdrive" / "dreams" / "checkpoints"
    )
    promotions: Path = field(
        default_factory=lambda: Path.home() / ".agentdrive" / "dreams" / "promotions"
    )
    diary: Path = field(default_factory=lambda: Path.home() / ".agentdrive" / "dreams" / "diary")
    locks: Path = field(default_factory=lambda: Path.home() / ".agentdrive" / "dreams" / "locks")
    snapshots: Path = field(
        default_factory=lambda: Path.home() / ".agentdrive" / "dreams" / "snapshots"
    )


@dataclass
class DreamRunRecord:
    """Metadata for one dream run."""

    run_id: str = ""
    created_at: float = 0.0
    status: str = "created"
    run_dir: Path | None = None
    snapshot_manifest: Path | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class PhaseCheckpoint:
    """Checkpoint emitted after each dream phase completes or aborts."""

    run_id: str = ""
    phase: str = ""
    status: str = "started"
    started_at: float = 0.0
    completed_at: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)
    artifact_paths: list[Path] = field(default_factory=list)


@dataclass
class DreamStorage:
    """Storage manager for locks, manifests, checkpoints, and staged promotions."""

    paths: DreamPaths = field(default_factory=DreamPaths)

    def ensure_layout(self) -> DreamPaths:
        """Create the standard dream directory layout if it does not already exist."""
        for path in [
            self.paths.root,
            self.paths.runs,
            self.paths.checkpoints,
            self.paths.promotions,
            self.paths.diary,
            self.paths.locks,
            self.paths.snapshots,
        ]:
            path.mkdir(parents=True, exist_ok=True)
        return self.paths

    def acquire_lock(self, name: str = "dreaming") -> Path | None:
        """Acquire a coarse-grained lock for a dream run."""
        self.ensure_layout()
        lock_path = self.paths.locks / f"{name}.lock"
        if lock_path.exists():
            return None
        lock_path.write_text(
            json.dumps({"created_at": time.time(), "name": name}) + "\n", encoding="utf-8"
        )
        return lock_path

    def release_lock(self, lock_path: Path | None) -> None:
        """Release a previously acquired dream lock."""
        if lock_path is None:
            return
        try:
            lock_path.unlink()
        except FileNotFoundError:
            return

    def create_run(self, window: SleepWindow | None = None) -> DreamRunRecord:
        """Create a new run directory and metadata record."""
        self.ensure_layout()
        created_at = time.time()
        run_id = f"dream-{int(created_at)}"
        run_dir = self.paths.runs / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        record = DreamRunRecord(
            run_id=run_id,
            created_at=created_at,
            run_dir=run_dir,
            provenance={"origin": "loom_dreaming", "window": asdict(window) if window else None},
        )
        (run_dir / "manifest.json").write_text(
            json.dumps(asdict(record), sort_keys=True, default=str) + "\n", encoding="utf-8"
        )
        return record

    def write_snapshot_manifest(self, run: DreamRunRecord, snapshot: dict[str, Any]) -> Path:
        """Persist the snapshot manifest used to isolate dreaming from waking state."""
        self.ensure_layout()
        manifest_path = self.paths.snapshots / f"{run.run_id}.json"
        payload = {"run_id": run.run_id, "created_at": time.time(), "snapshot": snapshot}
        manifest_path.write_text(
            json.dumps(payload, sort_keys=True, default=str) + "\n", encoding="utf-8"
        )
        run.snapshot_manifest = manifest_path
        return manifest_path

    def write_phase_checkpoint(self, checkpoint: PhaseCheckpoint) -> Path:
        """Write a phase checkpoint artifact."""
        self.ensure_layout()
        checkpoint_path = self.paths.checkpoints / f"{checkpoint.run_id}-{checkpoint.phase}.json"
        checkpoint_path.write_text(
            json.dumps(asdict(checkpoint), sort_keys=True, default=str) + "\n", encoding="utf-8"
        )
        return checkpoint_path

    def stage_promotion(self, run: DreamRunRecord, lane: str, candidate: DreamCandidate) -> Path:
        """Stage a promotion artifact under the dreams namespace."""
        lane_root = self.paths.promotions / lane
        lane_root.mkdir(parents=True, exist_ok=True)
        safe_id = candidate.candidate_id.replace("/", "_")
        artifact_path = lane_root / f"{run.run_id}-{safe_id}.json"
        payload = {
            "run_id": run.run_id,
            "lane": lane,
            "candidate": asdict(candidate),
            "staged_at": time.time(),
        }
        artifact_path.write_text(
            json.dumps(payload, sort_keys=True, default=str) + "\n", encoding="utf-8"
        )
        return artifact_path

    def commit_run(self, run: DreamRunRecord) -> None:
        """Mark a dream run as committed and eligible for waking-state backfill."""
        run.status = "committed"
        if run.run_dir:
            (run.run_dir / "status.json").write_text(
                json.dumps(asdict(run), sort_keys=True, default=str) + "\n", encoding="utf-8"
            )

    def rollback_run(self, run: DreamRunRecord, reason: str) -> None:
        """Rollback a run by marking its staged artifacts as retracted."""
        run.status = "rolled_back"
        if run.run_dir:
            payload = {"run_id": run.run_id, "reason": reason, "rolled_back_at": time.time()}
            (run.run_dir / "rollback.json").write_text(
                json.dumps(payload, sort_keys=True, default=str) + "\n", encoding="utf-8"
            )


def genome_storage_anchor(genome: Genome | None) -> str:
    """Return a stable Genome anchor for future staged promotion payloads."""
    return genome.genome_id if genome else ""
