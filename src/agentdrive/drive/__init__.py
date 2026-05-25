"""
AgentDrive — local-first Drive for each agent and sub-agent. Holds genomes, memory, and proven DNA.

Professional, user-controlled, swarm-aware DNA management for AI agents and their sub-agents.

Core philosophy (professional subagent handling):
- Every agent and every sub-agent gets its own isolated, persistent pool by default.
- DNA (memory + patterns) flows according to explicit, auditable, user-configurable policies.
- Safe defaults, powerful overrides, full provenance.
"""

from .content_store import (
    ContentStore,
    PutResult,
    canonical_genome_payload,
    canonical_json,
    genome_hash,
    hash_bytes,
    hash_payload,
)
from .drive import AgentDrive, DriveIngestResult, DriveQuery, get_default_drive
from .settings import (
    DriveSettings,
    DriveSettingsManager,
    get_drive_settings_manager,
    get_effective_drive_settings,
)
from .swarm_manager import SwarmDriveManager, get_swarm_drive_manager
from .swarm_policy import IsolationLevel, SharingPolicy, SwarmDrivePolicy

__all__ = [
    "AgentDrive",
    "DriveQuery",
    "DriveIngestResult",
    "get_default_drive",
    "SwarmDriveManager",
    "get_swarm_drive_manager",
    "SwarmDrivePolicy",
    "IsolationLevel",
    "SharingPolicy",
    "DriveSettings",
    "DriveSettingsManager",
    "get_drive_settings_manager",
    "get_effective_drive_settings",
    # v2 / Milestone 1: content-addressed object store
    "ContentStore",
    "PutResult",
    "canonical_json",
    "canonical_genome_payload",
    "genome_hash",
    "hash_bytes",
    "hash_payload",
]
