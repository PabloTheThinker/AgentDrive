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
from typing import Any, Callable

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
    reasoning_root: Path = field(
        default_factory=lambda: Path("~/.agentdrive/reasoning/ledger").expanduser()
    )
    pool_ingest_path: Path = field(
        default_factory=lambda: Path("~/.agentdrive/pool/ingest.jsonl").expanduser()
    )
    pool_genomes_root: Path = field(
        default_factory=lambda: Path("~/.agentdrive/pool/genomes").expanduser()
    )
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


def _record_ts(record: dict[str, Any]) -> float:
    try:
        return float(record.get("ts") or record.get("timestamp") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists() or not path.is_file():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            loaded = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            records.append(loaded)
    return records


def _iter_json_records(root: Path, patterns: tuple[str, ...]) -> list[tuple[Path, dict[str, Any]]]:
    if not root.exists():
        return []
    paths: list[Path] = []
    if root.is_file():
        paths = [root]
    else:
        for pattern in patterns:
            paths.extend(root.rglob(pattern))
    records: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(set(paths)):
        if not path.is_file():
            continue
        if path.suffix == ".jsonl":
            records.extend((path, record) for record in _iter_jsonl(path))
            continue
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        if isinstance(loaded, dict):
            records.append((path, loaded))
        elif isinstance(loaded, list):
            records.extend((path, item) for item in loaded if isinstance(item, dict))
    return records


@dataclass
class MultiSubstrateIngestor:
    """Collector that turns recent runtime evidence into normalized signals."""

    config: IngestionConfig = field(default_factory=IngestionConfig)

    def _collect_records(
        self,
        root: Path,
        since_ts: float,
        patterns: tuple[str, ...],
        normalizer: Callable[[dict[str, Any], Path], CandidateSignal],
    ) -> list[CandidateSignal]:
        signals: list[CandidateSignal] = []
        for path, record in _iter_json_records(root, patterns):
            if _record_ts(record) and _record_ts(record) < since_ts:
                continue
            signal = normalizer(record, path)
            weight = self.config.substrate_weights.get(signal.substrate)
            if weight is not None:
                signal.metadata.setdefault("substrate_weight", weight)
            signals.append(signal)
        return signals

    def collect_swarm_signals(self, since_ts: float) -> list[CandidateSignal]:
        """Collect recent swarm events and normalize them into dream signals."""
        return self._collect_records(
            self.config.swarms_root,
            since_ts,
            ("*.jsonl", "*.json"),
            signal_from_swarm_event,
        )

    def collect_genome_signals(self, since_ts: float) -> list[CandidateSignal]:
        """Collect genome deltas, selection traces, and staged genomes."""
        signals: list[CandidateSignal] = []
        for path, delta in _iter_json_records(
            self.config.pool_genomes_root, ("*.jsonl", "*delta*.json", "*.json")
        ):
            if _record_ts(delta) and _record_ts(delta) < since_ts:
                continue
            genome = self._load_genome(path)
            signal = signal_from_genome_delta(delta, path, genome=genome)
            signal.metadata.setdefault("substrate_weight", self.config.substrate_weights["genome"])
            signals.append(signal)
        return signals

    def collect_reasoning_signals(self, since_ts: float) -> list[CandidateSignal]:
        """Collect recent reasoning ledger entries for patterns, anomalies, and contradictions."""
        return self._collect_records(
            self.config.reasoning_root,
            since_ts,
            ("*.jsonl", "*.json"),
            signal_from_reasoning_entry,
        )

    def collect_pool_signals(self, since_ts: float) -> list[CandidateSignal]:
        """Collect recent pool ingest lines and map them into low-prior signals."""
        signals: list[CandidateSignal] = []
        for record in _iter_jsonl(self.config.pool_ingest_path):
            if _record_ts(record) and _record_ts(record) < since_ts:
                continue
            signal = signal_from_pool_ingest(record, self.config.pool_ingest_path)
            signal.metadata.setdefault("substrate_weight", self.config.substrate_weights["pool"])
            signals.append(signal)
        return signals

    def collect_peer_signals(self, since_ts: float) -> list[CandidateSignal]:
        """Collect recent peer interactions, trust shifts, and grant changes."""
        return self._collect_records(
            self.config.peers_root,
            since_ts,
            ("*.jsonl", "*.json"),
            signal_from_peer_event,
        )

    def collect_all_signals(self, now: float | None = None) -> list[CandidateSignal]:
        """Collect all recent signals across the substrate."""
        now = now or time.time()
        since_ts = now - self.config.since_seconds
        signals: list[CandidateSignal] = []
        signals.extend(self.collect_swarm_signals(since_ts))
        signals.extend(self.collect_genome_signals(since_ts))
        signals.extend(self.collect_reasoning_signals(since_ts))
        signals.extend(self.collect_pool_signals(since_ts))
        signals.extend(self.collect_peer_signals(since_ts))
        return signals

    def _load_genome(self, path: Path) -> Genome | None:
        if path.suffix not in {".json", ".yaml", ".yml"}:
            return None
        try:
            return Genome.load(path)
        except Exception:
            return None
