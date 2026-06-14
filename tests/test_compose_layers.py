"""Tests for Fabric-style layered composition in the Harness."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import agentdrive.drive.drive as drive_module
from agentdrive.drive.drive import AgentDrive
from agentdrive.harness import ComposeLayers, Harness
from agentdrive.harness.compose import (
    assemble_layered_prompt,
    resolve_genome_layer,
    resolve_pattern_layer,
    resolve_session_layer,
    sessions_dir,
)


def test_pattern_layer_morning_brief_v1() -> None:
    input_text = "Standup at 9am. Review overnight alerts."
    layer = resolve_pattern_layer("morning-brief-v1", input_text)

    assert input_text in layer
    assert "{{input}}" not in layer
    assert "# SYSTEM" in layer
    assert "# USER" in layer


def test_genome_layer_with_mocked_pool() -> None:
    genome = MagicMock()
    genome.framework = {
        "description": "Iterative refinement with explicit checkpoints.",
        "steps": [
            {"id": "gather", "name": "Gather context"},
            {"id": "plan", "name": "Draft plan"},
        ],
    }
    pool = MagicMock()
    pool.get_genome.return_value = genome

    layer = resolve_genome_layer(pool, "test-strategy-v1")

    assert "Iterative refinement" in layer
    assert "Gather context" in layer
    assert "Draft plan" in layer
    pool.get_genome.assert_called_with("test-strategy-v1")


def test_genome_layer_living_experience_seed(isolated_agentdrive_home: Path) -> None:
    drive_module.default_pool = None
    pool = AgentDrive()
    layer = resolve_genome_layer(pool, "living-experience-seed-v3")

    assert "living-experience" in layer.lower() or "experience layer" in layer.lower()
    assert "(genome not found" not in layer


def test_session_layer_reads_recent_entries(isolated_agentdrive_home: Path) -> None:
    session_path = sessions_dir() / "briefing-42.jsonl"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"event": "meta", "session_id": "briefing-42", "title": "Morning briefing"},
        {"event": "turn", "role": "user", "content": "What changed overnight?"},
        {"event": "turn", "role": "assistant", "content": "Two alerts resolved."},
        {"event": "turn", "role": "user", "content": "Any blockers for ship?"},
        {"event": "turn", "role": "assistant", "content": "Patterns catalog needs review."},
        {"event": "turn", "role": "user", "content": "Schedule follow-up."},
    ]
    session_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    layer = resolve_session_layer("briefing-42", limit=3)

    assert "[user] Any blockers for ship?" in layer
    assert "[assistant] Patterns catalog needs review." in layer
    assert "[user] Schedule follow-up." in layer
    assert "What changed overnight?" not in layer


def test_assemble_layered_prompt_order(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = MagicMock()
    pool.get_genome.return_value = None

    layers = ComposeLayers(
        strategy="missing-genome",
        context="Operator notes from yesterday.",
        pattern="morning-brief-v1",
        session_id="briefing-42",
        input_text="today's agenda",
    )

    monkeypatch.setattr(
        "agentdrive.harness.compose.resolve_session_layer",
        lambda _sid, limit=5: "[user] prior context",
    )
    composed = assemble_layered_prompt("Base task prompt", layers, pool)

    strategy_idx = composed.index("## STRATEGY")
    context_idx = composed.index("## CONTEXT")
    pattern_idx = composed.index("## PATTERN")
    session_idx = composed.index("## SESSION")
    base_idx = composed.index("Base task prompt")

    assert strategy_idx < context_idx < pattern_idx < session_idx < base_idx
    assert "Operator notes from yesterday." in composed
    assert "today's agenda" in composed


def test_compose_context_with_strategy_and_pattern(
    isolated_agentdrive_home: Path,
) -> None:
    drive_module.default_pool = None
    pool = AgentDrive()
    harness = Harness(agent_id="layered-agent", pool=pool)
    input_text = "Ship layered composition before standup."

    composed = harness.compose_context(
        "Execute the daily operator loop.",
        strategy="living-experience-seed-v3",
        pattern="morning-brief-v1",
        input_text=input_text,
        context="Focus on harness integration quality.",
    )

    assert "## STRATEGY" in composed
    assert "## CONTEXT" in composed
    assert "## PATTERN" in composed
    assert "Execute the daily operator loop." in composed
    assert input_text in composed
    assert "Focus on harness integration quality." in composed
    assert "living-experience" in composed.lower() or "experience layer" in composed.lower()


def test_compose_context_backward_compatible_without_layers() -> None:
    drive_module.default_pool = None
    harness = Harness(agent_id="plain-agent", pool=AgentDrive())

    composed = harness.compose_context("Only the base prompt.")

    assert composed == "Only the base prompt."


def test_compose_layers_exported_from_harness_package() -> None:
    from agentdrive.harness import ComposeLayers as ExportedComposeLayers

    assert ExportedComposeLayers is ComposeLayers
