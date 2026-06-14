"""Tests for SKILL.md registry and runner (Pattern 5)."""

from __future__ import annotations

from pathlib import Path

from agentdrive.skills import get_skill, init_skill, list_skills, run_skill
from agentdrive.skills.curation import (
    promote_inherited_skill,
    prune_inherited_skill,
    review_inherited_skills,
)
from agentdrive.skills.registry import install_inherited_skill, list_skills_by_tier
from agentdrive.skills.usage import get_skill_usage, record_skill_run


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


def test_run_skill_records_usage_outcome(isolated_agentdrive_home):
    init_skill("usage-demo")

    result = run_skill("usage-demo")

    assert result["success"] is True
    usage = get_skill_usage("usage-demo")
    assert usage.runs == 1
    assert usage.successes == 1
    assert usage.failures == 0


def test_review_promote_and_prune_inherited_skill(isolated_agentdrive_home):
    install_inherited_skill(
        name="reviewable-worker-playbook",
        description="Reusable worker playbook with enough evidence to promote",
        body="# Reviewable Worker Playbook\n\n1. Reuse the worker evidence.",
        source_subagent_id="worker-review",
        swarm_id="swarm-review",
        tags=["worker", "review"],
    )
    record_skill_run("reviewable-worker-playbook", success=True)
    record_skill_run("reviewable-worker-playbook", success=True)

    reviews = review_inherited_skills(include_promoted=False)
    review = next(r for r in reviews if r.name == "reviewable-worker-playbook")
    assert review.recommendation == "promote"

    promoted = promote_inherited_skill("reviewable-worker-playbook")
    assert promoted.promoted is True
    entry = get_skill("reviewable-worker-playbook")
    assert entry is not None
    assert entry.category == "promoted"

    path = prune_inherited_skill("reviewable-worker-playbook", reason="superseded")
    assert path.exists()
    assert get_skill("reviewable-worker-playbook") is None
    assert "disabled: true" in path.read_text(encoding="utf-8")


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
