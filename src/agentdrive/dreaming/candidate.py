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


def _list_field(record: dict[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        raw = record.get(key)
        if raw is None:
            continue
        if isinstance(raw, list | tuple | set):
            values.extend(str(item) for item in raw if item)
        else:
            values.append(str(raw))
    return values


def _float_field(record: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(record.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def signal_from_swarm_event(event: dict[str, Any], source_path: Path) -> CandidateSignal:
    """Normalize a swarm event log record into a candidate signal."""
    observed_at = float(event.get("ts") or event.get("timestamp") or time.time())
    kind = str(event.get("type") or event.get("kind") or "swarm_event")
    lane_hints: list[LaneName] = (
        ["pattern"] if kind in {"tool_sequence", "retry", "escalation"} else ["memory"]
    )
    signal = CandidateSignal(
        signal_id=str(event.get("event_id") or event.get("id") or observed_at),
        substrate="swarms",
        entity_key=str(event.get("task_id") or event.get("agent_id") or "swarm-event"),
        kind=kind,
        observed_at=observed_at,
        source_path=source_path,
        salience=0.55 + min(_float_field(event, "retry_count") * 0.05, 0.25),
        retrieval_quality=_float_field(event, "confidence", 0.5),
        context_key=str(event.get("task_id") or event.get("run_id") or ""),
        recurrence_key=str(
            event.get("tool_sequence") or event.get("task_id") or event.get("agent_id") or ""
        ),
        lane_hints=lane_hints,
        tags=_list_field(event, "tags", "concepts"),
        metadata={"raw": event, "substrate_weight": 0.9},
        provenance={"source_path": str(source_path), "origin": "loom_dreaming"},
    )
    return signal


def signal_from_genome_delta(
    delta: dict[str, Any],
    source_path: Path,
    genome: Genome | None = None,
) -> CandidateSignal:
    """Normalize a genome fitness delta or selection event into a candidate signal."""
    observed_at = float(delta.get("ts") or delta.get("timestamp") or time.time())
    genome_id = str(
        delta.get("genome_id")
        or getattr(getattr(genome, "manifest", None), "id", "")
        or "unknown-genome"
    )
    signal = CandidateSignal(
        signal_id=str(delta.get("delta_id") or genome_id or observed_at),
        substrate="genome",
        entity_key=genome_id,
        kind=str(delta.get("kind") or "fitness_delta"),
        observed_at=observed_at,
        source_path=source_path,
        salience=0.7 + min(abs(_float_field(delta, "fitness_delta")) * 0.2, 0.3),
        retrieval_quality=max(0.0, min(1.0, _float_field(delta, "evaluation_score", 0.65))),
        context_key=str(delta.get("evaluation_id") or delta.get("task_id") or ""),
        recurrence_key=genome_id,
        lane_hints=["genome"],
        tags=_list_field(delta, "tags", "concepts"),
        genome=genome,
        metadata={
            "raw": delta,
            "substrate_weight": 1.3,
            "recombination_count": int(_float_field(delta, "recombination_count")),
            "lineage_depth": int(_float_field(delta, "lineage_depth")),
        },
        provenance={"source_path": str(source_path), "origin": "loom_dreaming"},
    )
    return signal


def signal_from_reasoning_entry(entry: dict[str, Any], source_path: Path) -> CandidateSignal:
    """Normalize a reasoning ledger entry into a candidate signal."""
    observed_at = float(entry.get("ts") or entry.get("timestamp") or time.time())
    kind = str(entry.get("kind") or entry.get("operation") or "reasoning_pattern")
    risk_flags = _list_field(entry, "risk_flags")
    if "contradiction" in kind or entry.get("contradiction"):
        risk_flags.append("contradiction")
    signal = CandidateSignal(
        signal_id=str(entry.get("entry_id") or entry.get("pattern_id") or observed_at),
        substrate="reasoning",
        entity_key=str(
            entry.get("pattern_id")
            or entry.get("topic")
            or entry.get("operation")
            or "reasoning-entry"
        ),
        kind=kind,
        observed_at=observed_at,
        source_path=source_path,
        salience=0.68,
        retrieval_quality=_float_field(entry, "confidence", 0.6),
        context_key=str(entry.get("topic") or entry.get("run_id") or ""),
        recurrence_key=str(
            entry.get("pattern_id") or entry.get("topic") or entry.get("operation") or ""
        ),
        lane_hints=["pattern"],
        tags=_list_field(entry, "tags", "concepts"),
        metadata={"raw": entry, "substrate_weight": 1.2, "risk_flags": risk_flags},
        provenance={"source_path": str(source_path), "origin": "loom_dreaming"},
    )
    return signal


def signal_from_pool_ingest(entry: dict[str, Any], source_path: Path) -> CandidateSignal:
    """Normalize a pool ingest line into a candidate signal."""
    observed_at = float(entry.get("ts") or entry.get("timestamp") or time.time())
    signal = CandidateSignal(
        signal_id=str(entry.get("ingest_id") or entry.get("source") or observed_at),
        substrate="pool",
        entity_key=str(entry.get("source") or entry.get("uri") or "ingest-entry"),
        kind=str(entry.get("kind") or "ingest"),
        observed_at=observed_at,
        source_path=source_path,
        salience=0.35,
        retrieval_quality=_float_field(entry, "confidence", 0.4),
        context_key=str(entry.get("domain") or entry.get("source") or ""),
        recurrence_key=str(
            entry.get("canonical_key") or entry.get("uri") or entry.get("source") or ""
        ),
        lane_hints=["memory"],
        tags=_list_field(entry, "tags", "concepts"),
        metadata={"raw": entry, "substrate_weight": 0.7},
        provenance={"source_path": str(source_path), "origin": "loom_dreaming"},
    )
    return signal


def signal_from_peer_event(event: dict[str, Any], source_path: Path) -> CandidateSignal:
    """Normalize a peer interaction record into a candidate signal."""
    observed_at = float(event.get("ts") or event.get("timestamp") or time.time())
    signal = CandidateSignal(
        signal_id=str(event.get("event_id") or event.get("peer_id") or observed_at),
        substrate="peers",
        entity_key=str(event.get("peer_id") or "peer-event"),
        kind=str(event.get("kind") or "peer_interaction"),
        observed_at=observed_at,
        source_path=source_path,
        salience=0.45 + min(abs(_float_field(event, "trust_delta")) * 0.2, 0.25),
        retrieval_quality=_float_field(event, "confidence", 0.5),
        context_key=str(event.get("peer_id") or event.get("grant_id") or ""),
        recurrence_key=str(event.get("peer_id") or event.get("grant_id") or ""),
        lane_hints=["memory", "pattern"],
        tags=_list_field(event, "tags", "concepts"),
        metadata={"raw": event, "substrate_weight": 0.8},
        provenance={"source_path": str(source_path), "origin": "loom_dreaming"},
    )
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
        candidate.updated_at = max(candidate.updated_at, signal.observed_at)
        candidate.created_at = min(candidate.created_at, signal.observed_at)
        candidate.occurrence_count = len(candidate.supporting_signals)
        if signal.substrate and signal.substrate not in candidate.source_substrates:
            candidate.source_substrates.append(signal.substrate)
        if signal.source_path and signal.source_path not in candidate.content_refs:
            candidate.content_refs.append(signal.source_path)
        for hint in signal.lane_hints:
            if hint not in candidate.lane_hints:
                candidate.lane_hints.append(hint)
        for tag in signal.tags:
            if tag not in candidate.concepts:
                candidate.concepts.append(tag)
        if signal.genome:
            genome_ref = signal.genome.genome_id
            if genome_ref not in candidate.genome_refs:
                candidate.genome_refs.append(genome_ref)
        raw_metadata = signal.metadata
        candidate.recombination_count += int(raw_metadata.get("recombination_count") or 0)
        candidate.risk_flags.extend(
            flag for flag in raw_metadata.get("risk_flags", []) if flag not in candidate.risk_flags
        )
        candidate.distinct_contexts = len(
            {item.context_key for item in candidate.supporting_signals if item.context_key}
        )
        candidate.recurrence_days = len(
            {
                time.strftime("%Y-%m-%d", time.gmtime(item.observed_at))
                for item in candidate.supporting_signals
            }
        )
        candidate.provenance.setdefault("source_paths", [])
        if signal.source_path:
            source = str(signal.source_path)
            if source not in candidate.provenance["source_paths"]:
                candidate.provenance["source_paths"].append(source)
    return list(grouped.values())
