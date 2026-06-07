"""Tests for gstack-style sprint chains and STOP gate checkpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentdrive.harness.harness import Harness
from agentdrive.sprint import (
    CheckpointPending,
    CheckpointStore,
    SHIP_CHAIN,
    run_ship_chain,
)
from agentdrive.sprint.chain import SprintResult

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_checkpoint_store_roundtrip(isolated_agentdrive_home: Path) -> None:
    store = CheckpointStore("ship")
    assert store.path == isolated_agentdrive_home / "checkpoints" / "ship.json"

    cp_id = store.create("think_gaps", "Review gaps before ship")
    assert cp_id.startswith("cp-")
    assert not store.is_acked(cp_id)
    assert len(store.list_pending()) == 1

    assert store.ack(cp_id) is True
    assert store.is_acked(cp_id) is True
    assert store.list_pending() == []
    assert store.ack("cp-does-not-exist") is False

    store.mark_step_completed("reconcile")
    assert store.is_step_completed("reconcile")
    store.reset_chain()
    assert not store.is_step_completed("reconcile")
    assert store.list_pending() == []


def test_dry_run_ship_chain_returns_results_without_subprocess(
    isolated_agentdrive_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subprocess_mock = MagicMock(side_effect=AssertionError("subprocess should not run"))
    monkeypatch.setattr("agentdrive.sprint.chain.subprocess.run", subprocess_mock)

    results = run_ship_chain(dry_run=True, reset=True, project_root=_PROJECT_ROOT)

    assert len(results) == len(SHIP_CHAIN)
    assert {r.step_id for r in results} == {s.id for s in SHIP_CHAIN}
    assert all(r.success for r in results)
    assert results[1].detail.get("skipped") is True
    subprocess_mock.assert_not_called()


def test_checkpoint_pending_on_stop_gate(
    isolated_agentdrive_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = CheckpointStore("ship")
    store.reset_chain()

    monkeypatch.setattr(
        "agentdrive.sprint.chain._run_reconcile",
        lambda *, dry_run: SprintResult(
            step_id="reconcile",
            name="Reconcile",
            success=True,
            message="ok",
        ),
    )
    monkeypatch.setattr(
        "agentdrive.sprint.chain._run_test",
        lambda *, dry_run, pytest_path: SprintResult(
            step_id="test",
            name="Test",
            success=True,
            message="ok",
        ),
    )
    monkeypatch.setattr(
        "agentdrive.sprint.chain._run_think_gaps",
        lambda *, dry_run: SprintResult(
            step_id="think_gaps",
            name="Think Gaps",
            success=True,
            message="2 gap(s) surfaced",
            detail={"gaps": [{"description": "gap one"}, {"description": "gap two"}]},
        ),
    )

    with pytest.raises(CheckpointPending) as exc_info:
        run_ship_chain(dry_run=False, reset=True, project_root=_PROJECT_ROOT)

    pending = exc_info.value
    assert pending.step_id == "think_gaps"
    assert pending.checkpoint_id.startswith("cp-")
    assert store.is_acked(pending.checkpoint_id) is False

    with pytest.raises(CheckpointPending) as resume_exc:
        run_ship_chain(
            dry_run=False,
            ack_ids=[pending.checkpoint_id],
            project_root=_PROJECT_ROOT,
        )

    changelog_pending = resume_exc.value
    assert changelog_pending.step_id == "changelog_check"

    results = run_ship_chain(
        dry_run=False,
        ack_ids=[pending.checkpoint_id, changelog_pending.checkpoint_id],
        project_root=_PROJECT_ROOT,
    )
    assert len(results) == 0  # all steps completed; chain finished cleanly


def test_harness_checkpoint_and_ack(isolated_agentdrive_home: Path) -> None:
    harness = Harness(agent_id="sprint-test")

    with pytest.raises(CheckpointPending) as exc_info:
        harness.checkpoint("manual_review", "Operator must confirm deploy")

    cp_id = exc_info.value.checkpoint_id
    assert harness.ack_checkpoint(cp_id) is True

    with pytest.raises(CheckpointPending):
        harness.checkpoint("manual_review", "Still blocked until fresh checkpoint acked")