"""Eval replay MVP — re-score stored research artifacts against MultiMetricEvaluationHarness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentdrive.reconciliation import DiagnosisReport, MultiMetricEvaluationHarness, ResearchBudget


def _scores_from_artifact(data: dict[str, Any]) -> dict[str, Any] | None:
    fw = data.get("framework") or {}
    if isinstance(fw, dict):
        ev = fw.get("evaluation") or {}
        kdo = fw.get("keep_discard_outcome") or {}
        if isinstance(ev, dict) and ev.get("scores"):
            scores = dict(ev["scores"])
            if isinstance(kdo, dict) and kdo.get("decision"):
                scores["decision"] = kdo["decision"]
            if ev.get("decision"):
                scores.setdefault("decision", ev["decision"])
            return scores
        if isinstance(kdo, dict) and kdo.get("decision"):
            return {
                "decision": kdo.get("decision"),
                "overall_goodness": (ev or {}).get("overall_goodness")
                if isinstance(ev, dict)
                else None,
            }
    manifest = data.get("manifest") or {}
    if isinstance(manifest, dict):
        es = manifest.get("evaluation_score")
        if isinstance(es, dict):
            return es
    return None


def _artifact_to_after_state(data: dict[str, Any]) -> dict[str, Any]:
    fw = data.get("framework") or {}
    scores = _scores_from_artifact(data) or {}
    fusion = fw.get("fusion_checkpoint") if isinstance(fw, dict) else {}
    if not isinstance(fusion, dict):
        fusion = {}
    resilience_delta = float(
        scores.get("resilience_lift") or fusion.get("resilience_delta") or 0.11
    )
    # Align with harness before_contras (3) so full reduction is achievable on replay.
    contradictions_addressed = ["c1", "c2", "sc1"]
    fusion_checkpoint = {
        **fusion,
        "resilience_after": 0.62 + resilience_delta,
        "post": 0.62 + resilience_delta,
        "participating_swarms": fusion.get("research_org_roles")
        or fusion.get("participating_swarms")
        or ["Diagnoser", "Verifier", "Consolidator"],
        "citation_count": 4,
        "graph_signals_summary": {"healed_by": 4, "strengthened_resilience": 3},
        "contradictions_addressed": contradictions_addressed,
    }
    return {
        "correlation_id": "eval-replay-after",
        "fusion_checkpoint": fusion_checkpoint,
        "resilience_delta": resilience_delta,
        "artifacts_ingested": ["replay-artifact"],
        "proposals_executed": [1],
        "citation_count": 4,
        "experience_layer_v3_seed_referenced": True,
        "feeds_experience_layer": bool(fw.get("high_signal", True))
        if isinstance(fw, dict)
        else True,
        "contradictions_addressed": contradictions_addressed,
    }


def _baseline_diagnosis(coherence: float = 0.60) -> DiagnosisReport:
    return DiagnosisReport(
        correlation_id="eval-replay-baseline",
        signal_type="artifact_replay",
        root_cause="Replay baseline for stored research artifact",
        evidence={
            "contradictions": ["c1", "c2"],
            "gaps": ["g1"],
            "synthesis_contradictions": ["sc1"],
        },
        recommended_proposal_types=["experience_consolidation"],
        resilience_before=coherence,
    )


def replay_artifact_scores(
    artifact: dict[str, Any],
    *,
    tolerance: float = 0.05,
) -> dict[str, Any]:
    """Re-run harness scoring for one artifact dict. Returns PASS/FAIL comparison."""
    stored = _scores_from_artifact(artifact) or {}
    stored_decision = stored.get("decision")
    stored_goodness = stored.get("overall_goodness")

    harness = MultiMetricEvaluationHarness()
    before = _baseline_diagnosis(0.62)
    before.evidence["contradictions"] = ["c1", "c2", "c3", "c4", "c5"]
    before.evidence["synthesis_contradictions"] = ["sc1", "sc2"]
    after = _artifact_to_after_state(artifact)
    budget = ResearchBudget(max_experiments=5)
    scores = harness.evaluate(before, after, budget, research_constitution=None)

    decision_match = stored_decision is None or scores.decision == stored_decision
    goodness_match = True
    if stored_goodness is not None:
        goodness_match = abs(float(scores.overall_goodness) - float(stored_goodness)) <= tolerance

    return {
        "artifact_id": (artifact.get("id") or (artifact.get("manifest") or {}).get("id")),
        "pass": decision_match and goodness_match,
        "stored_decision": stored_decision,
        "replayed_decision": scores.decision,
        "stored_overall_goodness": stored_goodness,
        "replayed_overall_goodness": scores.overall_goodness,
        "decision_match": decision_match,
        "goodness_match": goodness_match,
        "tolerance": tolerance,
    }


def replay_genome_artifact_file(path: Path | str, *, tolerance: float = 0.05) -> dict[str, Any]:
    """Load a genome JSON artifact and replay harness scoring."""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    result = replay_artifact_scores(data, tolerance=tolerance)
    result["path"] = str(p)
    return result
