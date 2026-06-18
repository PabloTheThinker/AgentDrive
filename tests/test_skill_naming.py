"""Tests for descriptive learned/fused skill naming."""

from __future__ import annotations

from agentdrive.learning.skill_naming import (
    fused_skill_name,
    learned_skill_name,
    learned_skill_title,
)


def test_learned_skill_name_with_project_and_intent() -> None:
    name = learned_skill_name(
        "codebase_mimic",
        project_id="openmangos",
        intent="wire growth_merge_briefing into context pack",
    )
    assert name.startswith("learned-openmangos-mimic-")
    assert "growth" in name or "wire" in name
    assert "d416228298" not in name


def test_learned_skill_name_patterns_only() -> None:
    name = learned_skill_name("codebase_patterns_profile", project_id="openmangos")
    assert name == "learned-openmangos-patterns"


def test_learned_skill_name_decision_with_trigger() -> None:
    name = learned_skill_name(
        "external_parent_decision",
        trigger="Ship gateway helper with graph grounding",
    )
    assert name.startswith("learned-parent-decision-")
    assert "gateway" in name or "ship" in name


def test_fused_skill_name_uses_project_and_axes() -> None:
    name = fused_skill_name(
        trigger="",
        pattern_projects=["openmangos"],
        axes=["experience", "patterns", "skills"],
    )
    assert name == "fused-openmangos-experience-patterns-skills"


def test_fused_skill_name_falls_back_to_trigger() -> None:
    name = fused_skill_name(
        trigger="Gateway fetch helper",
        pattern_projects=[],
        axes=["experience", "skills"],
    )
    assert name.startswith("fused-gateway-fetch-helper-")


def test_learned_skill_title_readable() -> None:
    title = learned_skill_title(
        "codebase_mimic",
        project_id="openmangos",
        intent="add growth merge briefing",
    )
    assert "openmangos" in title
    assert "mimic" in title.lower()
