"""
Savant Framework

The Living, Learning Ecosystem for AI Agents.

Core idea: Agents should be able to scan, share, merge, and evolve specialized
capabilities ("DNA" / Genomes) across an open, versioned, evolutionary system —
designed for real, structured, improvable agent intelligence.
"""

__version__ = "0.1.0"

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

# Clean external agent adapter (Savant-native rich worker) — placed after registry import to avoid circular during 'from agentdrive import X'
from agentdrive.workers.rich_agent_adapter import RichAgentAdapter

ExternalWorkerAdapter = RichAgentAdapter  # preferred name for external/rich integrations

# Production foundations
# Multi-model / cross-AI AgentDrive adapters (the reason this package exists)
# Any model (Grok build, Claude, Codex, ...) can now be told by the user:
#     "use your AgentDrive for this swarm"
from agentdrive import (
    adapters as adapters,  # full namespace: savant.adapters.grok_build_adapter etc.
)

# Provider system — connect any AI model to Savant
from agentdrive import providers as providers
from agentdrive.adapters import (
    SavantAdapter,
    SavantAdapterBase,
    activate_for_claude,
    activate_for_grok_build,
    get_savant_adapter,
    get_savant_pool,
    get_scoped_pool,
)

# Savant Agent — the framework as a conversational AI agent
from agentdrive.agent import SAVANT_IDENTITY, AgentSession, Indicator, SavantAgent, Turn, TurnResult
from agentdrive.config import (
    ensure_savant_home,
    get_config_value,
    get_logger,
    load_config,
    save_config,
    set_config_value,
    setup_logging,
)
from agentdrive.constants import (
    SAVANT_VERSION,
    get_agentdrive_home,
    get_savant_config_path,
)
from agentdrive.exceptions import (
    SavantConfigError,
    SavantError,
    SavantRegistryError,
    SavantScanError,
    SavantWorkerError,
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
    "SAVANT_VERSION",
    # Config & Constants
    "get_agentdrive_home",
    "get_savant_config_path",
    "ensure_savant_home",
    "load_config",
    "save_config",
    "get_config_value",
    "set_config_value",
    "setup_logging",
    "get_logger",
    # Errors
    "SavantError",
    "SavantConfigError",
    "SavantRegistryError",
    "SavantWorkerError",
    "SavantScanError",
    # Workers / Adapters (key extension point)
    "Worker",
    "ExternalAgentAdapter",
    "get_default_adapter",
    "RichAgentAdapter",
    "ExternalWorkerAdapter",
    # Savant Swarm Pool core (per-subagent isolated persistent DNA)
    "SwarmDriveManager",
    "get_swarm_drive_manager",
    "get_global_drive",
    "using_swarm",
    "get_current_swarm_id",
    "get_current_subagent_id",
    # Multi-model adapters — the core of "use your AgentDrive for this swarm"
    "providers",
    "adapters",
    "SavantAdapter",
    "SavantAdapterBase",
    "get_savant_adapter",
    "get_scoped_pool",
    "get_savant_pool",
    "activate_for_grok_build",
    "activate_for_claude",
    # Savant Agent (framework-as-body conversational agent)
    "SavantAgent",
    "AgentSession",
    "Turn",
    "Indicator",
    "TurnResult",
    "SAVANT_IDENTITY",
    # Reasoning (DNA / Genome)
    "ReasoningEngine",
    "REASONING_PRIMITIVES_VERSION",
    "detect_anomalies",
    "mine_causality",
    "detect_contradictions",
    "synthesize_framework",
    "reconstruct_trace",
    "Ledger",
]
