"""
Savant Pool — Central living repository for Agent Genomes (DNA).

Professional, user-controlled, swarm-aware DNA management for AI agents and their sub-agents.

Core philosophy (professional subagent handling):
- Every agent and every sub-agent gets its own isolated, persistent pool by default.
- DNA (memory + patterns) flows according to explicit, auditable, user-configurable policies.
- Safe defaults, powerful overrides, full provenance.
"""

from .pool import SavantPool, PoolQuery, PoolIngestResult, get_default_pool
from .swarm_manager import SavantSwarmPoolManager, get_swarm_pool_manager
from .swarm_policy import SwarmPoolPolicy, IsolationLevel, SharingPolicy
from .settings import (
    PoolSettings,
    PoolSettingsManager,
    get_pool_settings_manager,
    get_effective_pool_settings,
)

__all__ = [
    "SavantPool",
    "PoolQuery",
    "PoolIngestResult",
    "get_default_pool",
    "SavantSwarmPoolManager",
    "get_swarm_pool_manager",
    "SwarmPoolPolicy",
    "IsolationLevel",
    "SharingPolicy",
    "PoolSettings",
    "PoolSettingsManager",
    "get_pool_settings_manager",
    "get_effective_pool_settings",
]