"""
AgentDrive — local-first Drive for each agent and sub-agent. Holds genomes, memory, and proven DNA.

Professional, user-controlled, swarm-aware DNA management for AI agents and their sub-agents.

Core philosophy (professional subagent handling):
- Every agent and every sub-agent gets its own isolated, persistent pool by default.
- DNA (memory + patterns) flows according to explicit, auditable, user-configurable policies.
- Safe defaults, powerful overrides, full provenance.
"""

# Self-healing first-run bootstrap (Stabilization Swarm component)
# ensure_experience_layer_seed + supporting healers for new AgentDrive instances
# (role-swarm self-host users): new instances start coherent, experience layer
# present from first think, defensive healing for production reliability.
from .bootstrap import (
    ensure_basic_reconciliation_state,
    ensure_directory_structure,
    ensure_experience_layer_seed,
    ensure_minimal_kg_index_bootstrap,
    ensure_trust_self_identity_placeholder,
)
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
    # First-run self-healing bootstrap exports (experience layer v3 seed etc.)
    "ensure_experience_layer_seed",
    "ensure_directory_structure",
    "ensure_minimal_kg_index_bootstrap",
    "ensure_basic_reconciliation_state",
    "ensure_trust_self_identity_placeholder",
]
