"""Tests for skills composition into system prompt."""

from __future__ import annotations

from agentdrive.skills.compose import compose_skills_block, match_skills_for_turn
from agentdrive.skills.registry import discover_skills, get_skill


def test_discover_skills_includes_nested_categories():
    names = {e.name for e in discover_skills()}
    assert "think" in names
    assert "pawn-worker" in names
    assert "regex-architect" in names
    assert "changelog" in names
    assert "systematic-debugging" in names
    assert "grok-changelog" not in names


def test_skill_entry_has_category_and_role():
    entry = get_skill("pawn-worker")
    assert entry is not None
    assert entry.category == "hive"
    assert entry.role == "pawn"
    assert "pawn" in entry.tags


def test_match_skills_for_regex_question():
    matched = match_skills_for_turn("help me write a regex for email validation")
    names = [e.name for e in matched]
    assert "regex-architect" in names


def test_pawn_role_boosts_pawn_skills():
    matched = match_skills_for_turn("finish the assigned task", role="pawn")
    names = [e.name for e in matched]
    assert any(n in names for n in ("pawn-worker", "swarm-worker", "hive-inheritance"))


def test_compose_skills_block_non_empty():
    block = compose_skills_block("debug this stack trace", top_k=1)
    assert "Skills on your bench" in block
    assert "error-translator" in block or "systematic-debugging" in block