"""
engine — top-level Loom Dreaming orchestrator.

Design goals:
- Thread sleep detection, phase execution, checkpointing, and narrative together.
- Keep all durable writes staged and reversible until run commit.
- No new magic — just disciplined composition + Agent Drive / Genome idioms.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentdrive.dreaming.dilation import (
    DilationPolicy,
    SleepWindow,
    detect_sleep_window,
    should_wake,
)
from agentdrive.dreaming.ingestion import IngestionConfig, MultiSubstrateIngestor
from agentdrive.dreaming.narrative import DreamNarrator
from agentdrive.dreaming.phases import (
    AdversarialPhase,
    DeepPhase,
    DreamPhaseContext,
    LightPhase,
    PhaseConfig,
    RemPhase,
)
from agentdrive.dreaming.scoring import ScoreWeights
from agentdrive.dreaming.storage import DreamPaths, DreamRunRecord, DreamStorage, PhaseCheckpoint
from agentdrive.genome.models import Genome
from agentdrive.reasoning.engine import ReasoningEngine


@dataclass
class DreamEngineConfig:
    """Runtime configuration for Loom Dreaming orchestration."""

    paths: DreamPaths = field(default_factory=DreamPaths)
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)
    dilation: DilationPolicy = field(default_factory=DilationPolicy)
    weights: ScoreWeights = field(default_factory=ScoreWeights)
    phase: PhaseConfig = field(default_factory=PhaseConfig)
    force_when_idle_unknown: bool = False


@dataclass
class DreamEngine:
    """Orchestrator that runs the full Light → REM → Adversarial → Deep cycle."""

    config: DreamEngineConfig = field(default_factory=DreamEngineConfig)
    reasoning_engine: ReasoningEngine | None = None
    storage: DreamStorage = field(init=False)
    ingestor: MultiSubstrateIngestor = field(init=False)
    narrator: DreamNarrator = field(init=False)
    light_phase: LightPhase = field(init=False)
    rem_phase: RemPhase = field(init=False)
    adversarial_phase: AdversarialPhase = field(init=False)
    deep_phase: DeepPhase = field(init=False)

    def __post_init__(self) -> None:
        """Wire phase objects and helpers from config."""
        self.storage = DreamStorage(paths=self.config.paths)
        self.ingestor = MultiSubstrateIngestor(config=self.config.ingestion)
        self.narrator = DreamNarrator()
        self.light_phase = LightPhase(ingestor=self.ingestor, config=self.config.phase)
        self.rem_phase = RemPhase(config=self.config.phase)
        self.adversarial_phase = AdversarialPhase()
        self.deep_phase = DeepPhase(weights=self.config.weights, config=self.config.phase)

    def run_if_idle(self) -> str | None:
        """Run Loom Dreaming only if a sleep window can be opened safely."""
        window = detect_sleep_window(self.config.dilation)
        if window is None and not self.config.force_when_idle_unknown:
            return None
        result = self.run_once(window=window)
        return str(result.get("run_id"))

    def run_once(self, window: SleepWindow | None = None) -> dict[str, Any]:
        """Execute one full dream cycle and return a structured run summary."""
        self.storage.ensure_layout()
        lock_path = self.storage.acquire_lock()
        if lock_path is None:
            return {"run_id": "", "status": "locked"}
        run = self.storage.create_run(window=window)
        context = self._build_context(run=run, window=window)
        status = "staged"
        staged: list[Path] = []
        try:
            snapshot_path = self.storage.write_snapshot_manifest(
                run,
                {"runtime_root": str(context.runtime_root), "started_at": context.started_at},
            )
            context.snapshot_manifest = snapshot_path
            light = self.light_phase.run(context)
            self.checkpoint_phase(run.run_id, "light", light.metrics)
            self._write_diary(run.run_id, "light", light.metrics)
            if window and should_wake(window, self.config.dilation):
                status = "woke_after_light"
                return {"run_id": run.run_id, "status": status}

            rem = self.rem_phase.run(context, light.candidates)
            self.checkpoint_phase(run.run_id, "rem", rem.metrics)
            self._write_diary(run.run_id, "rem", rem.metrics)
            if window and should_wake(window, self.config.dilation):
                status = "woke_after_rem"
                return {"run_id": run.run_id, "status": status}

            adversarial = self.adversarial_phase.run(context, rem.candidates)
            self.checkpoint_phase(run.run_id, "adversarial", adversarial.metrics)
            self._write_diary(run.run_id, "adversarial", adversarial.metrics)
            if window and should_wake(window, self.config.dilation):
                status = "woke_after_adversarial"
                return {"run_id": run.run_id, "status": status}

            deep = self.deep_phase.run(
                context, adversarial.survivors, reinforcement_by_key=rem.reinforcement_by_key
            )
            self.checkpoint_phase(run.run_id, "deep", deep.metrics)
            self._write_diary(run.run_id, "deep", deep.metrics)
            for lane, candidates in {
                "memory": deep.promoted_memory,
                "genome": deep.promoted_genomes,
                "pattern": deep.promoted_patterns,
            }.items():
                for candidate in candidates:
                    staged.append(self.storage.stage_promotion(run, lane, candidate))
            self.storage.commit_run(run)
            return {
                "run_id": run.run_id,
                "status": status,
                "staged_promotions": [str(path) for path in staged],
            }
        except Exception as exc:
            status = "failed"
            self.storage.rollback_run(run, reason=str(exc))
            raise
        finally:
            self.storage.release_lock(lock_path)

    def _build_context(self, run: DreamRunRecord, window: SleepWindow | None) -> DreamPhaseContext:
        """Build the shared phase context for one run."""
        return DreamPhaseContext(
            run_id=run.run_id,
            started_at=time.time(),
            runtime_root=self.config.paths.root.parent,
            tick_budget=window.tick_budget if window else 0,
            snapshot_manifest=run.snapshot_manifest,
            reasoning_engine=self.reasoning_engine,
            provenance={"origin": "dreaming", "dream_run_id": run.run_id},
        )

    def checkpoint_phase(self, run_id: str, phase: str, metrics: dict[str, Any]) -> Path:
        """Write a coarse-grained checkpoint for one finished phase."""
        now = time.time()
        checkpoint = PhaseCheckpoint(
            run_id=run_id,
            phase=phase,
            status="completed",
            started_at=now,
            completed_at=now,
            metrics=metrics,
        )
        return self.storage.write_phase_checkpoint(checkpoint)

    def _write_diary(self, run_id: str, phase: str, metrics: dict[str, Any]) -> None:
        entry = self.narrator.dispatch_phase_diary(run_id, phase, {"metrics": metrics})
        self.narrator.write_phase_entry(entry)


def genome_engine_anchor(genome: Genome | None) -> str:
    """Return a stable Genome anchor for future engine-level backfills."""
    return genome.genome_id if genome else ""
