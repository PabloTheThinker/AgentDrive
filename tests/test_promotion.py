"""Integration tests for v2 / M6 promotion gates.

The contract M6 has to deliver:

1. **Proposals are idempotent.** Re-proposing the same (Genome, target) pair
   collapses to a single proposal id with no extra records on disk.
2. **Self auto-approve preserves v1 flow.** With the default policy
   (``promotion_required=True``, ``auto_approve_from="self"``), an upward
   ingest from a child Drive lands in the parent automatically — same
   visible behavior as v1, but every step is now an auditable record.
3. **`auto_approve_from="none"` actually gates.** Switching the parent
   policy to ``"none"`` makes upward ingests stay pending until a manual
   review record approves them.
4. **Disk persistence.** Promotion records round-trip through a restart.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentdrive.drive.drive import AgentDrive
from agentdrive.drive.swarm_policy import SwarmDrivePolicy
from agentdrive.genome.models import Genome
from agentdrive.promotion import PromotionService


def _make_genome(gid: str, body: dict) -> Genome:
    return Genome.create(
        id=gid,
        version="1.0.0",
        framework=body,
        authors=[{"type": "agent", "id": "sub:alpha", "name": "alpha"}],
    )


# ─── PromotionService directly ─────────────────────────────────────────────


def test_propose_is_idempotent(tmp_path: Path) -> None:
    svc = PromotionService(tmp_path)
    a = svc.propose("sha256:abc", target_tier="swarm", author="sub:alpha", target_swarm="demo")
    b = svc.propose("sha256:abc", target_tier="swarm", author="sub:alpha", target_swarm="demo")
    assert a.proposal_id == b.proposal_id
    # Only one record on disk
    assert svc.log_path.read_text().count("\n") == 1


def test_review_approve_then_status(tmp_path: Path) -> None:
    svc = PromotionService(tmp_path)
    p = svc.propose("sha256:abc", target_tier="swarm", author="sub:a", target_swarm="demo")
    assert svc.status(p.proposal_id) == "pending"
    svc.review(p.proposal_id, decision="approve", reviewer="reviewer:human")
    assert svc.status(p.proposal_id) == "approved"


def test_duplicate_approve_is_idempotent(tmp_path: Path) -> None:
    svc = PromotionService(tmp_path)
    p = svc.propose("sha256:def", target_tier="swarm", author="sub:a", target_swarm="d")
    svc.review(p.proposal_id, decision="approve", reviewer="human")
    repeat = svc.review(p.proposal_id, decision="approve", reviewer="human")
    assert repeat is None  # second approve was a no-op
    # Two records on disk: propose + first approve
    assert svc.log_path.read_text().strip().count("\n") == 1


def test_reject_overrides_pending(tmp_path: Path) -> None:
    svc = PromotionService(tmp_path)
    p = svc.propose("sha256:xyz", target_tier="swarm", author="sub:a", target_swarm="d")
    svc.review(p.proposal_id, decision="reject", reviewer="human", rationale="off-topic")
    assert svc.status(p.proposal_id) == "rejected"


def test_list_pending_excludes_decided(tmp_path: Path) -> None:
    svc = PromotionService(tmp_path)
    p1 = svc.propose("sha256:a", target_tier="swarm", author="sub:a", target_swarm="d")
    p2 = svc.propose("sha256:b", target_tier="swarm", author="sub:b", target_swarm="d")
    svc.review(p1.proposal_id, decision="approve", reviewer="auto")
    pending = svc.list_pending()
    assert [r.proposal_id for r in pending] == [p2.proposal_id]


def test_review_unknown_proposal_raises(tmp_path: Path) -> None:
    svc = PromotionService(tmp_path)
    with pytest.raises(ValueError):
        svc.review("nonexistent", decision="approve", reviewer="x")


def test_records_survive_restart(tmp_path: Path) -> None:
    svc1 = PromotionService(tmp_path)
    p = svc1.propose("sha256:persisted", target_tier="swarm", author="sub:a", target_swarm="d")
    svc1.review(p.proposal_id, decision="approve", reviewer="human")

    svc2 = PromotionService(tmp_path)
    assert svc2.status(p.proposal_id) == "approved"


# ─── End-to-end: child → parent through promotion gate ─────────────────────


def _two_drives(parent_policy: SwarmDrivePolicy) -> tuple[AgentDrive, AgentDrive]:
    parent = AgentDrive(swarm_id="parent")
    parent.swarm_policy = parent_policy
    child = AgentDrive(swarm_id="child")
    child.parent_pool = parent
    child.sharing_policy = "full"
    return parent, child


def test_self_auto_approve_lands_in_parent() -> None:
    parent, child = _two_drives(SwarmDrivePolicy())  # default: required + self
    child.ingest(_make_genome("plan", {"steps": ["a"]}), source="child", actor="sub:alpha")

    assert parent.registry.load("plan") is not None
    svc = PromotionService(parent.drive_path)
    pending = svc.list_pending()
    assert pending == []  # auto-approved, not pending


def test_auto_approve_none_holds_proposal_pending() -> None:
    policy = SwarmDrivePolicy(auto_approve_from="none")
    parent, child = _two_drives(policy)

    child.ingest(_make_genome("plan", {"steps": ["a"]}), source="child", actor="sub:alpha")

    # Parent did NOT ingest because the proposal stayed pending
    assert parent.registry.load("plan") is None
    svc = PromotionService(parent.drive_path)
    pending = svc.list_pending()
    assert len(pending) == 1
    assert pending[0].genome_content_hash.startswith("sha256:")


def test_manual_approve_eventually_lands_genome() -> None:
    policy = SwarmDrivePolicy(auto_approve_from="none")
    parent, child = _two_drives(policy)

    genome = _make_genome("plan", {"steps": ["a"]})
    child.ingest(genome, source="child", actor="sub:alpha")

    svc = PromotionService(parent.drive_path)
    pending = svc.list_pending()
    assert pending
    svc.review(pending[0].proposal_id, decision="approve", reviewer="human")

    # The approved proposal does NOT auto-trigger the parent ingest in v1 —
    # that's a separate sweep an operator runs. Confirm the proposal records
    # 'approved' so a future sweeper can act.
    assert svc.status(pending[0].proposal_id) == "approved"


def test_promotion_required_false_uses_direct_ingest() -> None:
    policy = SwarmDrivePolicy(promotion_required=False)
    parent, child = _two_drives(policy)

    child.ingest(_make_genome("plan", {"steps": ["a"]}), source="child", actor="sub:alpha")
    # Direct upward ingest still works
    assert parent.registry.load("plan") is not None
    svc = PromotionService(parent.drive_path)
    assert svc.list_pending() == []
