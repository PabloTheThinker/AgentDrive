"""
Core schema pack primitives.

Lightweight, evolvable schema pack system for AgentDrive (works with genomes + raw drive content + knowledge_graph edges + graph signals + experience layer). Page types enable source_boost and page type aware routing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PageType:
    """Dynamic page type for raw drive content (pages, captures, observations, etc).

    Complements strong Genome typing: Genomes are the high-signal portable DNA;
    page types give lightweight classification + routing hints for everything else
    that lands in the drive filesystem or content store.
    """

    name: str
    primitive: str = "entity"  # entity | media | analysis | note | relation | etc.
    path_prefixes: list[str] = field(default_factory=list)
    extractable: bool = False
    expert_routing: bool = False
    description: str = ""
    # Future: extract_rules, mime_hints, etc. kept out for lightness


@dataclass
class DriveSchemaPack:
    """A named, versioned collection of PageTypes with resolution logic.

    Supports dynamic page typing:
    - Dynamic page_types with path_prefixes, extractable (for KG + graph signals), expert_routing flags for specialized handling and experience layer
    - detect / suggest / review flow (via manager helpers)
    - Runtime resolution (resolve_type + manager activation)
    """

    name: str
    version: str
    page_types: list[PageType] = field(default_factory=list)
    description: str = ""

    def get_type_for_path(self, path: str) -> PageType | None:
        """Longest-prefix match for determinism (runtime resolution primitive)."""
        best: PageType | None = None
        best_len = -1
        p = str(path).replace("\\", "/")
        for pt in self.page_types:
            for prefix in pt.path_prefixes:
                if p.startswith(prefix) and len(prefix) > best_len:
                    best = pt
                    best_len = len(prefix)
        return best

    def resolve_type(self, path: str, context: dict[str, Any] | None = None) -> PageType | None:
        """Runtime resolution entrypoint. Context allows future enrichment
        (mime, first bytes, swarm tags) without changing the pack.
        """
        # Current impl: robust prefix. Can be extended with context rules.
        t = self.get_type_for_path(path)
        if t is None and context:
            # Example hook: if context has explicit 'page_type_hint'
            hint = context.get("page_type_hint")
            if hint:
                for pt in self.page_types:
                    if pt.name == hint:
                        return pt
        return t

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DriveSchemaPack:
        pts: list[PageType] = []
        for ptd in data.get("page_types", []):
            pts.append(
                PageType(
                    name=ptd["name"],
                    primitive=ptd.get("primitive", "entity"),
                    path_prefixes=ptd.get("path_prefixes", []),
                    extractable=ptd.get("extractable", False),
                    expert_routing=ptd.get("expert_routing", False),
                    description=ptd.get("description", ""),
                )
            )
        return cls(
            name=data.get("name", "unnamed"),
            version=data.get("version", "0.1.0"),
            page_types=pts,
            description=data.get("description", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "page_types": [
                {
                    "name": pt.name,
                    "primitive": pt.primitive,
                    "path_prefixes": list(pt.path_prefixes),
                    "extractable": pt.extractable,
                    "expert_routing": pt.expert_routing,
                    "description": pt.description,
                }
                for pt in self.page_types
            ],
        }

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.to_dict(), sort_keys=False, allow_unicode=True)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> DriveSchemaPack:
        data = yaml.safe_load(yaml_str) or {}
        return cls.from_dict(data)


# ─────────────────────────────────────────────────────────────────────────────
# Starter "agentdrive-drive" pack — the practical default for this ecosystem.
# Makes sense for genomes (strong typing) + knowledge_graph + synthesis artifacts
# + dream observations + raw captures/pages + swarm coordination.
# This is the canonical starter pack definition. It provides page types that power graph signals (via source_boost), experience layer, synthesis, and calibration.
# ─────────────────────────────────────────────────────────────────────────────

AGENTDRIVE_DRIVE_PACK = DriveSchemaPack(
    name="agentdrive-drive",
    version="0.2.0",
    description=(
        "Primary schema pack for AgentDrive drives. Provides dynamic page typing "
        "for raw drive content (pages, captures, observations) that complements "
        "the first-class Genome typing system. Includes flags for: "
        "path_prefixes, extractable (for KG wiring), expert_routing (specialized agent handlers). "
        "Includes living-experience / experience-observation / experience-genome / daily-present / research-thread page types "
        "so the fused One Experience (via graph signals + calibration loops + synthesis) becomes the versioned, "
        "forkable living genome family and natural entry point for drive.think / Conductor daily use with experience layer boosts. "
        "daily-present supports supervisor-driven daily_consolidation for role-swarm coherence. "
        "research-thread enables native forked research thread living-experience genome families with lineage, constitution, budget, evaluation-based merge/promotion (full autoresearch integration for real-time Grid on stabilization-wave-20260531 drive). "
        "HealingFactor page types (healing-damage, regeneration-proposal, experience-consolidation) enable schema-pack governed "
        "experience layer regeneration: damage signal capture, safe proposal generation, durable healing phase execution, and consolidation feedback into v3. "
        "research-constitution page type registers Research Constitutions (experience-observation / synthesis-artifact / daily-present genomes) as first-class schema-pack governed artifacts for autonomous research threads, HealingFactor multi-metric evaluation, GridEngine v3 fusion rules, role-swarm org coordination (Diagnoser/Proposer/Verifier/Consolidator/Adversary), and constrained evolutionary search inside the Grid (research budgets + provenance discipline). "
        "loop-experience-graph + cycle-connection page types provide Obsidian-style bidirectional typed connection graphs for every canonical Parent-Overseer-Research real-time evolution loop iteration (clean ingestion of briefings/decisions/threads/synthesis/EpisodicTraces into metacognition + experience layer; explicit 'informed_by' / 'caused_adaptation' / 'produced_experience' / 'texture_resonance' relations with cycle_id + CID + fusion_checkpoint metadata). Enables models, Overseer, and Parent to see/traverse/strengthen connections so experience expands intelligently and grows from there. All on stabilization-wave-20260531 drive with full provenance for sibling swarm coordination."
    ),
    page_types=[
        PageType(
            name="genome",
            primitive="entity",
            path_prefixes=["genomes/", "genomes"],
            extractable=True,
            expert_routing=True,
            description="Core Agent DNA. Versioned portable capability. Primary KG extract target.",
        ),
        PageType(
            name="knowledge-graph-edge",
            primitive="relation",
            path_prefixes=["knowledge/", "kg/", "graph/", "knowledge_graph/"],
            extractable=False,
            expert_routing=False,
            description="Typed KG relations (authored_by, depends_on, etc) from ingest/synthesis.",
        ),
        PageType(
            name="synthesis-artifact",
            primitive="analysis",
            path_prefixes=["synthesis/", "synthesis-artifacts/", "gaps/"],
            extractable=True,
            expert_routing=True,
            description="Synthesis outputs: answers, citations, gaps. High value for reuse.",
        ),
        PageType(
            name="dream-observation",
            primitive="analysis",
            path_prefixes=["dreams/", "dreaming/", "observations/", "candidates/"],
            extractable=True,
            expert_routing=True,
            description="Dream/substrate observations + candidates. Feeds evolution.",
        ),
        # Living Experience Layer page types:
        # Turns fused "One Experience" (hybrid fusion via graph signals + schema page type boosts + calibration outputs)
        # into proper versioned, forkable "living experience" genome family.
        # Primary daily interface / single source of truth for Conductors via experience layer.
        # New Conductors start from current fused experience here.
        PageType(
            name="experience-observation",
            primitive="analysis",
            path_prefixes=[
                "experience/",
                "experiences/",
                "fused/",
                "fusion-obs/",
                "living-experience/",
            ],
            extractable=True,
            expert_routing=True,
            description="Raw fused experience observations from hybrid drive.think / synthesis. Pre-promotion stage for living experience genomes.",
        ),
        PageType(
            name="living-experience",
            primitive="entity",
            path_prefixes=[
                "experience-genomes/",
                "living-experience/",
                "one-experience/",
                "conductor-daily/",
            ],
            extractable=True,
            expert_routing=True,
            description="Versioned living experience genome family. The fused One Experience evolved into primary daily Conductor interface. Forkable, evolvable, with auto-incorporation from Graph Hardener + Calibration Engine outputs.",
        ),
        PageType(
            name="daily-present",
            primitive="entity",
            path_prefixes=[
                "daily-present/",
                "daily_consolidations/",
                "stabilization-daily/",
                "conductor-daily-present/",
            ],
            extractable=True,
            expert_routing=True,
            description="Attributed daily-present observation/genome produced by supervisor-driven daily_consolidation phase. Captures the fused 'all work together' role-swarm coherence via Drive.think(prefer_experience_layer=True) + synthesis + fusion_checkpoint. Auto-promotes into experience layer v3 for daily Conductor entrypoint using schema-driven signals.",
        ),
        # HealingFactor / experience layer regeneration page types (additive schema evolution for damage diagnosis, safe proposals, and consolidation artifacts).
        # Enables source_boost + expert_routing for healing-damage signals, regeneration proposals (schema-pack governed), and experience-consolidation outputs under DurableJobSupervisor healing phase.
        # research-constitution page type adds support for Research Constitutions as versionable first-class artifacts for role-specialized swarm research org and constrained evolutionary search.
        # Paths align with stabilization-wave observations/ + drive content for KG extract + graph signals + Conductor daily-present fusion.
        PageType(
            name="healing-damage",
            primitive="analysis",
            path_prefixes=[
                "observations/healing-damage/",
                "healing-damage/",
                "damage-signals/",
                "healing/damage/",
            ],
            extractable=True,
            expert_routing=True,
            description="First-class damage signals (synthesis contradiction clusters, persistent gaps, security posture needs_attention, durable job exhaustion, worker post-retry failures, immune CRITICAL). Triggers HealingFactor diagnosis via Drive.think(prefer_experience_layer=True) + run_synthesis + LineageImmune + graph signals. Schema-pack governed for role-swarm regeneration loops.",
        ),
        PageType(
            name="regeneration-proposal",
            primitive="analysis",
            path_prefixes=[
                "observations/healing-proposals/",
                "healing-proposals/",
                "regeneration-proposals/",
                "healing/proposals/",
            ],
            extractable=True,
            expert_routing=True,
            description="Safe first-class regeneration proposals produced by HealingFactor (correction_observation, immune_rule_update, experience_consolidation_genome, daily-present style). Never raw source patches. Carry verification_gates, correlation_id, self_referential notes. Execute under durable healing jobs with full promotion + immune + quarantine gates.",
        ),
        PageType(
            name="experience-consolidation",
            primitive="entity",
            path_prefixes=[
                "experience-consolidations/",
                "daily_consolidations/experience/",
                "healing/consolidation/",
                "stabilization-consolidation/",
            ],
            extractable=True,
            expert_routing=True,
            description="Experience layer consolidation artifacts and proposals (daily-present style or living-experience updates). Produced/ingested during HealingFactor closed-loop regeneration or DurableJobSupervisor healing phase. Feeds experience layer v3 fusion, KG resilience edges (strengthened_resilience), and future Drive.think(prefer_experience_layer=True) prevention.",
        ),
        # Research Constitution page type (additive for Research Constitution Architect Swarm + Multi-Agent Research Org Swarm evolution).
        # Enables schema-pack governed, versionable, human/Conductor-editable Research Constitutions
        # as first-class experience-observation / synthesis-artifact / daily-present genomes.
        # Directly usable by GridEngine, HealingFactor, daily_consolidation for autonomous
        # experience layer regeneration, role-swarm research org coordination, and constrained
        # evolutionary search. Paths align with stabilization-wave-20260531 drive artifacts.
        # Evolved here: specialist role charters (Diagnoser etc.), handoff protocols, dynamic team formation.
        PageType(
            name="research-constitution",
            primitive="entity",
            path_prefixes=[
                "constitutions/",
                "research-constitutions/",
                "experience-constitutions/",
                "stabilization-constitutions/",
                "genomes/research-constitutions/",
            ],
            extractable=True,
            expert_routing=True,
            description="Human-editable (or high-continuity Conductor-editable) Research Constitutions modeled on AgentDrive genome patterns. Schema-pack governed versionable artifacts (experience-observation / synthesis-artifact / daily-present genomes) for HealingFactor diagnosis criteria + multi-metric regeneration evaluation, GridEngine daily_consolidation + experience layer v3 fork/merge rules, role-specialized swarm research org (Diagnoser/Proposer/Verifier/Consolidator/Adversary + coordination protocols + role charters), and constrained evolutionary search (research budgets, objective evaluation harness, keep/discard provenance via genome forks + promotion). Directly consumable by GridEngine, HealingFactor, daily_consolidation for autonomous research threads inside the Grid on stabilization-wave-20260531 drive. Produced constitutions include full role charters, example thread manifests, and coordination discipline.",
        ),
        # Research-thread page type: first-class native support for forked "research thread"
        # living-experience genome families inside experience layer v3 (stabilization-wave-20260531 drive).
        # Each is a versioned fork with clear lineage (parent + constitution + budget provenance),
        # evaluation-based advancement, and merge/promotion gates that reuse existing promotion,
        # LineageImmuneSystem verification, and quarantine gates. GridEngine research threads and
        # HealingFactor autonomous iterations emit these as living branches; successful ones
        # advance via MultiMetricEvaluationHarness + Consolidator into main lineage during
        # daily_consolidation. Pure AgentDrive: Genome.fork + provenance + schema pack + KG research_branch edges.
        PageType(
            name="research-thread",
            primitive="entity",
            path_prefixes=[
                "research-threads/",
                "living-experience/research-threads/",
                "experience-genomes/research-threads/",
                "stabilization-research-branches/",
                "grid-research-threads/",
            ],
            extractable=True,
            expert_routing=True,
            description="First-class forked living-experience genome families for autonomous research threads (inspired by git branches in autoresearch but native to experience layer v3). Carries provenance (parent genome, constitution ref, research_budget snapshot, correlation_id, evaluation_harness scores). Forked by GridEngine._research_thread_coordinator_loop / HealingFactor research iterations via Genome.fork. Advancement (merge to main lineage or promotion) gated by promotion service + immune verification + multi-metric harness (resilience_delta, contradiction_reduction, fusion_quality, role_swarm_coherence, budget_efficiency). Daily_consolidation scans active research-thread artifacts for high-signal outcomes and performs merge/promote decisions into the canonical living-experience anchor. All coordination via live drive artifacts on stabilization-wave-20260531 drive.",
        ),
        # Experience Graph / Loop Connection page types (real-time Parent-Overseer-Research evolution loop).
        # Provides Obsidian-style bidirectional typed connection graphs scoped to each canonical loop iteration.
        # Enables the AI model, Overseer metacognition, and Parent Conductor to see, traverse, strengthen,
        # and grow connections between briefings, decisions, research threads, synthesis textures, EpisodicTraces,
        # fusion_checkpoints, and new experience observations — causing the overall experience to expand intelligently.
        # Dual-stored: per-cycle JSON (fast "note graph") + TypedEdges in main KG (global signals + Drive.think boosts).
        # All relations carry correlation_id + cycle_id + fusion_checkpoint snippets for full traceability.
        PageType(
            name="loop-experience-graph",
            primitive="analysis",
            path_prefixes=[
                "meta_evolution/loops/",
                "meta_evolution/loop-graphs/",
                "experience/loop-graphs/",
                "experience-graphs/",
                "loop-connections/",
                "cycle-graphs/",
            ],
            extractable=True,
            expert_routing=True,
            description="Per-iteration Obsidian-style connection graph for the exact canonical Parent-Overseer-Research real-time evolution loop. Nodes are artifacts (overseer_briefing, parent_decision, research_thread_outcome, synthesis_result, episodic_trace, fusion_checkpoint, new_experience_observation). Edges are explicit bidirectional typed relations (overseer_briefing_informed_parent_decision, parent_decision_executed_as_research_thread, research_thread_produced_synthesis, texture_resonance_to_episodic_trace, cycle_closed_with_experience_lift, connection_strengthened_by_densification, etc.). Produced by ExperienceGraphRecorder at cycle close. Queryable via get_cycle_graph() + existing KG traverse. High source_boost for Drive.think(prefer_experience_layer). Primary substrate for metacognitive growth and intelligent experience expansion per loop.",
        ),
        PageType(
            name="cycle-connection",
            primitive="relation",
            path_prefixes=[
                "meta_evolution/connections/",
                "loop-edges/",
                "experience/connections/",
            ],
            extractable=True,
            expert_routing=False,
            description="Individual typed connection edges within a loop-experience-graph (for granular KG indexing and multi-hop queries). Mirrors LoopEdge relations with full metadata (cycle_id, felt_texture, harness_scores, CID subtree).",
        ),
        PageType(
            name="experience-genome",
            primitive="entity",
            path_prefixes=["genomes/experience/", "agentdrive-example-experience/"],
            extractable=True,
            expert_routing=True,
            description="Specific living-experience genomes (e.g. agentdrive-experience-v3). High-signal entry points for drive.think on major topics via experience layer boosts. Strong KG wiring + graph signals make these the natural starting point.",
        ),
        PageType(
            name="capture",
            primitive="media",
            path_prefixes=["captures/", "raw/", "pages/", "screenshots/", "imports/"],
            extractable=True,
            expert_routing=False,
            description="Raw captures, pages, screenshots, imports. General raw drive content.",
        ),
        PageType(
            name="note",
            primitive="note",
            path_prefixes=["notes/", "inbox/", "scratch/", "todo/"],
            extractable=True,
            expert_routing=False,
            description="Free-form notes/inbox. Extractable for later genome promotion.",
        ),
        PageType(
            name="swarm-artifact",
            primitive="entity",
            path_prefixes=["swarms/", ".swarm/", "coordination/"],
            extractable=False,
            expert_routing=True,
            description="Swarm coordination, sub-agent status, shared role context for multi-swarm operation.",
        ),
        PageType(
            name="schema-pack",
            primitive="entity",
            path_prefixes=["schema_packs/", "packs/", "schema/"],
            extractable=True,
            expert_routing=True,
            description="Schema pack defs + YAML + design work. Self-hosting for this system.",
        ),
    ],
)

# Back-compat alias (old name now points at the real starter)
DEFAULT_PACK = AGENTDRIVE_DRIVE_PACK


# ─────────────────────────────────────────────────────────────────────────────
# SchemaPackManager + activation + detect/suggest/review + runtime flows
# Lightweight, no heavy deps, CLI-friendly Python API.
# All AgentDrive code (role swarms, synthesis, graph, drive, etc) should go through the manager for consistent page type resolution and source_boost integration
# for consistent pack usage.
# ─────────────────────────────────────────────────────────────────────────────

_active_pack: DriveSchemaPack | None = None
_manager: "SchemaPackManager | None" = None


class SchemaPackManager:
    """Central lightweight manager.

    - Register multiple packs (built-in + user)
    - Activate/switch at runtime (affects load_active_pack everywhere)
    - detect / suggest / review flow implementations
    - Runtime resolution delegation
    - Python API that is directly usable from CLI, TUI, agents, or tests.
    """

    def __init__(self) -> None:
        self._packs: dict[str, DriveSchemaPack] = {
            "agentdrive-drive": AGENTDRIVE_DRIVE_PACK,
            "agentdrive-base": DEFAULT_PACK,  # alias for compat
        }
        self._active_name: str = "agentdrive-drive"

    def register_pack(self, pack: DriveSchemaPack) -> None:
        """Add or override a pack by its .name."""
        self._packs[pack.name] = pack

    def activate(self, name: str) -> DriveSchemaPack:
        """Activate a registered pack. Returns the now-active pack.
        This is the main runtime switch used by agents and CLI.
        """
        if name not in self._packs:
            raise ValueError(f"Pack '{name}' not registered. Available: {list(self._packs.keys())}")
        global _active_pack
        self._active_name = name
        _active_pack = self._packs[name]
        return _active_pack

    def get_active(self) -> DriveSchemaPack:
        """Current active pack (with lazy init)."""
        global _active_pack
        if _active_pack is None:
            _active_pack = self._packs.get(self._active_name, AGENTDRIVE_DRIVE_PACK)
        return _active_pack

    def list_packs(self) -> list[str]:
        return sorted(self._packs.keys())

    def get_pack(self, name: str) -> DriveSchemaPack | None:
        return self._packs.get(name)

    # --- Core flows: detect / suggest / review (for page type inference + evolution supporting graph signals and experience layer) -----------------------

    def suggest_for_drive(self, drive_root: Path | str) -> list[dict[str, Any]]:
        """Suggest page types present in a drive root (detect + suggest flow).

        Returns rich dicts with type + reason. Used by synthesis, TUI, onboarding.
        """
        root = Path(drive_root)
        suggestions: list[dict[str, Any]] = []
        if not root.exists():
            return suggestions
        pack = self.get_active()
        for pt in pack.page_types:
            for prefix in pt.path_prefixes:
                candidate = root / prefix.rstrip("/")
                if candidate.exists():
                    suggestions.append(
                        {
                            "page_type": pt.name,
                            "primitive": pt.primitive,
                            "path": str(candidate),
                            "prefix_matched": prefix,
                            "extractable": pt.extractable,
                            "expert_routing": pt.expert_routing,
                            "description": pt.description,
                            "reason": f"filesystem prefix match: {prefix}",
                        }
                    )
                    break  # only once per type
        return suggestions

    def review_page_inference(
        self, path: str, pack: DriveSchemaPack | None = None
    ) -> dict[str, Any]:
        """Review flow: given a path, show the inference result + metadata + alts.

        Perfect for debugging, agent review steps, or TUI inspectors.
        """
        p = pack or self.get_active()
        inferred = p.resolve_type(path)
        alternatives = [
            pt.name
            for pt in p.page_types
            if any(str(path).replace("\\", "/").startswith(pre) for pre in pt.path_prefixes)
        ]
        return {
            "path": str(path),
            "inferred_type": inferred.name if inferred else None,
            "primitive": inferred.primitive if inferred else None,
            "extractable": bool(getattr(inferred, "extractable", False)),
            "expert_routing": bool(getattr(inferred, "expert_routing", False)),
            "description": getattr(inferred, "description", ""),
            "alternatives": alternatives,
            "confidence": 0.92 if inferred else 0.0,
            "pack": p.name,
            "pack_version": p.version,
        }

    def detect_schema(self, drive_root: Path | str) -> list[str]:
        """Lightweight detect: returns just the type names (back-compat + simple API)."""
        return [s["page_type"] for s in self.suggest_for_drive(drive_root)]

    def suggest_new_pack_version(
        self, drive_root: Path | str, *, min_volume: int = 3, max_proposals: int = 8
    ) -> dict[str, Any]:
        """Full schema evolution flow: diff drive contents vs active pack to propose new page types (e.g. for new high-volume experience observations or graph artifacts).

        Identifies high-volume untyped prefixes (new swarm dirs,
        dream outputs, synthesis artifacts, etc). Proposes new PageTypes.

        Returns rich proposal dict with:
          - untyped_high_volume_prefixes
          - proposals list (with suggested PageType specs)
          - candidate_yaml ready for "schema-pack-evolution" genome serialization
          - candidate_pack_name/version for v0.2 proposal

        This is the core of suggest_new_pack_version helper; genome-izing happens
        at call site (ingest as genome with framework={"kind": "schema-pack-evolution", "candidate_yaml": ...}).
        """
        from collections import Counter
        from pathlib import Path as _Path  # local alias

        root = _Path(drive_root).expanduser() if drive_root else _Path(".")
        if not root.exists():
            return {
                "current_pack": self.get_active().name,
                "proposals": [],
                "reason": "drive_root does not exist",
                "candidate_yaml": "",
            }

        pack = self.get_active()
        covered = set()
        for pt in pack.page_types:
            for pr in pt.path_prefixes:
                covered.add(str(pr).rstrip("/"))

        prefix_counts: Counter[str] = Counter()
        high_untyped: list[str] = []

        # Scan common drive areas for volume (light, bounded)
        candidate_areas = [
            "genomes",
            "dreams",
            "synthesis",
            "knowledge",
            "swarms",
            "captures",
            "notes",
            "schema_packs",
        ]
        try:
            for area in candidate_areas:
                area_path = root / area
                if not area_path.exists() or not area_path.is_dir():
                    continue
                for entry in list(area_path.iterdir())[:30]:  # bounded scan
                    if not entry.is_dir():
                        continue
                    rel = f"{area}/{entry.name}/"
                    # count rough volume (files + subdirs)
                    try:
                        vol = sum(1 for _ in entry.rglob("*") if _.is_file()) + 1
                    except Exception:
                        vol = 1
                    prefix_counts[rel] += vol
                    # Is it covered by current pack?
                    is_covered = any(
                        rel.startswith(cp)
                        or cp.startswith(rel.rstrip("/"))
                        or rel.rstrip("/") in cp
                        for cp in covered
                    )
                    if not is_covered and vol >= min_volume:
                        high_untyped.append(rel)
                        prefix_counts[rel] = vol  # override with accurate
        except Exception:
            pass

        # Also top-level swarm subdirs explicitly (for coordination artifacts)
        swarms_dir = root / "swarms"
        if swarms_dir.exists() and swarms_dir.is_dir():
            try:
                for sdir in list(swarms_dir.iterdir())[:15]:
                    if sdir.is_dir():
                        rel = f"swarms/{sdir.name}/"
                        try:
                            vol = sum(1 for _ in sdir.rglob("*") if _.is_file()) + 2
                        except Exception:
                            vol = 2
                        prefix_counts[rel] += vol
                        is_covered = any(rel.startswith(cp) for cp in covered)
                        if not is_covered and vol >= min_volume:
                            high_untyped.append(rel)
            except Exception:
                pass

        # Dedup + rank high volume untyped
        proposals: list[dict[str, Any]] = []
        seen_names: set[str] = set(pt.name for pt in pack.page_types)
        for pref, vol in prefix_counts.most_common(max_proposals + 5):
            if any(pref.startswith(cp) or cp in pref for cp in covered):
                continue
            base = pref.rstrip("/").replace("/", "-").replace("_", "-")[:50]
            name = base or "untyped-artifact"
            if name in seen_names:
                name = f"{name}-evolved-{len(proposals)}"
            seen_names.add(name)
            primitive = (
                "entity" if any(k in name for k in ("swarm", "schema", "genome")) else "analysis"
            )
            expert = any(k in name for k in ("swarm", "dream", "synthesis", "graph", "calibration"))
            pt_desc = f"Auto-proposed via suggest_new_pack_version. High-volume untyped prefix '{pref}' (est. volume {vol}). Supports schema evolution for experience layer and graph signals."
            pt_dict = {
                "name": name,
                "primitive": primitive,
                "path_prefixes": [pref, pref.rstrip("/")],
                "extractable": True,
                "expert_routing": expert,
                "description": pt_desc,
            }
            proposals.append(
                {
                    "proposed_page_type": name,
                    "prefix": pref,
                    "volume": vol,
                    "page_type": pt_dict,
                }
            )
            if len(proposals) >= max_proposals:
                break

        # Assemble candidate evolved pack
        new_pts = list(pack.page_types)
        for prop in proposals:
            new_pts.append(PageType(**prop["page_type"]))

        candidate = DriveSchemaPack(
            name="agentdrive-drive-pack-v0.2-proposal",
            version="0.2.0",
            page_types=new_pts,
            description=(
                pack.description
                + " | EVOLUTION PROPOSAL generated by schema pack evolution. "
                + f"Includes {len(proposals)} new page types for previously untyped high-volume content."
            ),
        )
        candidate_yaml = candidate.to_yaml()

        return {
            "current_pack": pack.name,
            "current_version": pack.version,
            "drive_root": str(root),
            "untyped_high_volume_prefixes": sorted(set(high_untyped)),
            "proposals": proposals,
            "num_new_types_proposed": len(proposals),
            "candidate_pack_name": candidate.name,
            "candidate_version": candidate.version,
            "candidate_yaml": candidate_yaml,
            "candidate_pack_dict": candidate.to_dict(),
        }


def get_schema_pack_manager() -> SchemaPackManager:
    """Singleton access. All code should prefer this + load_active_pack()."""
    global _manager
    if _manager is None:
        _manager = SchemaPackManager()
    return _manager


def load_active_pack() -> DriveSchemaPack:
    """Runtime resolution of the active pack. Swappable via activate_pack()."""
    return get_schema_pack_manager().get_active()


def activate_pack(name: str) -> DriveSchemaPack:
    """Python (and CLI-friendly) way to switch the active schema pack at runtime."""
    return get_schema_pack_manager().activate(name)


def detect_schema(drive_root: Path | str) -> list[str]:
    """Updated detect that delegates to the manager (uses active pack)."""
    return get_schema_pack_manager().detect_schema(drive_root)


def suggest_page_types(drive_root: Path | str) -> list[dict[str, Any]]:
    """Explicit suggest flow (rich). Use from synthesis, harness, TUI, agents."""
    return get_schema_pack_manager().suggest_for_drive(drive_root)


def review_page_inference(path: str) -> dict[str, Any]:
    """Explicit review flow. Returns full diagnostic dict for a path."""
    return get_schema_pack_manager().review_page_inference(path)


def load_pack_from_yaml(yaml_content: str) -> DriveSchemaPack:
    """Convenience: load a custom pack definition from YAML string (no FS write needed)."""
    return DriveSchemaPack.from_yaml(yaml_content)


def serialize_active_pack_to_yaml() -> str:
    """Export the active pack (e.g. for ingesting the schema definition itself as a genome)."""
    return load_active_pack().to_yaml()


def suggest_new_pack_version(drive_root: Path | str, **kwargs) -> dict[str, Any]:
    """Top-level entrypoint for schema pack evolution flow.
    Delegates to manager. Returns proposal + candidate YAML for genome-izing
    as 'schema-pack-evolution' artifact supporting richer page types for calibration, graph signals, living experience.
    """
    return get_schema_pack_manager().suggest_new_pack_version(drive_root, **kwargs)


# Auto-activate the canonical starter on import (ensures "agentdrive-drive" is live)
get_schema_pack_manager().activate("agentdrive-drive")
