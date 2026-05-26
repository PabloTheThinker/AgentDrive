"""
adversary — stress-test dream candidates before Deep promotion.

Design goals:
- Attack staged candidates using contradiction, provenance, and fitness pressure.
- Emit traceable pass/fail evidence instead of opaque penalties.
- No new magic — just disciplined composition + Agent Drive / Genome idioms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentdrive.dreaming.candidate import DreamCandidate
from agentdrive.genome.models import Genome
from agentdrive.reasoning.engine import ReasoningEngine


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

    def build_seed_profile(
        self, ledger_entries: list[dict[str, Any]] | None = None
    ) -> AdversaryProfile:
        """Build an adversary profile from recent contradiction and anomaly history."""
        ledger_entries = ledger_entries or []
        profile = AdversaryProfile()
        contradiction_refs = [
            str(entry.get("entry_id") or entry.get("id") or index)
            for index, entry in enumerate(ledger_entries)
            if "contradiction" in str(entry.get("kind") or entry.get("operation") or "")
        ]
        profile.provenance["ledger_entries"] = len(ledger_entries)
        profile.provenance["contradiction_refs"] = contradiction_refs[:20]
        return profile

    def attack_candidate(
        self,
        candidate: DreamCandidate,
        reasoning_engine: ReasoningEngine | None = None,
        ledger_entries: list[dict[str, Any]] | None = None,
    ) -> AdversaryResult:
        """Attack one candidate with lane-aware contradiction and fitness pressure."""
        ledger_entries = ledger_entries or []
        traces = [
            self._provenance_trace(candidate),
            self._contradiction_trace(candidate, ledger_entries),
            self._lane_trace(candidate, reasoning_engine),
        ]
        penalty = sum(trace.severity for trace in traces if not trace.passed)
        bonus = 0.05 * sum(1 for trace in traces if trace.passed)
        return AdversaryResult(
            candidate_id=candidate.candidate_id,
            survived=penalty < 0.35,
            bonus=bonus,
            penalty=min(1.0, penalty),
            traces=traces,
        )

    def attack_candidates(
        self,
        candidates: list[DreamCandidate],
        reasoning_engine: ReasoningEngine | None = None,
        ledger_entries: list[dict[str, Any]] | None = None,
    ) -> list[AdversaryResult]:
        """Attack a batch of candidates and return ordered results."""
        results: list[AdversaryResult] = []
        for candidate in candidates:
            result = self.attack_candidate(
                candidate, reasoning_engine=reasoning_engine, ledger_entries=ledger_entries
            )
            results.append(result)
        return results

    def _provenance_trace(self, candidate: DreamCandidate) -> AttackTrace:
        has_provenance = bool(candidate.content_refs or candidate.provenance.get("source_paths"))
        return AttackTrace(
            candidate_id=candidate.candidate_id,
            attack_kind="provenance_gap",
            passed=has_provenance,
            severity=0.0 if has_provenance else self.profile.provenance_attack_weight,
            notes=[] if has_provenance else ["candidate lacks source refs"],
            evidence_refs=[str(path) for path in candidate.content_refs],
        )

    def _contradiction_trace(
        self, candidate: DreamCandidate, ledger_entries: list[dict[str, Any]]
    ) -> AttackTrace:
        contradiction_refs = [
            str(entry.get("entry_id") or entry.get("id") or index)
            for index, entry in enumerate(ledger_entries)
            if candidate.canonical_key
            and candidate.canonical_key in str(entry)
            and "contradiction" in str(entry)
        ]
        passed = not contradiction_refs and "contradiction" not in candidate.risk_flags
        return AttackTrace(
            candidate_id=candidate.candidate_id,
            attack_kind="contradiction_probe",
            passed=passed,
            severity=0.0 if passed else self.profile.contradiction_weight,
            notes=[] if passed else ["contradictory evidence or risk flag found"],
            evidence_refs=contradiction_refs,
        )

    def _lane_trace(
        self, candidate: DreamCandidate, reasoning_engine: ReasoningEngine | None
    ) -> AttackTrace:
        lane = candidate.proposed_lane or (
            candidate.lane_hints[0] if candidate.lane_hints else "memory"
        )
        passed = bool(candidate.supporting_signals)
        severity = 0.0 if passed else self.profile.fitness_challenge_weight
        notes = [f"lane={lane}", f"reasoning_engine={reasoning_engine is not None}"]
        return AttackTrace(
            candidate_id=candidate.candidate_id,
            attack_kind=f"{lane}_stress",
            passed=passed,
            severity=severity,
            notes=notes,
        )


def genome_adversary_anchor(genome: Genome | None) -> str:
    """Return a stable Genome anchor for future adversary seed construction."""
    return genome.genome_id if genome else ""
