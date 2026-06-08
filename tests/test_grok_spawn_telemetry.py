"""Tests for Grok spawn_subagent SubagentDone telemetry."""

from __future__ import annotations

import time

from agentdrive.agent.turn_telemetry import (
    emit_external_subagent_done,
    emit_external_subagent_spawn,
)
from agentdrive.events import SubagentDone, SubagentSpawn, default_bus


def test_external_spawn_and_done_pair():
    captured: list[str] = []
    token = default_bus.subscribe(lambda ev: captured.append(type(ev).__name__))

    emit_external_subagent_spawn(
        subagent_id="ext-1",
        parent_id="orchestrator",
        label="test spawn",
    )
    time.sleep(0.01)
    emit_external_subagent_done(subagent_id="ext-1", ok=True, duration_s=0.5)

    default_bus.unsubscribe(token)
    assert captured.count("SubagentSpawn") == 1
    assert captured.count("SubagentDone") == 1