"""Tests for SKILL.md registry and runner (Pattern 5)."""

from __future__ import annotations

from pathlib import Path

from agentdrive.skills import get_skill, init_skill, list_skills, run_skill
from agentdrive.skills.registry import list_skills_by_tier


def test_list_skills_includes_bundled_and_vendor_tiers():
    entries = list_skills()
    names = {e.name for e in entries}
    assert "think" in names
    assert "golden-path-verify" in names
    assert "changelog" in names
    assert "mcp-agentdrive" in names
    assert "grok-changelog" in names
    assert len(entries) >= 60

    tiers = list_skills_by_tier()
    assert len(tiers["agentdrive"]) >= 20
    assert len(tiers["universal"]) >= 13
    assert len(tiers["grok"]) >= 10


def test_list_skills_harness_filter():
    universal = list_skills(harness="universal")
    assert universal
    assert all(e.harness == "universal" for e in universal)
    assert "changelog" in {e.name for e in universal}
    assert "think" not in {e.name for e in universal}

    grok = list_skills(harness="grok")
    assert grok
    assert all(e.harness == "grok" for e in grok)


def test_get_skill_missing():
    assert get_skill("definitely-not-a-skill-xyz") is None


def test_run_skill_unknown():
    result = run_skill("definitely-not-a-skill-xyz")
    assert result.get("success") is False


def test_run_golden_path_verify_skill(isolated_agentdrive_home):
    result = run_skill("golden-path-verify")
    assert result.get("skill") == "golden-path-verify"
    inner = result.get("result")
    assert isinstance(inner, dict)
    assert "steps" in inner


def test_init_skill_scaffold(isolated_agentdrive_home):
    path = init_skill("my-custom-skill")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "name: my-custom-skill" in text
    entry = get_skill("my-custom-skill")
    assert entry is not None


def test_init_skill_refuses_overwrite(isolated_agentdrive_home):
    init_skill("dup-skill")
    try:
        init_skill("dup-skill")
        assert False, "expected FileExistsError"
    except FileExistsError:
        pass


def test_user_skill_overlay(isolated_agentdrive_home):
    skills_dir = isolated_agentdrive_home / "skills" / "custom-test"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "---\nname: custom-test\ndescription: test skill\n---\n\nbody\n",
        encoding="utf-8",
    )
    entry = get_skill("custom-test")
    assert entry is not None
    assert entry.path == Path(skills_dir / "SKILL.md")