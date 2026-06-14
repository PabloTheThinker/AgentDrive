"""Tests for the phased agentdrive dream cycle."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from agentdrive.dreaming.cycle import (
    DREAM_PHASES,
    DreamCycleLockError,
    dream_audit_log_path,
    dream_lock_path,
    get_dream_cycle_status,
    run_dream_cycle,
)


def test_dream_phases_has_five_entries() -> None:
    assert len(DREAM_PHASES) == 5
    ids = [p.id for p in DREAM_PHASES]
    assert ids == [
        "reconcile",
        "extract_links",
        "consolidate",
        "grade_confidence",
        "purge_stale",
    ]


def test_dry_run_completes_all_phases(isolated_agentdrive_home: Path) -> None:
    results = run_dream_cycle(dry_run=True, home=isolated_agentdrive_home)
    assert len(results) == 5
    assert all(r.success for r in results)
    assert all(r.dry_run for r in results)
    assert [r.phase_id for r in results] == [p.id for p in DREAM_PHASES]


def test_audit_log_written(isolated_agentdrive_home: Path) -> None:
    run_dream_cycle(dry_run=True, home=isolated_agentdrive_home)
    log_path = dream_audit_log_path(isolated_agentdrive_home)
    assert log_path.is_file()
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) >= 5
    entry = json.loads(lines[0])
    assert "phase_id" in entry
    assert "run_id" in entry
    assert entry.get("dry_run") is True


def test_lock_file_created(isolated_agentdrive_home: Path) -> None:
    lock_path = dream_lock_path(isolated_agentdrive_home)
    assert not lock_path.exists()
    run_dream_cycle(dry_run=True, home=isolated_agentdrive_home)
    assert not lock_path.exists()


def test_lock_prevents_concurrent_run(isolated_agentdrive_home: Path) -> None:
    from agentdrive.dreaming.cycle import _DreamLock

    holder = _DreamLock(dream_lock_path(isolated_agentdrive_home))
    assert holder.acquire()
    errors: list[Exception] = []

    def _worker() -> None:
        try:
            run_dream_cycle(dry_run=True, home=isolated_agentdrive_home)
        except DreamCycleLockError as exc:
            errors.append(exc)

    thread = threading.Thread(target=_worker)
    thread.start()
    thread.join(timeout=10)
    holder.release()

    assert len(errors) == 1
    assert isinstance(errors[0], DreamCycleLockError)


def test_get_dream_cycle_status(isolated_agentdrive_home: Path) -> None:
    run_dream_cycle(dry_run=True, home=isolated_agentdrive_home)
    status = get_dream_cycle_status(home=isolated_agentdrive_home)
    assert status["lock_held"] is False
    assert len(status["phases"]) == 5
    assert status["last_run"] is not None
