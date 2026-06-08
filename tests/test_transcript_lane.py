"""Tests for TranscriptLane (UX Pattern 1)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from rich.console import Console

from agentdrive.events import PoolIngest, ReconciliationDelta, emit
from agentdrive.tui.transcript_lane import TranscriptLane


@pytest.fixture
def clean_bus() -> Iterator[None]:
    """Snapshot + restore default_bus subscribers around each test."""
    from agentdrive.events import default_bus

    with default_bus._lock:  # type: ignore[attr-defined]
        saved = list(default_bus._subs)  # type: ignore[attr-defined]
        default_bus._subs.clear()  # type: ignore[attr-defined]
    try:
        yield
    finally:
        with default_bus._lock:  # type: ignore[attr-defined]
            default_bus._subs = saved  # type: ignore[attr-defined]


def test_transcript_lane_records_pool_ingest(clean_bus: None) -> None:
    console = Console(file=open("/dev/null", "w"), force_terminal=False)
    lane = TranscriptLane(console)
    lane.attach()
    try:
        assert lane.line_count == 0
        emit(PoolIngest(genome_id="test-genome", source="scan", actor="agent"))
        assert lane.line_count == 1
    finally:
        lane.detach()


def test_transcript_lane_skips_empty_reconciliation_delta(clean_bus: None) -> None:
    console = Console(file=open("/dev/null", "w"), force_terminal=False)
    lane = TranscriptLane(console)
    lane.attach()
    try:
        emit(ReconciliationDelta(new_genomes=[], updated_genomes=[]))
        assert lane.line_count == 0
        emit(ReconciliationDelta(new_genomes=["g1"], updated_genomes=[]))
        assert lane.line_count == 1
    finally:
        lane.detach()


def test_transcript_lane_on_line_callback(clean_bus: None) -> None:
    console = Console(file=open("/dev/null", "w"), force_terminal=False)
    calls: list[int] = []
    lane = TranscriptLane(console, on_line=lambda: calls.append(1))
    lane.attach()
    try:
        emit(PoolIngest(genome_id="g", source="s", actor="a"))
        assert calls == [1]
        assert lane.line_count == 1
    finally:
        lane.detach()