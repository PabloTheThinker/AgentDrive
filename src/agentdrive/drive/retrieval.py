"""Reciprocal Rank Fusion helpers for Drive.query retrieval."""

from __future__ import annotations

from typing import Any

DEFAULT_RRF_K = 60

_EXPERIENCE_PRIORITY = (
    "living-experience",
    "experience-genome",
    "experience-observation",
    "research-thread",
    "fusion-observation",
    "dream-observation",
    "synthesis-artifact",
    "genome",
)


def reciprocal_rank_fusion(
    rankings: dict[str, list[str]],
    *,
    k: int = DEFAULT_RRF_K,
) -> dict[str, float]:
    """Fuse multiple rank lists with standard RRF: sum 1/(k + rank)."""
    scores: dict[str, float] = {}
    for _ranker, ordered in rankings.items():
        if not ordered:
            continue
        for rank, genome_id in enumerate(ordered, start=1):
            scores[genome_id] = scores.get(genome_id, 0.0) + 1.0 / (k + rank)
    return scores


def experience_priority(page_type: str) -> int:
    """Lower is better for ranking (living-experience first)."""
    try:
        return _EXPERIENCE_PRIORITY.index(page_type)
    except ValueError:
        return len(_EXPERIENCE_PRIORITY)


def build_query_rankings(
    scored: list[tuple[float, Any]],
    relevance: dict[str, dict[str, Any]],
    graph_signals: dict[str, dict[str, Any]],
    page_types: dict[str, str],
    edge_meta: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    """Build rank lists from existing hybrid + graph signals (no embeddings)."""
    by_structural = sorted(
        (g.genome_id for _, g in scored),
        key=lambda gid: relevance.get(gid, {}).get("structural", 0.0),
        reverse=True,
    )
    by_reasoning = sorted(
        (g.genome_id for _, g in scored),
        key=lambda gid: relevance.get(gid, {}).get("reasoning", 0.0),
        reverse=True,
    )
    by_graph = sorted(
        (g.genome_id for _, g in scored),
        key=lambda gid: float(
            graph_signals.get(gid, {}).get("gbrain_signal_score")
            or graph_signals.get(gid, {}).get("composite", 0.0)
            or 0.0
        ),
        reverse=True,
    )
    by_recency = sorted(
        (g.genome_id for _, g in scored),
        key=lambda gid: float(edge_meta.get(gid, {}).get("timestamp", 0.0)),
        reverse=True,
    )
    by_experience = sorted(
        (g.genome_id for _, g in scored),
        key=lambda gid: experience_priority(page_types.get(gid, "")),
    )
    return {
        "structural": by_structural,
        "reasoning": by_reasoning,
        "graph": by_graph,
        "recency": by_recency,
        "experience": by_experience,
    }


def fuse_scored_with_rrf(
    scored: list[tuple[float, Any]],
    relevance: dict[str, dict[str, Any]],
    graph_signals: dict[str, dict[str, Any]],
    page_types: dict[str, str],
    edge_meta: dict[str, dict[str, Any]],
    *,
    k: int = DEFAULT_RRF_K,
) -> list[tuple[float, Any]]:
    """Return scored list reordered by RRF fusion scores."""
    if not scored:
        return scored
    genome_by_id = {g.genome_id: g for _, g in scored}
    rankings = build_query_rankings(scored, relevance, graph_signals, page_types, edge_meta)
    rrf_scores = reciprocal_rank_fusion(rankings, k=k)
    fused: list[tuple[float, Any]] = []
    for gid, rrf in sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True):
        g = genome_by_id.get(gid)
        if g is None:
            continue
        rel = relevance.get(gid, {})
        try:
            setattr(
                g,
                "_hybrid_fusion",
                {
                    "mode": "rrf",
                    "rrf_score": round(rrf, 4),
                    "base_hybrid": rel.get("hybrid"),
                    "structural": rel.get("structural"),
                    "reasoning": rel.get("reasoning"),
                    "page_type": page_types.get(gid, ""),
                    "graph_signal": graph_signals.get(gid, {}).get("gbrain_signal_score"),
                    "rankings": {name: ids.index(gid) + 1 if gid in ids else None for name, ids in rankings.items()},
                },
            )
        except Exception:
            pass
        fused.append((rrf, g))
    return fused