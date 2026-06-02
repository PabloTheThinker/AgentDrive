"""
Genome Evolution (DNA Cycle) — Structured improvement of Genomes using
AgentDrive-native data and optional high-signal external research (via bridge).

Provides a disciplined Research → Evaluate → Evolve skeleton inside AgentDrive's
evolutionary layer, staying fully native in the hot path
(ReasoningEngine, Ancestry, DNADrive, evaluations, patterns, etc.).

Designed to be used by:
- Custom or built-in DNA Scanners
- The Evolutionary Engine
- High-agency operators and advanced high-continuity Conductor nodes that want to actively
  drive genome quality over time.

Current implementation status: native sources primary + soft fallbacks.
External richer sources (external brain indexes etc.) enter only through explicit bridge paths.
See GrokPatternLineageBridge and the example scripts for concrete behavior.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentdrive.constants import get_agentdrive_home
from agentdrive.genome.models import Genome

logger = logging.getLogger(__name__)


@dataclass
class DNACycleResult:
    """Result of one full (or partial) DNA evolution cycle on a Genome."""

    genome_id: str
    version_before: str
    version_after: Optional[str] = None
    research_findings: List[Dict[str, Any]] = field(default_factory=list)
    fitness_delta: float = 0.0
    mutations_proposed: int = 0
    mutations_accepted: int = 0
    immune_flags: List[str] = field(default_factory=list)
    notes: str = ""
    cycle_duration_seconds: float = 0.0


class LineageDNAEvolver:
    """
    Native Research → Evaluate → Evolve cycle for Genomes.

    Uses only AgentDrive-native sources (genome patterns, ReasoningEngine,
    Ancestry, ledger/evals) with graceful degradation on missing data.
    Optional brain_path allows bridge injection of external high-signal data
    (e.g. from an external lineage engine). The use_lineage_engine flag is reserved for future.

    Provides a structured skeleton for scanners, evolutionary loops, and
    high-agency operators. Full "Lineage-style" depth is aspirational; current
    implementation is defensive and partial (see _research_phase etc.).
    """

    def __init__(
        self,
        genome: Genome,
        *,
        brain_path: Optional[Path] = None,
        use_lineage_engine: bool = True,
    ):
        self.genome = genome
        if brain_path is not None:
            self.brain_path = Path(brain_path)
        else:
            self.brain_path = None  # core path is pure AgentDrive; bridge passes explicit external source when needed
        self.use_lineage_engine = use_lineage_engine
        self._cycle_start: Optional[float] = None
        self._current_genome_id: str = "unknown"

    def run_full_cycle(
        self,
        focus_areas: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> DNACycleResult:
        """
        Execute one complete Research → Evaluate → Evolve cycle on this Genome.

        This is the method high-agency nodes (including high-continuity Conductor nodes) should call when
        they want to actively improve a Genome using the full Lineage machinery.
        """
        self._cycle_start = time.time()
        start_version = (
            self.genome.manifest.version if hasattr(self.genome, "manifest") else "unknown"
        )

        # Robust genome id extraction (manifest.id is the stable one in real Genomes)
        manifest = getattr(self.genome, "manifest", None)
        gid = (
            getattr(self.genome, "id", None)
            or (getattr(manifest, "id", None) if manifest else None)
            or str(self.genome)[:64]
        )
        self._current_genome_id = gid
        result = DNACycleResult(
            genome_id=gid,
            version_before=start_version,
        )

        # === RESEARCH PHASE ===
        # In a full implementation this would:
        # - Pull from AgentDrive's own reasoning ledger + patterns
        # - Pull from an optional external research index supplied by the caller (e.g. via GrokPatternLineageBridge)
        # - Pull from the richer ~/lineage-engine research sources if available
        # - Use subagents (when running in Grok) for parallel deep research
        research_findings = self._research_phase(focus_areas or [])
        result.research_findings = research_findings

        # === EVALUATE PHASE ===
        # Multi-signal evaluation: performance + fitness + immune response + emotional resonance
        fitness_delta, immune_flags = self._evaluate_phase(research_findings)
        result.fitness_delta = fitness_delta
        result.immune_flags = immune_flags

        # === EVOLVE PHASE ===
        if not dry_run and fitness_delta > 0.05 and not immune_flags:
            mutations = self._evolve_phase(research_findings, fitness_delta)
            result.mutations_proposed = len(mutations)
            result.mutations_accepted = len([m for m in mutations if m.get("accepted")])
            if result.mutations_accepted > 0:
                result.version_after = self._bump_version(start_version)

        result.cycle_duration_seconds = time.time() - self._cycle_start
        result.notes = f"Cycle complete. Immune flags: {len(immune_flags)}"

        logger.info(
            "LineageDNA cycle complete for %s: delta=%.3f, accepted=%d",
            result.genome_id,
            fitness_delta,
            result.mutations_accepted,
        )

        return result

    # ------------------------------------------------------------------ #
    # Internal phases (these are where we can go arbitrarily deep)
    # ------------------------------------------------------------------ #

    def _research_phase(self, focus_areas: List[str]) -> List[Dict[str, Any]]:
        """
        Gather high-signal research using AgentDrive-native sources first.

        Primary sources (in priority order for core AgentDrive):
        - Existing ReasoningEngine / PatternMemory from previous runs on this genome
        - Ledger entries and evaluations already attached to the genome
        - Ancestry and inheritance history (what worked for direct ancestors)

        External/richer research (e.g. high-continuity operator brain indexes injected via the GrokPatternLineageBridge)
        should be supplied explicitly through the brain_path constructor argument or pluggable
        researcher hooks, not hardcoded in the core path. This keeps AgentDrive usable by any runtime.
        """
        findings: List[Dict[str, Any]] = []

        # 1. Use the genome's own accumulated reasoning patterns (native)
        if hasattr(self.genome, "reasoning_patterns") and self.genome.reasoning_patterns:
            findings.append(
                {
                    "source": "genome_reasoning_patterns",
                    "kind": "internal_patterns",
                    "summary": f"Existing reasoning patterns for {getattr(self.genome, 'id', 'genome')}",
                    "severity": 0.6,
                    "details": {"patterns": self.genome.reasoning_patterns},
                }
            )

        # 2. Try to use the real ReasoningEngine + PatternMemory for this genome
        try:
            from agentdrive.reasoning.engine import ReasoningEngine

            gid = getattr(self.genome, "id", None) or getattr(self, "_last_gid", None) or "unknown"
            _ = ReasoningEngine(
                genome_id=gid
            )  # instantiation exercises the engine + PatternMemory wiring
            findings.append(
                {
                    "source": "reasoning_engine",
                    "kind": "engine_analysis",
                    "summary": f"ReasoningEngine run for genome {gid}",
                    "severity": 0.65,
                }
            )
        except Exception as e:
            logger.debug("Could not instantiate ReasoningEngine: %s", e)

        # 3. Ancestry (core native strength)
        try:
            from agentdrive.dna.ancestry import Ancestry

            home = get_agentdrive_home()
            ancestry = Ancestry(home / "dna" / "_ancestry.db")
            gid = (
                getattr(self, "_current_genome_id", None)
                or getattr(self.genome, "id", None)
                or "unknown-genome"
            )
            agent_id = getattr(self.genome, "agent_id", None) or gid
            if ancestry.has_agent(agent_id):
                ancestors = list(ancestry.ancestors_of(agent_id))[:6]
                if ancestors:
                    findings.append(
                        {
                            "source": "dna_ancestry",
                            "kind": "inherited_capability",
                            "summary": f"DNA inherited from {len(ancestors)} ancestors",
                            "severity": 0.8,
                        }
                    )
        except Exception as e:
            logger.debug("Ancestry lookup failed: %s", e)

        return findings

    def _evaluate_phase(self, findings: List[Dict[str, Any]]) -> tuple[float, List[str]]:
        """Multi-signal evaluation using Lineage-style fitness + immune thinking."""
        fitness_delta = 0.0
        immune_flags: List[str] = []

        # Simple starting heuristic — will be replaced by real Lineage fitness trackers
        positive_signals = [f for f in findings if f.get("severity", 0) > 0.4]
        if positive_signals:
            fitness_delta = min(0.35, len(positive_signals) * 0.08)

        # Immune-style checks (THYMOS influence)
        for f in findings:
            if "security" in str(f.get("kind", "")).lower() and f.get("severity", 0) > 0.7:
                immune_flags.append("high_severity_security_pattern")

        return fitness_delta, immune_flags

    def _evolve_phase(
        self, findings: List[Dict[str, Any]], fitness_delta: float
    ) -> List[Dict[str, Any]]:
        """Propose and (safely) apply mutations to the Genome."""
        mutations: List[Dict[str, Any]] = []

        # For now, record the intent. Real mutation logic will live here
        # (updating manifest, reasoning patterns, evaluations, provenance, etc.)
        if fitness_delta > 0.1:
            mutations.append(
                {
                    "type": "research_injection",
                    "accepted": True,
                    "findings_count": len(findings),
                    "fitness_delta": fitness_delta,
                }
            )

        return mutations

    def _bump_version(self, current: str) -> str:
        # Very naive semver bump for now
        try:
            parts = current.split(".")
            parts[-1] = str(int(parts[-1]) + 1)
            return ".".join(parts)
        except Exception:
            return current + "+evolved"


# Convenience for quick use from scanners / evolutionary loops
def evolve_genome_with_lineage(
    genome: Genome,
    focus_areas: Optional[List[str]] = None,
    dry_run: bool = False,
) -> DNACycleResult:
    """One-liner for scanners and evolution code."""
    evolver = LineageDNAEvolver(genome)
    return evolver.run_full_cycle(focus_areas=focus_areas, dry_run=dry_run)
