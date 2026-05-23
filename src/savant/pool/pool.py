"""
Savant Pool — The central, living repository for all Agent DNA (Genomes).

This is the "pool" the user described:
- Every agent / run can **push** improved or new Genomes into the pool.
- Any agent can **pull** relevant, high-value DNA from the pool for its current task.
- Improvement proposals flow back into the pool, creating collective evolution.
- The pool maintains provenance, versioning, and quality signals.

The SavantPool is the shared evolutionary memory for the entire ecosystem.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from savant.genome.models import Genome
from savant.registry import GenomeRegistry
from savant.constants import (
    get_swarm_pool_path,
    get_savant_pool_path,
    get_current_swarm_id,
    get_current_subagent_id,
    get_swarms_dir,
    set_current_swarm_id,
    reset_current_swarm_id,
    set_current_subagent_id,
    reset_current_subagent_id,
    using_swarm,
)
from savant.pool.settings import get_effective_pool_settings, PoolSettings, get_pool_settings_manager

logger = logging.getLogger(__name__)


# --- Relevance scoring helpers (use style & logic from savant.reasoning primitives) ---
# _tokens mirrors causality.py for token carry / overlap detection
# _jaccard mirrors patterns.py for intent/field or textual reasoning overlap scoring
def _tokens(text: str) -> set[str]:
    """Tokenization logic aligned with savant.reasoning.causality for consistency in scoring."""
    TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{2,}")
    STOP = {
        "the", "and", "for", "with", "from", "this", "that", "have", "has",
        "was", "were", "are", "but", "not", "into", "out", "all", "any",
        "some", "none", "one", "two", "three", "step", "found", "use", "using",
        "via", "to", "of", "in", "on", "by", "a", "an", "is", "it", "be", "as",
        "get", "set", "do", "make", "new", "old", "high", "low", "data", "run",
    }
    return {
        t.lower()
        for t in TOKEN_RE.findall(text or "")
        if t.lower() not in STOP and len(t) > 2
    }


def _jaccard(a: Any, b: Any) -> float:
    """Jaccard set overlap, identical semantics to savant.reasoning.patterns."""
    sa, sb = set(a or []), set(b or [])
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sa | sb))


@dataclass
class PoolQuery:
    task_description: str = ""
    domains: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    min_score: float = 0.0
    limit: int = 10
    include_reasoning: bool = True


@dataclass
class PoolIngestResult:
    genome_id: str
    accepted: bool
    reason: str
    new_version: Optional[str] = None


class SavantPool:
    """
    The central Savant Pool.

    Persistent on-disk mode:
    - Backed by GenomeRegistry for genome storage/search
    - Maintains a simple append-only JSONL ingest log under ~/.savant/pool/ingest.jsonl  (or per-swarm equivalent)
    - Richer stats (sources, actors, registry integration)
    - First-class CLI service via `savant pool ...`

    Supports full per-swarm and per-subagent isolation:
    - When swarm_id or subagent_id provided (or via current context / SAVANT_*_ID env), uses
      ~/.savant/swarms/<swarm_id>/<subagent_id>/pool/  (starts empty: own genomes/ + ingest)
    - Parent/child sharing governed by user's PoolSettings.sharing_policy (none/read-only/selective/full)
    - Automatic provisioning via SavantSwarmPoolManager + get_default_pool()

    In production this can evolve to DB, but JSONL + registry is robust and simple.
    """

    def __init__(
        self,
        registry: Optional[GenomeRegistry] = None,
        name: str = "main",
        pool_dir: Optional[Path | str] = None,
        swarm_id: Optional[str] = None,
        subagent_id: Optional[str] = None,
    ):
        self.name = name
        self.swarm_id = swarm_id
        self.subagent_id = subagent_id

        # Load user settings for this scope (controls isolation behavior + sharing)
        try:
            self.settings: PoolSettings = get_effective_pool_settings(swarm_id, subagent_id)
        except Exception:
            self.settings = PoolSettings()  # safe default

        self.sharing_policy: str = self.settings.sharing_policy
        self.parent_pool: Optional["SavantPool"] = None

        # Determine pool_dir (scoped or global)
        if swarm_id is not None or subagent_id is not None:
            if pool_dir is None:
                pool_dir = get_swarm_pool_path(swarm_id or "default", subagent_id)
            if name == "main":
                self.name = f"swarm-{swarm_id or 'default'}-{subagent_id or 'root'}"
        if pool_dir is None:
            pool_dir = get_savant_pool_path()
        self.pool_dir = Path(pool_dir)
        self.pool_dir.mkdir(parents=True, exist_ok=True)
        (self.pool_dir / "genomes").mkdir(exist_ok=True)  # ensure for scoped registries
        self.ingest_log_path: Path = self.pool_dir / "ingest.jsonl"

        # Registry: auto-scoped for children (own empty DNA store)
        if registry is None:
            if swarm_id is not None or subagent_id is not None:
                reg_root = self.pool_dir / "genomes"
                self.registry = GenomeRegistry(root=reg_root, swarm_id=swarm_id, subagent_id=subagent_id)
            else:
                self.registry = GenomeRegistry()
        else:
            self.registry = registry

        self._ingest_log: List[Dict[str, Any]] = []
        self._load_ingest_log()

    def _load_ingest_log(self) -> None:
        """Load existing ingest events from the persistent JSONL log (append-only)."""
        self._ingest_log = []
        if not self.ingest_log_path.exists():
            return
        try:
            with open(self.ingest_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self._ingest_log.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue  # skip corrupt lines
        except Exception as exc:
            logger.warning(f"Failed to load ingest log {self.ingest_log_path}: {exc}")
            self._ingest_log = []

    def ingest(self, genome: Genome, source: str = "unknown", actor: Optional[str] = None) -> PoolIngestResult:
        """
        Push a new or improved Genome into the pool.
        The pool validates, versions, and accepts it (or proposes a merge).
        Appends to persistent JSONL ingest log.
        """
        # Basic acceptance policy (can be made much smarter later)
        existing = self.registry.search(query=genome.manifest.id, limit=5)

        accepted = True
        reason = "New genome accepted into pool"

        if existing:
            # Simple policy: accept higher-scoring or new versions (get_latest may not be present yet)
            try:
                if hasattr(self.registry, "get_latest"):
                    latest = self.registry.get_latest(genome.manifest.id)
                    if latest and genome.manifest.evaluation_score.get("reference_tasks", 0) <= latest.manifest.evaluation_score.get("reference_tasks", 0):
                        reason = "Accepted as improvement/fork of existing lineage"
                else:
                    reason = "Accepted as improvement/fork of existing lineage"
            except Exception:
                reason = "Accepted as improvement/fork of existing lineage"

        saved_path = self.registry.save(genome)

        entry: Dict[str, Any] = {
            "timestamp": time.time(),
            "genome_id": genome.genome_id,
            "source": source,
            "actor": actor,
            "path": str(saved_path),
        }
        self._ingest_log.append(entry)

        # Persist to JSONL (append-only, robust)
        try:
            with open(self.ingest_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as exc:
            logger.warning(f"Failed to append to ingest log {self.ingest_log_path}: {exc}")

        # Upward sharing for "full" policy: child contributions can propagate to parent pool
        if self.parent_pool and getattr(self, "sharing_policy", "selective") == "full":
            try:
                self.parent_pool.ingest(
                    genome,
                    source=f"{source} (upward from child swarm={self.swarm_id} sub={self.subagent_id})",
                    actor=actor,
                )
            except Exception as exc:
                logger.warning(f"Failed to upward-share ingest under full policy: {exc}")

        return PoolIngestResult(
            genome_id=genome.genome_id,
            accepted=accepted,
            reason=reason,
            new_version=genome.manifest.version
        )

    def query(self, query: PoolQuery) -> List[Genome]:
        """Pull the most relevant Genomes for a given task or need.

        Enhanced with hybrid scoring (structural applicability + reasoning pattern overlap)
        using primitives from savant.reasoning (Jaccard + tokenization inspired by
        patterns.py and causality.py). Registry search is used for candidate pre-filter,
        followed by re-ranking for smarter retrieval.
        """
        # Broad candidate fetch via existing registry (respects domains/caps/min_score)
        cands = self.registry.search(
            query=query.task_description,
            domains=query.domains,
            capabilities=query.required_capabilities,
            min_score=query.min_score,
            limit=max(100, (query.limit or 10) * 4),
        )
        if not cands and (query.task_description or query.domains):
            # Fallback: load recent genomes for reasoning-based ranking if registry substring was too strict
            try:
                for name in self.registry.list_genomes()[:50]:
                    g = self.registry.load(name)
                    if g:
                        cands.append(g)
            except Exception:
                pass

        # Re-rank with reasoning-enhanced relevance
        scored: List[tuple[float, Genome]] = []
        task_desc = query.task_description or ""
        for g in cands:
            rel = self._compute_relevance(g, task_desc)
            # Apply min_score to the new hybrid relevance if provided (overrides legacy min_score filter somewhat)
            if query.min_score and rel["hybrid"] < query.min_score:
                continue
            scored.append((rel["hybrid"], g))

        scored.sort(key=lambda x: x[0], reverse=True)
        # Dedup by genome_id (registry can surface id/ver and id@ver variants)
        seen_ids: set[str] = set()
        results: List[Genome] = []
        for _, g in scored:
            if g.genome_id not in seen_ids:
                seen_ids.add(g.genome_id)
                results.append(g)
            if len(results) >= (query.limit or 10):
                break

        # --- Swarm sharing: pull from parent pool according to policy (read-only / selective / full) ---
        shared = self._get_shared_genomes(query)
        for g in shared:
            if g.genome_id not in seen_ids:
                seen_ids.add(g.genome_id)
                results.append(g)
            if len(results) >= (query.limit or 10):
                break

        return results

    def get_dna_for_task(self, task: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Cleaner primary API: returns enriched DNA packets with "why this DNA is relevant"
        explanations. Uses the full reasoning-powered relevance engine (structural +
        reasoning overlap + Jaccard pattern matching from savant.reasoning.*).

        This is what the harness (and future orchestrators) should prefer for pulling
        truly useful genomes.
        """
        q = PoolQuery(task_description=task, limit=top_k)
        genomes = self.query(q)
        packets: List[Dict[str, Any]] = []
        for g in genomes:
            rel = self._compute_relevance(g, task)
            packet = {
                "genome_id": g.genome_id,
                "framework": g.framework,
                "top_reasoning": list(g.reasoning_patterns.keys())[:5] if g.reasoning_patterns else [],
                "score": g.manifest.evaluation_score.get("reference_tasks", 0.0),
                # New enriched fields for smarter usage
                "relevance_score": rel["hybrid"],
                "structural_score": rel["structural"],
                "reasoning_score": rel["reasoning"],
                "semantic_score": rel["reasoning"],  # hybrid reasoning overlap acts as semantic proxy
                "why_relevant": rel["why_relevant"],
            }
            packets.append(packet)
        return packets

    def get_relevant_dna(self, task: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Convenience method that returns lightweight "DNA packets" an agent harness can consume.
        Includes key reasoning patterns and framework steps.

        Now delegates to the enhanced get_dna_for_task (reasoning primitives powered)
        so callers automatically benefit from smarter matching without API break.
        Legacy 'score' field preserved for compat.
        """
        return self.get_dna_for_task(task, top_k=top_k)

    # --- Private relevance engine (core of the enhancement) ---
    def _compute_relevance(self, genome: Genome, task: str) -> Dict[str, Any]:
        """Compute hybrid score + human-readable 'why' by inspecting manifest applicability
        + deep content of reasoning_patterns and framework using pattern-matching primitives.

        - structural: domain/problem/capability/id keyword overlap
        - reasoning: Jaccard on tokenized reasoning texts + recognized patterns + framework steps
          (directly using the _jaccard / _tokens modeled after reasoning/patterns + causality)
        """
        task = (task or "").strip()
        task_tokens = _tokens(task)
        task_lower = task.lower()

        # --- Structural score (manifest + applicability) ---
        struct_score = 0.0
        struct_reasons: List[str] = []
        appl = genome.manifest.applicability or {}
        doms = [str(x).lower() for x in (appl.get("domains") or [])]
        sigs = [str(x).lower() for x in (appl.get("problem_signatures") or [])]
        caps = (genome.manifest.dependencies or {}).get("agent_capabilities", []) or []

        # Domain / signature keyword hits
        for d in doms:
            if d and (d in task_lower or any(t in d for t in task_tokens)):
                struct_score += 0.35
                dom_tag = f"domain:{d}"
                if dom_tag not in struct_reasons:
                    struct_reasons.append(dom_tag)
        for s in sigs:
            if any(tok in s for tok in task_tokens) or any(w in task_lower for w in s.split() if len(w) > 3):
                struct_score += 0.25
                struct_reasons.append(f"problem_signature_match")
                break
        for c in caps:
            cl = str(c).lower()
            if any(t in cl for t in task_tokens):
                struct_score += 0.20
                struct_reasons.append(f"capability:{c}")
        # ID / name textual match
        gid = genome.manifest.id.lower()
        if any(len(t) > 3 and t in gid for t in task_tokens):
            struct_score += 0.30
            struct_reasons.append(f"id:{genome.manifest.id}")

        # Legacy eval boost (small)
        eval_vals = [v for v in (genome.manifest.evaluation_score or {}).values() if isinstance(v, (int, float))]
        if eval_vals:
            max_eval = max(eval_vals)
            struct_score += min(0.15, max_eval * 0.15)

        struct_score = min(1.0, struct_score)

        # --- Reasoning overlap score (the key improvement: uses reasoning_patterns content) ---
        reasoning_score = 0.0
        reason_reasons: List[str] = []

        # Collect rich textual content from reasoning_patterns and framework (the DNA "why")
        reasoning_texts = self._collect_reasoning_texts(genome)
        for rt in reasoning_texts[:30]:
            rt_toks = _tokens(rt)
            jo = _jaccard(task_tokens, rt_toks)
            if jo >= 0.12:
                reasoning_score = max(reasoning_score, jo)
                if len(reason_reasons) < 3:
                    snippet = rt[:70].replace("\n", " ")
                    reason_reasons.append(f"reasoning_overlap({jo:.2f}): {snippet}...")

        # Explicit use of pattern matching primitive style on stored patterns_recognized
        pats = (genome.reasoning_patterns or {}).get("patterns_recognized") or []
        for p in pats:
            if not isinstance(p, dict):
                continue
            # support both flat and nested (from PatternMatch etc)
            p_ints = p.get("intents") or (p.get("signature") or {}).get("intents") or []
            p_flds = p.get("fields") or (p.get("signature") or {}).get("fields") or []
            io = _jaccard(list(task_tokens), p_ints)
            fo = _jaccard([], p_flds)
            pscore = 0.75 * io + 0.25 * fo
            if pscore > 0.1 and pscore > reasoning_score:
                reasoning_score = pscore
                fid = p.get("framework_id") or p.get("signature", {}).get("framework_id", "pattern")
                reason_reasons.append(f"pattern_recognized_match({pscore:.2f}): {fid}")

        # Framework step descriptions (playbook alignment) -- treated as reasoning DNA
        fw = genome.framework or {}
        steps = fw.get("steps", []) if isinstance(fw, dict) else []
        for step in (steps or []):
            if isinstance(step, dict):
                for key in ("description", "name", "rationale", "summary"):
                    val = step.get(key)
                    if val:
                        stoks = _tokens(str(val))
                        jo = _jaccard(task_tokens, stoks)
                        if jo >= 0.10:
                            reasoning_score = max(reasoning_score, jo * 0.9)
                            if len(reason_reasons) < 4:
                                reason_reasons.append(f"framework_step: {str(val)[:55]}")
            elif isinstance(step, str):
                stoks = _tokens(step)
                jo = _jaccard(task_tokens, stoks)
                if jo >= 0.10:
                    reasoning_score = max(reasoning_score, jo * 0.8)

        reasoning_score = min(1.0, reasoning_score)

        # --- Hybrid (favor reasoning overlap as requested) ---
        hybrid = 0.30 * struct_score + 0.70 * reasoning_score
        hybrid = min(1.0, hybrid)

        # Build the "why this DNA is relevant" explanation
        why_parts = struct_reasons + reason_reasons
        if not why_parts:
            why_parts = ["keyword match via registry; no strong reasoning pattern or domain overlap found"]
        why = "; ".join(why_parts[:5])

        return {
            "hybrid": round(hybrid, 3),
            "structural": round(struct_score, 3),
            "reasoning": round(reasoning_score, 3),
            "why_relevant": why,
            "eval_score": max(eval_vals) if eval_vals else 0.0,
        }

    def _collect_reasoning_texts(self, genome: Genome) -> List[str]:
        """Flatten all human-readable strings from reasoning_patterns + framework for overlap scoring.
        (Supports the seeded key_heuristics, causal_patterns, trace summaries, etc.)
        """
        texts: List[str] = []
        rp = genome.reasoning_patterns or {}

        def _walk(obj: Any) -> None:
            if isinstance(obj, str):
                if len(obj) > 4:
                    texts.append(obj)
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    _walk(item)
            elif isinstance(obj, dict):
                for v in obj.values():
                    _walk(v)

        _walk(rp)

        # Prioritize known high-value keys in reasoning_patterns (from scanners / seeds)
        for k in ("key_heuristics", "causal_patterns", "contradiction_heuristics", "patterns", "trace", "causality", "anomalies"):
            val = rp.get(k)
            if val:
                _walk(val)
                if isinstance(val, list):
                    texts.extend([str(x) for x in val if isinstance(x, (str, int, float))])

        # Framework content (playbook = part of DNA)
        fw = genome.framework or {}
        if isinstance(fw, dict):
            for k in ("steps", "inputs", "output_schema", "rationale", "description", "display_name"):
                if k in fw:
                    _walk(fw[k])
            # Deep steps
            for s in (fw.get("steps") or []):
                if isinstance(s, dict):
                    for kk in ("description", "name", "rationale"):
                        if s.get(kk):
                            texts.append(str(s[kk]))

        # Also manifest applicability text
        _walk(genome.manifest.applicability or {})
        texts.append(genome.manifest.id or "")
        texts.append(genome.manifest.version or "")

        # Dedup while preserving signal order
        seen: set[str] = set()
        uniq: List[str] = []
        for t in texts:
            t_clean = str(t).strip()
            if t_clean and len(t_clean) > 5 and t_clean not in seen:
                seen.add(t_clean)
                uniq.append(t_clean)
        return uniq

    def propose_improvement(self, genome_id: str, improved_genome: Genome, proposed_by: str) -> PoolIngestResult:
        """Agents or humans propose better versions back into the pool."""
        return self.ingest(improved_genome, source="improvement", actor=proposed_by)

    def get_pool_stats(self) -> Dict[str, Any]:
        """Rich stats combining registry + persistent ingest log."""
        from collections import Counter
        sources = Counter(e.get("source", "unknown") for e in self._ingest_log)
        actors = Counter(e.get("actor") for e in self._ingest_log if e.get("actor"))

        reg_stats: Dict[str, Any] = {}
        try:
            if hasattr(self.registry, "get_registry_stats"):
                reg_stats = self.registry.get_registry_stats()
            else:
                reg_stats = {"count": len(self.registry.list_genomes())}
        except Exception:
            reg_stats = {"count": len(self.registry.list_genomes())}

        return {
            "name": self.name,
            "pool_dir": str(self.pool_dir),
            "ingest_log_path": str(self.ingest_log_path),
            "total_genomes": reg_stats.get("count", len(self.registry.list_genomes())),
            "ingest_events": len(self._ingest_log),
            "last_ingest": self._ingest_log[-1]["timestamp"] if self._ingest_log else None,
            "sources": dict(sources),
            "top_actors": dict(actors.most_common(5)),
            "registry_stats": reg_stats,
        }

    def get_ingest_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent ingest events (newest first) from the persistent on-disk JSONL log."""
        hist = list(reversed(self._ingest_log[-limit:]))
        return hist

    # --- Swarm isolation & sharing support ---

    def _get_shared_genomes(self, query: PoolQuery) -> List[Genome]:
        """Return genomes from parent according to sharing_policy (implements read/selective/full)."""
        if not self.parent_pool or self.sharing_policy == "none":
            return []
        try:
            p_results = self.parent_pool.query(query)
            if self.sharing_policy == "selective":
                # Selective: only reasonably high-value DNA from parent
                filtered = []
                for g in p_results:
                    sc = 0.0
                    if g.manifest and g.manifest.evaluation_score:
                        vals = [v for v in g.manifest.evaluation_score.values() if isinstance(v, (int, float))]
                        sc = max(vals) if vals else 0.0
                    if sc >= 0.4:  # threshold for selective sharing
                        filtered.append(g)
                return filtered[: query.limit or 10]
            # read-only or full: return as-is (parent already ranked)
            return p_results[: query.limit or 10]
        except Exception:
            return []

    def get_genome(self, gid: str) -> Optional[Genome]:
        """Lookup that respects sharing: local first, then parent if policy permits.
        Used by harness for propose/record when DNA came via sharing.
        """
        g = self.registry.get_genome(gid)
        if g is None:
            try:
                g = self.registry.load(gid)
            except Exception:
                g = None
        if g is None and self.parent_pool and self.sharing_policy != "none":
            g = self.parent_pool.get_genome(gid)
        return g

# Global default pool (easy for agents to use) -- the root/parent pool
default_pool: Optional[SavantPool] = None

# Cache for scoped child pools (keyed by (swarm, subagent))
_scoped_pools: Dict[tuple[str, str], SavantPool] = {}

# Singleton manager
_swarm_pool_manager: Optional["SavantSwarmPoolManager"] = None


class SavantSwarmPoolManager:
    """
    Provisions and manages isolated per-swarm / per-subagent Savant Pools.

    Automatically creates the directory structure:
        ~/.savant/swarms/<swarm_id>/<subagent_id>/pool/
          ├── genomes/   (child's private DNA, starts empty)
          └── ingest.jsonl

    When any spawner (Grok's spawn_subagent, Claude, etc.) sets
    SAVANT_SWARM_ID + SAVANT_SUBAGENT_ID (or uses using_swarm() context),
    get_default_pool() + SavantHarness automatically give the child its own pool.

    Sharing policies (from user settings) are honored for parent<->child visibility.
    """

    def __init__(self):
        self._cache: Dict[tuple[str, str], SavantPool] = {}

    def provision(self, swarm_id: str, subagent_id: Optional[str] = None) -> Path:
        """Create the isolated dir tree (idempotent). Returns the pool/ path."""
        p = get_swarm_pool_path(swarm_id, subagent_id)
        p.mkdir(parents=True, exist_ok=True)
        (p / "genomes").mkdir(exist_ok=True)
        return p

    def get_pool(
        self, swarm_id: str, subagent_id: Optional[str] = None, **kwargs: Any
    ) -> SavantPool:
        """Return the child's private pool (creates + wires parent for sharing if new)."""
        key = (swarm_id or "default", subagent_id or "")
        if key in self._cache:
            return self._cache[key]
        self.provision(swarm_id, subagent_id)
        child = SavantPool(
            swarm_id=swarm_id,
            subagent_id=subagent_id,
            name=f"swarm:{swarm_id}/sub:{subagent_id or 'anon'}",
            **kwargs,
        )
        # Wire to global root parent so sharing policies work (query + full-ingest)
        child.parent_pool = get_global_pool()
        self._cache[key] = child
        _scoped_pools[key] = child  # also global cache
        return child


def get_swarm_pool_manager() -> "SavantSwarmPoolManager":
    global _swarm_pool_manager
    if _swarm_pool_manager is None:
        _swarm_pool_manager = SavantSwarmPoolManager()
    return _swarm_pool_manager


def get_global_pool() -> SavantPool:
    """Always returns the root (non-scoped) pool, regardless of current context/env ids."""
    global default_pool
    if default_pool is None:
        default_pool = SavantPool()  # no ids => global path + registry
    return default_pool


def get_default_pool() -> SavantPool:
    """
    Returns the appropriate pool for current context:
    - If SAVANT_SWARM_ID / SAVANT_SUBAGENT_ID (env or using_swarm() context) are set,
      returns (and auto-creates) the isolated per-subagent pool under swarms/.
    - Otherwise the global ~/.savant/pool .
    This makes *every* spawned sub-agent (via Grok build, or any other) get its own
    private persistent empty-starting DNA pool automatically.
    """
    swarm_id = get_current_swarm_id()
    subagent_id = get_current_subagent_id()

    if swarm_id is not None or subagent_id is not None:
        return get_swarm_pool_manager().get_pool(swarm_id or "default", subagent_id)

    return get_global_pool()


# Back-compat: old direct assignment still works for global
# Users / tests that did default_pool = SavantPool() continue to affect global.
