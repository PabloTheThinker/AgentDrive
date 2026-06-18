"""Tests for AgentDrive-as-framework skill playbook routing."""

from __future__ import annotations

import pytest

from agentdrive.learning.auto_absorb import reset_sessions
from agentdrive.learning.framework_skills import (
    build_framework_session_pack,
    route_skills_for_task,
)
from agentdrive.operations.registry import run_operation
from agentdrive.skills.registry import install_inherited_skill


@pytest.fixture(autouse=True)
def _clean_sessions():
    reset_sessions()
    yield
    reset_sessions()


@pytest.fixture
def swarm_id(isolated_agentdrive_home):
    return "framework-skills-test-swarm"


def _install_learned(name: str, *, when_to_call: str, project: str) -> None:
    install_inherited_skill(
        name=name,
        description=f"Learned playbook for {project}",
        body=f"# {name}\n\n1. Pull context.\n2. Apply {project} patterns.\n3. Record outcome.",
        source_subagent_id="mcp-auto-learning",
        swarm_id="framework-skills-test-swarm",
        tags=["learned", project, "codebase-mimic"],
        when_to_call=when_to_call,
        operation="codebase_mimic",
        update_existing=True,
    )


def test_route_prioritizes_learned_skills_for_project(swarm_id) -> None:
    _install_learned(
        "learned-openmangos-mimic-growth-merge",
        when_to_call="Task resembles: wire growth merge into OpenMango context pack",
        project="openmangos",
    )
    _install_learned(
        "learned-other-patterns",
        when_to_call="Other project patterns",
        project="other",
    )
    matches = route_skills_for_task(
        "wire growth merge into OpenMango context pack",
        swarm_id=swarm_id,
        project_id="openmangos",
        learned_only=True,
    )
    assert matches
    assert matches[0].name.startswith("learned-openmangos")
    assert matches[0].kind == "learned"
    assert "framework_skill_run" in matches[0].invoke_hint


def test_framework_session_start_operation(swarm_id) -> None:
    _install_learned(
        "learned-openmangos-mimic-test",
        when_to_call="OpenMango mimic tasks",
        project="openmangos",
    )
    result = run_operation(
        "framework_session_start",
        task="OpenMango adaptive terminal work",
        project_id="openmangos",
        swarm_id=swarm_id,
    )
    assert result.get("success") is True
    assert "framework_briefing" in result
    assert result.get("learned_skill_count", 0) >= 1
    assert result.get("matched_skills")


def test_framework_skill_route_operation(swarm_id) -> None:
    _install_learned(
        "learned-demo-mimic-gateway",
        when_to_call="Gateway helper tasks",
        project="demo",
    )
    result = run_operation(
        "framework_skill_route",
        task="gateway helper deploy",
        project_id="demo",
        swarm_id=swarm_id,
    )
    assert result.get("success") is True
    assert result.get("count", 0) >= 1
    assert "playbook" in result


def test_build_framework_session_pack_includes_workflow(swarm_id) -> None:
    pack = build_framework_session_pack(
        "ship feature",
        swarm_id=swarm_id,
        project_id="agentdrive",
    )
    assert "framework_workflow" in pack
    assert "framework_briefing" in pack
    assert "AgentDrive framework loop" in pack["framework_briefing"]
