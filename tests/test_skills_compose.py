"""Tests for skills composition into system prompt."""

from __future__ import annotations

from agentdrive.skills.compose import (
    active_harness,
    compose_skills_block,
    format_skills_catalog,
    match_skills_for_turn,
)
from agentdrive.skills.registry import discover_skills, get_skill, list_skills_by_tier


def test_discover_skills_includes_nested_categories():
    names = {e.name for e in discover_skills()}
    assert "think" in names
    assert "pawn-worker" in names
    assert "regex-architect" in names
    assert "changelog" in names
    assert "systematic-debugging" in names
    assert "mcp-agentdrive" in names


def test_vendor_skills_in_separate_tier():
    tiers = list_skills_by_tier()
    bundled = {e.name for e in tiers["agentdrive"] + tiers["universal"]}
    grok = {e.name for e in tiers["grok"]}
    assert "grok-changelog" in grok
    assert "grok-changelog" not in bundled


def test_skill_entry_has_category_and_role():
    entry = get_skill("pawn-worker")
    assert entry is not None
    assert entry.category == "hive"
    assert entry.role == "pawn"
    assert entry.harness == "agentdrive"
    assert "pawn" in entry.tags


def test_root_core_skills_use_agentdrive_harness():
    for name in ("think", "golden-path-verify"):
        entry = get_skill(name)
        assert entry is not None
        assert entry.harness == "agentdrive"


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


def test_vendor_skills_excluded_from_prompt_by_default():
    catalog = format_skills_catalog()
    assert "grok-changelog" not in catalog
    matched = match_skills_for_turn("update the changelog after this session", top_k=5)
    names = {e.name for e in matched}
    assert "changelog" in names
    assert "grok-changelog" not in names


def test_vendor_skills_included_when_harness_set(monkeypatch):
    monkeypatch.setenv("AGENTDRIVE_HARNESS", "grok")
    assert active_harness() == "grok"
    catalog = format_skills_catalog()
    assert "Grok harness" in catalog
    matched = match_skills_for_turn(
        "generate an image with imagine",
        top_k=5,
        harness="grok",
    )
    names = {e.name for e in matched}
    assert any(n.startswith("grok-") for n in names)