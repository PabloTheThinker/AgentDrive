"""
SavantRunScanner — DNA extraction from agent trajectories and runs.

Takes a rich agent run/trajectory/engagement (JSON or dict with conversations,
observations, ledger, claims, etc.) from Savant workers or compatible external
agents, and uses Savant's reasoning primitives (synthesizer, witness, causality,
contradictions, anomaly, patterns, ledger, reasoning) via the ReasoningEngine
to produce one or more candidate Genomes.

This is the canonical implementation of the DNA Scanner interface for the
Savant ecosystem.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from savant.genome.models import Genome, GenomeManifest, GenomeAuthor
from savant.reasoning import (
    ReasoningEngine,
    synthesize_framework,
    synthesis_summary,
)
from .base import BaseScanner


class SavantRunScanner(BaseScanner):
    """
    Scanner specialized for Savant and compatible external agent run data.

    Input formats supported:
    - Path to .json or .jsonl file containing trajectory / engagement dump
    - dict with keys: conversations, observations, ledger, claims, transcript, etc.

    Output: list of candidate Genome objects ready for review, enrichment,
    or direct registration. Each carries extracted reasoning_patterns from
    the full primitive suite and (when possible) a synthesized framework draft.
    """

    name: str = "savant-run"

    def __init__(self, actor: str = "savant-run-scanner-v0.1"):
        self.actor = actor

    def scan(self, run_data: dict[str, Any] | Path | str) -> list[Genome]:
        """
        Core entry point. Returns >=1 candidate Genomes.
        """
        data = self._normalize_input(run_data)

        # Use the high-level ReasoningEngine (wires all primitives + ledger audit)
        engine = ReasoningEngine(
            genome_id="candidate-savant-extraction",
            actor=self.actor,
        )
        enrichment = engine.extract_from_run(data)

        # Optional: if observations present, synthesize a candidate framework using
        # the dedicated synthesizer primitive (structural, deterministic).
        framework: dict[str, Any] | None = None
        obs = data.get("observations") or data.get("timeline_events") or []
        if obs and isinstance(obs, list) and len(obs) > 0:
            try:
                synth = synthesize_framework(
                    observations=obs,
                    framework_id="extracted-from-savant-run",
                    version="0.1.0-candidate",
                    display_name="Savant Run Synthesis",
                    category="extracted",
                )
                framework = {
                    "id": synth.framework_id,
                    "version": synth.version,
                    "display_name": synth.display_name,
                    "description": synthesis_summary(synth),
                    "inputs": synth.inputs,
                    "steps": synth.steps,
                    "output_schema": synth.output_schema,
                    "rationale": getattr(synth, "rationale", ""),
                }
            except Exception:
                framework = {"note": "synthesis attempted but fell back", "obs_count": len(obs)}

        # Build a production-quality candidate manifest
        now = datetime.utcnow()
        manifest = GenomeManifest(
            id="extracted-savant-patterns",
            version="0.1.0-candidate",
            content_hash="sha256:pending",
            created=now,
            authors=[
                GenomeAuthor(type="agent", name=self.actor, run=str(data.get("timestamp", "unknown")))
            ],
            applicability={
                "domains": ["agent-execution", "trajectory-analysis", "general"],
                "problem_signatures": [
                    "extract reusable capability from agent run",
                    "pattern mining from engagement logs"
                ],
                "source_agent": "savant",
            },
            dependencies={"genomes": [], "agent_capabilities": ["trajectory-parsing", "structural-reasoning"]},
            evaluation_score={"candidate_confidence": 0.65},
        )

        candidate = Genome(
            manifest=manifest,
            framework=framework,
            reasoning_patterns=enrichment.reasoning_patterns,
            provenance={
                "source_scanner": self.name,
                "source_run_summary": str(data)[:300],
                "ledger_ref": enrichment.ledger_ref,
                "extraction_timestamp": enrichment.timestamp,
                "primitives_used": [
                    "reconstruct_trace", "detect_anomalies", "detect_contradictions",
                    "mine_causality", "witness_claim", "PatternMemory", "synthesize_framework"
                ],
                "reasoning_primitives_version": "savant-reasoning-0.1.0",
            },
            tool_compositions={
                "common_sequences": enrichment.reasoning_patterns.get("patterns_recognized", []),
            },
        )
        candidate.finalize()

        # Return the rich candidate (future: could also emit variants, e.g. one per dominant pattern)
        return [candidate]

    def _normalize_input(self, run_data: dict[str, Any] | Path | str) -> dict[str, Any]:
        if isinstance(run_data, (str, Path)):
            p = Path(run_data)
            if not p.exists():
                return {"raw": str(run_data), "note": "path did not exist, treating as literal"}
            text = p.read_text(encoding="utf-8").strip()
            if p.suffix == ".jsonl":
                # take last complete entry as representative run
                for line in reversed(text.splitlines()):
                    line = line.strip()
                    if line:
                        try:
                            return json.loads(line)
                        except Exception:
                            continue
                return {"raw": text[-500:]}
            try:
                return json.loads(text)
            except Exception:
                return {"raw_text": text[:2000]}
        if isinstance(run_data, dict):
            return run_data
        return {"raw": str(run_data)}


# Also export a convenience alias for backward compatibility during transition
RichRunScanner = SavantRunScanner  # Rich external workers and Savant workers use the same scanner
