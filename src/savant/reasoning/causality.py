"""Causality miner — turn a flat trace into a DAG of cause→effect.

Core reasoning primitive in Savant for mining causal relationships from traces.

Savant role in DNA/Genome pipeline:
- After `reconstruct_trace` (reasoning.py) on a run's ledger entries,
  `mine_causality` builds a CausalGraph.
- The graph (with weights and rationales) is stored in
  `genome.reasoning_patterns["causality"]` or `["causal_graph"]`.
- Enables scanners and evolutionary engine to understand *why* one
  step led to success/failure — critical for framework synthesis and
  safe mutation.
- Heuristics: count carry, citation carry, token carry, failure cascade.
  All structural, citable.

Depends only on local .reasoning module (TraceStep etc.).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

from .reasoning import ReasoningTrace, TraceStep

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{2,}")
_STOP = {
    "the", "and", "for", "with", "from", "this", "that", "have", "has",
    "was", "were", "are", "but", "not", "into", "out", "all", "any",
    "some", "none", "one", "two", "three", "step", "found",
}


@dataclass(slots=True)
class CausalEdge:
    src_seq: int
    dst_seq: int
    weight: float
    rationale: str

    def to_dict(self) -> dict:
        return {"src": self.src_seq, "dst": self.dst_seq,
                "weight": round(self.weight, 3), "rationale": self.rationale}


@dataclass(slots=True)
class CausalGraph:
    edges: list[CausalEdge] = field(default_factory=list)
    node_count: int = 0

    def render(self) -> str:
        if not self.edges:
            return f"(no causal edges across {self.node_count} step(s))"
        lines = [f"causal graph — {self.node_count} step(s), "
                  f"{len(self.edges)} edge(s)"]
        for e in sorted(self.edges, key=lambda x: (x.src_seq, x.dst_seq)):
            lines.append(
                f"  {e.src_seq:>2} → {e.dst_seq:<2}  w={e.weight:.2f}  "
                f"{e.rationale[:100]}"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {"node_count": self.node_count,
                "edges": [e.to_dict() for e in self.edges]}


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "")
            if t.lower() not in _STOP and len(t) > 2}


def _citation_keys(step: TraceStep) -> set[str]:
    keys: set[str] = set()
    for c in step.citations:
        if not isinstance(c, dict):
            continue
        src = str(c.get("source") or "")
        sid = str(c.get("source_id") or "")
        if src and sid:
            keys.add(f"{src}:{sid}")
    return keys


def mine_causality(trace: ReasoningTrace,
                    observations: Iterable[dict] | None = None) -> CausalGraph:
    """Infer causal edges between steps in a trace.

    ``observations`` is accepted for symmetry with the rest of savant
    but is currently used only as a token-frequency prior so common
    project-wide tokens don't blow up the rationale.
    """
    steps = trace.steps
    if len(steps) < 2:
        return CausalGraph(node_count=len(steps))

    # Token-rarity prior from observations (or the trace itself).
    background: Counter = Counter()
    if observations:
        for o in observations:
            if isinstance(o, dict):
                background.update(_tokens(str(o.get("summary") or "")))
                background.update(_tokens(str(o.get("identity") or "")))
    else:
        for s in steps:
            background.update(_tokens(s.summary))

    edges: list[CausalEdge] = []
    for i, dst in enumerate(steps):
        dst_tokens = _tokens(dst.summary)
        dst_count_keys = set(dst.counts.keys())
        dst_cites = _citation_keys(dst)
        for src in steps[:i]:
            reasons: list[str] = []
            weight = 0.0

            # Count carry — strongest signal.
            shared_counts = set(src.counts.keys()) & dst_count_keys
            if shared_counts:
                weight += 0.5 * len(shared_counts)
                reasons.append(f"shared counts: {sorted(shared_counts)}")

            # Count keys mentioned in dst summary.
            mentioned = {k for k in src.counts if k.lower() in dst_tokens}
            if mentioned:
                weight += 0.3 * len(mentioned)
                reasons.append(f"counts referenced in summary: {sorted(mentioned)}")

            # Citation carry.
            shared_cites = _citation_keys(src) & dst_cites
            if shared_cites:
                weight += 0.4 * len(shared_cites)
                reasons.append(f"shared citations: {sorted(shared_cites)}")

            # Token carry — weighted by rarity.
            src_tokens = _tokens(src.summary)
            shared_tokens = src_tokens & dst_tokens
            rare_shared = [t for t in shared_tokens
                            if background.get(t, 0) <= 3]
            if rare_shared:
                weight += 0.1 * len(rare_shared)
                reasons.append(
                    f"rare tokens carried: {sorted(rare_shared)[:5]}"
                )

            # Failure cascade — if dst failed and we already have any
            # signal, bump the weight so the failure has a culprit.
            if (not dst.ok or dst.error) and reasons:
                weight += 0.5
                reasons.append("preceded a failure")

            if weight > 0 and reasons:
                edges.append(CausalEdge(
                    src_seq=src.seq, dst_seq=dst.seq,
                    weight=weight, rationale="; ".join(reasons),
                ))

    # Normalize weights into [0, 1] so renderers can use them.
    if edges:
        peak = max(e.weight for e in edges)
        if peak > 1.0:
            for e in edges:
                e.weight = e.weight / peak

    return CausalGraph(edges=edges, node_count=len(steps))


def explain_causality(graph: CausalGraph) -> str:
    """One-paragraph diagnostic of the causal graph."""
    if not graph.edges:
        return f"no causal edges inferred across {graph.node_count} step(s)."
    by_dst: dict[int, list[CausalEdge]] = {}
    for e in graph.edges:
        by_dst.setdefault(e.dst_seq, []).append(e)
    fragments: list[str] = []
    for dst, incoming in sorted(by_dst.items()):
        incoming.sort(key=lambda x: -x.weight)
        top = incoming[0]
        fragments.append(f"step {dst} ← step {top.src_seq} "
                          f"(w={top.weight:.2f}, {top.rationale[:60]})")
    return (f"{len(graph.edges)} edge(s) across {graph.node_count} step(s). "
             + "; ".join(fragments[:5]))
