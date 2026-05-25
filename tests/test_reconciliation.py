"""Tests for the pool reconciliation routine.

Covers:
- empty pool reports no changes
- new genomes since last scan are detected
- updated confidence markers are detected
- new ingest events since last scan are detected
- state persists atomically (no corruption mid-write)
- ReconciliationCompleted event fires on every scan
- ReconciliationDelta only fires when there's actually a delta
- background thread lifecycle (start + stop)
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentdrive.confidence import SIDECAR_NAME as CONF_SIDECAR
from agentdrive.confidence import ConfidenceRating
from agentdrive.drive.drive import AgentDrive
from agentdrive.events import (
    ReconciliationCompleted,
    ReconciliationDelta,
    default_bus,
)
from agentdrive.genome.models import Genome, GenomeManifest
from agentdrive.reconciliation import (
    STATE_FILENAME,
    ReconciliationReport,
    ReconciliationRunner,
)
from agentdrive.registry import GenomeRegistry

# ─────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def clean_bus() -> Iterator[None]:
    """Snapshot + restore default_bus subscribers around each test."""
    with default_bus._lock:  # type: ignore[attr-defined]
        saved = list(default_bus._subs)  # type: ignore[attr-defined]
        default_bus._subs.clear()  # type: ignore[attr-defined]
    try:
        yield
    finally:
        with default_bus._lock:  # type: ignore[attr-defined]
            default_bus._subs = saved  # type: ignore[attr-defined]


def _make_genome(gid: str, version: str = "1.0.0", score: float = 0.9) -> Genome:
    manifest = GenomeManifest(
        id=gid,
        version=version,
        content_hash="sha256:" + "deadbeef" * 8,
        created=datetime.now(UTC),
        authors=[],
        evaluation_score={"reference_tasks": score},
    )
    g = Genome(manifest=manifest, framework={"steps": [{"id": "1", "name": "x"}]})
    g.finalize()
    return g


def _build_runner(tmp_path: Path) -> tuple[ReconciliationRunner, AgentDrive, Path]:
    """Build a runner with an explicit state_path under the test home."""
    drive_path = tmp_path / "pool"
    drive_path.mkdir(parents=True, exist_ok=True)
    (drive_path / "genomes").mkdir(exist_ok=True)
    registry = GenomeRegistry(root=drive_path / "genomes")
    pool = AgentDrive(registry=registry, drive_path=drive_path)
    state_path = tmp_path / STATE_FILENAME
    runner = ReconciliationRunner(
        registry=registry,
        pool=pool,
        state_path=state_path,
        interval_s=0.05,
    )
    return runner, pool, state_path


# ─────────────────────────────────────────────────────────────────────
# scan_once: empty pool
# ─────────────────────────────────────────────────────────────────────


def test_scan_once_empty_pool_reports_no_changes(tmp_path: Path, clean_bus: None) -> None:
    runner, _pool, state_path = _build_runner(tmp_path)

    report = runner.scan_once()

    assert isinstance(report, ReconciliationReport)
    assert report.new_genomes == []
    assert report.updated_genomes == []
    assert report.new_ingest_events == 0
    assert report.pending_quarantine == 0
    assert report.duration_ms >= 0
    assert state_path.is_file()


# ─────────────────────────────────────────────────────────────────────
# scan_once: new genomes
# ─────────────────────────────────────────────────────────────────────


def test_scan_once_detects_new_genomes_since_last_scan(tmp_path: Path, clean_bus: None) -> None:
    runner, pool, _state_path = _build_runner(tmp_path)

    # Baseline scan with empty pool.
    first = runner.scan_once()
    assert first.new_genomes == []

    # Ingest a genome — now scan should see it.
    pool.ingest(_make_genome("alpha"), source="seed", actor="pytest")
    second = runner.scan_once()
    assert any("alpha" in gid for gid in second.new_genomes), (
        f"expected alpha in {second.new_genomes}"
    )

    # Third scan with no new ingestions should report no further new genomes.
    third = runner.scan_once()
    assert third.new_genomes == []


# ─────────────────────────────────────────────────────────────────────
# scan_once: updated confidence markers
# ─────────────────────────────────────────────────────────────────────


def test_scan_once_detects_updated_confidence_markers(tmp_path: Path, clean_bus: None) -> None:
    runner, pool, _state_path = _build_runner(tmp_path)

    pool.ingest(_make_genome("beta"), source="seed", actor="pytest")
    # Baseline: genome present, no confidence sidecar yet.
    first = runner.scan_once()
    assert any("beta" in gid for gid in first.new_genomes)

    # Locate the genome dir and write a confidence sidecar by hand so we
    # don't depend on the confidence module's update path.
    registry = runner.registry
    genome_name = next(g for g in registry.list_genomes() if "beta" in g)
    gdir = registry.get_genome_path(genome_name)
    assert gdir is not None and gdir.is_dir()
    rating = ConfidenceRating(
        stars=3,
        encounters=10,
        success_rate=0.8,
        avg_score=0.85,
        last_used=datetime.now(UTC).isoformat(),
    )
    (gdir / CONF_SIDECAR).write_text(rating.to_json(), encoding="utf-8")

    second = runner.scan_once()
    assert any("beta" in gid for gid in second.updated_genomes), (
        f"expected beta in updated, got {second.updated_genomes}"
    )

    # Third scan: no changes, no updates reported.
    third = runner.scan_once()
    assert third.updated_genomes == []


# ─────────────────────────────────────────────────────────────────────
# scan_once: new ingest events
# ─────────────────────────────────────────────────────────────────────


def test_scan_once_detects_new_ingest_events(tmp_path: Path, clean_bus: None) -> None:
    runner, pool, _state_path = _build_runner(tmp_path)

    # Baseline.
    runner.scan_once()

    # Add an ingest event whose timestamp is clearly after the last scan.
    # Sleep a beat to guarantee monotonic ordering against the persisted ISO.
    time.sleep(0.01)
    pool.ingest(_make_genome("gamma"), source="seed", actor="pytest")

    report = runner.scan_once()
    assert report.new_ingest_events >= 1


# ─────────────────────────────────────────────────────────────────────
# state persistence
# ─────────────────────────────────────────────────────────────────────


def test_scan_once_persists_state_atomically(tmp_path: Path, clean_bus: None) -> None:
    runner, pool, state_path = _build_runner(tmp_path)

    pool.ingest(_make_genome("delta"), source="seed", actor="pytest")
    runner.scan_once()

    # The state file exists and parses as JSON with the expected shape.
    assert state_path.is_file()
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert "last_scan_iso" in payload
    assert "known_genome_ids" in payload
    assert "known_markers" in payload
    assert any("delta" in gid for gid in payload["known_genome_ids"])

    # No leftover temp files in the dir (atomic write should clean up).
    siblings = [
        p.name
        for p in state_path.parent.iterdir()
        if p.name.startswith(state_path.name + ".") and p.name.endswith(".tmp")
    ]
    assert siblings == [], f"leftover temp files: {siblings}"


# ─────────────────────────────────────────────────────────────────────
# events
# ─────────────────────────────────────────────────────────────────────


def test_reconciliation_completed_event_fires(tmp_path: Path, clean_bus: None) -> None:
    runner, _pool, _state_path = _build_runner(tmp_path)

    received: list[ReconciliationCompleted] = []
    default_bus.subscribe(
        lambda e: received.append(e),  # type: ignore[arg-type]
        [ReconciliationCompleted],
    )

    runner.scan_once()
    assert len(received) == 1
    ev = received[0]
    assert ev.new_genomes_count == 0
    assert ev.updated_genomes_count == 0
    assert ev.new_ingest_events == 0
    assert ev.pending_quarantine == 0
    assert ev.duration_ms >= 0


def test_reconciliation_delta_only_fires_when_delta_nonzero(
    tmp_path: Path, clean_bus: None
) -> None:
    runner, pool, _state_path = _build_runner(tmp_path)

    deltas: list[ReconciliationDelta] = []
    default_bus.subscribe(
        lambda e: deltas.append(e),  # type: ignore[arg-type]
        [ReconciliationDelta],
    )

    # Empty scan: no delta event.
    runner.scan_once()
    assert deltas == []

    # New genome lands → delta fires exactly once.
    pool.ingest(_make_genome("epsilon"), source="seed", actor="pytest")
    runner.scan_once()
    assert len(deltas) == 1
    assert any("epsilon" in g for g in deltas[0].new_genomes)

    # Quiet scan again: no further delta.
    runner.scan_once()
    assert len(deltas) == 1


# ─────────────────────────────────────────────────────────────────────
# background thread lifecycle
# ─────────────────────────────────────────────────────────────────────


def test_start_and_stop_background_thread_lifecycle(tmp_path: Path, clean_bus: None) -> None:
    runner, _pool, _state_path = _build_runner(tmp_path)
    runner.interval_s = 0.05

    completed_count: list[int] = []
    default_bus.subscribe(
        lambda e: completed_count.append(1),  # type: ignore[arg-type]
        [ReconciliationCompleted],
    )

    runner.start_background()
    # Second call is a no-op — must not raise or spawn a second thread.
    runner.start_background()

    # Give the loop a couple of ticks.
    deadline = time.monotonic() + 2.0
    while len(completed_count) < 2 and time.monotonic() < deadline:
        time.sleep(0.02)
    assert len(completed_count) >= 2, (
        f"background loop did not produce >=2 scans in 2s (got {len(completed_count)})"
    )

    runner.stop_background(timeout=2.0)

    # Thread is gone.
    with runner._thread_lock:  # type: ignore[attr-defined]
        thread = runner._thread  # type: ignore[attr-defined]
    assert thread is None or not thread.is_alive(), (
        "background thread should have exited after stop_background()"
    )

    # After stop, no further completed events fire — sample for a beat.
    snapshot = len(completed_count)
    time.sleep(0.2)
    assert len(completed_count) == snapshot, "background loop kept firing after stop_background()"
