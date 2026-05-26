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
