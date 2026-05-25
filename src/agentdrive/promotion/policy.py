"""Promotion policy — when does a proposal auto-approve."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AutoApproveFrom = Literal["none", "self", "trusted-peer"]


@dataclass(frozen=True)
class PromotionPolicy:
    """Per-Drive policy controlling how proposals get reviewed.

    Defaults follow the Codex recommendation that Pablo accepted: every
    upward write requires a promotion record, but self-originated promotions
    auto-approve so the existing single-agent flow stays one logical step.
    Trusted-peer auto-approval is opt-in.
    """

    # If False, parent auto-ingests legacy-style and PromotionService is bypassed.
    # Kept off-the-default for a reason: explicit promotion is the v2 invariant.
    promotion_required: bool = True

    # Who can have their propose-records auto-approved.
    # - "none": every proposal needs a human/agent reviewer
    # - "self": the device that emitted the proposal can approve its own
    #            (matches the v1 "child wrote upward → just take it" flow)
    # - "trusted-peer": any device in the same trust circle can auto-approve
    auto_approve_from: AutoApproveFrom = "self"

    def should_auto_approve(self, *, proposer_is_self: bool, proposer_is_trusted: bool) -> bool:
        """Decide whether a fresh proposal can be approved without review."""
        if not self.promotion_required:
            return True
        if self.auto_approve_from == "none":
            return False
        if self.auto_approve_from == "self":
            return proposer_is_self
        if self.auto_approve_from == "trusted-peer":
            return proposer_is_self or proposer_is_trusted
        return False
