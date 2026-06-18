"""
AgentDrive Cognition — live operational thinking primitives for the 6-step loop.

Distinct from ``agentdrive.reasoning`` (post-hoc DNA extraction from runs).
Cognition modules power Parent/Overseer decision-making during active cycles.
"""

from __future__ import annotations

from typing import Any

from .llm_spawner import LLMBranchSpawner, resolve_available_local_model
from .roles import AXIS_GUIDANCE, ROLE_PROMPTS, role_system_prompt
from .store import MultiverseSessionStore, session_from_dict, session_to_dict
from .multiverse import (
    MULTIVERSE_RELATIONS,
    AdversaryVerdict,
    Branch,
    CollapsePolicy,
    ForwardStep,
    Invariant,
    InvariantKind,
    MultiverseEngine,
    MultiverseSession,
    COGNITIVE_ROLES,
)

COGNITION_VERSION = "agentdrive-cognition-0.2.0"

__all__ = [
    "AXIS_GUIDANCE",
    "COGNITION_VERSION",
    "LLMBranchSpawner",
    "ROLE_PROMPTS",
    "resolve_available_local_model",
    "role_system_prompt",
    "MULTIVERSE_RELATIONS",
    "AdversaryVerdict",
    "Branch",
    "CollapsePolicy",
    "COGNITIVE_ROLES",
    "ForwardStep",
    "Invariant",
    "InvariantKind",
    "MultiverseEngine",
    "MultiverseSession",
    "MultiverseSessionStore",
    "session_from_dict",
    "session_to_dict",
]


def get_multiverse_engine(recorder: Any, **kwargs: Any) -> MultiverseEngine:
    """Factory for MultiverseEngine bound to a recorder."""
    return MultiverseEngine(recorder, **kwargs)