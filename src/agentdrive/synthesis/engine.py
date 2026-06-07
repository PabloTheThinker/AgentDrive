"""
Synthesis + Gap Analysis engine for experience layer v3.

Role-specialized swarms use this for hybrid fusion with graph signals, schema packs
(page types for source_boost), genomes with provenance, and explicit Gap objects +
contradictions. Integrates durable dream observations, calibration state from
DurableJobSupervisor jobs, and KG signals into cited SynthesisResult.

All work shares the central Drive + knowledge_graph. Correlation ID (from
using_correlation_id or auto-provision) propagates from Drive.think entrypoints
and DurableJobSupervisor stabilization job runners into:
- candidate selection / scoring
- gap/contradiction detection
- fusion_checkpoint assembly

This enables full cross-component traces for production observability of
stabilization work performed by role-specialized swarms on the framework.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from agentdrive.constants import get_correlation_id, new_correlation_id
from agentdrive.knowledge_graph import SimpleGraph

logger = logging.getLogger(__name__)

# Contradiction detection (gap closure integrated with calibration loops and graph signals)
try:
    from agentdrive.reasoning import detect_contradictions
except Exception:
    detect_contradictions = None

# Schema pack awareness (page types for source_boost, experience layer, synthesis-artifact routing)
try:
    from agentdrive.schema_packs import (
        load_active_pack,
        review_page_inference,
        suggest_page_types,
    )
except Exception:
    load_active_pack = None
    suggest_page_types = None
    review_page_inference = None

# KG fusion helpers (graph signals + experience layer boosts for synthesis)
try:
    from agentdrive.knowledge_graph.graph import (
        compute_graph_signals,
        find_contradictions_candidates,
        fuse_graph_signals_into_scores,
        get_knowledge_graph_for_swarm,
        temporal_freshness_score,
    )
except Exception:
    compute_graph_signals = None
    find_contradictions_candidates = None
    fuse_graph_signals_into_scores = None
    get_knowledge_graph_for_swarm = None
    temporal_freshness_score = None

# Closed-loop calibration: load persisted state from role-swarm calibration work to adjust weights/boosts
try:
    from agentdrive.dreaming.durable import (
        CALIBRATION_SWARM_ID,
        _load_calibration_state,
        run_tranche3_auto_calibration_job,
    )
except Exception:
    CALIBRATION_SWARM_ID = "example-calibration-swarm"
    _load_calibration_state = None
    run_tranche3_auto_calibration_job = (
        None  # role-calibration loop integration (kept for closed-loop weight adjustment)
    )


@dataclass
class Gap:
    description: str
    severity: str = "medium"
    suggested_action: str | None = None


@dataclass
class Citation:
    source_type: str
    source_id: str
    snippet: str | None = None
    confidence: float = 1.0

    def render(self, index: int | None = None) -> str:
        """Render a human-readable citation with optional index."""
        prefix = f"[{index}] " if index is not None else ""
        snip = f" — {self.snippet}" if self.snippet else ""
        conf = f" (conf={self.confidence:.2f})" if self.confidence < 0.99 else ""
        return f"{prefix}{self.source_type}:{self.source_id}{snip}{conf}"


@dataclass
class SynthesisResult:
    question: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    genomes_used: list[str] = field(default_factory=list)
    graph_hits: int = 0
    warnings: list[str] = field(default_factory=list)
    # Schema pack enrichment (page types for source boosts and experience layer)
    source_page_types: dict[str, str] = field(
        default_factory=dict
    )  # genome_id or src_id -> page_type name
    schema_pack_used: str | None = None
    # Contradiction auto-integration (gap closure via calibration loops + graph signals)
    contradictions: list[dict] = field(default_factory=list)  # {description, severity, sources}
    contradiction_count: int = 0
    # Dream + KG fusion (graph signals + experience layer) + richer hybrid metadata for calibration
    dream_observations_used: list[str] = field(default_factory=list)
    kg_fusion_signals: dict[str, Any] = field(default_factory=dict)
    dream_citations_count: int = 0
    fusion_metadata: dict[str, Any] = field(
        default_factory=dict
    )  # richer signals, page_type, dream boosts etc.
    # Explicit synthesis damage signals for HealingFactor (contradiction clusters + persistent gaps as first-class experience layer regeneration triggers)
    damage_signals: list[dict[str, Any]] = field(
        default_factory=list
    )  # {type, load, severity, recommendation, correlation_id, ...}

    def render_citations(self) -> str:
        """Produce formatted citation block for display / logging."""
        if not self.citations:
            return "(no citations)"
        lines = ["## Citations"]
        for i, c in enumerate(self.citations, 1):
            lines.append(c.render(i))
        return "\n".join(lines)

    def summary(self) -> str:
        """Compact one-line summary for logs / dashboards."""
        return (
            f"Synthesis(q={self.question[:40]!r}, genomes={len(self.genomes_used)}, "
            f"dreams={len(self.dream_observations_used)}, gaps={len(self.gaps)}, "
            f"graph_edges={self.graph_hits}, schema={self.schema_pack_used or 'n/a'})"
        )

    def to_mcp_dict(self) -> dict[str, Any]:
        """Serialize synthesis output for MCP ``agentdrive_think`` responses."""
        cid = get_correlation_id() or new_correlation_id()
        return {
            "answer": self.answer,
            "citations": [
                {
                    "source_type": c.source_type,
                    "source_id": c.source_id,
                    "snippet": c.snippet,
                    "confidence": c.confidence,
                }
                for c in self.citations
            ],
            "gaps": [
                {
                    "description": g.description,
                    "severity": g.severity,
                    "suggested_action": g.suggested_action,
                }
                for g in self.gaps
            ],
            "contradictions": list(self.contradictions),
            "genomes_used": list(self.genomes_used),
            "correlation_id": cid,
        }


def _ensure_mandatory_gaps(result: dict[str, Any], question: str) -> dict[str, Any]:
    """Guarantee at least one honest gap in MCP synthesis payloads.

    MCP clients must never receive a gap-free synthesis — empty evidence surfaces
    as an explicit high-severity gap rather than false confidence.
    """
    gaps = result.get("gaps")
    if not isinstance(gaps, list):
        gaps = []
        result["gaps"] = gaps
    if not gaps:
        gaps.append(
            {
                "description": f"Insufficient evidence in drive for full answer on: {question}",
                "severity": "high",
                "suggested_action": (
                    "Ingest more specialized genomes or record reasoning traces "
                    "via experience_graph_record_reasoning."
                ),
            }
        )
    return result


def run_synthesis(
    question: str,
    *,
    available_genomes: list[dict[str, Any] | Any] | None = None,
    graph: SimpleGraph | None = None,
    max_genomes: int = 8,
    dream_sources: list[dict[str, Any]] | None = None,
    use_kg_fusion: bool = True,
    swarm_context: str | None = None,
    # schema pack: auto-provided page_type context (for source_boost and experience layer) from Drive.query / drive.think
    schema_page_types: dict[str, str] | None = None,
    schema_pack_name: str | None = None,
) -> SynthesisResult:
    """
    Core synthesis engine. Produces cited, structured answers + honest gaps.

    - Leverages genome framework **steps** (typed playbooks with depends_on)
    - Leverages **knowledge_graph** typed relationships + multi-hop
    - Proper Citation rendering + SynthesisResult helpers
    - Gap analysis: missing rels, connectivity, staleness

    Correlation ID: automatically inherits or creates one for the synthesis
    execution; included in logs for joinability with Drive and web layers.
    """
    available_genomes = available_genomes or []
    graph = graph or SimpleGraph()

    # Observability: participate in / establish correlation ID for this synthesis run.
    # Called from Drive.think (and directly); ctx ensures continuity.
    _cid = get_correlation_id() or new_correlation_id()
    logger.debug("run_synthesis started", extra={"correlation_id": _cid, "swarm": swarm_context})

    # --- Normalize input (support raw dicts + full Genome objects)
    normed: list[dict[str, Any]] = []
    GenomeCls = None
    try:
        from agentdrive.genome.models import Genome as _G

        GenomeCls = _G
    except Exception:
        pass

    for raw in available_genomes[:max_genomes]:
        if isinstance(raw, dict):
            gid = (
                raw.get("id")
                or raw.get("genome_id")
                or raw.get("manifest", {}).get("id", "unknown")
            )
            normed.append(
                {
                    "id": gid,
                    "framework": raw.get("framework") or {},
                    "manifest": raw.get("manifest") or raw,
                    "_raw": raw,
                }
            )
        elif GenomeCls is not None and isinstance(raw, GenomeCls):
            gid = getattr(raw, "genome_id", "unknown")
            normed.append(
                {
                    "id": gid,
                    "framework": getattr(raw, "framework", {}) or {},
                    "manifest": getattr(raw, "manifest", {}),
                    "_genome": raw,
                }
            )
        else:
            gid = str(getattr(raw, "id", getattr(raw, "genome_id", "unknown")))
            normed.append({"id": gid, "framework": {}, "manifest": {}, "_raw": raw})

    # --- Dream observation normalization (durable dream consumption for experience layer)
    dream_normed: list[dict[str, Any]] = []
    dream_observations_used: list[str] = []
    dream_sources = dream_sources or []
    for dsrc in dream_sources[:6]:  # cap high-signal dreams
        did = (
            dsrc.get("id")
            or dsrc.get("run_id")
            or dsrc.get("candidate_id")
            or f"dream-{len(dream_normed)}"
        )
        dtype = dsrc.get("page_type", "dream-observation")
        dream_normed.append(
            {
                "id": did,
                "page_type": dtype,
                "content": dsrc.get("content") or dsrc.get("summary") or str(dsrc)[:300],
                "source": dsrc.get("source", "durable_dream"),
                "_raw": dsrc,
            }
        )
        dream_observations_used.append(did)

    # --- Closed-Loop Calibration: consult persisted state from role-swarm calibration work
    # Auto-adjusts synthesis base scores, source/page boosts, recency when prior contradictions surfaced.
    calib_state: dict[str, Any] = {}
    calib_boost_overrides: dict[str, float] = {}
    if _load_calibration_state is not None:
        try:
            calib_state = _load_calibration_state(CALIBRATION_SWARM_ID) or {}
            bo = calib_state.get("boost_overrides", {})
            calib_boost_overrides = {
                k.replace("source_boost_", "").replace("page_type_", ""): float(v)
                for k, v in bo.items()
            }
            sw = calib_state.get("synthesis_weights", {})
            # Dynamic base from calib (self-improving)
            base_score_cal = float(sw.get("base_score", 0.45))
            fw_bonus_cal = float(sw.get("framework_bonus", 0.25))
        except Exception:
            base_score_cal, fw_bonus_cal = 0.45, 0.25
    else:
        base_score_cal, fw_bonus_cal = 0.45, 0.25

    # --- Candidate selection for hybrid fusion (experience layer v3)
    # Graph-aware + framework-aware scoring (calibration-aware via temporal freshness + closed-loop overrides from DurableJobSupervisor jobs)
    # This is the core candidate selection step inside synthesis engine.
    scored: list[tuple[float, str, dict[str, Any], list[dict]]] = []
    for norm in normed:
        gid = norm["id"]
        score = base_score_cal
        fw = norm.get("framework") or {}
        steps: list[dict] = fw.get("steps", []) if isinstance(fw, dict) else []
        if steps:
            score += fw_bonus_cal
        if graph and hasattr(graph, "neighbors"):
            try:
                neigh = len(graph.neighbors(gid) or [])
                graph_factor = 0.12
                if calib_state and "graph_signal_multipliers" in calib_state:
                    graph_factor *= calib_state["graph_signal_multipliers"].get("recency", 1.0)
                score += min(neigh * graph_factor, 0.45)
                if hasattr(graph, "traverse"):
                    paths = graph.traverse(gid, max_depth=2) or []
                    score += min(len(paths) * 0.05, 0.25)
            except Exception:
                pass
        scored.append((score, gid, norm, steps))

    scored.sort(reverse=True, key=lambda x: x[0])
    top = scored[:max_genomes]

    genomes_used = [gid for _, gid, _, _ in top]
    graph_hits = len(getattr(graph, "_edges", []))

    _cid = get_correlation_id()
    logger.debug(
        "synthesis_candidate_selection_complete",
        extra={
            "correlation_id": _cid,
            "genomes_considered": len(top),
            "graph_hits": graph_hits,
            "swarm_context": swarm_context,
            "step": "candidate_selection",
        },
    )

    # --- Schema pack awareness + scoring boost (page types drive source_boost and experience layer integration)
    source_page_types: dict[str, str] = {}
    resolved_schema_pack_name = (
        schema_pack_name or None
    )  # prefer caller-provided (from drive.think auto context)
    if schema_page_types:
        # Auto-receive from Drive.query / drive.think annotation (schema pack page types for boosts)
        source_page_types.update({k: v for k, v in schema_page_types.items() if v})

    if suggest_page_types is not None or load_active_pack is not None:
        try:
            pack = load_active_pack() if load_active_pack else None
            if pack and not resolved_schema_pack_name:
                resolved_schema_pack_name = getattr(pack, "name", None)
            for _, gid, norm, _ in top:
                if gid in source_page_types:
                    continue  # already provided by drive context
                # Conventional path for genomes in drive
                candidate_path = f"genomes/{gid.split('@')[0] if '@' in gid else gid}"
                pt = None
                if pack and hasattr(pack, "resolve_type"):
                    pt = pack.resolve_type(candidate_path)
                elif suggest_page_types is not None:
                    # Fallback: ask suggest on a synthetic root (best effort)
                    suggestions = suggest_page_types(".") or []
                    for s in suggestions:
                        if gid.lower() in str(s).lower() or "genome" in s.get("page_type", ""):
                            pt = type("obj", (object,), {"name": s.get("page_type", "genome")})()
                            break
                if pt and getattr(pt, "name", None):
                    source_page_types[gid] = pt.name
                    # Boost for high-value extractable/expert types (schema page type driven)
                    if getattr(pt, "extractable", False) or getattr(pt, "expert_routing", False):
                        # Re-score: find and bump the entry
                        pt_boost = 0.18
                        # calibration override for dynamic page_type boosts (experience/synthesis-artifact)
                        pt_name = getattr(pt, "name", "")
                        if pt_name in calib_boost_overrides:
                            pt_boost = calib_boost_overrides.get(pt_name, pt_boost)
                        for i, (sc, g, n, st) in enumerate(scored):
                            if g == gid:
                                scored[i] = (sc + pt_boost, g, n, st)
                                break
            # Re-sort after boosts
            scored.sort(reverse=True, key=lambda x: x[0])
            top = scored[:max_genomes]
            genomes_used = [gid for _, gid, _, _ in top]
        except Exception:
            pass

    # --- Richer persistent KG fusion (graph signals + temporal freshness + schema page type boosts)
    kg_fusion_signals: dict[str, Any] = {}
    if use_kg_fusion and get_knowledge_graph_for_swarm is not None:
        try:
            swarm_for_kg = swarm_context or "example-synthesis"
            kg_graph = get_knowledge_graph_for_swarm(swarm_for_kg)
            # Collect entities: genomes + dream ids + question tokens as proxies
            query_entities = (
                genomes_used + dream_observations_used + [question[:50].replace(" ", "_")]
            )
            edge_meta = {}
            # Try load raw for meta (recency/swarm)
            try:
                from agentdrive.knowledge_graph.graph import KnowledgeGraphStore

                store = KnowledgeGraphStore(swarm_id=swarm_for_kg)
                for rec in store.load_raw_edges()[:50]:
                    key = rec.get("source") or rec.get("target")
                    if key:
                        edge_meta[key] = rec
            except Exception:
                pass
            kg_fusion_signals = (
                compute_graph_signals(
                    kg_graph, query_entities, swarm_context=swarm_for_kg, edge_meta=edge_meta
                )
                if compute_graph_signals
                else {}
            )
            # Fuse into scored genomes
            if fuse_graph_signals_into_scores and genomes_used:
                base_scores = {gid: 0.5 for gid in genomes_used}
                fused = fuse_graph_signals_into_scores(
                    base_scores,
                    kg_graph,
                    genomes_used,
                    swarm_context=swarm_for_kg,
                    edge_meta=edge_meta,
                    calibration_overrides=calib_boost_overrides or None,
                )
                for i, (sc, gid, n, st) in enumerate(scored):
                    if gid in fused:
                        scored[i] = (sc + min(fused[gid] * 0.12, 0.35), gid, n, st)
                scored.sort(reverse=True, key=lambda x: x[0])
                top = scored[:max_genomes]
                genomes_used = [gid for _, gid, _, _ in top]
                graph_hits = max(graph_hits, len(getattr(kg_graph, "_edges", [])) or 0)
        except Exception:
            pass

    # --- Fusion checkpoint assembly (hybrid fusion with graph signals into experience layer v3)
    # Captures the state after candidate selection + KG fusion + calibration for
    # provenance, traceability, and potential genome recording of synthesis checkpoints.
    # Correlation ID is embedded for join with DurableJobSupervisor jobs and recon deltas.
    _cid = get_correlation_id()
    _fusion_checkpoint: dict[str, Any] = {
        "correlation_id": _cid,
        "timestamp": datetime.now(UTC).isoformat(),
        "swarm_context": swarm_context,
        "genomes_used": list(genomes_used),
        "kg_fusion_signals": kg_fusion_signals,
        "graph_hits": graph_hits,
        "source_page_types_count": len(source_page_types),
        "calib_overrides_applied": bool(calib_boost_overrides),
        "synthesis_step": "fusion_checkpoint_assembly",
    }
    logger.debug(
        "synthesis_fusion_checkpoint_assembled",
        extra={
            "correlation_id": _cid,
            "fusion_checkpoint_summary": {
                "genomes": len(genomes_used),
                "signals": len(kg_fusion_signals),
            },
            "component": "synthesis.engine",
        },
    )

    # --- Apply dream observation page_type + boost (extractable dream-observation)
    for d in dream_normed:
        did = d["id"]
        source_page_types[did] = d.get("page_type", "dream-observation")
        # Boost dreams as high-signal (per charter: dream-observation extractable=True)
        # (dreams integrated into answer/citations below, not in genome scored)

    # Living Experience Layer: apply experience-observation / living-experience page_types (experience layer boosts)
    # These become the fused daily interface; auto surface high-value from graph signals + calibration via KG.
    for gid, pt in list(source_page_types.items()):
        if "experience" in pt or pt in (
            "living-experience",
            "experience-genome",
            "experience-observation",
        ):
            # Ensure high visibility in citations + future evolution proposals
            source_page_types[gid] = pt  # already set, but mark for special treatment downstream
            # Note: experience genomes participate in scoring via drive hybrid fusion (higher pt_boost)

    # --- Build rich structured answer using steps + graph relationships + schema context + dreams + KG signals
    q_lower = (question or "").lower()
    q_tokens = set(re.findall(r"[a-z0-9_]{3,}", q_lower))

    answer_parts: list[str] = [
        "**Synthesis (AgentDrive native with graph signals + schema page types)**\n",
        f"**Question:** {question}\n",
        f"**Sources:** {len(top)} genomes | {graph_hits} typed graph edges\n",
    ]

    # 1. Genome playbook steps surfaced
    answer_parts.append("\n## Playbook Steps (from top genomes)\n")
    surfaced_steps: list[tuple[str, dict]] = []
    for _, gid, norm, steps in top:
        for st in steps:
            if not isinstance(st, dict):
                continue
            step_text = " ".join(str(v).lower() for v in st.values())
            if (
                any(tok in step_text for tok in q_tokens)
                or "synthesis" in step_text
                or "analyze" in step_text
                or "reason" in step_text
            ):
                surfaced_steps.append((gid, st))
    if surfaced_steps:
        for gid, st in surfaced_steps[:9]:
            sid = st.get("id", "step")
            out = st.get("output", "")
            deps = st.get("depends_on", [])
            dep_str = f" (depends: {deps})" if deps else ""
            answer_parts.append(f"- **{gid}** :: `{sid}` → {out}{dep_str}\n")
    else:
        answer_parts.append(
            "(No high-signal steps matched question tokens; falling back to genome headers.)\n"
        )

    # 2. Graph relationships woven in
    answer_parts.append("\n## Knowledge Graph Relationships\n")
    rels_found = 0
    for _, gid, norm, _ in top[:5]:
        if not (graph and hasattr(graph, "neighbors")):
            break
        for rel in (
            "depends_on",
            "references",
            "authored_by",
            "related_to",
            "contributed_to",
            "executes",
        ):
            try:
                neigh = graph.neighbors(gid, relation=rel) or []
                if neigh:
                    rels_found += 1
                    answer_parts.append(f"- `{gid}` --[{rel}]--> {neigh[:4]}\n")
            except Exception:
                continue
    if rels_found == 0:
        answer_parts.append(
            "Sparse typed relationships for current result set. "
            "Graph will densify with more ingests.\n"
        )

    # 3. Multi-hop paths (demonstrates the graph layer)
    if graph and hasattr(graph, "traverse") and top:
        try:
            seed = top[0][1]
            paths = graph.traverse(seed, max_depth=2)[:2]
            if paths:
                answer_parts.append("\n**Multi-hop example:**\n")
                for p in paths:
                    nodes = " → ".join(p.nodes)
                    answer_parts.append(f"  {nodes}  ({p.length} hops)\n")
        except Exception:
            pass

    # 4. Base retrieval note
    answer_parts.append(
        "\n**Retrieval note:** Top genomes prioritized by framework richness + "
        "graph degree + traversal depth.\n"
    )

    # 5. Dream-observation consolidated knowledge (experience layer + calibration fusion)
    if dream_normed:
        answer_parts.append("\n## Dream-Consolidated Knowledge (from durable dreams)\n")
        for d in dream_normed[:3]:
            did = d["id"]
            content_snip = (d.get("content") or "")[:180].replace("\n", " ")
            answer_parts.append(
                f"- **{did}** (page_type={d.get('page_type')}, src={d.get('source')}): {content_snip}...\n"
            )
        answer_parts.append(
            "Dream observations treated as first-class high-signal sources (citation type 'dream').\n"
        )

    # 6. KG fusion signals summary
    if kg_fusion_signals:
        answer_parts.append("\n## KG Fusion Signals Applied\n")
        top_signals = list(kg_fusion_signals.items())[:4]
        for ent, sig in top_signals:
            answer_parts.append(
                f"- {ent}: trust={sig.get('swarm_trust', 0.6)}, recency={sig.get('recency_boost', 0)}, composite={sig.get('composite', 0)}\n"
            )

    # Citations (with proper rendering) - genomes + dreams (special 'dream' type)
    citations: list[Citation] = []
    dream_citations_count = 0
    for i, (_, gid, norm, steps) in enumerate(top[:6], 1):
        snippet = None
        fw = norm.get("framework") or {}
        if isinstance(fw, dict) and fw.get("description"):
            snippet = str(fw["description"])[:140]
        elif steps:
            snippet = f"Framework with {len(steps)} steps"
        ptype = source_page_types.get(gid, "genome")
        citations.append(
            Citation(
                source_type="genome",
                source_id=gid,
                snippet=snippet
                or f"Contributed ({ptype}) structured steps + metadata to synthesis",
                confidence=0.82 if steps else 0.65,
            )
        )
    # Dream citations with type "dream"
    for d in dream_normed[:4]:
        dream_citations_count += 1
        citations.append(
            Citation(
                source_type="dream",
                source_id=d["id"],
                snippet=(d.get("content") or "")[:120],
                confidence=0.78,
            )
        )

    answer_parts.append(
        "\n" + SynthesisResult(question=question, answer="", citations=citations).render_citations()
    )

    # Schema context in answer (page types from active schema pack for transparent boosts)
    if source_page_types:
        answer_parts.append("\n## Source Page Types (schema pack)\n")
        for gid, ptype in list(source_page_types.items())[:6]:
            answer_parts.append(f"- {gid} → {ptype}\n")
        if resolved_schema_pack_name:
            answer_parts.append(f"**Active pack:** {resolved_schema_pack_name}\n")

    # --- Gap / contradiction detection for experience layer v3 (hybrid fusion)
    # Smart gap analysis using graph + genome metadata + schema pack signals.
    # Explicit Gap objects produced here; contradictions integrated from detect_contradictions
    # (wired via calibration loops from DurableJobSupervisor jobs) + find_contradictions_candidates.
    _cid = get_correlation_id()
    logger.debug(
        "synthesis_gap_contradiction_detection_start",
        extra={
            "correlation_id": _cid,
            "top_genomes": len(top),
            "graph_hits": graph_hits,
            "step": "gap_contradiction_detection",
        },
    )

    "".join(answer_parts)  # built for future use / logging
    gaps: list[Gap] = []

    if len(top) < 3:
        gaps.append(
            Gap(
                "Limited relevant genomes available for strong synthesis.",
                "high",
                "Ingest more specialized genomes (arch/security/research/reasoning) via the Drive.",
            )
        )

    if graph_hits < 4:
        gaps.append(
            Gap(
                "Knowledge graph sparse: few typed relationships for retrieved genomes.",
                "medium",
                "Ingest more work; drive.ingest() auto-extracts typed edges via link_extraction.",
            )
        )

    # Connectivity / missing relationship detection
    if graph and top:
        all_connected: set[str] = set()
        for _, gid, _, _ in top:
            all_connected.add(gid)
            try:
                all_connected.update(graph.neighbors(gid) or [])
                for p in graph.traverse(gid, max_depth=1) or []:
                    all_connected.update(p.nodes)
            except Exception:
                pass
        if len(all_connected) <= len(top):
            gaps.append(
                Gap(
                    "Graph connectivity low: genomes form isolated clusters (no bridging edges).",
                    "high",
                    "Add genome refs + depends_on edges. Run cross-swarm work to densify graph.",
                )
            )

    # Staleness detection
    try:
        now = datetime.now(UTC)
        for _, gid, norm, _ in top[:3]:
            manif = norm.get("manifest") or {}
            li = manif.get("last_improved") or manif.get("created")
            if li:
                age_days = 999
                if isinstance(li, datetime):
                    age_days = (now - li).days
                elif isinstance(li, str):
                    try:
                        parsed = datetime.fromisoformat(li.replace("Z", "+00:00"))
                        age_days = (now - parsed).days
                    except Exception:
                        pass
                if age_days > 120:
                    gaps.append(
                        Gap(
                            f"Genome {gid} is stale (>{age_days} days since last improvement).",
                            "medium",
                            "Trigger evolution cycle or re-ingest improved version.",
                        )
                    )
                    break
    except Exception:
        pass

    # Contradiction integration point (explicit for role-swarm calibration loops)
    contradictions_detected: list[dict[str, Any]] = []
    if detect_contradictions is not None:
        try:
            # Best-effort: surface contradictions from top genomes + graph for gap closure
            # (full wiring in calibration jobs dispatched via DurableJobSupervisor)
            raw_contras = (
                detect_contradictions([g.get("_raw") or g for g in [t[2] for t in top[:5]]]) or []
            )
            for c in raw_contras[:3]:
                contradictions_detected.append({"description": str(c)[:200], "severity": "medium"})
        except Exception:
            pass

    # Explicit synthesis damage signal production for HealingFactor (contradiction clusters + persistent gaps as first-class damage)
    # High load or clusters become "damage" that triggers regenerative diagnosis + experience consolidation proposals.
    damage_signals: list[dict[str, Any]] = []
    if (
        len(contradictions_detected) >= 2
        or len([g for g in gaps if g.severity in ("high", "medium")]) >= 3
    ):
        damage_signals.append(
            {
                "type": "synthesis_contradiction_cluster",
                "load": len(contradictions_detected) + len(gaps),
                "severity": "high" if len(contradictions_detected) >= 3 else "medium",
                "recommendation": "Dispatch healing_diagnosis job via DurableJobSupervisor for contradiction cluster closure and experience consolidation proposal.",
                "correlation_id": _cid,
            }
        )

    # Generic honest gap (calibration loop wires detect_contradictions + find_contradictions_candidates into SynthesisResult.contradictions; graph signals + temporal freshness feed resolutions)
    gaps.append(
        Gap(
            "Fuller cross-genome contradiction calibration + temporal freshness scoring + engine-abstraction (remaining cellular map items).",
            "medium",
            "Gap closure pass in progress via role-specialized swarm calibration using DurableJobSupervisor + two-phase leases.",
        )
    )

    # Attach to result (post-construction in caller path; here we log the checkpoint)
    logger.debug(
        "synthesis_gap_contradiction_detection_complete",
        extra={
            "correlation_id": _cid,
            "gaps_emitted": len(gaps),
            "contradictions_detected": len(contradictions_detected),
            "step": "gap_contradiction_detection",
        },
    )

    # Final SynthesisResult construction (source surface completion for full HealingFactor + drive.think integration).
    # Wires explicit damage_signals, gaps, contradictions, fusion metadata for experience layer regeneration diagnosis.
    final_answer = "\n".join(answer_parts)
    return SynthesisResult(
        question=question,
        answer=final_answer,
        citations=citations,
        gaps=gaps,
        genomes_used=[t[1] for t in top],
        graph_hits=graph_hits,
        warnings=[],
        source_page_types=source_page_types or {},
        schema_pack_used=resolved_schema_pack_name,
        contradictions=contradictions_detected,
        contradiction_count=len(contradictions_detected),
        dream_observations_used=dream_observations_used,
        kg_fusion_signals=kg_fusion_signals,
        dream_citations_count=dream_citations_count,
        fusion_metadata={
            "fusion_checkpoint": "synthesis_with_graph_signals_and_schema_boosts",
            "calibration_applied": bool(calib_state),
            "experience_layer_signals": True,
        },
        damage_signals=damage_signals,
    )


# --- BRAINENGINE SKETCH (unified abstraction for synthesis + think) ---
# Cells integrate: core_synthesis, dream phases, dispatch, calibration_loop, experience layer fusion (living-experience boosts), graph signals.
class BrainEngine:
    """Unified abstraction (for future expansion) for synthesis and Drive.think operations
    in experience layer v3.

    Routes through cells for calibration_loop (DurableJobSupervisor jobs), dream phases,
    experience_fusion with graph signals + schema packs, producing SynthesisResult with
    explicit Gap objects + contradictions.
    """

    def __init__(self, *, swarm_context: str = "example-synthesis"):
        self.swarm_context = swarm_context
        self.cells = {
            "core_synthesis": "run_synthesis refactored here",
            "dream_phases": "light/rem/adversarial/deep via DurableDreamRunner",
            "minions_dispatch": "via dispatch supervisor + spec-driven coordination",
            "calibration_loop": "closed-loop auto-calibration + temporal_freshness scoring",
            "experience_fusion": "living-experience page types + dynamic boosts from genome + graph signals",
            "graph_signals": "graph densification + SimpleGraph multi-hop + experience layer boosts",
        }

    def think(self, question: str, **kwargs):
        # Future: routes question through active cells, applies densification, returns SynthesisResult + auto proposals
        # For now: delegates (improvements are incremental)
        # Note: in real expansion this will not re-import self module
        return run_synthesis(question, **kwargs)

    def propose_evolution(self, **kwargs):
        from .engine import propose_experience_evolution

        return propose_experience_evolution(**kwargs)

    def status(self):
        return {
            "cells": list(self.cells.keys()),
            "note": "This sketch will be expanded by the brainengine abstraction job.",
        }


def propose_experience_evolution(
    current_experience_genome_id: str = "agentdrive-example-experience-v3",
    *,
    from_calibration: bool = False,
    from_graph_hardener: bool = False,
    proposed_changes: dict[str, Any] | None = None,
    swarm_context: str | None = "example-experience-swarm",
) -> dict[str, Any]:
    """
    Create an evolution proposal for the living experience genome family.
    Uses AgentDrive promotion system + Genome fork model.
    Called by Conductors, Calibration loops, or auto after high-value graph densification / synthesis work.
    Returns proposal payload ready for promotion.submit + Conductor review.
    """
    proposal = {
        "type": "experience_evolution_proposal",
        "target_genome": current_experience_genome_id,
        "family": "living-experience-genome-family",
        "proposed_version": "v3.1" if "v3" in current_experience_genome_id else "next",
        "source_swarms": [],
        "mechanics": "fork + promote via agentdrive.promotion + Genome.record_improvement",
        "auto_incorporated": [],
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if from_calibration:
        proposal["source_swarms"].append("calibration")
        proposal["auto_incorporated"].append("contradiction_resolutions + calibrated boosts")
    if from_graph_hardener:
        proposal["source_swarms"].append("graph")
        proposal["auto_incorporated"].append(
            "updated gbrain_signal_score + recency + centrality edges from graph signals"
        )
    if proposed_changes:
        proposal["proposed_changes"] = proposed_changes
    # In real flow: from agentdrive.promotion.service import submit_proposal; submit...
    proposal["status"] = "ready_for_promotion_gate"
    proposal["integration_note"] = (
        "New Conductors start from the (possibly updated) experience genome as single source of truth. "
        "Forks create parallel living-experience branches; best descendants bubble via selection in drive.think."
    )
    return proposal
