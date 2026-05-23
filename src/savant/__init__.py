"""
Savant Framework

The Living, Learning Ecosystem for AI Agents.

Core idea: Agents should be able to scan, share, merge, and evolve specialized
capabilities ("DNA" / Genomes) across an open, versioned, evolutionary system —
inspired by the Omnitrix but built for real, structured, improvable agent intelligence.
"""

__version__ = "0.1.0"

# Core public API
from savant.genome.models import (
    Genome,
    GenomeManifest,
    GenomeAuthor,
    GenomeProvenance,
    ImprovementEvent,
)

# Savant Pool & Harness (the central living DNA ecosystem)
from savant.pool.pool import (
    SavantPool,
    get_default_pool,
    PoolQuery,
    PoolIngestResult,
    SavantSwarmPoolManager,
    get_swarm_pool_manager,
    get_global_pool,
)
from savant.harness.harness import SavantHarness, create_harness
from savant.pool.settings import (
    PoolSettings,
    PoolSettingsManager,
    get_pool_settings_manager,
    get_effective_pool_settings,
)
from savant.constants import using_swarm, get_current_swarm_id, get_current_subagent_id

# TUI Pool View (first-class terminal interface for the Pool and swarms)
from savant.tui.views.pool_view import PoolView, register_pool_view

__all__ = [
    "Genome",
    "GenomeManifest",
    "GenomeAuthor",
    "GenomeProvenance",
    "ImprovementEvent",
    "SavantPool",
    "get_default_pool",
    "PoolQuery",
    "PoolIngestResult",
    "SavantSwarmPoolManager",
    "get_swarm_pool_manager",
    "get_global_pool",
    "using_swarm",
    "get_current_swarm_id",
    "get_current_subagent_id",
    "SavantHarness",
    "create_harness",
    "PoolView",
    "register_pool_view",
    "ExternalWorkerAdapter",
    "RichAgentAdapter",
    "PoolSettings",
    "PoolSettingsManager",
    "get_pool_settings_manager",
    "get_effective_pool_settings",
    "GenomeRegistry",
]

# Clean external agent adapter (Savant-native rich worker) — placed after registry import to avoid circular during 'from savant import X'
from savant.workers.rich_agent_adapter import RichAgentAdapter
ExternalWorkerAdapter = RichAgentAdapter  # preferred name for external/rich integrations

# Production foundations
from savant.constants import (
    get_savant_home,
    get_savant_config_path,
    SAVANT_VERSION,
)
from savant.config import (
    load_config,
    save_config,
    get_config_value,
    set_config_value,
    setup_logging,
    get_logger,
)
from savant.exceptions import (
    SavantError,
    SavantConfigError,
    SavantRegistryError,
    SavantWorkerError,
    SavantScanError,
)
from savant.workers import Worker, get_default_adapter, RichAgentAdapter, ExternalWorkerAdapter, ExternalAgentAdapter, HermesAdapter, HermesStyleWorker  # Hermes* legacy only

# Multi-model / cross-AI Savant Pool adapters (the reason this package exists)
# Any model (Grok build, Claude, Codex, ...) can now be told by the user:
#     "use your Savant Pool for this swarm"
from savant import adapters as adapters  # full namespace: savant.adapters.grok_build_adapter etc.
from savant.adapters import (
    SavantAdapter,
    SavantAdapterBase,
    get_savant_adapter,
    get_scoped_pool,
    get_savant_pool,
    activate_for_grok_build,
    activate_for_claude,
)

# Reasoning primitives for DNA extraction and Genome enrichment
from savant.reasoning import ReasoningEngine, REASONING_PRIMITIVES_VERSION
from savant.reasoning import (
    detect_anomalies,
    mine_causality,
    detect_contradictions,
    synthesize_framework,
    reconstruct_trace,
    Ledger,
)  # core primitives for scanners and evolution engine


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
    "get_savant_home",
    "get_savant_config_path",
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
    "HermesAdapter",  # legacy alias (see adapters.py)
    "get_default_adapter",
    "RichAgentAdapter",
    "ExternalWorkerAdapter",
    "HermesStyleWorker",  # deprecated back-compat alias for RichAgentAdapter
    # Savant Swarm Pool core (per-subagent isolated persistent DNA)
    "SavantSwarmPoolManager",
    "get_swarm_pool_manager",
    "get_global_pool",
    "using_swarm",
    "get_current_swarm_id",
    "get_current_subagent_id",
    # Multi-model adapters — the core of "use your Savant Pool for this swarm"
    "adapters",
    "SavantAdapter",
    "SavantAdapterBase",
    "get_savant_adapter",
    "get_scoped_pool",
    "get_savant_pool",
    "activate_for_grok_build",
    "activate_for_claude",
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
