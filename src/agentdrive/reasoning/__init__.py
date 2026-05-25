"""
Savant Reasoning Primitives — first-class components for DNA extraction
and Genome enrichment.

These are the core structural-cognition primitives powering Savant scanners,
Genome synthesis, and evolutionary improvement. (Detailed technical history
of the reasoning layer is recorded in ARCHITECTURE.md.)

The primitives implemented:

1. reasoning.py          → TraceStep, ReasoningTrace, reconstruct_trace,
                             explain_trace
   Why: The absolute foundation for "extracting reasoning patterns from runs".
        Any scanner that has ledger / trace / step data from an agent
        execution can turn it into a machine-readable, citable chain of
        thought. Stored verbatim in genome.reasoning_patterns["trace"].
        Used by causality, future postmortem-style analyzers, and the
        evolutionary engine for "why did this genome work?" queries.

2. anomaly.py            → Anomaly, detect_anomalies, explain_anomaly
   Why: Detects rare-kinds, state-outliers, stale observations, novel
        identities. Essential for surfacing "the one thing that didn't fit"
        during DNA extraction. Populates genome.reasoning_patterns["anomalies"].
        Pure offline heuristics → trustworthy for automated selection.

3. causality.py          → CausalEdge, CausalGraph, mine_causality,
                             explain_causality
   Why: Builds weighted DAGs from traces using count/citation/token carry
        + failure cascade. Directly fulfills "Building causal graphs".
        genome.reasoning_patterns["causality"] becomes a first-class
        evolvable artifact. Scanners + evo engine use it to propose
        "break this causal chain" improvements.

4. contradictions.py     → Contradiction, detect_contradictions
   Why: Zero-tolerance for numeric claims that disagree on the same
        normalized template. Critical for "Detecting ... contradictions".
        Feeds genome.reasoning_patterns["contradictions"] and drives
        prevention recommendations. Pairs perfectly with witness + ledger.

5. synthesizer.py        → FrameworkSynthesis, synthesize_framework,
                             synthesis_summary
   Why: The engine for "Synthesizing new framework steps" from raw
        observation blobs grouped by kind. The structural heart of
        turning a successful run into a reusable typed playbook step
        sequence. Output can seed or mutate genome.framework .

6. ledger.py             → Ledger, LedgerEntry, log_entry, audited,
                             record context manager
   Why: "Maintaining audit ledgers for genomes". Every extraction,
        enrichment, or evolutionary operation is written *before* it
        executes. Per-genome or global; lives at
        ~/.agentdrive/reasoning/ledger/ . Provides the raw material for
        reconstruct_trace and full provenance. The audit substrate for
        the entire evolutionary system.

7. witness.py            → Citation, NumericClaim, VaguenessReport,
                             witness_claim, audit_vagueness, witness_many
   Why: Enforces "every claim carries count + citation + timestamp".
        audit_vagueness kills vague language at extraction time.
        The rigor primitive that makes all other detectors (contradictions,
        anomalies, etc.) possible and trustworthy. Used heavily when
        scanners turn free-text run logs into structured claims.

8. patterns.py           → PatternSignature, PatternMatch, PatternMemory,
                             summarize_matches, from_run_data
   Why: "Extracting reasoning patterns from runs" at the meta level.
        Persists and recognizes signatures (intents + fields) across
        runs and genomes via Jaccard. Enables the registry/evo engine
        to say "this is 0.87 like the incident-postmortem genome".
        Long-term cross-genome learning store.

Not ported in this initial batch (but high quality and candidates for
future extension):
- postmortem_runner.py (domain-specific composer for security incidents;
  the example genome uses similar logic — can be re-implemented on top
  of these primitives)
- framework_runner.py (the full 5-layer savant pass; now easy to rebuild
  using the 8 primitives above + a new SavantPass orchestrator)
- inferencer.py, schema.py, calibration.py, joins.py, layers.py, etc.
  (valuable but lower priority for the core "reasoning for DNA" mandate;
  inferencer can be added when transcript-based scanners land)

Design decisions for the port:
- All code is 1:1 faithful in algorithms, dataclasses, and output shapes.
- Internal imports updated to relative (e.g. causality imports from .reasoning).
- Default storage paths use ~/.agentdrive/reasoning/...
  (ledger/, patterns/, etc.) and made overridable via SAVANT_REASONING_ROOT
  env var.
- Agent strings use "savant-core".
- Full docstrings updated with Savant/Genome/DNA scanner context while
  preserving the original "savant-like" voice and precision.
- No new runtime dependencies; pure stdlib + the dataclasses already used.
- Each module is independently importable and testable.

============================================================================
CLEAN INTEGRATION POINT
============================================================================

Scanners (src/agentdrive/scanners/*.py) and the future evolutionary engine
(src/agentdrive/evolution/) should import from here:

    from agentdrive.reasoning import (
        ReasoningEngine,                # <-- THE RECOMMENDED HIGH-LEVEL API
        # or the raw primitives when you need fine control:
        detect_anomalies,
        mine_causality,
        detect_contradictions,
        synthesize_framework,
        reconstruct_trace,
        Ledger,
        witness_claim,
        PatternMemory,
        # dataclasses for typing / serialization
        Anomaly, Contradiction, CausalGraph, ReasoningTrace, ...
    )

The ReasoningEngine class (defined below) is the primary "clean integration
point". It knows about Genomes, wires the primitives together, handles
ledger tagging for provenance, and returns enrichment payloads ready to
drop into genome.reasoning_patterns and genome.provenance.

Example usage in a future DNA Scanner:

    from agentdrive.genome.models import Genome
    from agentdrive.reasoning import ReasoningEngine

    engine = ReasoningEngine(genome_id="security-incident-postmortem", actor="scanner-v1")

    # run_data can be Path to trajectory, dict of events, ledger tail, etc.
    enrichment = engine.extract_from_run(run_data)

    genome.reasoning_patterns.update(enrichment["reasoning_patterns"])
    genome.provenance.setdefault("extraction_ledger", []).append(
        enrichment["ledger_ref"]
    )
    genome = engine.enrich_genome(genome)   # convenience

    # Later the evolutionary engine can call:
    #   engine.build_causal_graph(trace)
    #   engine.suggest_framework_mutations(genome)

This keeps scanners thin and delegates all structural rigor to the
reasoning package.

The primitives remain directly callable for power users and for
re-building higher-level composers (e.g. a SavantPass or domain
postmortems).

============================================================================
"""

from __future__ import annotations

# Re-export all public symbols from the 8 modules so "import agentdrive.reasoning"
# gives the full savant experience (and scanners don't have to know the file layout).
from .anomaly import (
    Anomaly,
    detect_anomalies,
    explain_anomaly,
)
from .causality import (
    CausalEdge,
    CausalGraph,
    explain_causality,
    mine_causality,
)
from .contradictions import (
    Contradiction,
    detect_contradictions,
)

# The star of the show: the high-level integration surface for scanners & evo engine.
from .engine import ReasoningEngine  # defined in engine.py (see below)
from .ledger import (
    Ledger,
    LedgerEntry,
    audited,
    ledger_path,
    log_entry,
)
from .patterns import (
    PatternMatch,
    PatternMemory,
    PatternSignature,
    summarize_matches,
)
from .reasoning import (
    ReasoningTrace,
    TraceStep,
    explain_trace,
    reconstruct_trace,
)
from .synthesizer import (
    FrameworkSynthesis,
    synthesis_summary,
    synthesize_framework,
)
from .witness import (
    Citation,
    NumericClaim,
    VaguenessReport,
    audit_vagueness,
    witness_claim,
    witness_many,
)

__all__ = [
    # High-level
    "ReasoningEngine",
    # Primitives (dataclasses)
    "Anomaly",
    "CausalEdge",
    "CausalGraph",
    "Citation",
    "Contradiction",
    "FrameworkSynthesis",
    "Ledger",
    "LedgerEntry",
    "NumericClaim",
    "PatternMatch",
    "PatternMemory",
    "PatternSignature",
    "ReasoningTrace",
    "TraceStep",
    "VaguenessReport",
    # Functions
    "audit_vagueness",
    "detect_anomalies",
    "detect_contradictions",
    "explain_anomaly",
    "explain_causality",
    "explain_trace",
    "ledger_path",
    "log_entry",
    "mine_causality",
    "reconstruct_trace",
    "summarize_matches",
    "synthesis_summary",
    "synthesize_framework",
    "witness_claim",
    "witness_many",
    # Decorators / helpers
    "audited",
]


# Convenience: also expose the package version / identity for genomes that
# record which reasoning primitives produced them.
REASONING_PRIMITIVES_VERSION = "savant-reasoning-0.1.0"
