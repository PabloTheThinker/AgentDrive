"""
Synthesis + Gap Analysis layer for AgentDrive.

"Think" layer on top of:
- The knowledge_graph (typed edges + graph signals + temporal freshness)
- Schema packs (page types for source_boost and experience layer)
- Existing Genomes (executable playbooks)
- Drive content + durable dream observations + calibration state

This gives agents not just retrieval, but synthesized answers with explicit gaps, contradictions, and experience layer context.
"""

from .engine import (
    Citation,
    Gap,
    SynthesisResult,
    propose_experience_evolution,
    run_synthesis,
)

__all__ = [
    "run_synthesis",
    "SynthesisResult",
    "Gap",
    "Citation",
    "propose_experience_evolution",
]
