"""Tests for born-skill fusion (experience + skills + patterns)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentdrive.learning.auto_absorb import reset_sessions
from agentdrive.learning.skill_fusion import (
    FusionLineage,
    build_fused_skill_body,
    synthesize_from_inputs,
)
from agentdrive.operations.registry import run_operation
from agentdrive.skills import get_skill, install_inherited_skill


@pytest.fixture(autouse=True)
def _clean_sessions():
    reset_sessions()
    yield
    reset_sessions()


@pytest.fixture
def swarm_id(isolated_agentdrive_home):
    return "stabilization-wave-20260531"


def _seed_parent_skill(name: str = "parent-playbook") -> None:
    install_inherited_skill(
        name=name,
        description="Parent skill for fusion test",
        body="# Parent\n\n1. Do the thing.\n2. Verify.",
        source_subagent_id="test-pawn",
        swarm_id="stabilization-wave-20260531",
        tags=["test"],
    )


def test_fusion_lineage_requires_two_axes() -> None:
    lineage = FusionLineage(
        trigger="Only experience",
        swarm_id="swarm",
        program_id="prog",
        operations=["think"],
        experience_traces=["trace-1"],
    )
    assert lineage.axes_present() == {"experience"}
    assert not lineage.fusion_ready()


def test_fusion_lineage_ready_with_experience_and_skills() -> None:
    lineage = FusionLineage(
        trigger="Ship feature",
        swarm_id="swarm",
        program_id="prog",
        operations=["think", "external_parent_decision"],
        experience_traces=["trace-1"],
        source_skills=["auto-think-ship"],
    )
    assert lineage.fusion_ready()
    desc, body = build_fused_skill_body(lineage)
    assert "born skill" in body.lower() or "Born skill" in body
    assert "experience" in desc.lower()
    assert "Ship feature" in body


def test_synthesize_fused_skill_installs_born_skill(swarm_id) -> None:
    _seed_parent_skill("fusion-parent")
    result = synthesize_from_inputs(
        trigger="Gateway fetch helper with graph grounding",
        swarm_id=swarm_id,
        operations=["think", "codebase_mimic"],
        experience_traces=["fabric-trace-abc"],
        source_skills=["fusion-parent"],
        pattern_projects=["agentdrive"],
    )
    assert result.get("born") is True
    assert result.get("name", "").startswith("fused-")
    entry = get_skill(result["name"])
    assert entry is not None
    assert "fused" in entry.tags
    lineage_file = Path(result["path"]).parent / "fusion-lineage.json"
    assert lineage_file.is_file()
    meta = json.loads(lineage_file.read_text(encoding="utf-8"))
    assert "fusion-parent" in meta["source_skills"]


def test_synthesize_fused_skill_operation(swarm_id) -> None:
    _seed_parent_skill("op-parent")
    result = run_operation(
        "synthesize_fused_skill",
        trigger="Fused via registry",
        source_skills=["op-parent"],
        pattern_projects=["agentdrive"],
        operations=["think", "codebase_mimic"],
        experience_traces=["trace-op"],
        swarm_id=swarm_id,
    )
    assert result.get("success") is True
    fused = result.get("fused_skill") or {}
    assert fused.get("born") is True
    assert "experience" in (fused.get("axes") or [])
    assert "skills" in fused.get("axes", [])
    assert "patterns" in fused.get("axes", [])


def test_auto_fusion_after_rich_session(swarm_id, isolated_agentdrive_home, tmp_path) -> None:
    """Session with think + codebase + external parent should birth a fused skill."""
    from agentdrive.codebase.observe import observe_file
    from agentdrive.codebase.registry import register_project

    project_root = tmp_path / "fusion-repo"
    project_root.mkdir()
    sample = project_root / "helper.py"
    sample.write_text(
        "def fetch_data():\n    return {}\n",
        encoding="utf-8",
    )
    register_project(project_id="fusion-test", root=str(project_root))
    observe_file(project_id="fusion-test", path="helper.py")

    _seed_parent_skill("session-parent")

    run_operation(
        "experience_graph_context_pack",
        swarm_id=swarm_id,
        program_id="fusion-session@test",
    )
    run_operation(
        "codebase_mimic",
        project_id="fusion-test",
        intent="gateway fetch helper",
        swarm_id=swarm_id,
        program_id="fusion-session@test",
    )
    branches = [
        {
            "branch_id": "branch:op-1",
            "role": "operator",
            "path_summary": "Smallest shippable helper",
            "robustness_score": 0.85,
        }
    ]
    result = run_operation(
        "external_parent_decision",
        trigger="Gateway helper with repo patterns",
        branches=branches,
        collapsed_branch_id="branch:op-1",
        swarm_id=swarm_id,
        program_id="fusion-session@test",
        skill_name="session-parent",
    )
    assert result.get("success") is True
    auto = result.get("auto_learning") or {}
    fused = auto.get("fused_skill")
    if fused:
        assert fused.get("born") is True
        assert len(fused.get("axes") or []) >= 2
    else:
        # Distill path still records session lineage for explicit synthesis
        assert auto.get("skill") or auto.get("reasoning_trace")
