"""
cycle — phased gbrain-style dream cycle for AgentDrive maintenance.

Composes existing dreaming / reconciliation / confidence / KG primitives into a
single ordered pass: reconcile → extract_links → consolidate → grade_confidence →
purge_stale. Append-only audit log + coarse home-level lock for safe scheduling.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentdrive.constants import get_agentdrive_home
from agentdrive.drive.drive import AgentDrive, get_default_drive
from agentdrive.registry import GenomeRegistry
from agentdrive.reconciliation import ReconciliationRunner

logger = logging.getLogger(__name__)

DREAM_LOCK_NAME = "dream.lock"
DREAM_AUDIT_REL = Path("logs") / "dream-cycle.jsonl"


def _publish_dream_phase_event(
    result: "DreamCycleResult",
    *,
    run_id: str,
    stop_gate: bool,
) -> None:
    """Emit DreamPhaseEvent to Mission Control (silent when hub unavailable)."""
    try:
        from agentdrive.mission_control.events import DreamPhaseEvent
        from agentdrive.mission_control.server import publish_event_sync

        publish_event_sync(
            DreamPhaseEvent(
                event_type="dream_phase",
                timestamp=time.time(),
                phase_id=result.phase_id,
                phase_name=result.phase_name,
                success=result.success,
                dry_run=result.dry_run,
                duration_ms=result.duration_ms,
                stop_gate=stop_gate,
                run_id=run_id,
                detail=result.detail,
                metadata={"source": "dreaming.cycle", "stabilization_wave": "stabilization-wave-20260531"},
            )
        )
    except Exception:
        pass


@dataclass(frozen=True)
class DreamPhaseSpec:
    """One phase in the ordered dream cycle."""

    id: str
    name: str
    stop_gate: bool = False


DREAM_PHASES: tuple[DreamPhaseSpec, ...] = (
    DreamPhaseSpec(id="reconcile", name="Reconcile", stop_gate=False),
    DreamPhaseSpec(id="extract_links", name="Extract Links", stop_gate=False),
    DreamPhaseSpec(id="consolidate", name="Consolidate", stop_gate=True),
    DreamPhaseSpec(id="grade_confidence", name="Grade Confidence", stop_gate=False),
    DreamPhaseSpec(id="purge_stale", name="Purge Stale", stop_gate=True),
)

_PHASE_BY_ID: dict[str, DreamPhaseSpec] = {p.id: p for p in DREAM_PHASES}


@dataclass
class DreamCycleResult:
    """Outcome for a single dream phase execution."""

    phase_id: str
    phase_name: str
    success: bool
    message: str
    detail: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0
    dry_run: bool = False


class DreamCyclePending(Exception):
    """Raised when a STOP gate pauses the cycle for operator acknowledgement."""

    def __init__(self, phase_id: str, message: str) -> None:
        self.phase_id = phase_id
        self.message = message
        super().__init__(message)


class DreamCycleLockError(Exception):
    """Raised when another process holds the dream cycle lock."""


@dataclass
class _DreamLock:
    """Coarse process lock at ``~/.agentdrive/dream.lock`` (fcntl when available)."""

    path: Path
    _fd: int | None = field(default=None, repr=False)

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(self.path), os.O_CREAT | os.O_RDWR, 0o644)
        try:
            try:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except ImportError:
                pass
            except BlockingIOError:
                os.close(fd)
                return False
            payload = json.dumps({"pid": os.getpid(), "created_at": time.time()}) + "\n"
            os.ftruncate(fd, 0)
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, payload.encode("utf-8"))
            self._fd = fd
            return True
        except Exception:
            os.close(fd)
            raise

    def release(self) -> None:
        if self._fd is None:
            return
        try:
            try:
                import fcntl

                fcntl.flock(self._fd, fcntl.LOCK_UN)
            except ImportError:
                pass
        finally:
            os.close(self._fd)
            self._fd = None
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass


def dream_lock_path(home: Path | None = None) -> Path:
    """Return the canonical dream cycle lock path under AgentDrive home."""
    return (home or get_agentdrive_home()) / DREAM_LOCK_NAME


def dream_audit_log_path(home: Path | None = None) -> Path:
    """Return the append-only dream cycle audit log path."""
    return (home or get_agentdrive_home()) / DREAM_AUDIT_REL


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _resolve_pool_and_registry(
    drive_path: Path | str | None,
    *,
    home: Path | None = None,
) -> tuple[AgentDrive, GenomeRegistry]:
    if drive_path is not None:
        root = Path(drive_path)
        pool = AgentDrive(drive_path=root)
        registry = (
            pool.registry
            if hasattr(pool, "registry") and pool.registry is not None
            else GenomeRegistry(root=root / "genomes")
        )
        return pool, registry
    if home is not None:
        # Fresh pool per home — avoids stale ``get_global_drive()`` singleton in tests.
        pool = AgentDrive(drive_path=Path(home) / "drive")
        registry = pool.registry if hasattr(pool, "registry") else GenomeRegistry()
        return pool, registry
    pool = get_default_drive()
    registry = pool.registry if hasattr(pool, "registry") else GenomeRegistry()
    return pool, registry


def _append_audit(
    *,
    run_id: str,
    result: DreamCycleResult,
    home: Path,
    extra: dict[str, Any] | None = None,
) -> None:
    log_path = dream_audit_log_path(home)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": _utc_now_iso(),
        "run_id": run_id,
        "phase_id": result.phase_id,
        "phase_name": result.phase_name,
        "success": result.success,
        "message": result.message,
        "duration_ms": result.duration_ms,
        "dry_run": result.dry_run,
        "detail": result.detail,
    }
    if extra:
        entry.update(extra)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")


def _run_reconcile(
    *,
    pool: AgentDrive,
    registry: GenomeRegistry,
    dry_run: bool,
    state_path: Path | None = None,
) -> DreamCycleResult:
    runner = ReconciliationRunner(registry=registry, pool=pool, state_path=state_path)
    t0 = time.monotonic()
    if dry_run:
        status = runner.status()
        detail = dict(status)
        msg = "Reconciliation status (dry-run; scan skipped)"
        success = bool(status.get("ok", True))
    else:
        report = runner.scan_once()
        detail = report.to_dict()
        msg = (
            f"Reconciliation: {len(report.new_genomes)} new, "
            f"{len(report.updated_genomes)} updated"
        )
        success = True
    return DreamCycleResult(
        phase_id="reconcile",
        phase_name="Reconcile",
        success=success,
        message=msg,
        detail=detail,
        duration_ms=int((time.monotonic() - t0) * 1000),
        dry_run=dry_run,
    )


def _run_extract_links(
    *,
    registry: GenomeRegistry,
    pool: AgentDrive,
    dry_run: bool,
) -> DreamCycleResult:
    t0 = time.monotonic()
    genome_names = registry.list_genomes()
    entities_total = 0
    edges_total = 0
    genomes_processed = 0
    errors: list[str] = []
    ingest_hints = 0

    try:
        from agentdrive.knowledge_graph.link_extraction import extract_from_genome
    except Exception as exc:
        extract_from_genome = None  # type: ignore[assignment]
        errors.append(f"link_extraction unavailable: {exc}")

    if extract_from_genome is not None:
        for name in genome_names:
            try:
                genome = registry.load(name)
                if genome is None:
                    continue
                entities, edges = extract_from_genome(genome)
                entities_total += len(entities)
                edges_total += len(edges)
                genomes_processed += 1
            except Exception as exc:
                errors.append(f"{name}: {exc}")

    if genomes_processed == 0:
        for entry in getattr(pool, "_ingest_log", []) or []:
            ingest_hints += 1
            if ingest_hints >= 50:
                break

    detail = {
        "genomes_seen": len(genome_names),
        "genomes_processed": genomes_processed,
        "entities_extracted": entities_total,
        "edges_extracted": edges_total,
        "ingest_log_entries_scanned": ingest_hints,
        "errors": errors[:10],
    }
    if dry_run:
        msg = (
            f"Link extraction dry-run: {genomes_processed} genome(s) scanned, "
            f"{edges_total} edge(s) (no graph write)"
        )
    else:
        msg = (
            f"Link extraction: {genomes_processed} genome(s), "
            f"{entities_total} entities, {edges_total} edges"
        )
    return DreamCycleResult(
        phase_id="extract_links",
        phase_name="Extract Links",
        success=True,
        message=msg,
        detail=detail,
        duration_ms=int((time.monotonic() - t0) * 1000),
        dry_run=dry_run,
    )


def _run_consolidate(*, dry_run: bool) -> DreamCycleResult:
    t0 = time.monotonic()
    if dry_run:
        detail = {
            "phase": "consolidate",
            "mode": "dry-run",
            "skipped": True,
            "would_run": ["run_consolidation_light_phase", "run_daily_consolidation_job"],
        }
        return DreamCycleResult(
            phase_id="consolidate",
            phase_name="Consolidate",
            success=True,
            message="Consolidation skipped in dry-run (light + daily stub paths)",
            detail=detail,
            duration_ms=int((time.monotonic() - t0) * 1000),
            dry_run=True,
        )

    detail: dict[str, Any] = {}
    try:
        from agentdrive.dreaming.durable import (
            run_consolidation_light_phase,
            run_daily_consolidation_job,
        )

        light = run_consolidation_light_phase()
        detail["light"] = {
            "phase": light.get("phase"),
            "scan_keys": list((light.get("scans") or {}).keys()),
        }
        # Daily consolidation is heavy; use light result as primary and note daily stub.
        detail["daily_stub"] = {
            "callable": "run_daily_consolidation_job",
            "invoked": False,
            "reason": "dream-cycle uses light phase; schedule daily via DurableJobSupervisor",
        }
        _ = run_daily_consolidation_job  # bound for supervisor scheduling reference
        msg = "Consolidation light phase complete (daily job available via supervisor)"
        success = True
    except Exception as exc:
        logger.warning("consolidate phase failed", exc_info=True)
        detail = {"error": str(exc)}
        msg = f"Consolidation failed: {exc}"
        success = False

    return DreamCycleResult(
        phase_id="consolidate",
        phase_name="Consolidate",
        success=success,
        message=msg,
        detail=detail,
        duration_ms=int((time.monotonic() - t0) * 1000),
        dry_run=False,
    )


def _run_grade_confidence(*, registry: GenomeRegistry) -> DreamCycleResult:
    from agentdrive.confidence import get_rating

    t0 = time.monotonic()
    ratings: list[dict[str, Any]] = []
    for gid in registry.list_genomes():
        rating = get_rating(gid, registry)
        if rating is None:
            continue
        ratings.append(
            {
                "genome_id": gid,
                "stars": rating.stars,
                "encounters": rating.encounters,
                "success_rate": rating.success_rate,
            }
        )
    detail = {
        "genomes_checked": len(registry.list_genomes()),
        "ratings_found": len(ratings),
        "ratings": ratings[:25],
    }
    return DreamCycleResult(
        phase_id="grade_confidence",
        phase_name="Grade Confidence",
        success=True,
        message=f"Graded confidence for {len(ratings)} genome(s) with sidecars",
        detail=detail,
        duration_ms=int((time.monotonic() - t0) * 1000),
        dry_run=False,
    )


def _run_purge_stale(*, dry_run: bool, swarm_id: str | None = None) -> DreamCycleResult:
    t0 = time.monotonic()
    stale: list[dict[str, Any]] = []
    try:
        from agentdrive.knowledge_graph.graph import get_stale_entities

        stale = get_stale_entities(swarm_id=swarm_id) or []
    except Exception as exc:
        logger.debug("get_stale_entities unavailable", exc_info=True)
        return DreamCycleResult(
            phase_id="purge_stale",
            phase_name="Purge Stale",
            success=True,
            message=f"Stale scan skipped (best effort): {exc}",
            detail={"stale_count": 0, "purged": 0, "dry_run": dry_run},
            duration_ms=int((time.monotonic() - t0) * 1000),
            dry_run=dry_run,
        )

    purged = 0
    if dry_run:
        msg = f"Stale report only (dry-run): {len(stale)} entity(ies), nothing removed"
    else:
        msg = f"Stale report: {len(stale)} entity(ies) (non-destructive; no purge executed)"
    detail = {
        "stale_count": len(stale),
        "stale_sample": stale[:15],
        "purged": purged,
        "destructive": False,
    }
    return DreamCycleResult(
        phase_id="purge_stale",
        phase_name="Purge Stale",
        success=True,
        message=msg,
        detail=detail,
        duration_ms=int((time.monotonic() - t0) * 1000),
        dry_run=dry_run,
    )


_PHASE_RUNNERS = {
    "reconcile": lambda *, pool, registry, dry_run, swarm_id, state_path: _run_reconcile(
        pool=pool, registry=registry, dry_run=dry_run, state_path=state_path
    ),
    "extract_links": lambda *, pool, registry, dry_run, swarm_id, state_path: _run_extract_links(
        registry=registry, pool=pool, dry_run=dry_run
    ),
    "consolidate": lambda *, pool, registry, dry_run, swarm_id, state_path: _run_consolidate(
        dry_run=dry_run
    ),
    "grade_confidence": lambda *, pool, registry, dry_run, swarm_id, state_path: _run_grade_confidence(
        registry=registry
    ),
    "purge_stale": lambda *, pool, registry, dry_run, swarm_id, state_path: _run_purge_stale(
        dry_run=dry_run, swarm_id=swarm_id
    ),
}


def run_dream_cycle(
    drive_path: Path | str | None = None,
    phases: list[str] | None = None,
    dry_run: bool = False,
    ack_phases: list[str] | None = None,
    *,
    acquire_lock: bool = True,
    home: Path | None = None,
) -> list[DreamCycleResult]:
    """Execute the ordered dream maintenance cycle.

    Parameters
    ----------
    drive_path:
        Optional pool root; defaults to ``get_default_drive()``.
    phases:
        Subset of phase ids to run (default: all ``DREAM_PHASES``).
    dry_run:
        Skip destructive / heavy writes; reconciliation uses status only.
    ack_phases:
        Phase ids whose STOP gates are acknowledged (resume after pause).
    acquire_lock:
        When True (default), take ``dream.lock`` for the whole run.
    home:
        Override AgentDrive home (for tests); defaults to ``get_agentdrive_home()``.
    """
    agent_home = home or get_agentdrive_home()
    run_id = f"dream-{uuid.uuid4().hex[:12]}"
    ack_set = set(ack_phases or [])

    selected: list[DreamPhaseSpec] = []
    if phases:
        for pid in phases:
            spec = _PHASE_BY_ID.get(pid)
            if spec is None:
                raise ValueError(f"Unknown dream phase: {pid}")
            selected.append(spec)
    else:
        selected = list(DREAM_PHASES)

    lock = _DreamLock(dream_lock_path(agent_home))
    if acquire_lock:
        if not lock.acquire():
            raise DreamCycleLockError(
                f"Dream cycle already running (lock held at {dream_lock_path(agent_home)})"
            )

    results: list[DreamCycleResult] = []
    try:
        pool, registry = _resolve_pool_and_registry(drive_path, home=agent_home)
        swarm_id = getattr(pool, "swarm_id", None)
        recon_state = agent_home / "reconciliation.json"

        for spec in selected:
            t_phase = time.monotonic()
            runner = _PHASE_RUNNERS[spec.id]
            result = runner(
                pool=pool,
                registry=registry,
                dry_run=dry_run,
                swarm_id=swarm_id,
                state_path=recon_state,
            )
            result.dry_run = dry_run
            result.duration_ms = result.duration_ms or int((time.monotonic() - t_phase) * 1000)
            results.append(result)
            _append_audit(run_id=run_id, result=result, home=agent_home, extra={"run_complete": False})
            _publish_dream_phase_event(result, run_id=run_id, stop_gate=spec.stop_gate)

            if not result.success:
                break

            if spec.stop_gate and not dry_run and spec.id not in ack_set:
                _append_audit(
                    run_id=run_id,
                    result=result,
                    home=agent_home,
                    extra={"stop_gate": spec.id, "run_complete": False},
                )
                raise DreamCyclePending(
                    spec.id,
                    f"STOP gate at {spec.name}: {result.message}",
                )

        if results:
            _append_audit(
                run_id=run_id,
                result=results[-1],
                home=agent_home,
                extra={"run_complete": True, "phases_run": len(results)},
            )
    finally:
        if acquire_lock:
            lock.release()

    return results


def get_dream_cycle_status(*, home: Path | None = None) -> dict[str, Any]:
    """Return lock + last audit entry snapshot for CLI ``dream status``."""
    agent_home = home or get_agentdrive_home()
    lock_path = dream_lock_path(agent_home)
    audit_path = dream_audit_log_path(agent_home)
    status: dict[str, Any] = {
        "lock_path": str(lock_path),
        "lock_held": lock_path.is_file(),
        "audit_log": str(audit_path),
        "last_run": None,
        "phases": [asdict(p) for p in DREAM_PHASES],
    }
    if audit_path.is_file():
        try:
            last_line = ""
            with audit_path.open(encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        last_line = line.strip()
            if last_line:
                status["last_run"] = json.loads(last_line)
        except Exception as exc:
            status["last_run_error"] = str(exc)
    return status


__all__ = [
    "DREAM_PHASES",
    "DreamCycleLockError",
    "DreamCyclePending",
    "DreamCycleResult",
    "DreamPhaseSpec",
    "dream_audit_log_path",
    "dream_lock_path",
    "get_dream_cycle_status",
    "run_dream_cycle",
]