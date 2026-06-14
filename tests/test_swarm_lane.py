"""Tests for SwarmActivityLane (UX Pattern 4)."""

from __future__ import annotations

from agentdrive.events import (
    SubagentDone,
    SubagentSpawn,
    SubagentTool,
    emit,
)
from agentdrive.tui.swarm_lane import SwarmActivityLane


def test_swarm_lane_tracks_spawn_and_done():
    lane = SwarmActivityLane()
    lane.attach()
    try:
        assert lane.renderable() is None

        emit(
            SubagentSpawn(
                subagent_id="worker-1",
                parent_id="orchestrator",
                label="worker-1",
            )
        )
        assert lane.has_swarm_activity()
        assert lane.renderable() is not None

        emit(SubagentTool(subagent_id="worker-1", tool="bash(rg)"))
        emit(
            SubagentDone(
                subagent_id="worker-1",
                ok=True,
                duration_s=1.2,
            )
        )
        emit(
            SubagentDone(
                subagent_id="orchestrator",
                ok=True,
                duration_s=2.0,
            )
        )

        assert not lane.has_swarm_activity()
        summary = lane.summary_line()
        assert summary is not None
        assert "1/1" in summary
    finally:
        lane.detach()


def test_swarm_lane_reset_clears_state():
    lane = SwarmActivityLane(root_label="test orchestrator")
    lane.attach()
    try:
        emit(
            SubagentSpawn(
                subagent_id="a",
                parent_id="orchestrator",
                label="a",
            )
        )
        assert lane.renderable() is not None
        lane.reset()
        assert lane.renderable() is None
        assert lane.summary_line() is None
    finally:
        lane.detach()


def test_swarm_lane_failed_subagent_summary():
    lane = SwarmActivityLane()
    lane.attach()
    try:
        emit(
            SubagentSpawn(
                subagent_id="bad-1",
                parent_id="orchestrator",
                label="bad-1",
            )
        )
        emit(SubagentDone(subagent_id="bad-1", ok=False, duration_s=0.5))
        emit(SubagentDone(subagent_id="orchestrator", ok=True, duration_s=1.0))

        summary = lane.summary_line()
        assert summary is not None
        assert "failed" in summary
    finally:
        lane.detach()
