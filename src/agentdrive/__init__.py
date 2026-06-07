"""
AgentDrive

The Living, Learning Ecosystem for AI Agents.

Core idea: Agents should be able to scan, share, merge, and evolve specialized
capabilities ("DNA" / Genomes) across an open, versioned, evolutionary system —
designed for real, structured, improvable agent intelligence.
"""

__version__ = "0.3.1-alpha"

# Core public API
# Production security visibility (lightweight, self-hosted focused)
from agentdrive import security as security
from agentdrive.constants import (
    AGENTDRIVE_INSTANCE_NAME,
    get_agentdrive_instance_name,
    get_correlation_id,
    get_current_subagent_id,
    get_current_swarm_id,
    new_correlation_id,
    reset_correlation_id,
    set_correlation_id,
    using_correlation_id,
    using_swarm,
)

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
from agentdrive.security import (
    SecurityPosture,
    get_security_posture,
    print_security_posture,
)

# TUI Pool View (first-class terminal interface for the Pool and swarms)
# New Mission Control surface (real-time unified view of the system)
try:
    from agentdrive.mission_control import (
        # Rich static fire surfaces (zero-friction harness integration for full Bay telemetry on 2min fires)
        FireSession,
        MissionControlHub,
        create_mission_control_app,
        publish_event_sync,
        publish_static_fire_telemetry,
        run_static_fire_with_mission_telemetry,
        smoke_mission_control_with_integrated_system,
    )
    from agentdrive.mission_control import (
        hub as mission_control_hub,
    )
except Exception:
    create_mission_control_app = None  # type: ignore[assignment]
    publish_event_sync = None  # type: ignore[assignment]
    smoke_mission_control_with_integrated_system = None  # type: ignore[assignment]
    MissionControlHub = None  # type: ignore[assignment]
    mission_control_hub = None  # type: ignore[assignment]
    FireSession = None  # type: ignore[assignment]
    run_static_fire_with_mission_telemetry = None  # type: ignore[assignment]
    publish_static_fire_telemetry = None  # type: ignore[assignment]

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
    "get_correlation_id",
    "set_correlation_id",
    "new_correlation_id",
    "using_correlation_id",
    "Harness",
    "create_harness",
    "MissionControlHub",
    "mission_control_hub",
    "publish_event_sync",
    "smoke_mission_control_with_integrated_system",
    "FireSession",
    "run_static_fire_with_mission_telemetry",
    "publish_static_fire_telemetry",
    "DriveView",
    "register_drive_view",
    "ExternalWorkerAdapter",
    "RichAgentAdapter",
    "DriveSettings",
    "DriveSettingsManager",
    "get_drive_settings_manager",
    "get_effective_drive_settings",
    "GenomeRegistry",
    "get_agentdrive_instance_name",
    # Schema packs (dynamic page typing for raw drive content)
    "schema_packs",
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

# Schema Packs
# Lightweight dynamic typing for raw drive content that works alongside Genomes.
# Use: from agentdrive import schema_packs; pack = schema_packs.load_active_pack()
from agentdrive import schema_packs as schema_packs
from agentdrive.adapters import (
    AgentDriveAdapter,
    AgentDriveAdapterBase,
    activate_for_claude,
    activate_for_grok_build,
    get_agentdrive_adapter,
    get_agentdrive_pool,
    get_scoped_pool,
)
from agentdrive.adapters.grok_build_adapter import (
    GrokPatternLineageBridge,
    ilo_pattern_to_genome,
    publish_ilo_genome,
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
    get_learnings_dir,
)
from agentdrive.learnings import (
    LearningsStore,
    ingest_learnings_to_experience,
    resolve_learnings_slug,
)

# First-class re-exports for the deep high-continuity Conductor integration points
# (lineage_immune + lineage_dna + the Grok / External High-Continuity Conductor Pattern Lineage Bridge live here)
from agentdrive.dna import (
    GenomeThreatAssessment,
    LineageImmuneSystem,
    ThreatLevel,
    lineage_immune,
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

# Dreaming + Contradiction & Calibration Engine
# + parallel Living Experience Layer for fused daily interface genomes.
# Real primitives for closed-loop auto-calibration on contradictions surfaced by drive.think / synthesis
from agentdrive.dreaming import (
    CALIBRATION_SWARM_ID,
    DurableDreamRunner,
    DurableJobSupervisor,
    apply_calibration_adjustments,
    compute_auto_calibration_adjustments,
    run_contradiction_calibration_job,
    run_tranche3_auto_calibration_job,
)

# Healing signal events (primary definitions live in events.py; re-exported here for
# the public API surface alongside other top-level concepts).
from agentdrive.events import (
    HealingSignalEvent,
    HealingSignalResolved,
)
from agentdrive.evolution import (
    CONNECTION_STRENGTHENED_BY,
    # Experience Graph v3 Multi-Cycle Memory Fabric (Grid-native GraphGardener + daily fusion surfaces)
    CROSS_CYCLE_CONTINUATION,
    CYCLE_FABRIC_PARTICIPATION,
    DENSIFIED_FROM_SIBLING_CYCLE,
    DENSIFIED_VIA_GARDENER,
    FABRIC_COHERENCE_CONTRIBUTED,
    FABRIC_LINK,
    GRAPH_COHERENCE_LIFT,
    MULTI_CYCLE_FUSION_EDGE,
    DNACycleResult,
    ExperienceGraphRecorder,
    LineageDNAEvolver,
    LoopCycle,
    LoopEdge,
    embed_graph_into_artifact,
    evolve_genome_with_lineage,
    get_recorder_for_drive,
    trigger_densification_for_weak_cycles,
)
from agentdrive.evolution.lineage_dna import (
    DNACycleResult,
    LineageDNAEvolver,
    evolve_genome_with_lineage,
)
from agentdrive.evolution.real_time_evolution_overseer import RealTimeEvolutionOverseer
from agentdrive.exceptions import (
    AgentDriveConfigError,
    AgentDriveDriveError,
    AgentDriveError,
    AgentDriveReconciliationError,
    AgentDriveRegistryError,
    AgentDriveScanError,
    AgentDriveSecurityError,
    AgentDriveWorkerError,
)

# Real-time active Grid engine — the persistent, always-on substrate
# that keeps the Grid (self-organizing, regenerative experience layer) reactive.
from agentdrive.grid.engine import GridConfig, GridEngine, get_active_grid

# Knowledge Graph layer (see agentdrive/knowledge_graph/)
# Graph signals + temporal freshness for calibration feedback loops.
from agentdrive.knowledge_graph.graph import (
    get_living_experience_for_topic,  # Experience layer entry point helper
    get_stale_entities,
    temporal_freshness_score,
)

# Advanced trust, lineage, and observability surfaces (opt-in but first-class)
# These power the new DNA/Quarantine/Reconciliation/Lineage-enhanced experience.
# Correlation IDs (get_correlation_id etc.) provide lightweight cross-component
# tracing for self-hosted / production Drive, synthesis and reconciliation runs.
from agentdrive.quarantine import (
    Quarantine,
    QuarantineEntry,
    QuarantineStatus,
    ValidationRule,
    get_default_quarantine,
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
from agentdrive.reconciliation import (
    DiagnosisReport,
    EvaluationScores,
    HealingFactor,
    MultiMetricEvaluationHarness,
    ReconciliationReport,
    ReconciliationRunner,
    ResearchBudget,
    # Experience Layer Research Branching Swarm — native research thread support (first-class forked living-experience genome families)
    ResearchThreadLineage,
    create_research_thread_fork,
    decide_research_thread_advancement,
)

# Living Experience Layer Evolution
# The fused One Experience -> versioned living-experience genome family + daily Conductor interface.
# Primary entry: from agentdrive import get_swarm_family_status, create_initial_experience_genome_v3, get_living_experience_for_topic
from agentdrive.swarm_family import (
    AGENTDRIVE_SWARM_ID as EXPERIENCE_SWARM_ID,
)
from agentdrive.swarm_family import (
    INITIAL_EXPERIENCE_GENOME_V3,
    create_initial_experience_genome_v3,
    get_experience_evolution_proposal,
    # propose_experience_evolution lives primarily in synthesis; swarm_family provides fallback wrapper
    get_living_experience_entrypoints,
    get_swarm_family_status,
)
from agentdrive.synthesis import (
    Citation,
    Gap,
    SynthesisResult,
    propose_experience_evolution,  # Experience layer mechanics (forks + auto-incorporation from Graph+Calib)
    run_synthesis,
)

# Integrated real-time evolution system (Parent + Overseer + Experience Graph v2 + Grid substrate)
# The unified entrypoint that owns the ExperienceGraphRecorder and exposes trigger_graph_densification,
# get_experience_graph_for_cycle, embed helpers, etc. Re-exported for the public surfaces smoke.
from agentdrive.system.integrated_real_time_evolution_system import (
    IntegratedRealTimeEvolutionSystem,
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
    "get_learnings_dir",
    "LearningsStore",
    "resolve_learnings_slug",
    "ingest_learnings_to_experience",
    "ensure_agentdrive_home",
    "load_config",
    "save_config",
    "get_config_value",
    "set_config_value",
    "setup_logging",
    "get_logger",
    # Errors (full specific hierarchy for reconciliation healing, Drive lifecycle, security posture, grants.db, first-run self-healing)
    "AgentDriveError",
    "AgentDriveConfigError",
    "AgentDriveDriveError",
    "AgentDriveReconciliationError",
    "AgentDriveRegistryError",
    "AgentDriveScanError",
    "AgentDriveSecurityError",
    "AgentDriveWorkerError",
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
    # Correlation IDs for production tracing / observability (contextvar, non-breaking)
    "get_correlation_id",
    "set_correlation_id",
    "new_correlation_id",
    "using_correlation_id",
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
    # Regenerative HealingFactor (experience layer regeneration coordinator + signals)
    # Full substrate self-healing loop: detect (damage signals), diagnose (Drive.think +
    # run_synthesis Gaps/Contradictions + LineageImmune + graph signals + Multi-Agent
    # Research Org role swarms), propose safe first-class artifacts only, execute under
    # DurableJobSupervisor "healing" phase with verification gates, close via healing_attempt
    # ingest + KG edges. Integrates research-constitution governed specialist roles
    # (Diagnoser/Proposer/Verifier/Consolidator/Adversary) + coordination protocols.
    # All framed in experience layer regeneration, role-swarm immune response, durable
    # healing jobs, schema-pack governed evolution, LineageImmune adaptive memory.
    "HealingFactor",
    "DiagnosisReport",
    "HealingSignalEvent",
    "HealingSignalResolved",
    # Constrained Evolutionary Search primitives (ResearchBudget + harness) for
    # bounded autonomous research threads inside the real-time GridEngine on the
    # stabilization-wave-20260531 drive. Wired for constitution-governed keep/discard
    # decisions with full provenance (experience genome forks + fusion).
    "ResearchBudget",
    "EvaluationScores",
    "MultiMetricEvaluationHarness",
    "ResearchThreadLineage",
    "create_research_thread_fork",
    "decide_research_thread_advancement",
    # Synthesis + Gap Analysis (cited answers + explicit gaps via genomes + knowledge_graph)
    "run_synthesis",
    "SynthesisResult",
    "Gap",
    # Calibration Engine
    "CALIBRATION_SWARM_ID",
    "DurableDreamRunner",
    "DurableJobSupervisor",
    "run_contradiction_calibration_job",
    "run_tranche3_auto_calibration_job",
    "compute_auto_calibration_adjustments",
    "apply_calibration_adjustments",
    "Citation",
    # Living Experience Layer Evolution
    # Fused One Experience into versioned living-experience genome family + primary daily Conductor interface.
    # Use: create_initial_experience_genome_v3(), get_living_experience_for_topic(), propose_experience_evolution()
    "EXPERIENCE_SWARM_ID",
    "get_swarm_family_status",
    "get_living_experience_entrypoints",
    "create_initial_experience_genome_v3",
    "INITIAL_EXPERIENCE_GENOME_V3",
    "get_living_experience_for_topic",
    "propose_experience_evolution",
    "get_experience_evolution_proposal",
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
    # Grok / External High-Continuity Conductor Pattern Lineage Bridge (PUBLISH/CONSUME/ACTIVATE for Conductor nodes)
    "GrokPatternLineageBridge",
    "ilo_pattern_to_genome",
    "publish_ilo_genome",
    # Immune singleton (shared adaptive state)
    "lineage_immune",
    # Schema Packs: dynamic page typing for raw drive content
    "schema_packs",
    # Knowledge Graph (robust, persistent, typed, multi-hop + helpers)
    # All role-swarm participants rely on this for "find X related to Y via Z" queries. Central drive flow.
    "SimpleGraph",
    "GraphEdge",
    "GraphPath",
    "TypedEdge",
    "EntityRef",
    "KnowledgeGraphStore",
    "get_knowledge_graph_for_swarm",
    "extract_from_genome",
    "extract_entities_and_edges",
    "edges_to_drive_events",
    "load_graph_from_drive_events",
    # Experience Graph (clean loop ingestion + Obsidian-style connection graphs for Parent-Overseer-Research cycles)
    "ExperienceGraphRecorder",
    "LoopCycle",
    "LoopEdge",
    "get_recorder_for_drive",
    # GraphGardener v2 densifier (new relations + trigger for weak cycle densification)
    "DENSIFIED_VIA_GARDENER",
    "CONNECTION_STRENGTHENED_BY",
    "GRAPH_COHERENCE_LIFT",
    "trigger_densification_for_weak_cycles",
    # Experience Graph v3 Multi-Cycle Memory Fabric relations (Grid-native GraphGardener dispatch + daily fusion + ResearchThreadLineage fabric_coherence)
    "CROSS_CYCLE_CONTINUATION",
    "FABRIC_COHERENCE_CONTRIBUTED",
    "DENSIFIED_FROM_SIBLING_CYCLE",
    "MULTI_CYCLE_FUSION_EDGE",
    "FABRIC_LINK",
    "CYCLE_FABRIC_PARTICIPATION",
    # Experience Graph v2/v3 Renderers + Fusion (mermaid + text + embed for diary/densified cycles + fabric briefings)
    "embed_graph_into_artifact",
    # Graph Signals
    "compute_graph_signals",
    "fuse_graph_signals_into_scores",
    "fuse_for_synthesis",
    "recency_boost",
    "swarm_trust_tier",
    "source_boost",
    "find_contradictions_candidates",
    "temporal_freshness_score",  # Calibration primitive
    "get_stale_entities",
    "get_stale_entities",
    "get_high_centrality_genomes",
    # Real-time active Grid engine — the persistent, always-on, event-driven living Grid
    # substrate. Hosts continuous autonomous research threads (governed by research-constitution
    # page_type artifacts), auto-detects damage signals (HealingSignalEvent, synthesis, posture,
    # reconciliation), auto-dispatches HealingFactor regeneration + bounded research jobs under
    # DurableJobSupervisor. Full correlation, heartbeats, experience layer auto-incorporation
    # of thread outcomes, and observability for Grid health + active threads. All on
    # stabilization-wave-20260531 drive with role-swarm coherence.
    "GridEngine",
    "GridConfig",
    "get_active_grid",
    # Integrated system (v2/v3 wiring owner for Experience Graph Recorder + GraphGardener (v2 densif + v3 fabric) surfaces)
    "IntegratedRealTimeEvolutionSystem",
    "RealTimeEvolutionOverseer",
    "FireSession",
    "run_static_fire_with_mission_telemetry",
    "publish_static_fire_telemetry",
]
