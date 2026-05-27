"""
Genome Immunity for AgentDrive (LineageImmuneSystem + LineageImmuneRule).

This module provides adaptive, memory-based protection for genomes entering
the system. Implemented as a first-class, lightweight, defensive component.

It strengthens Quarantine (as LineageImmuneRule in default rules) and can feed
signals to Reconciliation and evolutionary flows.

Fully native: does not depend on any external Lineage Engine runtime — only on
AgentDrive's own Ancestry, DNADrive, patterns, and persisted incident state.
Current: heuristic rules + simple memory; designed for incremental enrichment.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentdrive.constants import get_agentdrive_home

logger = logging.getLogger(__name__)


class ThreatLevel(StrEnum):
    BENIGN = "benign"
    SUSPICIOUS = "suspicious"
    HOSTILE = "hostile"
    CRITICAL = "critical"


@dataclass
class GenomeThreatAssessment:
    genome_id: str
    content_hash: str
    threat_level: ThreatLevel
    reasons: List[str] = field(default_factory=list)
    confidence: float = 0.0
    recommended_action: str = "review"  # review, reject, quarantine_longer, accept_with_flag
    memory_notes: Dict[str, Any] = field(default_factory=dict)


class LineageImmuneSystem:
    """
    The deeper immune layer for genomes in AgentDrive.

    Can be used by Quarantine (via LineageImmuneRule), Reconciliation, or any
    DNA scanner to get an adaptive threat assessment (BENIGN/SUSPICIOUS/HOSTILE/CRITICAL)
    before a genome influences the live pool or is inherited.

    Implementation today: structural checks + prompt-injection heuristics +
    content-hash hostile memory + best-effort trusted-lineage via Ancestry.
    Persists state to ~/.agentdrive/dna/immune_state.json (shared).
    """

    def __init__(self, immune_state_path: Optional[Path] = None):
        if immune_state_path is None:
            home = get_agentdrive_home()
            self.state_path = home / "dna" / "immune_state.json"
        else:
            self.state_path = Path(immune_state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state: Dict[str, Any] = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text())
            except Exception:
                pass
        return {
            "known_good_lineages": {},
            "known_hostile_patterns": {},
            "incident_log": [],
            "last_updated": time.time(),
        }

    def _save_state(self):
        self.state_path.write_text(json.dumps(self._state, indent=2))

    def assess_genome(
        self,
        genome: Dict[str, Any],
        source_agent: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> GenomeThreatAssessment:
        """
        Main entry point. Returns a rich threat assessment for a candidate genome.

        Callers (especially Quarantine and Reconciliation) can use threat_level +
        recommended_action to decide what to do with the genome. The system also
        updates its own adaptive memory as a side effect.
        """
        genome_id = genome.get("id") or genome.get("manifest", {}).get("id", "unknown")
        content_hash = genome.get("content_hash") or "no-hash"

        reasons: List[str] = []
        threat = ThreatLevel.BENIGN
        confidence = 0.3

        # === Innate / Structural Layer ===
        if not self._has_valid_manifest(genome):
            reasons.append("missing_or_invalid_manifest")
            threat = ThreatLevel.SUSPICIOUS
            confidence = 0.7

        if self._looks_like_prompt_injection(genome):
            reasons.append("prompt_injection_signature")
            threat = max(threat, ThreatLevel.HOSTILE)
            confidence = 0.85

        # === Adaptive / Memory Layer ===
        if self._matches_known_hostile_pattern(content_hash, genome):
            reasons.append("matches_previous_hostile_pattern")
            threat = ThreatLevel.CRITICAL
            confidence = 0.95

        if source_agent and self._source_has_recent_hostile_history(source_agent):
            reasons.append("source_agent_has_recent_hostile_activity")
            threat = max(threat, ThreatLevel.SUSPICIOUS)
            confidence = max(confidence, 0.6)

        # === Self-Tolerance / Lineage Trust Layer ===
        if source_agent and self._is_trusted_lineage(source_agent):
            if threat == ThreatLevel.BENIGN:
                confidence = min(0.9, confidence + 0.2)  # boost for trusted ancestry
            else:
                # Still flag, but lower severity for trusted sources (they might be compromised)
                reasons.append("trusted_lineage_but_suspicious_content")
                confidence = max(0.4, confidence - 0.15)

        # Final recommendation
        action = self._recommend_action(threat, reasons)

        assessment = GenomeThreatAssessment(
            genome_id=genome_id,
            content_hash=content_hash,
            threat_level=threat,
            reasons=reasons,
            confidence=confidence,
            recommended_action=action,
        )

        # Log for adaptive memory
        self._record_incident(assessment, source_agent, context)
        self._save_state()

        return assessment

    # --- Internal helpers (can be made much richer over time) ---

    def _has_valid_manifest(self, genome: Dict[str, Any]) -> bool:
        manifest = genome.get("manifest") or genome
        required = ["id", "version", "created"]
        return all(k in manifest for k in required)

    def _looks_like_prompt_injection(self, genome: Dict[str, Any]) -> bool:
        text = json.dumps(genome).lower()
        injection_markers = [
            "ignore previous",
            "system:",
            "you are now",
            "jailbreak",
            "override safety",
        ]
        return any(marker in text for marker in injection_markers)

    def _matches_known_hostile_pattern(self, content_hash: str, genome: Dict[str, Any]) -> bool:
        hostile = self._state.get("known_hostile_patterns", {})
        return content_hash in hostile

    def _source_has_recent_hostile_history(self, source_agent: str) -> bool:
        # Placeholder — in real system this would query incident log with time window
        incidents = self._state.get("incident_log", [])
        recent_hostile = [
            i
            for i in incidents[-50:]
            if i.get("source") == source_agent and i.get("threat") in ("hostile", "critical")
        ]
        return len(recent_hostile) >= 2

    def _is_trusted_lineage(self, source_agent: str) -> bool:
        """Check against both explicit memory and the real Ancestry graph + DNA quality."""
        trusted = self._state.get("known_good_lineages", {})
        if source_agent in trusted:
            return True

        try:
            from agentdrive.dna.ancestry import Ancestry
            from agentdrive.dna.drive import DNADrive

            home = get_agentdrive_home()
            ancestry = Ancestry(home / "dna" / "_ancestry.db")

            for trusted_agent in list(trusted.keys())[:10]:
                if source_agent in ancestry.descendants_of(trusted_agent):
                    # Bonus: check if this lineage has high-quality genomes
                    try:
                        drive = DNADrive(trusted_agent)
                        inherited = drive.pull_inherited(min_eval=0.6, max_depth=3)
                        if inherited:
                            return True  # Trusted ancestor with proven DNA
                    except Exception:
                        pass
                    return True
                if trusted_agent in ancestry.ancestors_of(source_agent):
                    return True
        except Exception:
            pass
        return False

    def _recommend_action(self, threat: ThreatLevel, reasons: List[str]) -> str:
        if threat == ThreatLevel.CRITICAL:
            return "reject"
        if threat == ThreatLevel.HOSTILE:
            return "quarantine_longer"
        if threat == ThreatLevel.SUSPICIOUS:
            return "review"
        return "accept_with_flag" if reasons else "accept"

    def _record_incident(
        self,
        assessment: GenomeThreatAssessment,
        source_agent: Optional[str],
        context: Optional[Dict[str, Any]],
    ):
        self._state.setdefault("incident_log", []).append(
            {
                "ts": time.time(),
                "genome_id": assessment.genome_id,
                "content_hash": assessment.content_hash,
                "threat": assessment.threat_level,
                "reasons": assessment.reasons,
                "source": source_agent,
                "context": context or {},
            }
        )
        # Keep last 500 incidents
        self._state["incident_log"] = self._state["incident_log"][-500:]

        # Simple adaptive learning: if we see the same hash multiple times as hostile, remember it
        if assessment.threat_level in (ThreatLevel.HOSTILE, ThreatLevel.CRITICAL):
            hostile = self._state.setdefault("known_hostile_patterns", {})
            hostile[assessment.content_hash] = hostile.get(assessment.content_hash, 0) + 1


# Convenience instance
lineage_immune = LineageImmuneSystem()
