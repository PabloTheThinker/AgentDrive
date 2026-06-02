"""
Robust, queryable, persistent typed knowledge graph for AgentDrive.

- Real persistence under <drive>/knowledge/edges.jsonl (append-only, swarm-scoped)
- Improved multi-hop with relation filters + path scoring (weight, confidence, length)
- Graph-aware helpers ("find genomes related to X via Y")
- Automatic indexing: every Drive.ingest() now persists TypedEdges
- Everything flows to central drive (per-swarm drives + event bridges for cross-swarm)

Graph fabric hardening + link extraction produce dense, queryable multi-hop paths across genomes, observations, and key primitives. New genomes document explicit edge additions and deliver measurable drive.think quality improvements.

This is the living relational memory the entire system relies on.
"""

from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .link_extraction import TypedEdge

# Schema pack integration for source_boost (page type driven source boosts for graph signals)
try:
    from agentdrive.schema_packs import load_active_pack
except Exception:
    load_active_pack = None


@dataclass
class GraphEdge:
    """Canonical edge in the typed graph. Compatible with TypedEdge + persistence."""

    source: str
    target: str
    relation: str
    weight: float = 1.0
    confidence: float = 1.0
    metadata: dict[str, Any] | None = None
    swarm_id: str | None = None
    timestamp: float | None = None


@dataclass
class GraphPath:
    """A traversal path with scoring support."""

    nodes: list[str]
    edges: list[GraphEdge]
    length: int
    score: float = 0.0  # populated by scoring functions


@dataclass
class KnowledgeGraphStore:
    """
    Real persistence for the knowledge graph.

    Stores under the drive's "knowledge/" namespace:
        <drive_path>/knowledge/edges.jsonl

    - Append-only JSONL (robust, human readable, git friendly)
    - Per-drive / per-swarm isolation (matches AgentDrive model)
    - Loadable as SimpleGraph or raw TypedEdge list
    - Also supports reconstruction from drive events (ingest.jsonl + emitted knowledge_graph_edge)
    - Central drive friendly: graph signal aggregation across swarms for drive queries
    """

    drive_path: Path | None = None
    swarm_id: str | None = None

    def __post_init__(self):
        if self.drive_path is None:
            from agentdrive.constants import get_default_drive_path, get_swarm_drive_path

            if self.swarm_id:
                self.drive_path = get_swarm_drive_path(self.swarm_id)
            else:
                self.drive_path = get_default_drive_path()
        self.drive_path = Path(self.drive_path)
        self.knowledge_dir = self.drive_path / "knowledge"
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        self.edges_path = self.knowledge_dir / "edges.jsonl"

    def add_edge(self, edge: GraphEdge | TypedEdge, swarm_id: str | None = None) -> None:
        """Persist a single edge (converts TypedEdge on the fly)."""
        if isinstance(edge, TypedEdge):
            gedge = GraphEdge(
                source=edge.source,
                target=edge.target,
                relation=edge.relation,
                weight=1.0,
                confidence=getattr(edge, "confidence", 1.0),
                metadata=getattr(edge, "provenance", None),
                swarm_id=swarm_id or self.swarm_id,
                timestamp=time.time(),
            )
        else:
            gedge = edge
            if swarm_id:
                gedge.swarm_id = swarm_id
            if gedge.timestamp is None:
                gedge.timestamp = time.time()

        record = {
            "source": gedge.source,
            "target": gedge.target,
            "relation": gedge.relation,
            "weight": gedge.weight,
            "confidence": gedge.confidence,
            "metadata": gedge.metadata,
            "swarm_id": gedge.swarm_id or self.swarm_id,
            "timestamp": gedge.timestamp or time.time(),
            "kind": "knowledge_graph_edge",
        }
        with open(self.edges_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def add_edges(self, edges: list[GraphEdge | TypedEdge], swarm_id: str | None = None) -> None:
        for e in edges:
            self.add_edge(e, swarm_id=swarm_id)

    def load_raw_edges(self) -> list[dict]:
        """Load raw JSON records (latest on disk wins for duplicates)."""
        if not self.edges_path.exists():
            return []
        records: list[dict] = []
        try:
            with open(self.edges_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            rec = json.loads(line)
                            if rec.get("kind") == "knowledge_graph_edge" or "relation" in rec:
                                records.append(rec)
                        except json.JSONDecodeError:
                            continue
        except Exception:
            pass
        return records

    def load_as_typed_edges(self) -> list[TypedEdge]:
        """Rehydrate as TypedEdge list for consumers that prefer the extraction types."""
        typed: list[TypedEdge] = []
        for rec in self.load_raw_edges():
            typed.append(
                TypedEdge(
                    source=rec["source"],
                    target=rec["target"],
                    relation=rec["relation"],
                    confidence=rec.get("confidence", 1.0),
                    provenance=rec.get("metadata") or {"swarm_id": rec.get("swarm_id")},
                )
            )
        return typed

    def load_as_simple_graph(self) -> "SimpleGraph":
        """Convenience: full in-memory graph ready for queries."""
        g = SimpleGraph()
        for rec in self.load_raw_edges():
            g.add_edge(
                GraphEdge(
                    source=rec["source"],
                    target=rec["target"],
                    relation=rec.get("relation", "related_to"),
                    weight=float(rec.get("weight", 1.0)),
                    confidence=float(rec.get("confidence", 1.0)),
                    metadata=rec.get("metadata"),
                    swarm_id=rec.get("swarm_id"),
                    timestamp=rec.get("timestamp"),
                )
            )
        return g

    def load_from_drive_events(self, events: list[dict]) -> None:
        """Bridge: ingest knowledge_graph_edge events (from ingest.jsonl or EventRecorder) into persistent store."""
        added = 0
        for ev in events:
            if ev.get("kind") != "knowledge_graph_edge" and "relation" not in ev:
                continue
            self.add_edge(
                GraphEdge(
                    source=ev.get("source") or ev.get("genome"),
                    target=ev.get("target"),
                    relation=ev.get("relation", "references"),
                    weight=float(ev.get("weight", 1.0)),
                    swarm_id=ev.get("swarm") or ev.get("swarm_id"),
                    timestamp=ev.get("timestamp", time.time()),
                )
            )
            added += 1
        # Note: we don't dedup here; JSONL is append-only history. Query layers handle freshness.

    def __len__(self) -> int:
        return len(self.load_raw_edges())


class SimpleGraph:
    """
    In-memory typed multi-hop graph (robust v2).

    Backed by KnowledgeGraphStore for persistence in production.
    Used by synthesis, reasoning, drive.think, and cross-swarm retrieval.
    """

    def __init__(self):
        self._edges: list[GraphEdge] = []
        self._nodes: set[str] = set()

    def add_edge(self, edge: GraphEdge):
        self._edges.append(edge)
        self._nodes.add(edge.source)
        self._nodes.add(edge.target)

    def add_edges(self, edges: list[GraphEdge]):
        for e in edges:
            self.add_edge(e)

    @property
    def nodes(self) -> set[str]:
        return set(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def neighbors(self, node: str, relation: str | None = None) -> list[str]:
        result = []
        for e in self._edges:
            if e.source == node:
                if relation is None or e.relation == relation:
                    result.append(e.target)
        return result

    # --- Core improved multi-hop (relation filters + path scoring) ---

    def traverse(
        self,
        start: str,
        max_depth: int = 3,
        relation_filter: set[str] | None = None,
    ) -> list[GraphPath]:
        """BFS multi-hop. Returns all simple paths up to depth. (Improved: no early termination of alternates.)"""
        if relation_filter is None:
            relation_filter = set()

        paths: list[GraphPath] = []
        # (current, path_nodes, path_edges, visited_in_path to prevent simple cycles)
        queue: deque[tuple[str, list[str], list[GraphEdge], set[str]]] = deque(
            [(start, [start], [], {start})]
        )

        while queue:
            current, path_nodes, path_edges, path_visited = queue.popleft()

            if len(path_nodes) > 1:
                p = GraphPath(nodes=path_nodes, edges=path_edges, length=len(path_edges))
                p.score = self._score_path(p)
                paths.append(p)

            if len(path_nodes) >= max_depth + 1:
                continue

            for edge in self._edges:
                if edge.source != current:
                    continue
                if relation_filter and edge.relation not in relation_filter:
                    continue
                if edge.target in path_visited:
                    continue  # avoid simple cycles in this path

                new_visited = path_visited | {edge.target}
                queue.append(
                    (
                        edge.target,
                        path_nodes + [edge.target],
                        path_edges + [edge],
                        new_visited,
                    )
                )

        return paths

    def find_paths(
        self,
        start: str,
        end: str | None = None,
        max_depth: int = 4,
        relation_filter: set[str] | None = None,
        top_k: int = 20,
    ) -> list[GraphPath]:
        """Find scored paths. If end given, only paths terminating at end. Sorted by score desc."""
        all_paths = self.traverse(start, max_depth=max_depth, relation_filter=relation_filter)
        if end:
            all_paths = [p for p in all_paths if p.nodes[-1] == end]
        all_paths.sort(key=lambda p: p.score, reverse=True)
        return all_paths[:top_k]

    def _score_path(self, path: GraphPath) -> float:
        """Composite path score: favors high-weight/confidence, penalizes long paths slightly."""
        if not path.edges:
            return 0.0
        w_sum = sum(e.weight * max(0.1, e.confidence) for e in path.edges)
        # Length penalty (prefer concise strong connections)
        length_penalty = 1.0 / (1.0 + 0.15 * path.length)
        return w_sum * length_penalty

    # --- Graph-aware helpers for other swarms (the key deliverable) ---

    def find_genomes_related_to(
        self,
        entity: str,
        via: list[str] | None = None,
        max_depth: int = 2,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Swarm-friendly helper: "find genomes related to X via Y".

        Example:
            graph.find_genomes_related_to("genomes/knowledge-graph-v2", via=["depends_on", "references"])
        Returns scored list of reachable genome slugs + path evidence.
        """
        if via is None:
            via = ["depends_on", "references", "implements", "authored_by", "related_to", "indexes"]
        rel_set = set(via)
        paths = self.find_paths(
            entity, max_depth=max_depth, relation_filter=rel_set, top_k=limit * 3
        )

        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for p in paths:
            target = p.nodes[-1]
            if target.startswith("genomes/") and target not in seen:
                seen.add(target)
                results.append(
                    {
                        "genome": target,
                        "score": round(p.score, 4),
                        "depth": p.length,
                        "relations": [e.relation for e in p.edges],
                        "path": p.nodes,
                    }
                )
            if len(results) >= limit:
                break
        return results

    def find_entities_related_via(self, start: str, relation: str, max_depth: int = 2) -> list[str]:
        """Direct helper: all entities reachable from start using only the given relation (multi-hop)."""
        paths = self.find_paths(start, max_depth=max_depth, relation_filter={relation})
        targets = []
        for p in paths:
            if p.nodes[-1] != start:
                targets.append(p.nodes[-1])
        return sorted(set(targets))

    def get_relation_summary(self) -> dict[str, int]:
        """Quick stats for observability / synthesis gap detection."""
        summary: dict[str, int] = {}
        for e in self._edges:
            summary[e.relation] = summary.get(e.relation, 0) + 1
        return dict(sorted(summary.items(), key=lambda x: -x[1]))

    def subgraph_for(self, seeds: list[str], max_depth: int = 1) -> "SimpleGraph":
        """Extract a focused subgraph around seeds (useful for scoped synthesis)."""
        sub = SimpleGraph()
        for seed in seeds:
            for p in self.find_paths(seed, max_depth=max_depth, top_k=50):
                for e in p.edges:
                    sub.add_edge(e)
        return sub

    # --- Query helpers for contradiction detection, calibration, staleness, centrality, and experience layer (graph signals integration for drive.think) ---
    def find_contradictions_candidates(
        self, min_degree: int = 2, relation_focus: set[str] | None = None
    ) -> list[dict[str, Any]]:
        return find_contradictions_candidates(
            self, min_degree=min_degree, relation_focus=relation_focus
        )

    def get_stale_entities(
        self, max_age_days: float = 14.0, min_degree: int = 1
    ) -> list[dict[str, Any]]:
        return get_stale_entities(self, max_age_days=max_age_days, min_degree=min_degree)

    def get_high_centrality_genomes(
        self, top_k: int = 20, min_gbrain_score: float = 0.1
    ) -> list[dict[str, Any]]:
        return get_high_centrality_genomes(self, top_k=top_k, min_gbrain_score=min_gbrain_score)

    # traverse is already the robust multi-hop impl (the queue-based one above).
    # find_paths / find_genomes_related_to provide the advanced scored API.
    # Old call sites using traverse() continue to work and now get better results + .score on paths.


# --- Persistence helpers (enhanced by Graph Architect Swarm) ---


def edges_to_drive_events(graph: SimpleGraph, swarm_id: str) -> list[dict]:
    """Convert to drive events (kind=knowledge_graph_edge) for cross-swarm / coordinator use."""
    events = []
    for e in getattr(graph, "_edges", []):
        events.append(
            {
                "kind": "knowledge_graph_edge",
                "source": e.source,
                "target": e.target,
                "relation": e.relation,
                "swarm": swarm_id,
                "weight": getattr(e, "weight", 1.0),
                "confidence": getattr(e, "confidence", 1.0),
                "timestamp": getattr(e, "timestamp", time.time()),
            }
        )
    return events


def load_graph_from_drive_events(events: list[dict]) -> SimpleGraph:
    """Rebuild from any drive events (ingest log, emitted events, coordinator reports)."""
    g = SimpleGraph()
    for ev in events:
        if ev.get("kind") == "knowledge_graph_edge" or "relation" in ev:
            g.add_edge(
                GraphEdge(
                    source=ev.get("source") or ev.get("genome", ""),
                    target=ev.get("target", ""),
                    relation=ev.get("relation", "references"),
                    weight=float(ev.get("weight", 1.0)),
                    confidence=float(ev.get("confidence", 1.0)),
                    swarm_id=ev.get("swarm") or ev.get("swarm_id"),
                )
            )
    return g


def get_knowledge_graph_for_swarm(swarm_id: str | None = None) -> SimpleGraph:
    """
    High-level entry point for role-swarms.
    Returns a fully populated in-memory graph from the swarm's persistent knowledge store.
    Falls back to default drive when swarm_id=None.
    """
    store = KnowledgeGraphStore(swarm_id=swarm_id)
    return store.load_as_simple_graph()


# === Graph Signals ===
# All signals fused into "gbrain_signal_score" (composite of degree, recency, trust, source boosts).
# Used by synthesis, calibration loops, drive.think, experience layer, and cross-swarm retrieval.


def recency_boost(
    timestamp: float | None, *, now: float | None = None, half_life_days: float = 7.0
) -> float:
    """
    Recency boost: exponential-ish decay favoring fresh edges/genomes.
    Based on edge.timestamp or (for genome entities) source last_improved.
    Returns [0.0, ~0.3] boost.
    """
    if timestamp is None:
        return 0.0
    now = now or time.time()
    try:
        age_h = max(0.1, (now - float(timestamp)) / 3600.0)
    except (TypeError, ValueError):
        return 0.0
    age_days = age_h / 24.0
    # Gentle decay: recent = high, after half_life_days ~0.5 strength
    decay = 1.0 / (1.0 + (age_days / half_life_days))
    return round(min(0.30, 0.30 * decay), 4)


def temporal_freshness_score(
    timestamp: float | None,
    *,
    now: float | None = None,
    half_life_days: float = 7.0,
    max_boost: float = 0.35,
    staleness_penalty: float = 0.15,
) -> dict[str, float]:
    """
    Temporal freshness scoring for calibration loops and contradiction handling.
    Returns dict with freshness_score, recency_boost, staleness_factor for use in
    auto-calibration of synthesis weights, source_boost, graph signals.
    When contradictions surface, calibration adjusts half_life / boosts for recency-aware retrieval.
    """
    if timestamp is None:
        return {
            "freshness_score": 0.0,
            "recency_boost": 0.0,
            "staleness_factor": 1.0,
            "age_days": 999.0,
        }
    now = now or time.time()
    try:
        age_h = max(0.1, (now - float(timestamp)) / 3600.0)
    except (TypeError, ValueError):
        return {
            "freshness_score": 0.0,
            "recency_boost": 0.0,
            "staleness_factor": 1.0,
            "age_days": 999.0,
        }
    age_days = age_h / 24.0
    decay = 1.0 / (1.0 + (age_days / half_life_days))
    rec_b = round(min(max_boost, max_boost * decay), 4)
    # Staleness: > max_age triggers penalty for calibration adjustments
    stale_threshold = half_life_days * 4
    staleness = (
        max(0.0, min(1.0, (age_days - stale_threshold) / (stale_threshold * 2)))
        if age_days > stale_threshold
        else 0.0
    )
    freshness = round(max(0.0, 1.0 - staleness), 3)
    staleness_factor = round(1.0 - (staleness * staleness_penalty), 3)
    return {
        "freshness_score": freshness,
        "recency_boost": rec_b,
        "staleness_factor": staleness_factor,
        "age_days": round(age_days, 2),
    }


def swarm_trust_tier(swarm_id: str | None) -> float:
    """
    Swarm trust tier for gbrain_signal_score.
    Higher for core production swarms and high-continuity lineage nodes.
    Lower for demo/test swarms.
    """
    if not swarm_id:
        return 0.55
    sid = str(swarm_id).lower()
    core = {
        "example-dissector",
        "example-graph",
        "example-synthesis",
        "example-schema",
        "example-dream-swarm",
        "example-2026-05",
        "high-continuity-lineage-001",
        "conductor",
        "example-calibration",
        "example-experience",  # experience layer: high trust for fused daily interface genomes (living-experience page types)
    }
    if any(c in sid for c in core):
        return 0.95
    if any(x in sid for x in ("demo", "test", "scratch", "temp")):
        return 0.30
    if "example-" in sid or "role-" in sid:
        # legacy role-swarm production identifiers retain elevated tier
        return 0.80
    return 0.60


def source_boost(
    source_type: str | None,
    *,
    schema_pack: Any | None = None,
    entity_slug: str | None = None,
    calibration_overrides: dict[str, float] | None = None,
) -> float:
    """
    Source boost preferring high-value page types via schema_packs.
    Primary: "genome", "synthesis-artifact", "dream-observation".
    Falls back to prefix inference + active pack if schema_pack provided or loadable.
    Accepts calibration_overrides (e.g. {"synthesis-artifact": 0.22}) from closed-loop calibration for dynamic experience layer and synthesis boosts.
    """
    boost = 0.0
    st = (source_type or "").lower().strip()
    high_value = {
        "genome",
        "synthesis-artifact",
        "dream-observation",
        "synthesis",
        "dream",
        "living-experience",
        "experience-genome",
        "experience-observation",
    }
    if st in high_value:
        boost = 0.18
    elif st in ("knowledge-graph-edge", "schema-pack", "swarm-artifact"):
        boost = 0.10

    # Apply calibration overrides from closed-loop engine (e.g. boost high-signal resolving artifacts for experience layer)
    if calibration_overrides:
        for key, val in calibration_overrides.items():
            if key in st or (st and key in st):
                boost = max(boost, float(val))
            if st == "" and entity_slug and key in str(entity_slug).lower():
                boost = max(boost, float(val))

    # Schema pack driven inference for entity_slug (e.g. "genomes/..." or "synthesis/...")
    if boost == 0.0 and (schema_pack or load_active_pack) and entity_slug:
        try:
            pack = schema_pack or (load_active_pack() if load_active_pack else None)
            if pack and hasattr(pack, "resolve_type"):
                pt = pack.resolve_type(entity_slug)
                if pt:
                    name = getattr(pt, "name", "") or ""
                    if name in (
                        "genome",
                        "synthesis-artifact",
                        "dream-observation",
                        "living-experience",
                        "experience-genome",
                        "experience-observation",
                    ):
                        boost = 0.16
                    elif name in ("schema-pack", "swarm-artifact", "knowledge-graph-edge"):
                        boost = 0.09
                    elif getattr(pt, "extractable", False):
                        boost = 0.05
        except Exception:
            pass
    return round(boost, 4)


def compute_graph_signals(
    graph: SimpleGraph,
    query_entities: list[str],
    *,
    swarm_context: str | None = None,
    edge_meta: dict[str, dict] | None = None,
    schema_pack: Any | None = None,
    calibration_overrides: dict[str, float] | None = None,
) -> dict[str, dict]:
    """
    Graph signals computation.
    Computes degree + adjacency, plus:
      - recency_boost (edge.timestamp or genome last_improved proxy)
      - swarm_trust_tier (core production + high-continuity lineage elevated; demo low)
      - source_boost (via schema_packs page types: genome/synthesis-artifact/dream-observation/living-experience preferred)
    Returns per-entity dict including "gbrain_signal_score" (composite of graph signals + experience boosts) + components.
    Auto-derives rich meta by scanning graph edges when edge_meta not supplied.
    """
    signals: dict[str, dict] = {}
    now = time.time()
    # Build richer per-entity meta from actual edges (timestamps, swarms, source_types)
    derived_meta: dict[str, dict] = {}
    if hasattr(graph, "_edges"):
        for e in graph._edges:
            for ent in (e.source, e.target):
                if ent not in derived_meta:
                    derived_meta[ent] = {"timestamps": [], "swarms": [], "source_types": []}
                if getattr(e, "timestamp", None):
                    derived_meta[ent]["timestamps"].append(e.timestamp)
                if getattr(e, "swarm_id", None):
                    derived_meta[ent]["swarms"].append(e.swarm_id)
                meta = getattr(e, "metadata", None) or {}
                if isinstance(meta, dict):
                    st = meta.get("source_type")
                    if st:
                        derived_meta[ent]["source_types"].append(st)

    for entity in query_entities:
        if not hasattr(graph, "neighbors"):
            signals[entity] = {"degree": 0, "adjacency_boost": 0.0, "gbrain_signal_score": 0.0}
            continue

        neighbors = graph.neighbors(entity)
        # Also consider incoming (reverse neighbors via edges)
        in_neighbors = [e.source for e in getattr(graph, "_edges", []) if e.target == entity]
        degree = len(set(neighbors) | set(in_neighbors))

        # Aggregate recency from derived or passed
        recency_b = 0.0
        ts = None
        if edge_meta and entity in edge_meta:
            ts = edge_meta[entity].get("timestamp")
        elif entity in derived_meta and derived_meta[entity]["timestamps"]:
            ts = max(derived_meta[entity]["timestamps"])  # freshest connected
        # Use temporal freshness scoring (calibration-aware for recency in synthesis and experience layer)
        try:
            from agentdrive.knowledge_graph.graph import temporal_freshness_score

            fres = temporal_freshness_score(ts, now=now)
            recency_b = fres.get("recency_boost", recency_boost(ts, now=now))
            # stash for calibration consumers
            freshness_meta = fres
        except Exception:
            recency_b = recency_boost(ts, now=now)
            freshness_meta = {"recency_boost": recency_b}

        # Swarm trust: prefer context, else best from derived edges
        trust = swarm_trust_tier(swarm_context)
        if (not swarm_context or trust < 0.8) and entity in derived_meta:
            for sw in derived_meta[entity]["swarms"]:
                t2 = swarm_trust_tier(sw)
                if t2 > trust:
                    trust = t2

        # Source boost with schema_pack context
        source_b = 0.0
        st = None
        if edge_meta and entity in edge_meta:
            st = edge_meta[entity].get("source_type")
        elif entity in derived_meta and derived_meta[entity]["source_types"]:
            st = derived_meta[entity]["source_types"][0]
        source_b = source_boost(
            st,
            schema_pack=schema_pack,
            entity_slug=entity,
            calibration_overrides=calibration_overrides,
        )

        adj_b = min(degree * 0.08, 0.45)  # slightly tuned
        gbrain_score = round(adj_b + recency_b + (trust - 0.5) * 0.25 + source_b, 4)

        signals[entity] = {
            "degree": degree,
            "adjacency_boost": round(adj_b, 3),
            "recency_boost": recency_b,
            "swarm_trust": round(trust, 3),
            "source_boost": source_b,
            "is_hub": degree > 4,
            "gbrain_signal_score": gbrain_score,
            "temporal_freshness": freshness_meta
            if "freshness_meta" in locals()
            else {"recency_boost": recency_b},
            "components": {
                "adj": adj_b,
                "recency": recency_b,
                "trust": round((trust - 0.5) * 0.25, 3),
                "source": source_b,
            },
        }
    return signals


def fuse_graph_signals_into_scores(
    base_scores: dict[str, float],
    graph: SimpleGraph,
    query_entities: list[str],
    *,
    swarm_context: str | None = None,
    edge_meta: dict[str, dict] | None = None,
    schema_pack: Any | None = None,
    calibration_overrides: dict[str, float] | None = None,
) -> dict[str, float]:
    """
    Enhanced graph signal fusion into base scores. Supports synthesis, drive.think, and calibration-aware retrieval.
    """
    signals = compute_graph_signals(
        graph,
        query_entities,
        swarm_context=swarm_context,
        edge_meta=edge_meta,
        schema_pack=schema_pack,
        calibration_overrides=calibration_overrides,
    )
    fused = {}
    for entity, base in base_scores.items():
        sig = signals.get(entity, {})
        boost = (
            sig.get("gbrain_signal_score")
            or sig.get("composite")
            or sig.get("adjacency_boost", 0.0)
        )
        fused[entity] = round(base + float(boost), 5)
    return fused


def fuse_for_synthesis(
    base_scores: dict[str, float],
    graph: SimpleGraph,
    query_entities: list[str],
    *,
    swarm_context: str | None = None,
    schema_pack: Any | None = None,
    context_hint: str | None = None,
) -> dict[str, float]:
    """
    Synthesis and drive.think friendly graph signal fusion entrypoint.
    Takes optional schema_pack context for richer source_boost from page types (genome, synthesis-artifact, living-experience, etc).
    Emits gbrain_signal_score fused scores. Self-referential for drive.think queries.
    """
    # Derive edge_meta hint from context if provided (future: could parse more)
    edge_meta = None
    if context_hint:
        # lightweight: allow caller to pass hints like "recent_genome" etc. (extensible)
        pass
    return fuse_graph_signals_into_scores(
        base_scores,
        graph,
        query_entities,
        swarm_context=swarm_context or context_hint,
        edge_meta=edge_meta,
        schema_pack=schema_pack,
    )


# === Query Helpers for calibration loops, contradiction detection, experience layer, and dream consolidation (enrich graph signals) ===


def find_contradictions_candidates(
    graph: SimpleGraph | None = None,
    *,
    swarm_id: str | None = None,
    min_degree: int = 2,
    relation_focus: set[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Identify candidate entities with potential contradictions (high connectivity across
    differing relations or from multiple swarms with conflicting signals).
    Feeds Dissector / calibration work. Returns scored candidates with evidence.
    """
    if graph is None:
        graph = get_knowledge_graph_for_swarm(swarm_id)
    if relation_focus is None:
        relation_focus = {"depends_on", "references", "implements", "related_to", "authored_by"}

    candidates: list[dict[str, Any]] = []
    rel_counts: dict[str, dict[str, int]] = {}
    swarm_diversity: dict[str, set[str]] = {}

    for e in getattr(graph, "_edges", []):
        if e.relation not in relation_focus:
            continue
        src, tgt = e.source, e.target
        for ent in (src, tgt):
            if ent not in rel_counts:
                rel_counts[ent] = {}
                swarm_diversity[ent] = set()
            rel_counts[ent][e.relation] = rel_counts[ent].get(e.relation, 0) + 1
            if e.swarm_id:
                swarm_diversity[ent].add(e.swarm_id)

    for ent, counts in rel_counts.items():
        if sum(counts.values()) < min_degree:
            continue
        diversity = len(swarm_diversity.get(ent, []))
        # Heuristic contradiction score: many different relations + cross-swarm
        score = (len(counts) * 0.4) + (min(diversity, 4) * 0.25) + (sum(counts.values()) * 0.05)
        if score > 0.8:
            candidates.append(
                {
                    "entity": ent,
                    "contradiction_score": round(score, 3),
                    "relation_diversity": len(counts),
                    "swarm_diversity": diversity,
                    "relations": counts,
                    "evidence_swarms": list(swarm_diversity.get(ent, []))[:5],
                }
            )

    candidates.sort(key=lambda x: x["contradiction_score"], reverse=True)
    return candidates[:50]


def get_stale_entities(
    graph: SimpleGraph | None = None,
    *,
    swarm_id: str | None = None,
    max_age_days: float = 14.0,
    min_degree: int = 1,
) -> list[dict[str, Any]]:
    """
    Surface stale/low-recency high-degree entities for dream consolidation / refresh work.
    Uses edge timestamps for recency.
    """
    if graph is None:
        graph = get_knowledge_graph_for_swarm(swarm_id)
    now = time.time()
    stale: list[dict[str, Any]] = []
    entity_ts: dict[str, float] = {}
    entity_degree: dict[str, int] = {}

    for e in getattr(graph, "_edges", []):
        ts = getattr(e, "timestamp", None) or now - (30 * 86400)
        for ent in (e.source, e.target):
            entity_degree[ent] = entity_degree.get(ent, 0) + 1
            if ent not in entity_ts or ts > entity_ts[ent]:
                entity_ts[ent] = ts

    for ent, deg in entity_degree.items():
        if deg < min_degree:
            continue
        ts = entity_ts.get(ent, now - 1e9)
        age_days = (now - ts) / 86400.0
        if age_days > max_age_days:
            stale.append(
                {
                    "entity": ent,
                    "age_days": round(age_days, 1),
                    "degree": deg,
                    "last_seen": ts,
                    "stale_score": round(min(1.0, age_days / (max_age_days * 2)), 3),
                }
            )

    stale.sort(key=lambda x: (-x["stale_score"], -x["degree"]))
    return stale[:100]


def get_high_centrality_genomes(
    graph: SimpleGraph | None = None,
    *,
    swarm_id: str | None = None,
    top_k: int = 20,
    min_gbrain_score: float = 0.1,
) -> list[dict[str, Any]]:
    """
    High-centrality genomes for prioritization (dream consolidation, synthesis seeding).
    Uses gbrain_signal_score + degree from compute_graph_signals.
    Only returns genome/* entities.
    """
    if graph is None:
        graph = get_knowledge_graph_for_swarm(swarm_id)
    # Focus on genome entities present in the graph
    genome_entities = [n for n in getattr(graph, "nodes", set()) if str(n).startswith("genomes/")]
    if not genome_entities:
        # fallback scan edges
        genome_entities = []
        for e in getattr(graph, "_edges", []):
            for x in (e.source, e.target):
                if str(x).startswith("genomes/"):
                    genome_entities.append(x)
        genome_entities = list(set(genome_entities))

    if not genome_entities:
        return []

    signals = compute_graph_signals(graph, genome_entities)
    ranked = []
    for ent in genome_entities:
        sig = signals.get(ent, {})
        gscore = sig.get("gbrain_signal_score", 0.0)
        if gscore < min_gbrain_score:
            continue
        ranked.append(
            {
                "genome": ent,
                "gbrain_signal_score": gscore,
                "degree": sig.get("degree", 0),
                "recency_boost": sig.get("recency_boost", 0.0),
                "swarm_trust": sig.get("swarm_trust", 0.6),
                "source_boost": sig.get("source_boost", 0.0),
                "is_hub": sig.get("is_hub", False),
            }
        )

    ranked.sort(key=lambda x: x["gbrain_signal_score"], reverse=True)
    return ranked[:top_k]


# Living Experience Layer helpers
# Makes the experience layer (via living-experience / experience-genome page types + KG wiring) the natural high-signal entry point for drive.think queries on major topics. Experience layer boosts integrate graph signals, calibration outputs, and daily fused observations.
def get_living_experience_for_topic(
    topic: str,
    graph: SimpleGraph | None = None,
    *,
    swarm_id: str | None = None,
    min_score: float = 0.6,
) -> list[dict[str, Any]]:
    """
    Experience Layer entrypoint helper.
    Given a major topic (e.g. "drive.think", "conductor-daily", "synthesis"),
    returns the highest-signal living-experience / experience-genome entry points wired via KG.
    Used by Conductors as the daily starting point; auto surfaces forks + latest from calibration, graph densification, and synthesis work via experience layer boosts.
    """
    if graph is None:
        graph = get_knowledge_graph_for_swarm(swarm_id)
    # Prefer direct "is_primary_entry_for" or "has_experience_entry" edges + high role-signal score
    candidates = []
    for e in getattr(graph, "_edges", []):
        if e.relation in ("is_primary_entry_for", "has_experience_entry") and topic in (
            e.source,
            e.target,
        ):
            other = e.target if e.source == topic else e.source
            if "experience" in other.lower() or "living" in other.lower():
                candidates.append(other)
    # Enrich with signals
    if candidates:
        sigs = compute_graph_signals(
            graph, list(set(candidates)), swarm_context=swarm_id or "example-experience"
        )
        enriched = []
        for c in set(candidates):
            s = sigs.get(c, {})
            score = s.get("gbrain_signal_score", 0.5) + (
                0.3 if "living-experience" in c.lower() or "experience-genome" in c.lower() else 0.0
            )
            if score >= min_score:
                enriched.append(
                    {
                        "experience_entry": c,
                        "for_topic": topic,
                        "gbrain_signal_score": round(s.get("gbrain_signal_score", 0.0), 3),
                        "relations": [
                            e.relation
                            for e in getattr(graph, "_edges", [])
                            if (e.source == c or e.target == c) and topic in (e.source, e.target)
                        ],
                        "swarm_trust": s.get("swarm_trust"),
                    }
                )
        enriched.sort(key=lambda x: x["gbrain_signal_score"], reverse=True)
        return enriched
    # Fallback: search high centrality experience genomes
    high = get_high_centrality_genomes(graph, top_k=5, min_gbrain_score=min_score)
    return [h for h in high if "experience" in h.get("genome", "").lower()]
