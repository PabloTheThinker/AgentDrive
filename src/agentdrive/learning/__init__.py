"""Automatic experience + skill absorption for MCP/CLI operation runs."""

from agentdrive.learning.auto_absorb import maybe_absorb_operation_outcome
from agentdrive.learning.framework_skills import (
    build_framework_session_pack,
    route_skills_for_task,
    run_framework_skill,
)
from agentdrive.learning.growth_merge import build_growth_briefing, merge_session_growth
from agentdrive.learning.skill_fusion import synthesize_from_inputs

__all__ = [
    "maybe_absorb_operation_outcome",
    "synthesize_from_inputs",
    "build_growth_briefing",
    "merge_session_growth",
    "route_skills_for_task",
    "build_framework_session_pack",
    "run_framework_skill",
]
