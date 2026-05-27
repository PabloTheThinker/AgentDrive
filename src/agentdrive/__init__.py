"""
AgentDrive

The Living, Learning Ecosystem for AI Agents.

Core idea: Agents should be able to scan, share, merge, and evolve specialized
capabilities ("DNA" / Genomes) across an open, versioned, evolutionary system —
designed for real, structured, improvable agent intelligence.
"""

__version__ = "0.2.0"

# Core public API
from agentdrive.constants import get_current_subagent_id, get_current_swarm_id, using_swarm

# AgentDrive & Harness (each agent owns its own persistent Drive)
from agentdrive.drive.drive import (
    AgentDrive,
    DriveIngestResult,
    DriveQuery,
    SwarmDriveManager,
    get_default_drive,
    get_global_drive,
    get_swarm_drive_manager,
)
from agentdrive.drive.settings import (
    DriveSettings,
    DriveSettingsManager,
    get_drive_settings_manager,
    get_effective_drive_settings,
)
from agentdrive.genome.models import (
    Genome,
    GenomeAuthor,
    GenomeManifest,
    GenomeProvenance,
    ImprovementEvent,
)
from agentdrive.harness.harness import Harness, create_harness
from agentdrive.registry import GenomeRegistry

# TUI Pool View (first-class terminal interface for the Pool and swarms)
from agentdrive.tui.views.drive_view import DriveView, register_drive_view

__all__ = [
    "Genome",
    "GenomeManifest",
    "GenomeAuthor",
    "GenomeProvenance",
    "ImprovementEvent",
    "AgentDrive",
    "get_default_drive",
    "DriveQuery",
    "DriveIngestResult",
    "SwarmDriveManager",
    "get_swarm_drive_manager",
    "get_global_drive",
    "using_swarm",
    "get_current_swarm_id",
    "get_current_subagent_id",
    "Harness",
    "create_harness",
    "DriveView",
    "register_drive_view",
    "ExternalWorkerAdapter",
    "RichAgentAdapter",
    "DriveSettings",
    "DriveSettingsManager",
    "get_drive_settings_manager",
    "get_effective_drive_settings",
    "GenomeRegistry",
]

# Clean external agent adapter (Agent Drive-native rich worker) — placed after registry import to avoid circular during 'from agentdrive import X'
from agentdrive.workers.rich_agent_adapter import RichAgentAdapter

ExternalWorkerAdapter = RichAgentAdapter  # preferred name for external/rich integrations

# Production foundations
# Multi-model / cross-AI AgentDrive adapters (the reason this package exists)
# Any model (Grok build, Claude, Codex, ...) can now be told by the user:
#     "use your AgentDrive for this swarm"
from agentdrive import (
    adapters as adapters,  # full namespace: agentdrive.adapters.grok_build_adapter etc.
)

# Provider system — connect any AI model to Agent Drive
from agentdrive import providers as providers
from agentdrive.adapters import (
    AgentDriveAdapter,
    AgentDriveAdapterBase,
    activate_for_claude,
    activate_for_grok_build,
    get_agentdrive_adapter,
    get_agentdrive_pool,
    get_scoped_pool,
)

# Agent Drive Agent — the framework as a conversational AI agent
from agentdrive.agent import (
    AGENTDRIVE_IDENTITY,
    AgentDriveAgent,
    AgentSession,
    Indicator,
    Turn,
    TurnResult,
)
from agentdrive.config import (
    ensure_agentdrive_home,
    get_config_value,
    get_logger,
    load_config,
    save_config,
    set_config_value,
    setup_logging,
)
from agentdrive.constants import (
    AGENTDRIVE_VERSION,
    get_agentdrive_config_path,
    get_agentdrive_home,
)
from agentdrive.exceptions import (
    AgentDriveConfigError,
    AgentDriveError,
    AgentDriveRegistryError,
    AgentDriveScanError,
    AgentDriveWorkerError,
)

# Reasoning primitives for DNA extraction and Genome enrichment
from agentdrive.reasoning import (
    REASONING_PRIMITIVES_VERSION,
    Ledger,
    ReasoningEngine,
    detect_anomalies,
    detect_contradictions,
    mine_causality,
    reconstruct_trace,
    synthesize_framework,
)  # core primitives for scanners and evolution engine

# First-class re-exports for the deep ILO / Conductor integration points
# (lineage_immune + lineage_dna + the Grok/ILO Pattern Lineage Bridge live here)
from agentdrive.dna import (
    LineageImmuneSystem,
    GenomeThreatAssessment,
    ThreatLevel,
    lineage_immune,
)
from agentdrive.evolution import (
    LineageDNAEvolver,
    DNACycleResult,
    evolve_genome_with_lineage,
)
from agentdrive.adapters.grok_build_adapter import (
    GrokPatternLineageBridge,
    ilo_pattern_to_genome,
    publish_ilo_genome,
)

# Advanced trust, lineage, and observability surfaces (opt-in but first-class)
# These power the new DNA/Quarantine/Reconciliation/Lineage-enhanced experience.
from agentdrive.quarantine import (
    Quarantine,
    QuarantineEntry,
    QuarantineStatus,
    ValidationRule,
    get_default_quarantine,
)
from agentdrive.reconciliation import (
    ReconciliationReport,
    ReconciliationRunner,
)
from agentdrive.dna.drive import DNADrive, InheritedGenome
from agentdrive.dna.grants import (
    GrantScope,
    GrantStore,
    LineageShareGrant,
    pull_via_grant,
)
from agentdrive.dna.lineage_immune import (
    GenomeThreatAssessment,
    LineageImmuneSystem,
    ThreatLevel,
)
from agentdrive.evolution.lineage_dna import (
    DNACycleResult,
    LineageDNAEvolver,
    evolve_genome_with_lineage,
)
from agentdrive.workers import (
    ExternalAgentAdapter,
    ExternalWorkerAdapter,
    RichAgentAdapter,
    Worker,
    get_default_adapter,
)

__all__ = [
    # Genome DNA system (core hardened primitive)
    "Genome",
    "GenomeManifest",
    "GenomeAuthor",
    "GenomeProvenance",
    "ImprovementEvent",
    "GenomeRegistry",
    # Version
    "__version__",
    "AGENTDRIVE_VERSION",
    # Config & Constants
    "get_agentdrive_home",
    "get_agentdrive_config_path",
    "ensure_agentdrive_home",
    "load_config",
    "save_config",
    "get_config_value",
    "set_config_value",
    "setup_logging",
    "get_logger",
    # Errors
    "AgentDriveError",
    "AgentDriveConfigError",
    "AgentDriveRegistryError",
    "AgentDriveWorkerError",
    "AgentDriveScanError",
    # Workers / Adapters (key extension point)
    "Worker",
    "ExternalAgentAdapter",
    "get_default_adapter",
    "RichAgentAdapter",
    "ExternalWorkerAdapter",
    # Agent Drive Swarm Pool core (per-subagent isolated persistent DNA)
    "SwarmDriveManager",
    "get_swarm_drive_manager",
    "get_global_drive",
    "using_swarm",
    "get_current_swarm_id",
    "get_current_subagent_id",
    # Multi-model adapters — the core of "use your AgentDrive for this swarm"
    "providers",
    "adapters",
    "AgentDriveAdapter",
    "AgentDriveAdapterBase",
    "get_agentdrive_adapter",
    "get_scoped_pool",
    "get_agentdrive_pool",
    "activate_for_grok_build",
    "activate_for_claude",
    # Agent Drive Agent (framework-as-body conversational agent)
    "AgentDriveAgent",
    "AgentSession",
    "Turn",
    "Indicator",
    "TurnResult",
    "AGENTDRIVE_IDENTITY",
    # Reasoning (DNA / Genome)
    "ReasoningEngine",
    "REASONING_PRIMITIVES_VERSION",
    "detect_anomalies",
    "mine_causality",
    "detect_contradictions",
    "synthesize_framework",
    "reconstruct_trace",
    "Ledger",
    # Quarantine (mandatory gate for all foreign DNA)
    "Quarantine",
    "QuarantineEntry",
    "QuarantineStatus",
    "ValidationRule",
    "get_default_quarantine",
    # Reconciliation (background delta detection + events)
    "ReconciliationRunner",
    "ReconciliationReport",
    # DNA Drives + forward inheritance
    "DNADrive",
    "InheritedGenome",
    # Lineage grants (signed sideways sharing)
    "GrantStore",
    "LineageShareGrant",
    "GrantScope",
    "pull_via_grant",
    # Lineage immune system (adaptive threat assessment)
    "LineageImmuneSystem",
    "ThreatLevel",
    "GenomeThreatAssessment",
    # Lineage DNA evolver (Research/Evaluate/Evolve cycles)
    "LineageDNAEvolver",
    "DNACycleResult",
    "evolve_genome_with_lineage",
    # Grok/ILO Pattern Lineage Bridge (PUBLISH/CONSUME/ACTIVATE for Conductor nodes)
    "GrokPatternLineageBridge",
    "ilo_pattern_to_genome",
    "publish_ilo_genome",
    # Immune singleton (shared adaptive state)
    "lineage_immune",
]
