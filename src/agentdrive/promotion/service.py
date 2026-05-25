"""Promotion service — propose / approve / reject lifecycle, disk-backed.

Persistence model: append-only JSONL at ``<drive_root>/promotions/proposals.jsonl``.
Each line is a :class:`PromotionRecord`. The current status of a proposal is
derived by replaying its records (proposal_id → latest decision wins).

Idempotency: duplicate ``propose`` for the same ``(genome, target)`` collapses
to a single proposal_id; duplicate ``approve``/``reject`` decisions on the
same proposal are dropped without writing a record.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from agentdrive.promotion.models import (
    PromotionDecision,
    PromotionRecord,
    PromotionStatus,
    PromotionTier,
)

logger = logging.getLogger(__name__)


def _proposal_id(genome_content_hash: str, target_tier: str, target_swarm: str | None) -> str:
    """Stable proposal id derived from the (genome, target) pair.

    Re-emitting the same upward write produces the same id — that's how
    propose() stays idempotent without a separate uniqueness index.
    """
    raw = f"{genome_content_hash}|{target_tier}|{target_swarm or ''}".encode()
    return hashlib.sha256(raw).hexdigest()[:24]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class PromotionService:
    """Persistent propose/review log for cross-tier Genome promotions."""

    def __init__(self, drive_root: Path) -> None:
        self.root = Path(drive_root) / "promotions"
        self.root.mkdir(parents=True, exist_ok=True)
        self.log_path = self.root / "proposals.jsonl"

    # ─── write side ─────────────────────────────────────────────────────────

    def propose(
        self,
        genome_content_hash: str,
        target_tier: PromotionTier,
        author: str,
        *,
        target_swarm: str | None = None,
        rationale: str | None = None,
    ) -> PromotionRecord:
        """Emit a propose record (idempotent on (genome, target))."""
        pid = _proposal_id(genome_content_hash, target_tier, target_swarm)
        for existing in self._records_for(pid):
            if existing.decision == "propose":
                return existing
        record = PromotionRecord(
            proposal_id=pid,
            genome_content_hash=genome_content_hash,
            target_tier=target_tier,
            target_swarm=target_swarm,
            decision="propose",
            author=author,
            reviewer=None,
            rationale=rationale,
            decided_at=_utc_now(),
        )
        self._append(record)
        return record

    def review(
        self,
        proposal_id: str,
        decision: PromotionDecision,
        reviewer: str,
        *,
        rationale: str | None = None,
    ) -> PromotionRecord | None:
        """Approve or reject an existing proposal. Returns the new record or
        ``None`` if the decision was already recorded (idempotent)."""
        if decision == "propose":
            raise ValueError("review() takes approve/reject; use propose() to create a proposal")
        records = list(self._records_for(proposal_id))
        if not records:
            raise ValueError(f"No proposal with id {proposal_id!r}")
        latest = records[-1]
        if latest.decision == decision:
            return None  # already in this state — no extra record
        propose_rec = next((r for r in records if r.decision == "propose"), None)
        if propose_rec is None:
            raise ValueError(f"Proposal {proposal_id!r} has no propose record")
        record = PromotionRecord(
            proposal_id=proposal_id,
            genome_content_hash=propose_rec.genome_content_hash,
            target_tier=propose_rec.target_tier,
            target_swarm=propose_rec.target_swarm,
            decision=decision,
            author=propose_rec.author,
            reviewer=reviewer,
            rationale=rationale,
            decided_at=_utc_now(),
        )
        self._append(record)
        return record

    # ─── read side ──────────────────────────────────────────────────────────

    def status(self, proposal_id: str) -> PromotionStatus:
        records = list(self._records_for(proposal_id))
        if not records:
            return "pending"  # treat unknown as pending — caller can check
        latest = records[-1]
        if latest.decision == "approve":
            return "approved"
        if latest.decision == "reject":
            return "rejected"
        return "pending"

    def list_pending(self) -> list[PromotionRecord]:
        """All proposals whose latest record is still ``propose``."""
        latest: dict[str, PromotionRecord] = {}
        for record in self._iter_records():
            latest[record.proposal_id] = record
        return [r for r in latest.values() if r.decision == "propose"]

    def get(self, proposal_id: str) -> PromotionRecord | None:
        records = list(self._records_for(proposal_id))
        return records[-1] if records else None

    # ─── persistence helpers ────────────────────────────────────────────────

    def _append(self, record: PromotionRecord) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")

    def _iter_records(self) -> Iterable[PromotionRecord]:
        if not self.log_path.exists():
            return
        with self.log_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield PromotionRecord.model_validate(json.loads(line))
                except Exception as exc:
                    logger.warning("Skipping bad promotion record: %s", exc)

    def _records_for(self, proposal_id: str) -> Iterable[PromotionRecord]:
        for record in self._iter_records():
            if record.proposal_id == proposal_id:
                yield record
