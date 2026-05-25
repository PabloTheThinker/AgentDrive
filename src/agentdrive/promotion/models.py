"""Promotion record model — references a Genome rather than wrapping it.

A promotion is a separate, lightweight artifact. It links a Genome (by
content hash) to a higher-tier target and carries the propose / approve /
reject decision trail. Genome state stays unmodified through the promotion
lifecycle.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PromotionDecision = Literal["propose", "approve", "reject"]
PromotionStatus = Literal["pending", "approved", "rejected"]
PromotionTier = Literal["swarm", "agent", "peer"]


class PromotionRecord(BaseModel):
    """A single propose/approve/reject step in a Genome's promotion lifecycle.

    The full lifecycle of a promotion is the chain of records with the same
    ``proposal_id``: one ``propose``, then optional ``approve``/``reject``.
    Idempotency is handled by ``PromotionService`` — duplicate decisions are
    silently dropped instead of producing extra records.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True, str_strip_whitespace=True)

    proposal_id: str = Field(..., min_length=8, description="Stable id for the proposal lifecycle")
    genome_content_hash: str = Field(..., description="The Genome being promoted (sha256:<hex>)")
    target_tier: PromotionTier = Field(
        ..., description="The tier this proposal lifts the Genome to"
    )
    target_swarm: str | None = Field(
        default=None,
        description="Specific swarm id when target_tier='swarm', else None",
    )
    decision: PromotionDecision = Field(..., description="propose / approve / reject")
    author: str = Field(..., description="Sub-agent / device that emitted this record")
    reviewer: str | None = Field(
        default=None,
        description="Who approved / rejected (None for propose records)",
    )
    rationale: str | None = Field(
        default=None,
        description="Free-form 'why' for approve/reject — visible in audit trails",
    )
    decided_at: datetime
