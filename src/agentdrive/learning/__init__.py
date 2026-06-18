"""Automatic experience + skill absorption for MCP/CLI operation runs."""

from agentdrive.learning.auto_absorb import maybe_absorb_operation_outcome
from agentdrive.learning.skill_fusion import synthesize_from_inputs

__all__ = ["maybe_absorb_operation_outcome", "synthesize_from_inputs"]