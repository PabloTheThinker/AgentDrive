"""Tests for Grok spawn_subagent SubagentDone telemetry."""

from __future__ import annotations

import sys
import time
import types

from agentdrive.agent.turn_telemetry import (
    emit_external_subagent_done,
    emit_external_subagent_spawn,
)
from agentdrive.adapters import grok_build_adapter
from agentdrive.events import SubagentDone, SubagentSpawn, default_bus
from agentdrive.inheritance import load_manifest


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


def test_grok_wrapper_writes_skill_handoff_manifest(monkeypatch):
    fake_grok = types.ModuleType("grok_build")

    def _spawn_subagent(**_kwargs):
        return """
```agentdrive-skill
name: grok-worker-handoff
description: Convert a successful Grok worker result into a parent skill.
tags: [grok, handoff]
---
# Grok Worker Handoff

1. Preserve the worker's reusable procedure.
2. Return a parent-ready skill block with evidence.
```
"""

    fake_grok.spawn_subagent = _spawn_subagent
    monkeypatch.setitem(sys.modules, "grok_build", fake_grok)
    monkeypatch.setattr(grok_build_adapter, "spawn_subagent", None)

    adapter = grok_build_adapter.GrokBuildAgentDriveAdapter()
    adapter.activate_for_current_session(swarm_id="grok-swarm")

    fake_grok.spawn_subagent(task="teach parent from worker", subagent_id="worker-1")

    manifest = load_manifest("grok-swarm", "worker-1")
    assert manifest is not None
    assert manifest.skills_created[0].name == "grok-worker-handoff"
    assert "worker's reusable procedure" in manifest.skills_created[0].body
