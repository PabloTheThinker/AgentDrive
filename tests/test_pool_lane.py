"""Tests for PoolActivityLane (UX Pattern 3)."""

from __future__ import annotations

from agentdrive.events import PoolMatch, PoolOutcome, emit
from agentdrive.tui.pool_lane import PoolActivityLane


def test_pool_lane_match_line():
    lane = PoolActivityLane()
    lane.attach()
    try:
        assert lane.renderable() is None
        emit(PoolMatch(genomes=["g1", "g2"], scores=[0.87, 0.61]))
        row = lane.renderable()
        assert row is not None
        plain = str(row)
        assert "matched" in plain
        assert "2" in plain
    finally:
        lane.detach()


def test_pool_lane_outcome_updates_line():
    lane = PoolActivityLane()
    lane.attach()
    try:
        emit(PoolOutcome(genome_id="test-genome", score=0.72))
        row = lane.renderable()
        assert row is not None
        assert "outcome" in str(row).lower()
        assert "test-genome" in str(row)
    finally:
        lane.detach()


def test_pool_lane_reset():
    lane = PoolActivityLane()
    lane.attach()
    try:
        emit(PoolMatch(genomes=["g1"], scores=[0.5]))
        assert lane.renderable() is not None
        lane.reset()
        assert lane.renderable() is None
    finally:
        lane.detach()
