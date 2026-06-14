"""AgentDrive skills — SKILL.md registry (Pattern 5)."""

from agentdrive.skills.compose import compose_skills_block, match_skills_for_turn
from agentdrive.skills.registry import (
    SkillEntry,
    discover_skills,
    get_skill,
    init_skill,
    install_inherited_skill,
    list_skills,
    list_skills_by_tier,
)
from agentdrive.skills.runner import run_skill
from agentdrive.skills.usage import (
    SkillUsage,
    get_skill_usage,
    list_skill_usage,
    record_skill_match,
    record_skill_run,
)

__all__ = [
    "SkillEntry",
    "compose_skills_block",
    "discover_skills",
    "get_skill",
    "init_skill",
    "install_inherited_skill",
    "list_skills",
    "list_skills_by_tier",
    "match_skills_for_turn",
    "run_skill",
    "SkillUsage",
    "get_skill_usage",
    "list_skill_usage",
    "record_skill_match",
    "record_skill_run",
]
