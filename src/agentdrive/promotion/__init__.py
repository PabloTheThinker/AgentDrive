"""Promotion gates for AgentDrive v2 / Milestone 6 — tiered sync.

A child Drive promotes a Genome upward by emitting a :class:`PromotionRecord`
that *references* the Genome by content hash, not by copying it. The parent
Drive either auto-approves (per policy) or holds the proposal pending review.
Approved promotions trigger the actual cross-tier ingest. Rejected proposals
stay on disk for audit.

The previous ``auto_ingest_from_children`` boolean was a coarse on/off. M6
replaces it with the explicit ``promotion_required`` +
``auto_approve_from`` pair, matching the four-tier promotion DAG from
``docs/AGENTDRIVE-V2.md``.
"""

from agentdrive.promotion.models import (
    PromotionDecision,
    PromotionRecord,
    PromotionStatus,
)
from agentdrive.promotion.policy import PromotionPolicy
from agentdrive.promotion.service import PromotionService

__all__ = [
    "PromotionDecision",
    "PromotionPolicy",
    "PromotionRecord",
    "PromotionService",
    "PromotionStatus",
]
