"""
dreaming — public surface for Loom Dreaming.

Design goals:
- Expose a small orchestration surface without hiding raw primitives.
- Keep dreaming append-only, provenance-rich, and ledger disciplined.
- No new magic — just disciplined composition + Agent Drive / Genome idioms.
"""

from __future__ import annotations

from agentdrive.dreaming.candidate import CandidateSignal, DreamCandidate
from agentdrive.dreaming.cycle import (
    DREAM_PHASES,
    DreamCycleLockError,
    DreamCyclePending,
    DreamCycleResult,
    DreamPhaseSpec,
    get_dream_cycle_status,
    run_dream_cycle,
)
from agentdrive.dreaming.dilation import DilationPolicy, SleepWindow
from agentdrive.dreaming.durable import (
    AGENTDRIVE_SWARM_ID,
    CALIBRATION_SWARM_ID,
    DISPATCH_SWARM_ID,
    DreamJob,
    DurableDreamRunner,
    DurableJobSupervisor,
    JobStatus,
    QueuedDreamJob,
    apply_calibration_adjustments,
    auto_attributed_ingest_from_dream_job,
    compute_auto_calibration_adjustments,
    run_consolidation_adversarial_phase,
    run_consolidation_deep_phase,
    run_consolidation_light_phase,
    run_consolidation_rem_phase,
    run_contradiction_calibration_job,
    run_daily_consolidation_job,
    run_minions_dispatch_tranche2_consolidation,
    run_tranche3_auto_calibration_job,
)
from agentdrive.dreaming.engine import DreamEngine, DreamEngineConfig
from agentdrive.dreaming.phases import AdversarialResult, DeepResult, LightResult, RemResult

__all__ = [
    "AGENTDRIVE_SWARM_ID",
    "CALIBRATION_SWARM_ID",
    "DISPATCH_SWARM_ID",
    "AdversarialResult",
    "CandidateSignal",
    "DeepResult",
    "DilationPolicy",
    "DreamCandidate",
    "DreamEngine",
    "DreamEngineConfig",
    "DreamJob",
    "DurableDreamRunner",
    "DREAM_PHASES",
    "DreamCycleLockError",
    "DreamCyclePending",
    "DreamCycleResult",
    "DreamPhaseSpec",
    "DurableJobSupervisor",
    "JobStatus",
    "LightResult",
    "QueuedDreamJob",
    "RemResult",
    "SleepWindow",
    "auto_attributed_ingest_from_dream_job",
    "run_consolidation_adversarial_phase",
    "run_consolidation_deep_phase",
    "run_consolidation_light_phase",
    "run_consolidation_rem_phase",
    "run_contradiction_calibration_job",
    "run_daily_consolidation_job",
    "run_minions_dispatch_tranche2_consolidation",
    "run_tranche3_auto_calibration_job",
    "compute_auto_calibration_adjustments",
    "apply_calibration_adjustments",
    "get_dream_cycle_status",
    "run_dream_cycle",
]
