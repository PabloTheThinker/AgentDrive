"""Tests for MultiverseEngine core pipeline (beyond external_parent path)."""

from __future__ import annotations

import pytest

from agentdrive.cognition.multiverse import (
    CollapsePolicy,
    MultiverseEngine,
    SessionStatus,
)
from agentdrive.evolution.experience_graph import ExperienceGraphRecorder
from agentdrive.operations.registry import run_operation


@pytest.fixture
def swarm_id(isolated_agentdrive_home):
    return "stabilization-wave-20260531"


@pytest.fixture
def recorder(isolated_agentdrive_home, swarm_id):
    from agentdrive.drive.drive import get_swarm_drive_path

    drive_path = get_swarm_drive_path(swarm_id)
    return ExperienceGraphRecorder(drive_path=drive_path)


@pytest.fixture
def engine(recorder):
    return MultiverseEngine(
        recorder,
        program_id="multiverse-test@stabilization-wave-20260531",
        use_llm=False,
    )


def test_spawn_session_creates_branches(engine) -> None:
    session = engine.spawn_session("Ship feature X", n_branches=5)
    assert session.session_id.startswith("multiverse-session:")
    assert len(session.branches) == 5
    assert session.status == SessionStatus.OPEN
    roles = {b.role for b in session.branches}
    assert roles  # heuristic spawner assigns cognitive roles


def test_run_full_collapses_session(engine) -> None:
    session = engine.run_full(
        "Consolidation sprint: archive stale docs",
        n_branches=4,
        forward_steps=2,
        stress_test_top_n=1,
        densify_invariants=False,
    )
    assert session.status == SessionStatus.COLLAPSED
    assert session.collapsed_branch_id
    assert session.collapse_policy is not None
    assert session.invariants  # extract_invariants runs in run_full


def test_simulate_and_extract_invariants(engine) -> None:
    session = engine.spawn_session("Probe invariant extraction", n_branches=3)
    engine.simulate_branches(session.session_id, forward_steps=2)
    updated = engine.extract_invariants(session.session_id)
    assert updated.invariants
    assert updated.convergence_points is not None
    assert updated.divergence_points is not None


def test_collapse_selects_branch(engine) -> None:
    session = engine.spawn_session("Manual collapse test", n_branches=3)
    target = session.branches[0].branch_id
    collapsed = engine.collapse(
        session.session_id,
        branch_id=target,
        policy=CollapsePolicy.CONDUCTOR_OVERRIDE,
        reason="Test override",
    )
    assert collapsed.status == SessionStatus.COLLAPSED
    assert collapsed.collapsed_branch_id == target
    assert collapsed.collapse_policy == CollapsePolicy.CONDUCTOR_OVERRIDE


def test_list_and_get_session_round_trip(engine) -> None:
    spawned = engine.spawn_session("List/get round trip", n_branches=2)
    listed = engine.list_sessions(limit=5)
    assert any(s.session_id == spawned.session_id for s in listed)
    loaded = engine.get_session(spawned.session_id)
    assert loaded is not None
    assert loaded.trigger == spawned.trigger


def test_multiverse_run_full_operation(swarm_id) -> None:
    result = run_operation(
        "multiverse_run_full",
        trigger="Ops registry multiverse smoke",
        n_branches=3,
        forward_steps=2,
        swarm_id=swarm_id,
    )
    assert result.get("success") is True
    session = result.get("session") or {}
    assert session.get("session_id")
    assert session.get("collapsed_branch_id")


def test_multiverse_parent_decision_heuristic(swarm_id) -> None:
    result = run_operation(
        "multiverse_parent_decision",
        trigger="Integrated parent decision smoke",
        n_branches=3,
        heuristic_only=True,
        skip_densify=True,
        swarm_id=swarm_id,
    )
    assert result.get("success") is True
    payload = result.get("result") or {}
    assert payload.get("session_id")
    assert payload.get("collapsed_branch_id")


def test_multiverse_list_sessions_operation(swarm_id) -> None:
    run_operation(
        "multiverse_parent_decision",
        trigger="Seed session for list test",
        n_branches=2,
        heuristic_only=True,
        skip_densify=True,
        swarm_id=swarm_id,
    )
    listed = run_operation("multiverse_list_sessions", swarm_id=swarm_id, limit=5)
    assert listed.get("success") is True
    sessions = listed.get("sessions") or []
    assert len(sessions) >= 1


def test_resolve_llm_mode_heuristic_when_disabled(engine) -> None:
    assert engine.resolve_llm_mode("any trigger") == "heuristic"
