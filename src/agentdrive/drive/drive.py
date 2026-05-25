"""
AgentDrive — The central, living repository for all Agent DNA (Genomes).

This is the "pool" the user described:
- Every agent / run can **push** improved or new Genomes into the Drive.
- Any agent can **pull** relevant, high-value DNA from the Drive for its current task.
- Improvement proposals flow back into the Drive, creating collective evolution.
- The pool maintains provenance, versioning, and quality signals.

The AgentDrive is the shared evolutionary memory for the entire ecosystem.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentdrive.constants import (
    get_current_subagent_id,
    get_current_swarm_id,
    get_default_drive_path,
    get_swarm_drive_path,
)
from agentdrive.drive.settings import (
    DriveSettings,
    get_effective_drive_settings,
)
from agentdrive.events import PoolIngest, emit
from agentdrive.genome.models import Genome
from agentdrive.registry import GenomeRegistry

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from agentdrive.cap import CapStore
    from agentdrive.cap.store import SignedCap


def _m4_disabled() -> bool:
    """Env opt-out for the v2 / M4 CRDT + conflict-copy ingest logic."""
    import os

    return os.environ.get("AGENTDRIVE_M4_DISABLE", "").strip() in {"1", "true", "yes"}


# --- Relevance scoring helpers (use style & logic from agentdrive.reasoning primitives) ---
# _tokens mirrors causality.py for token carry / overlap detection
# _jaccard mirrors patterns.py for intent/field or textual reasoning overlap scoring
def _tokens(text: str) -> set[str]:
    """Tokenization logic aligned with savant.reasoning.causality for consistency in scoring."""
    TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{2,}")
    STOP = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "have",
        "has",
        "was",
        "were",
        "are",
        "but",
        "not",
        "into",
        "out",
        "all",
        "any",
        "some",
        "none",
        "one",
        "two",
        "three",
        "step",
        "found",
        "use",
        "using",
        "via",
        "to",
        "of",
        "in",
        "on",
        "by",
        "a",
        "an",
        "is",
        "it",
        "be",
        "as",
        "get",
        "set",
        "do",
        "make",
        "new",
        "old",
        "high",
        "low",
        "data",
        "run",
    }
    return {t.lower() for t in TOKEN_RE.findall(text or "") if t.lower() not in STOP and len(t) > 2}


def _jaccard(a: Any, b: Any) -> float:
    """Jaccard set overlap, identical semantics to savant.reasoning.patterns."""
    sa, sb = set(a or []), set(b or [])
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sa | sb))


@dataclass
class DriveQuery:
    task_description: str = ""
    domains: list[str] = field(default_factory=list)
    required_capabilities: list[str] = field(default_factory=list)
    min_score: float = 0.0
    limit: int = 10
    include_reasoning: bool = True


@dataclass
class DriveIngestResult:
    genome_id: str
    accepted: bool
    reason: str
    new_version: str | None = None


class AgentDrive:
    """
    The central AgentDrive.

    Persistent on-disk mode:
    - Backed by GenomeRegistry for genome storage/search
    - Maintains a simple append-only JSONL ingest log under ~/.agentdrive/pool/ingest.jsonl  (or per-swarm equivalent)
    - Richer stats (sources, actors, registry integration)
    - First-class CLI service via `savant pool ...`

    Supports full per-swarm and per-subagent isolation:
    - When swarm_id or subagent_id provided (or via current context / SAVANT_*_ID env), uses
      ~/.agentdrive/swarms/<swarm_id>/<subagent_id>/pool/  (starts empty: own genomes/ + ingest)
    - Parent/child sharing governed by user's DriveSettings.sharing_policy (none/read-only/selective/full)
    - Automatic provisioning via SwarmDriveManager + get_default_drive()

    In production this can evolve to DB, but JSONL + registry is robust and simple.
    """

    def __init__(
        self,
        registry: GenomeRegistry | None = None,
        name: str = "main",
        drive_path: Path | str | None = None,
        swarm_id: str | None = None,
        subagent_id: str | None = None,
    ):
        self.name = name
        self.swarm_id = swarm_id
        self.subagent_id = subagent_id

        # Load user settings for this scope (controls isolation behavior + sharing)
        try:
            self.settings: DriveSettings = get_effective_drive_settings(swarm_id, subagent_id)
        except Exception:
            self.settings = DriveSettings()  # safe default

        self.sharing_policy: str = self.settings.sharing_policy
        self.parent_pool: AgentDrive | None = None

        # Determine drive_path (scoped or global)
        if swarm_id is not None or subagent_id is not None:
            if drive_path is None:
                drive_path = get_swarm_drive_path(swarm_id or "default", subagent_id)
            if name == "main":
                self.name = f"swarm-{swarm_id or 'default'}-{subagent_id or 'root'}"
        if drive_path is None:
            drive_path = get_default_drive_path()
        self.drive_path = Path(drive_path)
        self.drive_path.mkdir(parents=True, exist_ok=True)
        (self.drive_path / "genomes").mkdir(exist_ok=True)  # ensure for scoped registries
        self.ingest_log_path: Path = self.drive_path / "ingest.jsonl"

        # Registry: auto-scoped for children (own empty DNA store)
        if registry is None:
            if swarm_id is not None or subagent_id is not None:
                reg_root = self.drive_path / "genomes"
                self.registry = GenomeRegistry(
                    root=reg_root, swarm_id=swarm_id, subagent_id=subagent_id
                )
            else:
                self.registry = GenomeRegistry()
        else:
            self.registry = registry

        # v2 / Milestone 1: every Drive has a content-addressed object store
        # sitting beside its registry. Genomes that pass ingest are also written
        # here, keyed by sha256 of canonical content. This is what unlocks dedup,
        # cryptographic provenance, and the v2 supersedes-DAG.
        from agentdrive.drive.content_store import ContentStore  # local: avoid import cycle

        self.content_store = ContentStore(self.drive_path)

        self._ingest_log: list[dict[str, Any]] = []
        self._load_ingest_log()

    def _load_ingest_log(self) -> None:
        """Load existing ingest events from the persistent JSONL log (append-only)."""
        self._ingest_log = []
        if not self.ingest_log_path.exists():
            return
        try:
            with open(self.ingest_log_path, encoding="utf-8") as f:
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

    # ── v2 / M4: CRDT merge + conflict-copy resolution ───────────────────────
    def _apply_m4_merge_or_conflict(
        self,
        incoming: Genome,
        actor: str | None,
    ) -> tuple[Genome, str | None]:
        """Reconcile an incoming write against any existing same-id Genome.

        Returns ``(genome_to_save, event)`` where ``event`` is one of:

        - ``None`` — no collision, normal write
        - ``"crdt-merge"`` — strategies matched, state was merged into the latest
        - ``"conflict-copy"`` — last-write collision with different content; the
          returned genome is a conflict copy and the original is left untouched
        """
        from agentdrive.drive.conflict import emit_conflict_genome
        from agentdrive.drive.crdt import merge_counters, merge_sets

        try:
            latest = self.registry.load(incoming.manifest.id)
        except Exception:
            latest = None
        if latest is None:
            return incoming, None

        strategy = incoming.manifest.merge_strategy
        latest_strategy = latest.manifest.merge_strategy

        if strategy in ("crdt-counter", "crdt-set") and strategy == latest_strategy:
            merged = incoming.model_copy(deep=True)
            existing_state = latest.manifest.crdt_state or {}
            incoming_state = incoming.manifest.crdt_state or {}
            if strategy == "crdt-counter":
                merged.manifest.crdt_state = merge_counters(existing_state, incoming_state)
            else:
                members = merge_sets(
                    existing_state.get("members", []),
                    incoming_state.get("members", []),
                )
                merged.manifest.crdt_state = {"members": members}
            # Supersedes chain names both parents so the merge is auditable.
            parents = [latest.manifest.content_hash]
            for h in incoming.manifest.supersedes:
                if h and h not in parents:
                    parents.append(h)
            merged.manifest.supersedes = parents
            merged.manifest.content_hash = "sha256:pending"
            merged.finalize(update_timestamp=False)
            from agentdrive.genome.models import Genome  # avoid module-level cycle

            return Genome.model_validate(merged.model_dump()), "crdt-merge"

        if strategy == "last-write" and latest_strategy == "last-write":
            if latest.manifest.content_hash and (
                latest.manifest.content_hash == incoming.manifest.content_hash
            ):
                return incoming, None  # exact dedup, not a conflict
            vector = {actor or "unknown": int(time.time() * 1000)}
            conflict = emit_conflict_genome(latest, incoming, vector)
            return conflict, "conflict-copy"

        # Mixed-strategy or unsupported combinations fall through to normal write
        # so back-compat is preserved.
        return incoming, None

    def ingest(
        self,
        genome: Genome,
        source: str = "unknown",
        actor: str | None = None,
        subagent_id: str | None = None,
    ) -> DriveIngestResult:
        """Push a new or improved Genome into the Drive.

        The Drive validates, versions, accepts (or proposes a merge), and
        appends to the persistent JSONL ingest log.

        v2 / Milestone 2a: ``subagent_id`` namespaces the write inside a
        shared swarm Drive. When set, the Genome's author list is stamped
        with an agent entry ``id="sub:<subagent_id>"`` so siblings can
        filter / attribute / score each other's contributions. Pass the
        sub-agent ID once at ingest time; the rest of the Drive layer
        treats it as opaque provenance metadata.
        """
        # v2 / M2a: auto-stamp sub-agent author tag for shared-Drive namespacing.
        if subagent_id:
            from agentdrive.genome.models import GenomeAuthor

            tag = f"sub:{subagent_id}"
            if not any(getattr(a, "id", None) == tag for a in (genome.manifest.authors or [])):
                genome.manifest.authors.append(GenomeAuthor(type="agent", id=tag, name=tag))

        # v2 / M4: CRDT merge or conflict-copy emission before the write. May
        # mutate `genome` (crdt merge) or replace it with a conflict copy. The
        # resulting `genome` is what we register, content-address, and log.
        m4_event: str | None = None
        if not _m4_disabled():
            genome, m4_event = self._apply_m4_merge_or_conflict(genome, actor=actor)

        # Basic acceptance policy (can be made much smarter later)
        existing = self.registry.search(query=genome.manifest.id, limit=5)

        accepted = True
        reason = "New genome accepted into pool"

        if existing:
            # Simple policy: accept higher-scoring or new versions (get_latest may not be present yet)
            try:
                if hasattr(self.registry, "get_latest"):
                    latest = self.registry.get_latest(genome.manifest.id)
                    if latest and genome.manifest.evaluation_score.get(
                        "reference_tasks", 0
                    ) <= latest.manifest.evaluation_score.get("reference_tasks", 0):
                        reason = "Accepted as improvement/fork of existing lineage"
                else:
                    reason = "Accepted as improvement/fork of existing lineage"
            except Exception:
                reason = "Accepted as improvement/fork of existing lineage"

        saved_path = self.registry.save(genome)

        # v2 / Milestone 1: also write to the content-addressed store. Dedup is
        # free (second write of the same bytes is a no-op). The content hash is
        # what later milestones (caps, supersedes-DAG, peer sync) key off.
        put = self.content_store.put_genome(genome)

        entry: dict[str, Any] = {
            "timestamp": time.time(),
            "genome_id": genome.genome_id,
            "source": source if not m4_event else f"{source} ({m4_event})",
            "actor": actor,
            "path": str(saved_path),
            "content_hash": put.hash,
            "deduped": put.existed,
            "subagent_id": subagent_id,
            "m4_event": m4_event,
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

        # Emit PoolIngest so subscribers (chat ribbon) see new DNA land.
        try:
            import os

            actor_str = actor if actor is not None else os.environ.get("USER", "unknown")
            emit(
                PoolIngest(
                    genome_id=genome.genome_id,
                    source=source or "unknown",
                    actor=actor_str,
                    swarm_id=self.swarm_id,
                    subagent_id=self.subagent_id,
                )
            )
        except Exception:
            logger.debug("Failed to emit PoolIngest", exc_info=True)

        return DriveIngestResult(
            genome_id=genome.genome_id,
            accepted=accepted,
            reason=reason,
            new_version=genome.manifest.version,
        )

    def query(self, query: DriveQuery) -> list[Genome]:
        """Pull the most relevant Genomes for a given task or need.

        Enhanced with hybrid scoring (structural applicability + reasoning pattern overlap)
        using primitives from agentdrive.reasoning (Jaccard + tokenization inspired by
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
        scored: list[tuple[float, Genome]] = []
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
        results: list[Genome] = []
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

    # --- Capability-gated boundary helpers ---

    def capability_resource(self) -> tuple[str, str]:
        """Return the capability resource selector for this Drive.

        Existing callers still use ``ingest`` / ``query`` directly. New
        external boundaries should route through ``authorized_ingest`` and
        ``authorized_query`` so the same capability resolver protects Drive
        access without changing the legacy in-process API in one large break.
        """
        if self.swarm_id:
            return ("swarm", self.swarm_id)
        if self.subagent_id:
            return ("agent", self.subagent_id)
        return ("default", self.name or "main")

    def verify_capability(
        self,
        cap_store: "CapStore",
        cap: "SignedCap",
        *,
        action: str,
        resource_kind: str | None = None,
        resource_id: str | None = None,
        attenuations: tuple[tuple[str, str], ...] = (),
    ) -> None:
        """Verify that ``cap`` authorizes an operation against this Drive."""
        from agentdrive.cap import CapVerifyContext

        default_kind, default_id = self.capability_resource()
        ctx = CapVerifyContext(
            scheme="drive",
            action=action,
            resource_kind=resource_kind or default_kind,
            resource_id=resource_id or default_id,
            attenuations=tuple(sorted(attenuations)),
        )
        cap_store.verify_request(cap, ctx)

    def authorized_ingest(
        self,
        cap_store: "CapStore",
        cap: "SignedCap",
        genome: Genome,
        source: str = "unknown",
        actor: str | None = None,
        subagent_id: str | None = None,
    ) -> DriveIngestResult:
        """Capability-checked wrapper for the write boundary."""
        attenuations = (("sub", subagent_id),) if subagent_id else ()
        self.verify_capability(cap_store, cap, action="write", attenuations=attenuations)
        return self.ingest(genome, source=source, actor=actor, subagent_id=subagent_id)

    def authorized_query(
        self,
        cap_store: "CapStore",
        cap: "SignedCap",
        query: DriveQuery,
    ) -> list[Genome]:
        """Capability-checked wrapper for the read boundary."""
        attenuations: list[tuple[str, str]] = []
        if query.min_score:
            attenuations.append(("min_eval", str(query.min_score)))
        self.verify_capability(
            cap_store,
            cap,
            action="read",
            attenuations=tuple(attenuations),
        )
        return self.query(query)

    def get_dna_for_task(self, task: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        Cleaner primary API: returns enriched DNA packets with "why this DNA is relevant"
        explanations. Uses the full reasoning-powered relevance engine (structural +
        reasoning overlap + Jaccard pattern matching from agentdrive.reasoning.*).

        This is what the harness (and future orchestrators) should prefer for pulling
        truly useful genomes.
        """
        q = DriveQuery(task_description=task, limit=top_k)
        genomes = self.query(q)
        packets: list[dict[str, Any]] = []
        for g in genomes:
            rel = self._compute_relevance(g, task)
            packet = {
                "genome_id": g.genome_id,
                "framework": g.framework,
                "top_reasoning": list(g.reasoning_patterns.keys())[:5]
                if g.reasoning_patterns
                else [],
                "score": g.manifest.evaluation_score.get("reference_tasks", 0.0),
                # New enriched fields for smarter usage
                "relevance_score": rel["hybrid"],
                "structural_score": rel["structural"],
                "reasoning_score": rel["reasoning"],
                "semantic_score": rel[
                    "reasoning"
                ],  # hybrid reasoning overlap acts as semantic proxy
                "why_relevant": rel["why_relevant"],
            }
            packets.append(packet)
        return packets

    def get_relevant_dna(self, task: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        Convenience method that returns lightweight "DNA packets" an agent harness can consume.
        Includes key reasoning patterns and framework steps.

        Now delegates to the enhanced get_dna_for_task (reasoning primitives powered)
        so callers automatically benefit from smarter matching without API break.
        Legacy 'score' field preserved for compat.
        """
        return self.get_dna_for_task(task, top_k=top_k)

    # --- Private relevance engine (core of the enhancement) ---
    def _compute_relevance(self, genome: Genome, task: str) -> dict[str, Any]:
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
        struct_reasons: list[str] = []
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
            if any(tok in s for tok in task_tokens) or any(
                w in task_lower for w in s.split() if len(w) > 3
            ):
                struct_score += 0.25
                struct_reasons.append("problem_signature_match")
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
        eval_vals = [
            v
            for v in (genome.manifest.evaluation_score or {}).values()
            if isinstance(v, (int, float))
        ]
        if eval_vals:
            max_eval = max(eval_vals)
            struct_score += min(0.15, max_eval * 0.15)

        struct_score = min(1.0, struct_score)

        # --- Reasoning overlap score (the key improvement: uses reasoning_patterns content) ---
        reasoning_score = 0.0
        reason_reasons: list[str] = []

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
        for step in steps or []:
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
            why_parts = [
                "keyword match via registry; no strong reasoning pattern or domain overlap found"
            ]
        why = "; ".join(why_parts[:5])

        return {
            "hybrid": round(hybrid, 3),
            "structural": round(struct_score, 3),
            "reasoning": round(reasoning_score, 3),
            "why_relevant": why,
            "eval_score": max(eval_vals) if eval_vals else 0.0,
        }

    def _collect_reasoning_texts(self, genome: Genome) -> list[str]:
        """Flatten all human-readable strings from reasoning_patterns + framework for overlap scoring.
        (Supports the seeded key_heuristics, causal_patterns, trace summaries, etc.)
        """
        texts: list[str] = []
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
        for k in (
            "key_heuristics",
            "causal_patterns",
            "contradiction_heuristics",
            "patterns",
            "trace",
            "causality",
            "anomalies",
        ):
            val = rp.get(k)
            if val:
                _walk(val)
                if isinstance(val, list):
                    texts.extend([str(x) for x in val if isinstance(x, (str, int, float))])

        # Framework content (playbook = part of DNA)
        fw = genome.framework or {}
        if isinstance(fw, dict):
            for k in (
                "steps",
                "inputs",
                "output_schema",
                "rationale",
                "description",
                "display_name",
            ):
                if k in fw:
                    _walk(fw[k])
            # Deep steps
            for s in fw.get("steps") or []:
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
        uniq: list[str] = []
        for t in texts:
            t_clean = str(t).strip()
            if t_clean and len(t_clean) > 5 and t_clean not in seen:
                seen.add(t_clean)
                uniq.append(t_clean)
        return uniq

    def propose_improvement(
        self, genome_id: str, improved_genome: Genome, proposed_by: str
    ) -> DriveIngestResult:
        """Agents or humans propose better versions back into the Drive."""
        return self.ingest(improved_genome, source="improvement", actor=proposed_by)

    def get_pool_stats(self) -> dict[str, Any]:
        """Rich stats combining registry + persistent ingest log."""
        from collections import Counter

        sources = Counter(e.get("source", "unknown") for e in self._ingest_log)
        actors = Counter(e.get("actor") for e in self._ingest_log if e.get("actor"))

        reg_stats: dict[str, Any] = {}
        try:
            if hasattr(self.registry, "get_registry_stats"):
                reg_stats = self.registry.get_registry_stats()
            else:
                reg_stats = {"count": len(self.registry.list_genomes())}
        except Exception:
            reg_stats = {"count": len(self.registry.list_genomes())}

        return {
            "name": self.name,
            "drive_path": str(self.drive_path),
            "ingest_log_path": str(self.ingest_log_path),
            "total_genomes": reg_stats.get("count", len(self.registry.list_genomes())),
            "ingest_events": len(self._ingest_log),
            "last_ingest": self._ingest_log[-1]["timestamp"] if self._ingest_log else None,
            "sources": dict(sources),
            "top_actors": dict(actors.most_common(5)),
            "registry_stats": reg_stats,
        }

    def get_ingest_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent ingest events (newest first) from the persistent on-disk JSONL log."""
        hist = list(reversed(self._ingest_log[-limit:]))
        return hist

    # --- Swarm isolation & sharing support ---

    def _get_shared_genomes(self, query: DriveQuery) -> list[Genome]:
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
                        vals = [
                            v
                            for v in g.manifest.evaluation_score.values()
                            if isinstance(v, (int, float))
                        ]
                        sc = max(vals) if vals else 0.0
                    if sc >= 0.4:  # threshold for selective sharing
                        filtered.append(g)
                return filtered[: query.limit or 10]
            # read-only or full: return as-is (parent already ranked)
            return p_results[: query.limit or 10]
        except Exception:
            return []

    def get_genome(self, gid: str) -> Genome | None:
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

    # ── v2 / Milestone 2a: sibling attribution in a shared swarm Drive ──────
    def writers(self) -> list[str]:
        """All sub-agent IDs that have ever written to this Drive.
        Returns short IDs (without the ``sub:`` prefix). Used by
        sibling-learning queries — 'show me what cousin-B wrote' becomes
        a filter on this set.
        """
        seen: set[str] = set()
        for entry in self._ingest_log:
            sid = entry.get("subagent_id")
            if sid:
                seen.add(sid)
        return sorted(seen)

    def genomes_by_subagent(self, subagent_id: str) -> list[dict[str, Any]]:
        """Return ingest-log entries whose author was a given sub-agent.
        Filters the in-memory ingest log. For semantically-scored sibling
        retrieval, layer this over the normal query path with an author
        filter applied at re-ranking time.
        """
        return [e for e in self._ingest_log if e.get("subagent_id") == subagent_id]

    # ── v2 / Milestone 1: content-address lookup ────────────────────────────
    def has_content(self, content_hash: str) -> bool:
        """True iff this Drive holds the object addressed by ``content_hash``.
        Cheap path-existence check; does not load the object.
        """
        return self.content_store.has(content_hash)

    def get_content(self, content_hash: str) -> dict[str, Any] | None:
        """Return the stored canonical payload for ``content_hash``, or None.
        This is the raw object — wrap in ``Genome`` reconstruction if you need
        the full manifest (manifest is observation metadata, not in the object).
        """
        return self.content_store.get_payload(content_hash)

    def content_count(self) -> int:
        """Number of unique content-addressed objects in this Drive.
        Will diverge from ingest-log length once dedup hits start landing —
        that gap IS the dedup signal.
        """
        return self.content_store.count()


# Global default pool (easy for agents to use) -- the root/parent pool
default_pool: AgentDrive | None = None

# Cache for scoped child pools (keyed by (swarm, subagent))
_scoped_pools: dict[tuple[str, str], AgentDrive] = {}

# Singleton manager
_swarm_pool_manager: SwarmDriveManager | None = None


class SwarmDriveManager:
    """
    Provisions and manages isolated per-swarm / per-subagent AgentDrives.

    Automatically creates the directory structure:
        ~/.agentdrive/swarms/<swarm_id>/<subagent_id>/pool/
          ├── genomes/   (child's private DNA, starts empty)
          └── ingest.jsonl

    When any spawner (Grok's spawn_subagent, Claude, etc.) sets
    AGENTDRIVE_SWARM_ID + AGENTDRIVE_SUBAGENT_ID (or uses using_swarm() context),
    get_default_drive() + Harness automatically give the child its own pool.

    Sharing policies (from user settings) are honored for parent<->child visibility.
    """

    def __init__(self):
        self._cache: dict[tuple[str, str], AgentDrive] = {}

    def provision(self, swarm_id: str, subagent_id: str | None = None) -> Path:
        """Create the isolated dir tree (idempotent). Returns the Drive/ path."""
        p = get_swarm_drive_path(swarm_id, subagent_id)
        p.mkdir(parents=True, exist_ok=True)
        (p / "genomes").mkdir(exist_ok=True)
        return p

    def get_pool(self, swarm_id: str, subagent_id: str | None = None, **kwargs: Any) -> AgentDrive:
        """Return the child's private pool (creates + wires parent for sharing if new)."""
        key = (swarm_id or "default", subagent_id or "")
        if key in self._cache:
            return self._cache[key]
        self.provision(swarm_id, subagent_id)
        child = AgentDrive(
            swarm_id=swarm_id,
            subagent_id=subagent_id,
            name=f"swarm:{swarm_id}/sub:{subagent_id or 'anon'}",
            **kwargs,
        )
        # Wire to global root parent so sharing policies work (query + full-ingest)
        child.parent_pool = get_global_drive()
        self._cache[key] = child
        _scoped_pools[key] = child  # also global cache
        return child


def get_swarm_drive_manager() -> SwarmDriveManager:
    global _swarm_pool_manager
    if _swarm_pool_manager is None:
        _swarm_pool_manager = SwarmDriveManager()
    return _swarm_pool_manager


def get_global_drive() -> AgentDrive:
    """Always returns the root (non-scoped) pool, regardless of current context/env ids."""
    global default_pool
    if default_pool is None:
        default_pool = AgentDrive()  # no ids => global path + registry
    return default_pool


def get_default_drive() -> AgentDrive:
    """
    Returns the appropriate pool for current context:
    - If AGENTDRIVE_SWARM_ID / AGENTDRIVE_SUBAGENT_ID (env or using_swarm() context) are set,
      returns (and auto-creates) the isolated per-subagent pool under swarms/.
    - Otherwise the global ~/.agentdrive/pool .
    This makes *every* spawned sub-agent (via Grok build, or any other) get its own
    private persistent empty-starting DNA pool automatically.
    """
    swarm_id = get_current_swarm_id()
    subagent_id = get_current_subagent_id()

    if swarm_id is not None or subagent_id is not None:
        return get_swarm_drive_manager().get_pool(swarm_id or "default", subagent_id)

    return get_global_drive()


# Back-compat: old direct assignment still works for global
# Users / tests that did default_pool = AgentDrive() continue to affect global.
