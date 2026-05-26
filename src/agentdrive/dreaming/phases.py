"""
phases — Light, REM, Adversarial, and Deep dream phases.

Design goals:
- Keep each phase explicit, testable, and checkpoint-friendly.
- Separate discovery, generation, attack, and promotion decisions cleanly.
- No new magic — just disciplined composition + Agent Drive / Genome idioms.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import agentdrive.evolution as evolution
from agentdrive.dreaming.adversary import AdversaryResult, DreamAdversary
from agentdrive.dreaming.candidate import DreamCandidate, LaneName, merge_signals_into_candidates
from agentdrive.dreaming.ingestion import MultiSubstrateIngestor
from agentdrive.dreaming.scoring import ScoreWeights, rank_candidates
from agentdrive.genome.models import Genome
from agentdrive.reasoning.engine import ReasoningEngine


@dataclass
class DreamPhaseContext:
    """Shared context passed through all phases in one run."""

    run_id: str = ""
    started_at: float = 0.0
    runtime_root: Path = field(default_factory=lambda: Path("~/.agentdrive").expanduser())
    tick_budget: int = 0
    snapshot_manifest: Path | None = None
    reasoning_engine: ReasoningEngine | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class PhaseConfig:
    """Thresholds and fanout values for phase execution."""

    rem_candidate_limit: int = 12
    rem_recombine_fanout: int = 3
    deep_promotion_threshold: float = 0.55
    memory_threshold: float = 0.60
    genome_threshold: float = 0.65
    pattern_threshold: float = 0.62
    quarantine_on_risk_flags: bool = True


@dataclass
class HypotheticalInhabitant:
    """A simulated agent produced during REM from dream-favored genomes."""

    inhabitant_id: str = ""
    genome: Genome | None = None
    parent_candidate_ids: list[str] = field(default_factory=list)
    simulated_ticks: int = 0
    simulated_fitness: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass
class LightResult:
    """Outputs of the Light phase."""

    signals_collected: int = 0
    candidates: list[DreamCandidate] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class RemResult:
    """Outputs of the REM phase."""

    inhabitants: list[HypotheticalInhabitant] = field(default_factory=list)
    candidates: list[DreamCandidate] = field(default_factory=list)
    reinforcement_by_key: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdversarialResult:
    """Outputs of the adversarial phase."""

    survivors: list[DreamCandidate] = field(default_factory=list)
    defeated: list[DreamCandidate] = field(default_factory=list)
    results: list[AdversaryResult] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeepResult:
    """Outputs of the Deep phase."""

    promoted_memory: list[DreamCandidate] = field(default_factory=list)
    promoted_genomes: list[DreamCandidate] = field(default_factory=list)
    promoted_patterns: list[DreamCandidate] = field(default_factory=list)
    demoted: list[DreamCandidate] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


def choose_promotion_lane(candidate: DreamCandidate) -> LaneName | None:
    """Choose the best promotion lane for a candidate based on stable evidence shape."""
    hint_set = set(candidate.lane_hints)
    if "genome" in hint_set or candidate.recombination_count > 0:
        return "genome"
    if "pattern" in hint_set or candidate.pattern_refs:
        return "pattern"
    if candidate.supporting_signals:
        return "memory"
    return None


@dataclass
class LightPhase:
    """Discovery phase that stages normalized candidates without durable promotion."""

    ingestor: MultiSubstrateIngestor
    config: PhaseConfig = field(default_factory=PhaseConfig)

    def run(self, context: DreamPhaseContext) -> LightResult:
        """Collect recent signals and merge them into initial dream candidates."""
        signals = self.ingestor.collect_all_signals(now=context.started_at or time.time())
        candidates = merge_signals_into_candidates(signals)
        return LightResult(
            signals_collected=len(signals),
            candidates=candidates,
            metrics={"candidates": len(candidates), "signals": len(signals)},
        )


@dataclass
class RemPhase:
    """Generative phase that recombines favored structures and simulates inhabitants."""

    config: PhaseConfig = field(default_factory=PhaseConfig)

    def run(self, context: DreamPhaseContext, candidates: list[DreamCandidate]) -> RemResult:
        """Generate hypothetical inhabitants and reinforcement from top dream candidates."""
        ranked = sorted(candidates, key=lambda item: item.total_score, reverse=True)
        selected = ranked[: self.config.rem_candidate_limit]
        reinforcement_by_key: dict[str, float] = {}
        inhabitants: list[HypotheticalInhabitant] = []
        evolution_exports = getattr(evolution, "__all__", [])
        # TODO: Replace this placeholder once agentdrive.evolution exports recombination primitives.
        for index, candidate in enumerate(selected):
            candidate.reinforcement_hits += 1
            reinforcement_by_key[candidate.canonical_key] = 1.0
            if candidate.genome_refs:
                inhabitants.append(
                    HypotheticalInhabitant(
                        inhabitant_id=f"{context.run_id}-rem-{index}",
                        parent_candidate_ids=[candidate.candidate_id],
                        simulated_ticks=min(context.tick_budget, 60),
                        simulated_fitness=min(1.0, candidate.total_score + 0.05),
                        notes=[
                            "Loom REM placeholder; no concrete evolution primitive exported yet."
                        ],
                    )
                )
        return RemResult(
            inhabitants=inhabitants,
            candidates=selected,
            reinforcement_by_key=reinforcement_by_key,
            metrics={
                "selected": len(selected),
                "inhabitants": len(inhabitants),
                "evolution_exports": len(evolution_exports),
            },
        )


@dataclass
class AdversarialPhase:
    """Threat-consolidation phase that attacks staged dream artifacts."""

    adversary: DreamAdversary = field(default_factory=DreamAdversary)

    def run(
        self, context: DreamPhaseContext, candidates: list[DreamCandidate]
    ) -> AdversarialResult:
        """Attack staged candidates and partition survivors from defeated entries."""
        results = self.adversary.attack_candidates(
            candidates, reasoning_engine=context.reasoning_engine
        )
        survivors: list[DreamCandidate] = []
        defeated: list[DreamCandidate] = []
        for candidate, result in zip(candidates, results):
            candidate.adversary_penalty = result.penalty
            (survivors if result.survived else defeated).append(candidate)
        return AdversarialResult(
            survivors=survivors,
            defeated=defeated,
            results=results,
            metrics={"survivors": len(survivors), "defeated": len(defeated)},
        )


@dataclass
class DeepPhase:
    """Consolidation phase that scores, lanes, and stages promotion decisions."""

    weights: ScoreWeights = field(default_factory=ScoreWeights)
    config: PhaseConfig = field(default_factory=PhaseConfig)

    def run(
        self,
        context: DreamPhaseContext,
        candidates: list[DreamCandidate],
        reinforcement_by_key: dict[str, float] | None = None,
    ) -> DeepResult:
        """Score candidates and route strong survivors into memory, genome, or pattern lanes."""
        reinforcement_by_key = reinforcement_by_key or {}
        for candidate in candidates:
            if reinforcement_by_key.get(candidate.canonical_key):
                candidate.reinforcement_hits += int(reinforcement_by_key[candidate.canonical_key])
        ranked = rank_candidates(
            candidates, weights=self.weights, now=context.started_at or time.time()
        )
        result = DeepResult()
        for candidate in ranked:
            candidate.proposed_lane = choose_promotion_lane(candidate)
            if self.config.quarantine_on_risk_flags and candidate.risk_flags:
                result.demoted.append(candidate)
                continue
            if (
                candidate.proposed_lane == "memory"
                and candidate.total_score >= self.config.memory_threshold
            ):
                result.promoted_memory.append(candidate)
            elif (
                candidate.proposed_lane == "genome"
                and candidate.total_score >= self.config.genome_threshold
            ):
                result.promoted_genomes.append(candidate)
            elif (
                candidate.proposed_lane == "pattern"
                and candidate.total_score >= self.config.pattern_threshold
            ):
                result.promoted_patterns.append(candidate)
            elif (
                candidate.total_score >= self.config.deep_promotion_threshold
                and candidate.proposed_lane == "memory"
            ):
                result.promoted_memory.append(candidate)
            else:
                result.demoted.append(candidate)
        result.metrics = {
            "ranked": len(ranked),
            "memory": len(result.promoted_memory),
            "genome": len(result.promoted_genomes),
            "pattern": len(result.promoted_patterns),
            "demoted": len(result.demoted),
        }
        return result
