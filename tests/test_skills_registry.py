"""Tests for SKILL.md registry and runner (Pattern 5)."""

from __future__ import annotations

from pathlib import Path

import yaml

from agentdrive.drive.drive import AgentDrive
from agentdrive.skills import get_skill, init_skill, list_skills, run_skill
from agentdrive.skills.curation import (
    assimilate_inherited_skills,
    ingest_skill_as_dna,
    promote_inherited_skill,
    prune_inherited_skill,
    review_inherited_skills,
    skill_to_genome,
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


def test_ingest_promoted_skill_as_dna(registry, isolated_agentdrive_home):
    install_inherited_skill(
        name="dna-worker-playbook",
        description="Reusable worker playbook that should become DNA",
        body=(
            "# DNA Worker Playbook\n\n"
            "1. Gather the worker evidence.\n"
            "2. Summarize the reusable decision rule."
        ),
        source_subagent_id="worker-dna",
        swarm_id="swarm-dna",
        tags=["worker", "decision"],
    )
    record_skill_run("dna-worker-playbook", success=True)
    promote_inherited_skill("dna-worker-playbook")
    entry = get_skill("dna-worker-playbook")
    assert entry is not None

    genome = skill_to_genome(entry)
    assert genome.manifest.id == "skill-dna-worker-playbook"
    assert genome.framework is not None
    assert genome.framework["skill_name"] == "dna-worker-playbook"
    assert genome.manifest.evaluation_score["skill_successes"] == 1.0

    drive = AgentDrive(registry=registry)
    export = ingest_skill_as_dna("dna-worker-playbook", target_drive=drive)

    assert export.accepted is True
    assert export.genome_id == "skill-dna-worker-playbook@1.0.0"
    details = registry.list_genome_details()
    assert any(d.get("id") == "skill-dna-worker-playbook" for d in details)
    skill_text = entry.path.read_text(encoding="utf-8")
    assert "genome_id: skill-dna-worker-playbook@1.0.0" in skill_text


def test_assimilate_promotes_and_ingests_proven_inherited_skills(
    registry,
    isolated_agentdrive_home,
):
    install_inherited_skill(
        name="assimilate-worker-playbook",
        description="Reusable worker playbook that should be assimilated",
        body="# Assimilate Worker Playbook\n\n1. Preserve the useful child-agent procedure.",
        source_subagent_id="worker-assimilate",
        swarm_id="swarm-assimilate",
        tags=["worker", "assimilation"],
    )
    install_inherited_skill(
        name="watch-worker-playbook",
        description="Reusable worker playbook without enough evidence yet",
        body="# Watch Worker Playbook\n\n1. Wait for more evidence.",
        source_subagent_id="worker-watch",
        swarm_id="swarm-assimilate",
        tags=["worker", "watch"],
    )
    record_skill_run("assimilate-worker-playbook", success=True)
    record_skill_run("assimilate-worker-playbook", success=True)

    drive = AgentDrive(registry=registry)
    report = assimilate_inherited_skills(target_drive=drive)

    assert report.reviewed >= 2
    assert [item.name for item in report.promoted] == ["assimilate-worker-playbook"]
    assert [item.skill_name for item in report.dna_exports] == ["assimilate-worker-playbook"]
    assert report.errors == []
    assimilated = get_skill("assimilate-worker-playbook")
    watched = get_skill("watch-worker-playbook")
    assert assimilated is not None
    assert watched is not None
    assert assimilated.category == "promoted"
    assert watched.category == "inherited"
    details = registry.list_genome_details()
    assert any(d.get("id") == "skill-assimilate-worker-playbook" for d in details)


def test_init_skill_refuses_overwrite(isolated_agentdrive_home):
    init_skill("dup-skill")
    try:
        init_skill("dup-skill")
        assert False, "expected FileExistsError"
    except FileExistsError:
        pass


def test_inherited_skill_update_existing_records_revision(isolated_agentdrive_home):
    first_path = install_inherited_skill(
        name="self-improving-worker",
        description="First worker version",
        body="# First Worker\n\n1. Gather initial evidence.",
        source_subagent_id="worker-a",
        swarm_id="swarm-self",
        tags=["worker"],
    )
    second_path = install_inherited_skill(
        name="self-improving-worker",
        description="Second worker version",
        body="# Second Worker\n\n1. Gather initial evidence.\n2. Add contradiction checks.",
        source_subagent_id="worker-b",
        swarm_id="swarm-self",
        tags=["worker", "contradiction"],
        update_existing=True,
    )

    assert second_path == first_path
    entry = get_skill("self-improving-worker")
    assert entry is not None
    assert "Add contradiction checks" in entry.body
    assert "contradiction" in entry.tags

    text = first_path.read_text(encoding="utf-8")
    raw_meta = text.split("---", 2)[1]
    meta = yaml.safe_load(raw_meta)
    inheritance = meta["inheritance"]
    assert inheritance["revision_count"] == 2
    assert inheritance["latest_source"] == "inheritance:swarm-self:worker-b"
    assert inheritance["revisions"][0]["source"] == "inheritance:swarm-self:worker-a"
    assert inheritance["revisions"][1]["source"] == "inheritance:swarm-self:worker-b"


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
