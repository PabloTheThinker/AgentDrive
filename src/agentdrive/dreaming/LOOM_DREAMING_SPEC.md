Codex usage: in=1617 out=22188
# Loom Dreaming — Refined Concept

Loom Dreaming is Agent Drive’s substrate-wide reflection cycle: an append-only, offline-biased process that consolidates signals from the whole Loom, stress-tests what it learned, and turns the strongest structures into three kinds of waking-state artifacts: durable memory, evolved genomes, and reusable reasoning patterns. The key architectural shift from OpenClaw is that dreaming is no longer “workspace memory maintenance”; it is a substrate self-modeling mechanism.

## 1) Common signal model

Each substrate emits different raw evidence, but Light normalizes everything into a single candidate schema.

**Swarm event logs** emit:
- task completions, retries, failures, escalations
- agent participation counts
- repeated tool sequences
- operator intervention frequency

These are high-context but noisy. They get moderate base salience and strong diversity/context credit.

**Genome fitness deltas** emit:
- genome id
- fitness delta magnitude and sign
- recombination count
- mutation lineage depth
- selection/survival events

These are structurally important. A genome with repeated positive deltas or deep recombination history gets much higher dream-time than a one-off operational event.

**Reasoning ledger patterns** emit:
- contradiction detected/resolved
- anomaly cluster recurrence
- witness confirmations
- synthesis success/failure
- reasoning pattern ids and confidence shifts

These are coherence-rich and heavily inform both pattern promotion and adversarial attack design.

**Pool ingest** emits:
- new external inputs from `ingest.jsonl`
- source/domain metadata
- repeated resurfacing of similar documents/tasks
- tags/concepts extracted upstream

These start with low prior salience unless echoed by other substrates.

**Peer interactions** emit:
- grant changes
- trust/confidence shifts
- repeated collaboration or refusal patterns
- cross-peer requests that repeatedly succeed or fail

These are social coordination signals; they matter most when they align with reasoning or genome outcomes.

All raw inputs become `DreamCandidate` instances through a **normalized signal layer** with:
- canonical key / recurrence key
- substrate provenance
- timestamp bounds
- source refs
- structural refs: genome ids, ledger ids, peer ids, content paths
- salience features
- lane hints: `memory`, `genome`, `pattern`
- risk flags

This is important: Light does **not** decide truth. It decides what the substrate keeps noticing.

## 2) Dream candidate shape

A dream candidate is the minimum unit that can survive across phases.

Core fields:
- `candidate_id`
- `canonical_key`
- `kind`
- `supporting_signals[]`
- `source_substrates[]`
- `content_refs[]`
- `genome_refs[]`
- `first_seen`, `last_seen`
- `occurrence_count`
- `distinct_contexts`
- `recurrence_days`
- `recombination_count`
- `concepts[]`
- `reinforcement_hits`
- `risk_flags[]`
- `score_components{}`
- `total_score`
- `proposed_lane`
- `provenance{ dream_run_id, snapshot_manifest, source_paths }`

This schema keeps raw primitive references intact. Dreaming must always be able to point back to the exact waking evidence that generated a candidate.

## 3) Time-dilated sleep windows

Dreaming should run when the operator is offline, not at a fixed wall-clock time.

**Offline detection** should be heuristic and conservative:
- no operator-tagged events for `quiet_period_seconds`
- no recent writes to interactive surfaces like ingest, active swarm logs, or direct operator control paths
- no exclusive runtime lock already held by waking orchestration
- optional low system load / no urgent quarantine backlog

A sleep window opens only if quiet persists past a threshold, e.g. 10–15 minutes.

**Time dilation** means:
- wall-clock budget is small, e.g. 5–20 minutes
- simulated budget is larger, e.g. 2–12 “reasoning hours”
- REM uses compressed tick evaluation on snapshots, not live agents

Practical rule: dreaming works against a **run snapshot** of recent ledgers, pool state, swarm logs, and selected genomes. Wake conditions:
- operator activity resumes
- tick budget exhausted
- error budget exceeded
- exclusive lock contested
- quarantine or safety threshold trips

The dream ends immediately on wake, with a checkpoint.

## 4) Adversarial phase

Between REM and Deep, every staged candidate is attacked by an adversary-class genome.

The **Adversary genome** is not random. It is built from the substrate’s strongest contradiction-finding, anomaly-detecting, and exploit-seeking patterns:
- contradiction injectors from reasoning ledger history
- provenance tamper probes
- counterfactual task framings
- fitness challenge templates
- peer/social manipulation tests where relevant

Operationally, “attack” means different things by lane:

- **Memory candidate**: search for contradictory evidence, stale evidence, provenance gaps, or overgeneralization.
- **Genome candidate**: run simulated tasks against the day’s ledger; challenge reward hacking, brittleness, contradiction susceptibility, or confidence collapse.
- **Pattern candidate**: replay the pattern across multiple contexts to see whether it remains useful or collapses outside its original frame.

Outputs are not just pass/fail. Each candidate gets:
- survival boolean
- penalty/bonus
- trace of attack vectors
- contradiction refs
- reason for demotion or quarantine

This makes REM biologically useful: the Loom doesn’t merely fantasize; it tests its fantasies against internal threat models.

## 5) Three-lane promotion

Deep scoring uses the six-signal weighted ranker plus REM reinforcement and adversarial adjustment, but promotion has **three destinations**:

**Memory lane**
- stable factual or procedural knowledge
- multiple supporting substrates
- low contradiction risk
- strong provenance anchors
- little need for mutation

**Genome lane**
- recombinant or highly selected behavioral structures
- simulated fitness uplift in REM
- adversarial survival
- clear ancestry/provenance
- worth adding to `pool/genomes`

**Pattern lane**
- repeated reasoning strategies that worked across contexts/dreams
- tied to ledger evidence, not just one success
- useful as meta-strategies for future reasoning

Same scoring math, different lane validators.

## 6) Coherence guarantees

Dreaming must never corrupt waking state.

Guarantees:
- snapshot-based reads
- append-only dream namespace under `~/.agentdrive/dreams/`
- two-phase promotion: stage first, commit later
- provenance tagging on every artifact: `origin=dreaming`, `dream_run_id`, source refs
- no direct mutation of active swarm state
- no ISO/hypothetical agent promoted directly into active execution
- quarantine hook for failed or suspicious artifacts
- every promotion reversible by `dream_run_id`

Dreaming writes proposals, not silent replacements.

## 7) Failure modes and reversibility

Failure modes:
- false salience from noisy logs
- offline misdetection causing contention
- REM overfitting to recent anomalies
- adversary too weak or too punitive
- score inflation from self-reinforcement loops
- hypothetical genomes that look good in compressed simulation but fail in live conditions

Rollback story:
- every run has a manifest and checkpoints
- every staged promotion is recorded before commit
- commits are append-only with tombstone/retraction support
- backfill into durable destinations is grounded by source refs
- a full run can be replayed or reverted by `dream_run_id`

## Genuine uncertainties

These should be named explicitly:

1. **Operator-offline signal quality** — exact runtime hooks for detecting true operator presence may not yet exist.
2. **Compressed simulation fidelity** — how faithfully the day’s reasoning ledger can stand in for live environmental pressure is uncertain.
3. **Adversary seed construction** — initial adversary may need a hand-tuned profile before enough ledger history exists.
4. **Pattern extraction richness** — conceptual richness depends on tag quality already present upstream.
5. **ISO precipitation threshold** — when a hypothetical agent becomes a real candidate inhabitant should begin conservatively.

The design should therefore launch with strict staging, narrow commit thresholds, and strong replay/rollback discipline.

---

# Module Skeleton

## agentdrive/dreaming/__init__.py

```python
"""
dreaming — public surface for Loom Dreaming.

Design goals:
- Expose a small orchestration surface without hiding raw primitives.
- Keep dreaming append-only, provenance-rich, and ledger disciplined.
- No new magic — just disciplined composition + Agent Drive / Genome idioms.
"""

from __future__ import annotations

from agentdrive.dreaming.candidate import CandidateSignal, DreamCandidate
from agentdrive.dreaming.dilation import DilationPolicy, SleepWindow
from agentdrive.dreaming.engine import DreamEngine, DreamEngineConfig
from agentdrive.dreaming.phases import AdversarialResult, DeepResult, LightResult, RemResult

__all__ = [
    "AdversarialResult",
    "CandidateSignal",
    "DeepResult",
    "DilationPolicy",
    "DreamCandidate",
    "DreamEngine",
    "DreamEngineConfig",
    "LightResult",
    "RemResult",
    "SleepWindow",
]
```

## agentdrive/dreaming/candidate.py

```python
"""
candidate — normalized dream candidates across heterogeneous substrate signals.

Design goals:
- Normalize swarm, genome, ledger, pool, and peer evidence into one shape.
- Preserve provenance tagging and raw primitive references for rollback.
- No new magic — just disciplined composition + Agent Drive / Genome idioms.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from agentdrive.genome.models import Genome

LaneName = Literal["memory", "genome", "pattern"]


@dataclass
class CandidateSignal:
    """A single normalized observation emitted by one substrate."""

    signal_id: str = ""
    substrate: str = ""
    entity_key: str = ""
    kind: str = ""
    observed_at: float = 0.0
    source_path: Path | None = None
    salience: float = 0.0
    retrieval_quality: float = 0.0
    context_key: str = ""
    recurrence_key: str = ""
    lane_hints: list[LaneName] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    genome: Genome | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class DreamCandidate:
    """Aggregate candidate used across Light, REM, Adversarial, and Deep phases."""

    candidate_id: str = ""
    canonical_key: str = ""
    kind: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    supporting_signals: list[CandidateSignal] = field(default_factory=list)
    source_substrates: list[str] = field(default_factory=list)
    content_refs: list[Path] = field(default_factory=list)
    genome_refs: list[str] = field(default_factory=list)
    pattern_refs: list[str] = field(default_factory=list)
    peer_refs: list[str] = field(default_factory=list)
    lane_hints: list[LaneName] = field(default_factory=list)
    occurrence_count: int = 0
    distinct_contexts: int = 0
    recurrence_days: int = 0
    recombination_count: int = 0
    concepts: list[str] = field(default_factory=list)
    reinforcement_hits: int = 0
    adversary_penalty: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    score_components: dict[str, float] = field(default_factory=dict)
    total_score: float = 0.0
    proposed_lane: LaneName | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)


def signal_from_swarm_event(event: dict[str, Any], source_path: Path) -> CandidateSignal:
    """Normalize a swarm event log record into a candidate signal."""
    observed_at = float(event.get("ts") or time.time())
    signal = CandidateSignal(
        signal_id=str(event.get("event_id") or event.get("id") or observed_at),
        substrate="swarms",
        entity_key=str(event.get("task_id") or event.get("agent_id") or "swarm-event"),
        kind=str(event.get("type") or "swarm_event"),
        observed_at=observed_at,
        source_path=source_path,
    )
    # Lift swarm-specific semantics into lane hints, recurrence keys, and salience.
    # Favor retries, escalations, repeated tool chains, and operator interventions.
    # Preserve the raw event in metadata for grounded replay and backfill.
    return signal


def signal_from_genome_delta(
    delta: dict[str, Any],
    source_path: Path,
    genome: Genome | None = None,
) -> CandidateSignal:
    """Normalize a genome fitness delta or selection event into a candidate signal."""
    observed_at = float(delta.get("ts") or time.time())
    signal = CandidateSignal(
        signal_id=str(delta.get("delta_id") or delta.get("genome_id") or observed_at),
        substrate="genome",
        entity_key=str(delta.get("genome_id") or "unknown-genome"),
        kind=str(delta.get("kind") or "fitness_delta"),
        observed_at=observed_at,
        source_path=source_path,
        genome=genome,
    )
    # Encode delta magnitude, lineage depth, and recombination count in metadata.
    # Give genome-origin signals higher structural salience than one-off log lines.
    # Keep enough provenance to reconstruct ancestry and drive lineage later.
    return signal


def signal_from_reasoning_entry(entry: dict[str, Any], source_path: Path) -> CandidateSignal:
    """Normalize a reasoning ledger entry into a candidate signal."""
    observed_at = float(entry.get("ts") or time.time())
    signal = CandidateSignal(
        signal_id=str(entry.get("entry_id") or entry.get("pattern_id") or observed_at),
        substrate="reasoning",
        entity_key=str(entry.get("pattern_id") or entry.get("topic") or "reasoning-entry"),
        kind=str(entry.get("kind") or "reasoning_pattern"),
        observed_at=observed_at,
        source_path=source_path,
    )
    # Reasoning entries carry contradiction, synthesis, witness, and anomaly semantics.
    # Promote strong pattern entries toward the pattern lane unless evidence says otherwise.
    # Store ledger references verbatim so the adversary can attack grounded artifacts later.
    return signal


def signal_from_pool_ingest(entry: dict[str, Any], source_path: Path) -> CandidateSignal:
    """Normalize a pool ingest line into a candidate signal."""
    observed_at = float(entry.get("ts") or time.time())
    signal = CandidateSignal(
        signal_id=str(entry.get("ingest_id") or entry.get("source") or observed_at),
        substrate="pool",
        entity_key=str(entry.get("source") or entry.get("uri") or "ingest-entry"),
        kind=str(entry.get("kind") or "ingest"),
        observed_at=observed_at,
        source_path=source_path,
    )
    # Pool ingest starts with a low prior until echoed by other substrates.
    # Lift concepts, tags, and document references into the normalized schema.
    # Preserve raw ingest metadata so Deep can later backfill durable memory safely.
    return signal


def signal_from_peer_event(event: dict[str, Any], source_path: Path) -> CandidateSignal:
    """Normalize a peer interaction record into a candidate signal."""
    observed_at = float(event.get("ts") or time.time())
    signal = CandidateSignal(
        signal_id=str(event.get("event_id") or event.get("peer_id") or observed_at),
        substrate="peers",
        entity_key=str(event.get("peer_id") or "peer-event"),
        kind=str(event.get("kind") or "peer_interaction"),
        observed_at=observed_at,
        source_path=source_path,
    )
    # Social signals matter most when they correlate with reasoning or genome outcomes.
    # Encode trust shifts, grant changes, and repeated coordination patterns as metadata.
    # Keep peer identifiers stable so recurrence can be measured across dream runs.
    return signal


def merge_signals_into_candidates(signals: list[CandidateSignal]) -> list[DreamCandidate]:
    """Coalesce normalized signals into aggregate dream candidates."""
    grouped: dict[str, DreamCandidate] = {}
    for signal in signals:
        key = signal.recurrence_key or signal.entity_key or signal.signal_id
        candidate = grouped.setdefault(
            key,
            DreamCandidate(
                candidate_id=key,
                canonical_key=key,
                kind=signal.kind,
                created_at=signal.observed_at,
                updated_at=signal.observed_at,
            ),
        )
        candidate.supporting_signals.append(signal)
        # Fold substrate lists, refs, concepts, and lane hints into the aggregate candidate.
        # Update occurrence, recency bounds, and structural counters from source metadata.
    return list(grouped.values())
```

## agentdrive/dreaming/ingestion.py

```python
"""
ingestion — collect and normalize recent signals from every major substrate.

Design goals:
- Pull from runtime roots without inventing new storage contracts.
- Keep substrate weighting explicit and provenance tagging intact.
- No new magic — just disciplined composition + Agent Drive / Genome idioms.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentdrive.dreaming.candidate import (
    CandidateSignal,
    signal_from_genome_delta,
    signal_from_peer_event,
    signal_from_pool_ingest,
    signal_from_reasoning_entry,
    signal_from_swarm_event,
)
from agentdrive.genome.models import Genome


@dataclass
class IngestionConfig:
    """Filesystem roots and substrate weighting for Light-phase ingestion."""

    runtime_root: Path = field(default_factory=lambda: Path("~/.agentdrive").expanduser())
    swarms_root: Path = field(default_factory=lambda: Path("~/.agentdrive/swarms").expanduser())
    reasoning_root: Path = field(default_factory=lambda: Path("~/.agentdrive/reasoning/ledger").expanduser())
    pool_ingest_path: Path = field(default_factory=lambda: Path("~/.agentdrive/pool/ingest.jsonl").expanduser())
    pool_genomes_root: Path = field(default_factory=lambda: Path("~/.agentdrive/pool/genomes").expanduser())
    peers_root: Path = field(default_factory=lambda: Path("~/.agentdrive/peers").expanduser())
    since_seconds: int = 86_400
    substrate_weights: dict[str, float] = field(
        default_factory=lambda: {
            "swarms": 0.9,
            "genome": 1.3,
            "reasoning": 1.2,
            "pool": 0.7,
            "peers": 0.8,
        }
    )


@dataclass
class MultiSubstrateIngestor:
    """Collector that turns recent runtime evidence into normalized signals."""

    config: IngestionConfig = field(default_factory=IngestionConfig)

    def collect_swarm_signals(self, since_ts: float) -> list[CandidateSignal]:
        """Collect recent swarm events and normalize them into dream signals."""
        signals: list[CandidateSignal] = []
        # Walk ~/.agentdrive/swarms/* for event logs or ledger-like JSONL files.
        # Filter records by timestamp and ignore files older than the sleep window.
        # Normalize each retained record through signal_from_swarm_event().
        # Apply substrate weighting in metadata rather than mutating the raw event.
        return signals

    def collect_genome_signals(self, since_ts: float) -> list[CandidateSignal]:
        """Collect genome deltas, selection traces, and staged genomes."""
        signals: list[CandidateSignal] = []
        # Inspect pool genomes and any fitness-delta sidecars available at runtime.
        # Optionally hydrate a Genome object when a stable model file is present.
        # Normalize recombination depth, fitness movement, and ancestry refs.
        # Emit higher-salience signals for repeated winners or heavily recombined genomes.
        return signals

    def collect_reasoning_signals(self, since_ts: float) -> list[CandidateSignal]:
        """Collect recent reasoning ledger entries for patterns, anomalies, and contradictions."""
        signals: list[CandidateSignal] = []
        # Read ledger shards from ~/.agentdrive/reasoning/ledger/.
        # Retain only entries newer than since_ts and relevant to nightly consolidation.
        # Normalize witness hits, synthesis outcomes, and contradiction records.
        # Preserve ledger ids exactly so adversarial replay can target the same evidence.
        return signals

    def collect_pool_signals(self, since_ts: float) -> list[CandidateSignal]:
        """Collect recent pool ingest lines and map them into low-prior signals."""
        signals: list[CandidateSignal] = []
        # Stream ingest.jsonl rather than loading the full file into memory.
        # Ignore records older than since_ts unless explicitly reinforced elsewhere.
        # Normalize source metadata, tags, and raw content references.
        # Keep pool-origin items weak until cross-substrate recurrence emerges.
        return signals

    def collect_peer_signals(self, since_ts: float) -> list[CandidateSignal]:
        """Collect recent peer interactions, trust shifts, and grant changes."""
        signals: list[CandidateSignal] = []
        # Read any peer event ledgers or interaction logs under ~/.agentdrive/peers/.
        # Normalize trust changes, repeated collaborations, and request outcomes.
        # Favor peer patterns corroborated by swarms or reasoning evidence.
        # Tag every signal with its source file for auditability.
        return signals

    def collect_all_signals(self, now: float | None = None) -> list[CandidateSignal]:
        """Collect all recent signals across the substrate."""
        now = now or time.time()
        since_ts = now - self.config.since_seconds
        signals: list[CandidateSignal] = []
        # Aggregate substrate-specific collectors in a fixed, deterministic order.
        signals.extend(self.collect_swarm_signals(since_ts))
        signals.extend(self.collect_genome_signals(since_ts))
        signals.extend(self.collect_reasoning_signals(since_ts))
        signals.extend(self.collect_pool_signals(since_ts))
        signals.extend(self.collect_peer_signals(since_ts))
        return signals
```

## agentdrive/dreaming/scoring.py

```python
"""
scoring — weighted candidate scoring for Deep promotion and REM reinforcement.

Design goals:
- Keep the OpenClaw math recognizable while adapting it to a living Loom.
- Separate raw component calculation from lane choice and storage.
- No new magic — just disciplined composition + Agent Drive / Genome idioms.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

from agentdrive.dreaming.candidate import DreamCandidate
from agentdrive.genome.models import Genome


@dataclass
class ScoreWeights:
    """Weights for the six core scoring signals plus dream-specific modifiers."""

    frequency: float = 0.24
    relevance: float = 0.30
    query_diversity: float = 0.15
    recency: float = 0.15
    consolidation: float = 0.10
    conceptual_richness: float = 0.06
    reinforcement: float = 0.10
    adversary_survival_bonus: float = 0.08
    adversary_failure_penalty: float = 0.15


@dataclass
class CandidateScore:
    """Computed score breakdown for one dream candidate."""

    candidate_id: str = ""
    components: dict[str, float] = field(default_factory=dict)
    reinforcement_boost: float = 0.0
    adversary_adjustment: float = 0.0
    total_score: float = 0.0


def compute_component_scores(candidate: DreamCandidate, now: float | None = None) -> dict[str, float]:
    """Compute the six base signal components for a candidate."""
    now = now or time.time()
    components = {
        "frequency": 0.0,
        "relevance": 0.0,
        "query_diversity": 0.0,
        "recency": 0.0,
        "consolidation": 0.0,
        "conceptual_richness": 0.0,
    }
    # Frequency is log-scaled occurrence volume across supporting signals.
    # Relevance averages retrieval-quality style evidence available on signals.
    # Recency uses a time-decay curve anchored on candidate.updated_at.
    # Consolidation and richness reward multi-day recurrence and concept density.
    return components


def compute_reinforcement_boost(candidate: DreamCandidate) -> float:
    """Compute REM reinforcement for a candidate using recency-decayed hits."""
    boost = 0.0
    # REM reinforcement should be bounded so it cannot dominate base evidence.
    # Use candidate.reinforcement_hits as the primary carrier for dream feedback.
    # Fold in candidate.adversary_penalty later rather than mutating the boost here.
    # Keep the value unitless so Deep can combine it with the weighted base score.
    return boost


def score_candidate(
    candidate: DreamCandidate,
    weights: ScoreWeights | None = None,
    now: float | None = None,
) -> CandidateScore:
    """Score a dream candidate and update its cached score fields."""
    weights = weights or ScoreWeights()
    components = compute_component_scores(candidate, now=now)
    base_score = (
        components["frequency"] * weights.frequency
        + components["relevance"] * weights.relevance
        + components["query_diversity"] * weights.query_diversity
        + components["recency"] * weights.recency
        + components["consolidation"] * weights.consolidation
        + components["conceptual_richness"] * weights.conceptual_richness
    )
    # Apply REM reinforcement and adversarial adjustments after the six-signal base score.
    # Cache the result on the candidate so later phases stay 100% compatible with raw primitives.
    return CandidateScore(candidate_id=candidate.candidate_id, components=components, total_score=base_score)


def rank_candidates(
    candidates: list[DreamCandidate],
    weights: ScoreWeights | None = None,
    now: float | None = None,
) -> list[DreamCandidate]:
    """Score and sort candidates from strongest to weakest."""
    weights = weights or ScoreWeights()
    ranked: list[DreamCandidate] = []
    for candidate in candidates:
        score = score_candidate(candidate, weights=weights, now=now)
        candidate.score_components = score.components
        candidate.total_score = score.total_score
        ranked.append(candidate)
    ranked.sort(key=lambda item: item.total_score, reverse=True)
    return ranked
```

## agentdrive/dreaming/dilation.py

```python
"""
dilation — detect operator-offline windows and allocate dream tick budgets.

Design goals:
- Prefer conservative wake/sleep boundaries over aggressive background work.
- Translate wall-clock quiet into bounded simulated reasoning time.
- No new magic — just disciplined composition + Agent Drive / Genome idioms.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentdrive.genome.models import Genome


@dataclass
class DilationPolicy:
    """Policy for opening, sustaining, and closing a sleep window."""

    runtime_root: Path = field(default_factory=lambda: Path("~/.agentdrive").expanduser())
    quiet_period_seconds: int = 900
    min_window_seconds: int = 300
    max_window_seconds: int = 1_800
    dilation_ratio: float = 24.0
    ticks_per_simulated_hour: int = 60
    wake_paths: list[Path] = field(
        default_factory=lambda: [
            Path("~/.agentdrive/pool/ingest.jsonl").expanduser(),
            Path("~/.agentdrive/swarms").expanduser(),
            Path("~/.agentdrive/reasoning/ledger").expanduser(),
        ]
    )


@dataclass
class SleepWindow:
    """Computed sleep window and tick budget for one dream run."""

    opened_at: float = 0.0
    last_operator_activity: float = 0.0
    wall_budget_seconds: int = 0
    simulated_hours: float = 0.0
    tick_budget: int = 0
    wake_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def estimate_operator_last_activity(policy: DilationPolicy) -> float:
    """Estimate the most recent operator or waking-state activity timestamp."""
    mtimes: list[float] = []
    # Probe known interactive paths and collect the freshest modification times.
    # A future implementation can also consult event streams or explicit operator heartbeats.
    # If nothing is available, treat "now" as recent activity to stay conservative.
    # This errs on the side of not dreaming rather than dreaming unsafely.
    return max(mtimes) if mtimes else time.time()


def compute_tick_budget(window_seconds: int, policy: DilationPolicy) -> int:
    """Translate wall-clock sleep time into a bounded simulated tick budget."""
    simulated_hours = (window_seconds / 3600.0) * policy.dilation_ratio
    tick_budget = int(simulated_hours * policy.ticks_per_simulated_hour)
    # Clamp budgets so short idle periods do not trigger huge REM simulations.
    # The returned value is a soft cap for simulated evaluation, not live agent execution.
    # Wake conditions can still cut the run short even if budget remains.
    return max(0, tick_budget)


def detect_sleep_window(policy: DilationPolicy) -> SleepWindow | None:
    """Detect whether the substrate is sufficiently idle to start dreaming."""
    now = time.time()
    last_activity = estimate_operator_last_activity(policy)
    quiet_for = now - last_activity
    if quiet_for < policy.quiet_period_seconds:
        return None
    wall_budget = min(max(int(quiet_for), policy.min_window_seconds), policy.max_window_seconds)
    tick_budget = compute_tick_budget(wall_budget, policy)
    return SleepWindow(
        opened_at=now,
        last_operator_activity=last_activity,
        wall_budget_seconds=wall_budget,
        simulated_hours=(wall_budget / 3600.0) * policy.dilation_ratio,
        tick_budget=tick_budget,
    )


def should_wake(window: SleepWindow, policy: DilationPolicy) -> bool:
    """Check whether current conditions should terminate the sleep window."""
    latest_activity = estimate_operator_last_activity(policy)
    # Wake immediately if new operator activity appears after the window opened.
    # A future implementation can also watch locks, quarantine backlog, or error budgets.
    # This function is intentionally cheap so the engine can poll it between phases.
    return latest_activity > window.opened_at
```

## agentdrive/dreaming/adversary.py

```python
"""
adversary — stress-test dream candidates before Deep promotion.

Design goals:
- Attack staged candidates using contradiction, provenance, and fitness pressure.
- Emit traceable pass/fail evidence instead of opaque penalties.
- No new magic — just disciplined composition + Agent Drive / Genome idioms.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from agentdrive.dreaming.candidate import DreamCandidate
from agentdrive.genome.models import Genome


@dataclass
class AdversaryProfile:
    """Configuration and provenance for the current adversary-class genome."""

    name: str = "counterexample_hunter"
    source_genome_ids: list[str] = field(default_factory=list)
    contradiction_weight: float = 0.40
    anomaly_weight: float = 0.25
    provenance_attack_weight: float = 0.20
    fitness_challenge_weight: float = 0.15
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class AttackTrace:
    """Trace record describing one adversarial pressure applied to a candidate."""

    candidate_id: str = ""
    attack_kind: str = ""
    passed: bool = False
    severity: float = 0.0
    notes: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdversaryResult:
    """Summarized adversarial result for one candidate."""

    candidate_id: str = ""
    survived: bool = False
    bonus: float = 0.0
    penalty: float = 0.0
    traces: list[AttackTrace] = field(default_factory=list)


@dataclass
class DreamAdversary:
    """Adversarial evaluator for REM outputs and Light-stage winners."""

    profile: AdversaryProfile = field(default_factory=AdversaryProfile)

    def build_seed_profile(self, ledger_entries: list[dict[str, Any]] | None = None) -> AdversaryProfile:
        """Build an adversary profile from recent contradiction and anomaly history."""
        ledger_entries = ledger_entries or []
        profile = AdversaryProfile()
        # Mine recent ledger history for contradiction-heavy and exploit-finding patterns.
        # Keep the profile explainable: each weight should map back to real ledger evidence.
        # A later implementation can hydrate a concrete Genome once the adversary seed exists.
        # For now, return a portable profile that phases can log and replay.
        return profile

    def attack_candidate(
        self,
        candidate: DreamCandidate,
        reasoning_engine: Any | None = None,
        ledger_entries: list[dict[str, Any]] | None = None,
    ) -> AdversaryResult:
        """Attack one candidate with lane-aware contradiction and fitness pressure."""
        ledger_entries = ledger_entries or []
        result = AdversaryResult(candidate_id=candidate.candidate_id)
        # Memory lane: seek contradiction, stale provenance, and overgeneralization.
        # Genome lane: run compressed task challenges against ledger-derived scenarios.
        # Pattern lane: replay the strategy across multiple contexts to test transferability.
        # Emit structured traces instead of mutating the candidate in place here.
        return result

    def attack_candidates(
        self,
        candidates: list[DreamCandidate],
        reasoning_engine: Any | None = None,
        ledger_entries: list[dict[str, Any]] | None = None,
    ) -> list[AdversaryResult]:
        """Attack a batch of candidates and return ordered results."""
        results: list[AdversaryResult] = []
        for candidate in candidates:
            result = self.attack_candidate(candidate, reasoning_engine=reasoning_engine, ledger_entries=ledger_entries)
            # Later phases can translate each result into bonus, penalty, quarantine, or demotion.
            results.append(result)
        return results
```

## agentdrive/dreaming/narrative.py

```python
"""
narrative — write Dream Diary entries as a byproduct of substantive dream work.

Design goals:
- Keep diary generation secondary to actual consolidation and ISO emergence.
- Preserve phase context and provenance for auditability.
- No new magic — just disciplined composition + Agent Drive / Genome idioms.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentdrive.genome.models import Genome


@dataclass
class NarrativeConfig:
    """Paths and formatting rules for Dream Diary output."""

    diary_root: Path = field(default_factory=lambda: Path("~/.agentdrive/dreams/diary").expanduser())
    diary_name: str = "DREAMS.md"
    append_jsonl: bool = True


@dataclass
class DreamDiaryEntry:
    """Narrative record emitted after a dream phase finishes."""

    run_id: str = ""
    phase: str = ""
    created_at: float = 0.0
    summary: str = ""
    prompt: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DreamNarrator:
    """Diary writer that can use a subagent or raw primitives."""

    config: NarrativeConfig = field(default_factory=NarrativeConfig)

    def render_phase_prompt(self, run_id: str, phase: str, payload: dict[str, Any]) -> str:
        """Render the prompt/context passed to the Dream Diary writer."""
        prompt_lines = [
            f"Run: {run_id}",
            f"Phase: {phase}",
            "Summarize the substrate's reflection in Tron-like but operationally precise terms.",
        ]
        # Include key metrics, top candidates, and any adversarial wins/losses.
        # Keep the prompt deterministic so diary output can be compared across runs.
        # Diary output is expressive, but the prompt should stay ledger disciplined.
        return "\n".join(prompt_lines)

    def dispatch_phase_diary(self, run_id: str, phase: str, payload: dict[str, Any]) -> DreamDiaryEntry:
        """Dispatch or synthesize a Dream Diary entry for one completed phase."""
        prompt = self.render_phase_prompt(run_id, phase, payload)
        entry = DreamDiaryEntry(run_id=run_id, phase=phase, created_at=time.time(), prompt=prompt)
        # A future implementation can call a Agent Drive subagent or raw LLM primitive here.
        # If no subagent is available, fall back to a deterministic summary string.
        # Keep the diary optional; failure to narrate must not fail the dream run.
        return entry

    def write_phase_entry(self, entry: DreamDiaryEntry) -> Path:
        """Persist a Dream Diary entry to markdown and optional JSONL."""
        self.config.diary_root.mkdir(parents=True, exist_ok=True)
        markdown_path = self.config.diary_root / self.config.diary_name
        # Append a markdown section keyed by run id and phase for human-readable review.
        # Optionally mirror the structured entry into JSONL for tooling and replay.
        # Keep diary writes append-only so they never rewrite waking-state artifacts.
        return markdown_path
```

## agentdrive/dreaming/storage.py

```python
"""
storage — run layout, checkpoints, locks, and staged promotion artifacts for dreaming.

Design goals:
- Keep dream writes isolated under ~/.agentdrive/dreams/ until explicit commit.
- Make every phase replayable, auditable, and reversible by dream_run_id.
- No new magic — just disciplined composition + Agent Drive / Genome idioms.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentdrive.dreaming.candidate import DreamCandidate
from agentdrive.dreaming.dilation import SleepWindow
from agentdrive.genome.models import Genome


@dataclass
class DreamPaths:
    """Filesystem layout for dream runs and staged artifacts."""

    root: Path = field(default_factory=lambda: Path("~/.agentdrive/dreams").expanduser())
    runs: Path = field(default_factory=lambda: Path("~/.agentdrive/dreams/runs").expanduser())
    checkpoints: Path = field(default_factory=lambda: Path("~/.agentdrive/dreams/checkpoints").expanduser())
    promotions: Path = field(default_factory=lambda: Path("~/.agentdrive/dreams/promotions").expanduser())
    diary: Path = field(default_factory=lambda: Path("~/.agentdrive/dreams/diary").expanduser())
    locks: Path = field(default_factory=lambda: Path("~/.agentdrive/dreams/locks").expanduser())
    snapshots: Path = field(default_factory=lambda: Path("~/.agentdrive/dreams/snapshots").expanduser())


@dataclass
class DreamRunRecord:
    """Metadata for one dream run."""

    run_id: str = ""
    created_at: float = 0.0
    status: str = "created"
    run_dir: Path | None = None
    snapshot_manifest: Path | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class PhaseCheckpoint:
    """Checkpoint emitted after each dream phase completes or aborts."""

    run_id: str = ""
    phase: str = ""
    status: str = "started"
    started_at: float = 0.0
    completed_at: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)
    artifact_paths: list[Path] = field(default_factory=list)


@dataclass
class DreamStorage:
    """Storage manager for locks, manifests, checkpoints, and staged promotions."""

    paths: DreamPaths = field(default_factory=DreamPaths)

    def ensure_layout(self) -> DreamPaths:
        """Create the standard dream directory layout if it does not already exist."""
        for path in [
            self.paths.root,
            self.paths.runs,
            self.paths.checkpoints,
            self.paths.promotions,
            self.paths.diary,
            self.paths.locks,
            self.paths.snapshots,
        ]:
            path.mkdir(parents=True, exist_ok=True)
        return self.paths

    def acquire_lock(self, name: str = "dreaming") -> Path | None:
        """Acquire a coarse-grained lock for a dream run."""
        self.ensure_layout()
        lock_path = self.paths.locks / f"{name}.lock"
        # Use a simple file lock first; replace with a stronger primitive if runtime demands it.
        # Refuse to proceed if a sibling dream run or waking coordinator already owns the lock.
        # Keep lock acquisition auditable by writing run metadata beside the lock later.
        return lock_path

    def release_lock(self, lock_path: Path | None) -> None:
        """Release a previously acquired dream lock."""
        if lock_path is None:
            return
        # Remove or invalidate the lock file only if this run still owns it.
        # A later implementation should store owner metadata to avoid stale-lock races.
        # Silent cleanup is acceptable here because release happens in a finally block.
        return None

    def create_run(self, window: SleepWindow | None = None) -> DreamRunRecord:
        """Create a new run directory and metadata record."""
        created_at = time.time()
        run_id = f"dream-{int(created_at)}"
        run_dir = self.paths.runs / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        # Persist a small manifest with timing, window info, and initial provenance.
        # Keep the record minimal so aborted runs are still easy to inspect and purge.
        return DreamRunRecord(run_id=run_id, created_at=created_at, run_dir=run_dir)

    def write_snapshot_manifest(self, run: DreamRunRecord, snapshot: dict[str, Any]) -> Path:
        """Persist the snapshot manifest used to isolate dreaming from waking state."""
        manifest_path = self.paths.snapshots / f"{run.run_id}.json"
        # Record source roots, ledger shards, selected genomes, and time bounds.
        # Snapshot manifests make dream outputs replayable and reversible later.
        # The manifest should be append-only once written for a given run id.
        return manifest_path

    def write_phase_checkpoint(self, checkpoint: PhaseCheckpoint) -> Path:
        """Write a phase checkpoint artifact."""
        checkpoint_path = self.paths.checkpoints / f"{checkpoint.run_id}-{checkpoint.phase}.json"
        # Persist structured status, metrics, and artifact refs after each phase.
        # Checkpoints should survive partial failure so rollback has a stable story.
        # Avoid embedding bulky payloads; point at files staged elsewhere instead.
        return checkpoint_path

    def stage_promotion(self, run: DreamRunRecord, lane: str, candidate: DreamCandidate) -> Path:
        """Stage a promotion artifact under the dreams namespace."""
        lane_root = self.paths.promotions / lane
        lane_root.mkdir(parents=True, exist_ok=True)
        artifact_path = lane_root / f"{run.run_id}-{candidate.candidate_id}.json"
        # Write a reversible proposal artifact, not a direct mutation of live state.
        # Include provenance, score breakdown, source refs, and adversarial traces.
        # Later commit logic can backfill this artifact into durable waking destinations.
        return artifact_path

    def commit_run(self, run: DreamRunRecord) -> None:
        """Mark a dream run as committed and eligible for waking-state backfill."""
        # Commit should only flip run status and finalize staged artifacts.
        # Real destination writes can remain a separate step if operational caution is needed.
        # This keeps dreaming 100% compatible with manual review or delayed promotion.
        return None

    def rollback_run(self, run: DreamRunRecord, reason: str) -> None:
        """Rollback a run by marking its staged artifacts as retracted."""
        # Do not delete evidence; write a tombstone or rollback manifest keyed by run id.
        # Keep enough structured context to back out memory, genome, or pattern promotions later.
        # Rollback should be idempotent so repeated safety calls remain harmless.
        return None
```

## agentdrive/dreaming/phases.py

```python
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

from agentdrive.dreaming.adversary import AdversaryResult, DreamAdversary
from agentdrive.dreaming.candidate import DreamCandidate, LaneName, merge_signals_into_candidates
from agentdrive.dreaming.ingestion import MultiSubstrateIngestor
from agentdrive.dreaming.scoring import ScoreWeights, rank_candidates
from agentdrive.genome.models import Genome


@dataclass
class DreamPhaseContext:
    """Shared context passed through all phases in one run."""

    run_id: str = ""
    started_at: float = 0.0
    runtime_root: Path = field(default_factory=lambda: Path("~/.agentdrive").expanduser())
    tick_budget: int = 0
    snapshot_manifest: Path | None = None
    reasoning_engine: Any | None = None
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
        # Light performs no durable writes beyond checkpoints written by the engine.
        # Deduping and recurrence shaping happen here before any REM generation begins.
        # Keep the result rich enough for raw-primitive inspection if needed.
        return LightResult(signals_collected=len(signals), candidates=candidates)


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
        # Recombine genome-rich candidates using existing agentdrive.evolution primitives.
        # Spawn hypothetical agents and evaluate them against the day's reasoning ledger snapshot.
        # Convert noteworthy survivors back into candidate reinforcement rather than live agents.
        # The diary is a byproduct; the real REM output is inhabitants plus reinforcement.
        return RemResult(inhabitants=inhabitants, candidates=selected, reinforcement_by_key=reinforcement_by_key)


@dataclass
class AdversarialPhase:
    """Threat-consolidation phase that attacks staged dream artifacts."""

    adversary: DreamAdversary = field(default_factory=DreamAdversary)

    def run(self, context: DreamPhaseContext, candidates: list[DreamCandidate]) -> AdversarialResult:
        """Attack staged candidates and partition survivors from defeated entries."""
        results = self.adversary.attack_candidates(candidates, reasoning_engine=context.reasoning_engine)
        survivors: list[DreamCandidate] = []
        defeated: list[DreamCandidate] = []
        for candidate, result in zip(candidates, results):
            # Apply penalty or bonus later; this phase just records outcome and partition.
            (survivors if result.survived else defeated).append(candidate)
        return AdversarialResult(survivors=survivors, defeated=defeated, results=results)


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
        ranked = rank_candidates(candidates, weights=self.weights, now=context.started_at or time.time())
        result = DeepResult()
        for candidate in ranked:
            candidate.proposed_lane = choose_promotion_lane(candidate)
            # Apply thresholds, risk checks, and lane-specific rules before promotion.
            # Keep suspicious artifacts out of live destinations; quarantine remains available upstream.
            # Route each passing candidate into exactly one lane for coherent waking-state backfill.
        return result
```

## agentdrive/dreaming/engine.py

```python
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

from agentdrive.dreaming.dilation import DilationPolicy, SleepWindow, detect_sleep_window, should_wake
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
    reasoning_engine: Any | None = None
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
        # Return the run id so operators can inspect checkpoints and staged promotions.
        # A future daemon can use this as a heartbeat or scheduler output.
        return str(result.get("run_id"))

    def run_once(self, window: SleepWindow | None = None) -> dict[str, Any]:
        """Execute one full dream cycle and return a structured run summary."""
        self.storage.ensure_layout()
        lock_path = self.storage.acquire_lock()
        run = self.storage.create_run(window=window)
        context = self._build_context(run=run, window=window)
        # Snapshot runtime state, then execute Light, REM, Adversarial, and Deep in order.
        # Write checkpoints after every phase and stage promotions under ~/.agentdrive/dreams/.
        # Abort cleanly if should_wake() flips true between phases or an error budget is exceeded.
        # Commit only after all phases complete and the run remains coherent.
        self.storage.release_lock(lock_path)
        return {"run_id": run.run_id, "status": "staged"}

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
        checkpoint = PhaseCheckpoint(
            run_id=run_id,
            phase=phase,
            status="completed",
            started_at=time.time(),
            completed_at=time.time(),
            metrics=metrics,
        )
        # Checkpoints are the rollback spine of the whole design.
        # Keep them lightweight and phase-scoped rather than embedding huge payloads.
        # The returned path can be linked into narratives or operator review tooling.
        return self.storage.write_phase_checkpoint(checkpoint)
```

End.
