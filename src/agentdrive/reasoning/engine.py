"""
ReasoningEngine — the primary clean integration point for Savant DNA
Scanners and the Evolutionary Engine.

This class wires the core reasoning primitives into high-level,
Genome-aware operations so that scanner authors and evolution code
can call one object instead of orchestrating individual detectors.

Design goals:
- Scanners stay thin: `enrichment = engine.extract_from_run(run_data)`
- All structural work, ledger discipline, and provenance tagging happens here.
- Output shapes are directly consumable by Genome.reasoning_patterns
  and Genome.provenance (dicts of primitives, serializable).
- Remains 100% compatible with calling the raw primitives when needed.
- Future: can grow calibration, joins, full savant-pass composition, etc.

No new magic — just disciplined composition + Savant/Genome idioms.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentdrive.genome.models import Genome

from .anomaly import Anomaly, detect_anomalies
from .causality import CausalGraph, mine_causality
from .contradictions import Contradiction, detect_contradictions
from .ledger import Ledger
from .patterns import PatternMemory, PatternSignature
from .reasoning import ReasoningTrace, explain_trace, reconstruct_trace
from .synthesizer import FrameworkSynthesis, synthesize_framework
from .witness import NumericClaim, witness_claim


@dataclass(slots=True)
class ExtractionResult:
    """Structured payload ready to merge into a Genome."""

    genome_id: str
    reasoning_patterns: dict[str, Any] = field(default_factory=dict)
    ledger_ref: dict[str, Any] = field(default_factory=dict)
    synthesized: dict[str, Any] | None = None
    timestamp: float = field(default_factory=time.time)


class ReasoningEngine:
    """
    High-level orchestrator for all Savant reasoning primitives.

    Typical lifecycle for a DNA Scanner:

        engine = ReasoningEngine(
            genome_id="my-special-capability",
            actor="dna-scanner-v0.2",
            ledger_root=...  # optional
        )

        # 1. Record that we are starting an extraction (audit before action)
        with engine.ledger.record("scanner.extract_start", ...):
            ...

        # 2. Do your scanner-specific work to turn raw run into observations/claims/ledger_entries
        observations = ...
        ledger_entries = ...
        claims = ...

        # 3. Call the one-stop enrichment
        result: ExtractionResult = engine.extract_from_run(
            run_data={"observations": observations, "ledger": ledger_entries, "claims": claims}
        )

        # 4. Attach to genome
        genome.reasoning_patterns.update(result.reasoning_patterns)
        genome.provenance.setdefault("extractions", []).append(result.ledger_ref)

        # 5. Optionally synthesize framework steps or recognize patterns
        synth = engine.synthesize_framework_steps(observations, framework_id=...)
        ...

    The evolutionary engine can later call the same instance (or a fresh one)
    on historical data or proposed mutations.
    """

    def __init__(
        self,
        genome_id: str,
        *,
        actor: str = "savant-reasoning-engine",
        ledger_root: Path | None = None,
        pattern_corpus: str = "genomes",
    ) -> None:
        self.genome_id = genome_id
        self.actor = actor
        self.ledger = Ledger(root=ledger_root, actor=f"{actor}:{genome_id}")
        self.pattern_memory = PatternMemory(corpus=pattern_corpus)
        self._extractions: list[ExtractionResult] = []

    # ------------------------------------------------------------------ #
    # Core extraction entry point — the main thing scanners call
    # ------------------------------------------------------------------ #
    def extract_from_run(self, run_data: dict[str, Any] | Path) -> ExtractionResult:
        """
        Given raw run data (observations, ledger entries, claims, etc.),
        run the full suite of reasoning primitives and return an
        enrichment payload.

        run_data shape (flexible):
            {
                "observations": list[dict],
                "ledger": list[dict],           # or path to jsonl
                "claims": list[dict],
                "prior_observations": list[dict],
                "transcript": ...               # future
            }
        """
        if isinstance(run_data, Path):
            # Minimal support: treat as ledger file for now
            run_data = {"ledger": self._load_ledger_from_path(run_data)}

        obs = run_data.get("observations") or []
        ledger_entries = run_data.get("ledger") or []
        claims = run_data.get("claims") or []
        prior = run_data.get("prior_observations")

        # Always record the extraction itself (audit before heavy work)
        with self.ledger.record(
            operation="reasoning.extract_from_run",
            summary=f"DNA extraction for {self.genome_id}",
            metadata={"obs_count": len(obs), "claim_count": len(claims)},
        ) as entry:
            # 1. Reconstruct the reasoning trace (foundational)
            trace = reconstruct_trace(ledger_entries) if ledger_entries else ReasoningTrace()

            # 2. Anomalies
            anomalies: list[Anomaly] = detect_anomalies(obs, prior_observations=prior)

            # 3. Contradictions (only on well-formed claims)
            contradictions: list[Contradiction] = detect_contradictions(claims)

            # 4. Causal graph (needs a trace)
            causal_graph: CausalGraph = mine_causality(trace, observations=obs)

            # 5. Witness any raw claims that weren't already NumericClaims
            witnessed_claims: list[dict] = []
            for c in claims:
                if isinstance(c, dict) and "statement" in c and "count" in c:
                    nc = witness_claim(
                        statement=str(c["statement"]),
                        count=int(c["count"]),
                        source=c.get("source", "run"),
                        source_id=c.get("source_id", "unknown"),
                        fields=c.get("fields"),
                    )
                    witnessed_claims.append(nc.to_dict())

            # 6. Pattern signature from this run (if we have enough signal)
            signature = None
            if obs or ledger_entries:
                intent_hints = [str(o.get("kind", "")) for o in obs if o.get("kind")]
                field_hints = list({k for o in obs for k in (o.get("details") or {}).keys()})
                if intent_hints or field_hints:
                    signature = PatternSignature.from_run_data(
                        framework_id=self.genome_id,
                        intents=intent_hints,
                        fields=field_hints,
                        display_name=self.genome_id.replace("-", " ").title(),
                    )
                    self.pattern_memory.remember(signature)

            # Assemble the reasoning_patterns section for the Genome
            reasoning_patterns: dict[str, Any] = {
                "trace": {
                    "summary": explain_trace(trace) if trace.steps else "no trace",
                    "step_count": len(trace.steps),
                    "operation_counts": trace.operation_counts,
                    "failed": [f.operation for f in trace.failed],
                    "total_duration_ms": trace.total_duration_ms,
                },
                "anomalies": [
                    {
                        "rule": a.rule,
                        "kind": a.kind,
                        "identity": a.identity,
                        "severity": a.severity,
                        "rationale": a.rationale,
                        "citation": a.citation,
                    }
                    for a in anomalies
                ],
                "contradictions": [
                    {
                        "template": c.template,
                        "counts": list(c.counts),
                        "sources": list(c.sources),
                        "rationale": c.rationale,
                    }
                    for c in contradictions
                ],
                "causality": causal_graph.to_dict(),
                "witnessed_claims": witnessed_claims,
                "patterns_recognized": [
                    m.to_dict() for m in self.pattern_memory.recognize(signature)
                ]
                if signature
                else [],
                "extraction_meta": {
                    "obs_count": len(obs),
                    "claim_count": len(claims),
                    "ledger_steps": len(trace.steps),
                },
            }

            # Record completion
            entry.counts["anomalies"] = len(anomalies)
            entry.counts["contradictions"] = len(contradictions)
            entry.counts["causal_edges"] = len(causal_graph.edges)
            entry.counts["trace_steps"] = len(trace.steps)

            result = ExtractionResult(
                genome_id=self.genome_id,
                reasoning_patterns=reasoning_patterns,
                ledger_ref={
                    "ledger_entry_id": entry.id,
                    "operation": entry.operation,
                    "started_at": entry.started_at,
                    "actor": entry.actor,
                },
                timestamp=time.time(),
            )

            self._extractions.append(result)
            return result

    # ------------------------------------------------------------------ #
    # Individual high-value operations (can be called directly)
    # ------------------------------------------------------------------ #
    def build_causal_graph(
        self, trace: ReasoningTrace, observations: list[dict] | None = None
    ) -> CausalGraph:
        """Thin wrapper around mine_causality with ledger discipline."""
        with self.ledger.record(
            "reasoning.build_causal_graph", summary=f"causal analysis for {self.genome_id}"
        ):
            return mine_causality(trace, observations=observations)

    def synthesize_framework_steps(
        self,
        observations: list[Any],
        *,
        framework_id: str | None = None,
        **kwargs,
    ) -> FrameworkSynthesis:
        """Synthesize a draft framework from observations (used by scanners & evo)."""
        fid = framework_id or f"{self.genome_id}-synthesized"
        with self.ledger.record(
            "reasoning.synthesize_framework", summary=f"synthesize steps for {fid}"
        ):
            return synthesize_framework(observations, framework_id=fid, **kwargs)

    def detect_anomalies(self, observations: list[Any], **kwargs) -> list[Anomaly]:
        with self.ledger.record("reasoning.detect_anomalies"):
            return detect_anomalies(observations, **kwargs)

    def detect_contradictions(self, claims: list[Any]) -> list[Contradiction]:
        with self.ledger.record("reasoning.detect_contradictions"):
            return detect_contradictions(claims)

    def reconstruct_trace(self, entries: list[dict]) -> ReasoningTrace:
        return reconstruct_trace(entries)

    def witness_claim(self, *args, **kwargs) -> NumericClaim:
        return witness_claim(*args, **kwargs)

    def recognize_patterns(self, signature: PatternSignature, k: int = 3):
        return self.pattern_memory.recognize(signature, k=k)

    # ------------------------------------------------------------------ #
    # Genome convenience
    # ------------------------------------------------------------------ #
    def enrich_genome(self, genome: Genome) -> Genome:
        """Convenience: attach the latest extraction to an existing Genome object.

        Uses the structured GenomeProvenance (lineage list) for auditability.
        """
        if self._extractions:
            latest = self._extractions[-1]
            genome.reasoning_patterns.update(latest.reasoning_patterns)
            # Append to structured lineage (the official place for history events)
            event = {
                "type": "reasoning_extraction",
                "genome_id": latest.genome_id,
                "timestamp": latest.timestamp,
                "ledger_ref": latest.ledger_ref,
                "summary": f"DNA extraction via {self.actor}",
            }
            genome.provenance.lineage.append(event)
        return genome

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _load_ledger_from_path(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        out = []
        for line in lines:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
        return out

    def __repr__(self) -> str:
        return f"ReasoningEngine(genome_id={self.genome_id!r}, actor={self.actor!r})"
