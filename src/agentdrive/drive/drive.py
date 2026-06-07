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
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentdrive.constants import (
    get_correlation_id,
    get_current_subagent_id,
    get_current_swarm_id,
    get_default_drive_path,
    get_swarm_drive_path,
    new_correlation_id,
)
from agentdrive.drive.retrieval import fuse_scored_with_rrf
from agentdrive.drive.settings import (
    DriveSettings,
    get_effective_drive_settings,
)
from agentdrive.events import HealingSignalEvent, PoolIngest, emit
from agentdrive.exceptions import (
    AgentDriveConfigError,
    AgentDriveDriveError,
    AgentDriveRegistryError,
)
from agentdrive.genome.models import Genome
from agentdrive.registry import GenomeRegistry

# Role-specialized graph + experience layer integration: richer hybrid retrieval
# Coordinates with graph signal integration (compute_graph_signals, fuse_*), schema page-type inference, and synthesis (think paths)
try:
    from agentdrive.knowledge_graph.graph import (
        compute_graph_signals,
        fuse_graph_signals_into_scores,
        get_knowledge_graph_for_swarm,
    )
    from agentdrive.schema_packs import load_active_pack
except Exception:
    get_knowledge_graph_for_swarm = None  # graceful
    compute_graph_signals = None
    fuse_graph_signals_into_scores = None
    load_active_pack = None

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from agentdrive.cap import CapStore
    from agentdrive.cap.store import SignedCap


def _m4_disabled() -> bool:
    """Env opt-out for the v2 / M4 CRDT + conflict-copy ingest logic."""
    return os.environ.get("AGENTDRIVE_M4_DISABLE", "").strip() in {"1", "true", "yes"}


# --- Relevance scoring helpers (use style & logic from agentdrive.reasoning primitives) ---
# _tokens mirrors causality.py for token carry / overlap detection
# _jaccard mirrors patterns.py for intent/field or textual reasoning overlap scoring
def _tokens(text: str) -> set[str]:
    """Tokenization logic aligned with agentdrive.reasoning.causality for consistency in scoring."""
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
    """Jaccard set overlap, identical semantics to agentdrive.reasoning.patterns."""
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
    - First-class CLI service via `agentdrive pool ...`

    Supports full per-swarm and per-subagent isolation:
    - When swarm_id or subagent_id provided (or via current context / AGENTDRIVE_*_ID env), uses
      ~/.agentdrive/swarms/<swarm_id>/<subagent_id>/pool/  (starts empty: own genomes/ + ingest)
    - Parent/child sharing governed by user's DriveSettings.sharing_policy (none/read-only/selective/full)
    - Automatic provisioning via SwarmDriveManager + get_default_drive()

    In production this can evolve to DB, but JSONL + registry is robust and simple.

    First-run self-healing (via drive/bootstrap.py): on __init__ we now guarantee
    for role-swarm users who self-host their AgentDrive instances that new
    instances start coherent, the experience layer (v3 living-experience seed
    observation + genome) is present from first think, and defensive healing
    runs for production reliability — even before onboarding completes.
    """

    def __init__(
        self,
        registry: GenomeRegistry | None = None,
        name: str = "main",
        drive_path: Path | str | None = None,
        swarm_id: str | None = None,
        subagent_id: str | None = None,
        schema_pack: Any | None = None,  # DriveSchemaPack (lazy to avoid cycles at import time)
        auto_seed: bool = True,
    ):
        # Production tracing: ensure we have a correlation ID for this Drive instance
        from agentdrive.constants import get_correlation_id, new_correlation_id

        if not get_correlation_id():
            new_correlation_id()
        self.name = name
        self.swarm_id = swarm_id
        self.subagent_id = subagent_id
        self._auto_seed = auto_seed

        # Load user settings for this scope (controls isolation behavior + sharing)
        try:
            self.settings: DriveSettings = get_effective_drive_settings(swarm_id, subagent_id)
        except AgentDriveConfigError as e:
            logger.warning(
                f"Drive settings load failed for swarm={swarm_id}: {e}. Using safe defaults."
            )
            self.settings = DriveSettings()
        except Exception:
            logger.exception("Unexpected error loading DriveSettings — falling back to defaults")
            self.settings = DriveSettings()

        self.sharing_policy: str = self.settings.sharing_policy
        self.parent_pool: AgentDrive | None = None

        # Ensure base AgentDrive home (config, logs, drive root, swarms) exists
        # defensively even if called before any onboarding / cli setup. This
        # makes first-run and empty-drive scenarios robust.
        try:
            from agentdrive.config import ensure_agentdrive_home

            ensure_agentdrive_home()
        except Exception:
            # Non-fatal; our per-drive mkdirs below will still attempt creation.
            pass

        # Determine drive_path (scoped or global)
        if swarm_id is not None or subagent_id is not None:
            if drive_path is None:
                drive_path = get_swarm_drive_path(swarm_id or "default", subagent_id)
            if name == "main":
                self.name = f"swarm-{swarm_id or 'default'}-{subagent_id or 'root'}"
        if drive_path is None:
            drive_path = get_default_drive_path()
        # ``os.path.realpath`` is CodeQL's documented sanitizer for
        # ``py/path-injection``. Collapses symlink escapes AND breaks the
        # taint flow established by get_swarm_drive_path(swarm_id).
        self.drive_path = Path(os.path.realpath(os.fspath(drive_path)))

        # Defensive self-healing initialization for missing / corrupted structures.
        # Expanded first-run healing (Self-Healing First-Run & Experience Seed Operator):
        # Ensures clear directory structure, minimal KG index bootstrap, experience
        # layer v3 seed genome + observation (living-experience page type), basic
        # reconciliation state, and trust self-identity placeholder.
        #
        # This guarantees that for role-swarm users who self-host their AgentDrive:
        #   - new instances start coherent
        #   - experience layer present from first think
        #   - defensive healing for production reliability
        # All before full onboarding or any user genomes.
        try:
            self.drive_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise AgentDriveDriveError(
                f"Cannot create Drive directory at {self.drive_path}: {e}. "
                "Check that AGENTDRIVE_HOME (or the provided drive_path) is writable. "
                "For new installs: run `agentdrive doctor` or `agentdrive reconcile seed-experience-v3`."
            ) from e

        for sub in ("genomes", "objects"):
            try:
                (self.drive_path / sub).mkdir(exist_ok=True)
            except Exception:
                pass

        self.ingest_log_path: Path = self.drive_path / "ingest.jsonl"

        # Recover if ingest log is corrupted structure (e.g. a dir instead of file)
        # on weird first-run or partial failure states.
        try:
            if self.ingest_log_path.exists() and not self.ingest_log_path.is_file():
                bak = self.ingest_log_path.with_suffix(".corrupt.bak")
                self.ingest_log_path.rename(bak)
            if not self.ingest_log_path.exists():
                self.ingest_log_path.touch(exist_ok=True)
        except Exception:
            # best effort; _load will handle absence
            pass

        # Delegate to the dedicated bootstrap helper (new drive/bootstrap.py).
        # This performs the full expanded self-healing for experience layer v3 etc.
        # Old private method is now an alias that forwards here for compatibility.
        #
        # ``auto_seed=False`` lets library embedders (and tests that need a
        # genuinely empty drive to exercise delta/reconciliation logic) construct
        # a Drive without the first-run experience-layer seed being written to
        # disk as a construction side effect. The CLI / onboarding / setup paths
        # keep the default (True) so self-hosted users still start coherent.
        if self._auto_seed:
            try:
                from .bootstrap import ensure_experience_layer_seed

                ensure_experience_layer_seed(self.drive_path, self.swarm_id)
            except Exception as exc:
                logger.debug(
                    f"Non-fatal bootstrap ensure failed (first-run healing best-effort): {exc}"
                )

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

        # Schema pack integration: activate + runtime page type inference
        # for raw drive content alongside genomes. Complements the Genome system with experience layer and hybrid fusion support.
        if schema_pack is not None:
            self.schema_pack = schema_pack
        else:
            try:
                from agentdrive.schema_packs import load_active_pack

                self.schema_pack = load_active_pack()
            except Exception:
                self.schema_pack = None  # graceful degrade

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

    def _ensure_experience_layer_seed(self) -> None:
        """Deprecated internal bridge.

        Delegates to the strengthened public ensure_experience_layer_seed in
        drive/bootstrap.py (Self-Healing First-Run & Experience Seed Operator).

        Maintains full backward compatibility for any legacy direct calls while
        delivering the expanded v3 living-experience seed, KG bootstrap,
        reconciliation state, and trust placeholder.

        For role-swarm self-host AgentDrive users: new instances start coherent;
        experience layer present from first think; defensive healing for
        production reliability.
        """
        try:
            from .bootstrap import ensure_experience_layer_seed as _bootstrap_ensure

            _bootstrap_ensure(self.drive_path, getattr(self, "swarm_id", None))
        except Exception as exc:
            logger.debug(f"Legacy _ensure bridge non-fatal: {exc}")

    # ── v2 / M6: promotion gate for upward ingest ────────────────────────────
    def _promote_to_parent(
        self,
        genome: Genome,
        *,
        source: str,
        actor: str | None,
    ) -> None:
        """Route an upward write through the promotion service when policy demands it.

        Falls back to the legacy direct ingest when the parent has no policy
        attached or ``promotion_required`` is False — that preserves every
        existing call site even before consumers know about promotions.
        """
        from agentdrive.drive.swarm_policy import SwarmDrivePolicy
        from agentdrive.promotion import PromotionPolicy, PromotionService

        parent = self.parent_pool
        assert parent is not None  # guarded by the caller

        swarm_policy = getattr(parent, "swarm_policy", None) or SwarmDrivePolicy()
        promotion_policy = PromotionPolicy(
            promotion_required=getattr(swarm_policy, "promotion_required", True),
            auto_approve_from=getattr(swarm_policy, "auto_approve_from", "self"),
        )

        if not promotion_policy.promotion_required:
            parent.ingest(
                genome,
                source=f"{source} (upward from child swarm={self.swarm_id} sub={self.subagent_id})",
                actor=actor,
            )
            return

        service = PromotionService(parent.drive_path)
        # Exercise schema methods on promotion path (Phase 2 gap close)
        try:
            _ = self.get_active_schema_pack()
            _ = self.infer_page_type(f"promotions/{genome.genome_id}")
        except Exception as e:
            logger.debug(f"Schema inference during promotion failed (non-fatal): {e}")
        proposer = actor or self.subagent_id or "self"
        proposal = service.propose(
            genome_content_hash=genome.manifest.content_hash,
            target_tier="swarm",
            author=proposer,
            target_swarm=getattr(parent, "swarm_id", None),
            rationale=f"upward from child swarm={self.swarm_id} sub={self.subagent_id}",
        )
        # Self-originated proposals on this Drive count as "self" for the
        # auto-approve rule. Trusted-peer evaluation lives outside this hook
        # (the caller is the proposer; trust circle is per-device).
        if promotion_policy.should_auto_approve(proposer_is_self=True, proposer_is_trusted=False):
            service.review(
                proposal.proposal_id,
                decision="approve",
                reviewer=f"auto:{proposer}",
                rationale="auto-approve: auto_approve_from='self'",
            )
            parent.ingest(
                genome,
                source=f"{source} (promoted upward, proposal={proposal.proposal_id[:12]})",
                actor=actor,
            )
        # else: proposal stays pending; ``PromotionService.list_pending`` surfaces it.

    # ── v2 / M4: CRDT merge + conflict-copy resolution ───────────────────────
    _M4_INTENTIONAL_SUPERSESSION_SOURCES = (
        "improvement",
        "evolution",
        "promotion",
        "ultimate",
        "promoted",
    )

    def _apply_m4_merge_or_conflict(
        self,
        incoming: Genome,
        actor: str | None,
        source: str = "",
    ) -> tuple[Genome, str | None]:
        """Reconcile an incoming write against any existing same-id Genome.

        Returns ``(genome_to_save, event)`` where ``event`` is one of:

        - ``None`` — no collision, normal write
        - ``"crdt-merge"`` — strategies matched, state was merged into the latest
        - ``"conflict-copy"`` — last-write collision with different content; the
          returned genome is a conflict copy and the original is left untouched

        Conflict-copy is suppressed when the write declares itself an
        intentional supersession — either via a known source label
        (``improvement``, ``evolution``, ``promotion``, …) or by listing the
        existing content hash in ``manifest.supersedes``. Those paths are
        legitimate version progression, not sibling races.
        """
        from agentdrive.drive.conflict import emit_conflict_genome
        from agentdrive.drive.crdt import merge_counters, merge_sets

        try:
            latest = self.registry.load(incoming.manifest.id)
        except (AgentDriveRegistryError, FileNotFoundError, json.JSONDecodeError) as e:
            logger.debug(
                f"Registry load for {incoming.manifest.id} failed during conflict check: {e}"
            )
            latest = None
        except Exception as e:
            logger.warning(f"Unexpected registry error loading {incoming.manifest.id}: {e}")
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

            # Intentional supersession bypass: improvement / evolution / etc.
            source_norm = (source or "").strip().lower()
            if any(source_norm.startswith(s) for s in self._M4_INTENTIONAL_SUPERSESSION_SOURCES):
                return incoming, None

            # Declared supersession bypass: incoming names the existing as parent.
            if latest.manifest.content_hash in (incoming.manifest.supersedes or []):
                return incoming, None

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

        Correlation ID (if present in context or auto-provisioned) is carried
        through for tracing and included in relevant structured logs.
        """
        # Observability: ensure a correlation ID is active for this ingest (non-breaking).
        # Subsequent nested calls (e.g. think paths) will see the same ID.
        _cid = get_correlation_id() or new_correlation_id()

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
            genome, m4_event = self._apply_m4_merge_or_conflict(genome, actor=actor, source=source)

        # Basic acceptance policy (can be made much smarter later)
        existing = self.registry.search(query=genome.manifest.id, limit=5)

        accepted = True

        # GBrain-inspired self-wiring knowledge graph (zero LLM for edge extraction).
        # Knowledge graph layer: Real persistence under dedicated "knowledge/" namespace + auto-index for all role-swarms.
        # New edges from any ingest (any swarm) are now durably stored under knowledge/edges.jsonl and queryable.
        # Everything flows back to central drive (scoped + event bridges + coordinator).
        try:
            from agentdrive.knowledge_graph import (
                KnowledgeGraphStore,
                extract_from_genome,
            )

            # Enrich with README when possible for stronger cross-links (e.g. usage genomes referencing graph)
            extra = ""
            try:
                gid = getattr(genome.manifest, "id", "") if genome.manifest else ""
                for cand_name in (f"{gid}/README.md", "README.md"):
                    p = self.drive_path / "genomes" / cand_name
                    if p.exists():
                        extra = p.read_text(encoding="utf-8", errors="ignore")[:6000]
                        break
            except Exception:
                pass

            entities, typed_edges = extract_from_genome(genome, extra_text=extra)
            if typed_edges:
                logger.info(
                    "knowledge_graph_edges_extracted",
                    extra={
                        "genome_id": genome.manifest.id if genome.manifest else "unknown",
                        "edge_count": len(typed_edges),
                        "sample_relations": [e.relation for e in typed_edges[:3]],
                        "swarm_id": self.swarm_id,
                        "correlation_id": get_correlation_id(),
                    },
                )

                # PRIMARY PERSISTENCE: dedicated knowledge/ namespace (robust, typed, swarm-isolated but centralizable)
                kg_store = KnowledgeGraphStore(drive_path=self.drive_path, swarm_id=self.swarm_id)
                kg_store.add_edges(typed_edges, swarm_id=self.swarm_id)

                # SECONDARY: also to main ingest.jsonl for replayability via load_graph_from_drive_events
                for edge in typed_edges:
                    kg_event = {
                        "timestamp": time.time(),
                        "kind": "knowledge_graph_edge",
                        "source": edge.source,
                        "target": edge.target,
                        "relation": edge.relation,
                        "genome": getattr(genome.manifest, "id", None) if genome.manifest else None,
                        "confidence": getattr(edge, "confidence", 1.0),
                        "swarm_id": self.swarm_id,
                    }
                    self._ingest_log.append(kg_event)
                    try:
                        with open(self.ingest_log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps(kg_event, default=str) + "\n")
                    except Exception as exc:
                        logger.debug(f"Failed to append kg edge to ingest log: {exc}")
        except Exception as e:
            logger.debug(f"Knowledge graph extraction + persistence skipped: {e}")

        # Living Experience Layer wiring (core experience evolution work):
        # Auto-emit strong KG edges so living-experience / experience-genomes / research-thread
        # (forked research thread living-experience genome families) become the natural entry
        # point for drive.think on major topics. This makes the fused experience the single
        # source of truth / daily starting interface for Conductors. Native research thread
        # branching support wired on stabilization-wave-20260531 drive.
        # High-value outputs from Graph Hardener + Calibration are incorporated via these edges + promotion.
        try:
            gid = getattr(genome.manifest, "id", "") or ""
            # Fallback inference from id/path (page_type_map not in scope at raw ingest time)
            is_experience_genome = (
                "experience" in gid.lower()
                or "living-experience" in gid.lower()
                or "agentdrive-experience" in gid.lower()
                or "research-thread" in gid.lower()
                or "research_thread" in gid.lower()
            )
            if is_experience_genome:
                from agentdrive.knowledge_graph.graph import GraphEdge, KnowledgeGraphStore

                kg_store = KnowledgeGraphStore(drive_path=self.drive_path, swarm_id=self.swarm_id)
                major_topics = [
                    "drive.think",
                    "conductor-daily-interface",
                    "synthesis",
                    "one-experience",
                    "major-topics",
                    "daily-start",
                ]
                exp_edges = []
                for topic in major_topics:
                    exp_edges.append(
                        GraphEdge(
                            source=f"genomes/{gid}",
                            target=topic,
                            relation="is_primary_entry_for",
                            weight=0.95,
                            confidence=0.92,
                            metadata={
                                "swarm_id": self.swarm_id or "experience-layer",
                                "source_type": "living-experience",
                                "fused_from": [
                                    "hybrid_fusion",
                                    "graph_signal_integration",
                                    "calibration_engine",
                                ],
                            },
                            swarm_id=self.swarm_id,
                            timestamp=time.time(),
                        )
                    )
                    # Reverse for natural traversal from topic -> experience
                    exp_edges.append(
                        GraphEdge(
                            source=topic,
                            target=f"genomes/{gid}",
                            relation="has_experience_entry",
                            weight=0.90,
                            confidence=0.90,
                            metadata={"experience_genome": gid},
                            swarm_id=self.swarm_id,
                        )
                    )
                kg_store.add_edges(exp_edges, swarm_id=self.swarm_id or "experience-layer")
                logger.info(
                    "experience_layer_kg_wired",
                    extra={
                        "genome": gid,
                        "entry_topics": major_topics,
                        "correlation_id": get_correlation_id(),
                    },
                )
                # Also emit event for coordinator / other swarms to react
                emit(
                    "experience_layer_entry_wired",
                    {
                        "genome_id": gid,
                        "version": getattr(genome.manifest, "version", None),
                        "topics": major_topics,
                        "swarm": self.swarm_id,
                        "auto_incorporates": ["graph_signal_integration", "calibration_engine"],
                    },
                )
        except Exception as _exp_kg_err:
            logger.debug(f"Experience layer KG wiring skipped (non-fatal): {_exp_kg_err}")

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

        # Page type inference on ingest (schema integration): every genome ingest
        # is also a "page" of type "genome" under the active schema pack.
        # This wires raw-drive + genome worlds together for hybrid fusion and experience layer.
        page_type_inferred = None
        try:
            page_type_inferred = self.infer_page_type_for_genome(genome)
            if page_type_inferred is not None:
                entry_pt = getattr(page_type_inferred, "name", str(page_type_inferred))
            else:
                entry_pt = "genome"
        except Exception:
            entry_pt = "genome"

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
            "page_type": entry_pt,  # NEW: schema pack inference result
            "schema_pack": getattr(self.schema_pack, "name", "unknown"),
        }
        self._ingest_log.append(entry)

        # Persist to JSONL (append-only, robust)
        try:
            with open(self.ingest_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as exc:
            logger.warning(f"Failed to append to ingest log {self.ingest_log_path}: {exc}")

        # Upward sharing for "full" policy: child contributions can propagate to parent pool.
        # v2 / M6: when the parent policy requires promotion, route via
        # PromotionService instead of direct ingest. Self-originated proposals
        # auto-approve (matches the v1 single-agent flow); peer / cross-agent
        # promotions stay pending until reviewed.
        if self.parent_pool and getattr(self, "sharing_policy", "selective") == "full":
            try:
                self._promote_to_parent(genome, source=source, actor=actor)
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

    def _rrf_fusion_enabled(self) -> bool:
        flag = os.environ.get("AGENTDRIVE_RRF_FUSION", "").strip().lower()
        if flag in {"1", "true", "yes", "on"}:
            return True
        return bool(getattr(self.settings, "use_rrf_fusion", False))

    def _apply_additive_fusion(
        self,
        scored: list[tuple[float, Genome]],
        signals: dict[str, dict[str, Any]],
        page_type_map: dict[str, str],
    ) -> None:
        """Legacy additive graph + page_type fusion (default when RRF is off)."""
        for i, (sc, g) in enumerate(scored):
            gid = g.genome_id
            sig = signals.get(gid, {})
            gbrain_sig = sig.get("gbrain_signal_score") or sig.get("composite", 0.0)
            rec_b = float(sig.get("recency_boost", 0.0) or sig.get("recency", 0.0))
            trust_b = float(sig.get("swarm_trust", 0.0) or sig.get("swarm_trust_tier", 0.0))
            src_b = float(sig.get("source_boost", 0.0) or 0.0)
            boost = gbrain_sig or sig.get("adjacency_boost", 0.0)
            pt_boost = 0.0
            pt = page_type_map.get(gid, "")
            if pt in ("living-experience", "experience-genome"):
                pt_boost = 0.28
            elif pt == "research-thread":
                pt_boost = 0.25
            elif pt in ("genome", "synthesis-artifact", "dream-observation"):
                pt_boost = 0.14 if pt == "dream-observation" else 0.12
            elif pt in ("experience-observation", "fusion-observation"):
                pt_boost = 0.19
            elif "schema" in pt:
                pt_boost = 0.07
            dream_b = (
                0.09
                if "dream" in pt or "observation" in str(getattr(g, "_page_type", ""))
                else 0.0
            )
            experience_b = (
                0.22
                if pt
                in (
                    "living-experience",
                    "experience-genome",
                    "experience-observation",
                    "research-thread",
                )
                else 0.0
            )
            fused = min(
                1.0,
                sc
                + 0.35 * boost
                + 0.22 * rec_b
                + 0.18 * trust_b
                + 0.12 * src_b
                + pt_boost
                + dream_b
                + experience_b,
            )
            scored[i] = (fused, g)
            try:
                setattr(
                    g,
                    "_hybrid_fusion",
                    {
                        "mode": "additive",
                        "base": round(sc, 3),
                        "graph_boost": round(boost, 3),
                        "gbrain_signal_score": round(gbrain_sig, 3),
                        "recency_boost": round(rec_b, 3),
                        "swarm_trust": round(trust_b, 3),
                        "source_boost": round(src_b, 3),
                        "pt_boost": pt_boost,
                        "dream_boost": dream_b,
                        "experience_boost": round(experience_b, 3),
                        "page_type": pt,
                        "fused_total": round(fused, 3),
                        "experience_layer": pt
                        in (
                            "living-experience",
                            "experience-genome",
                            "experience-observation",
                            "research-thread",
                        ),
                    },
                )
            except Exception:
                pass

    def query(self, query: DriveQuery) -> list[Genome]:
        """Pull the most relevant Genomes for a given task or need.

        Richer hybrid retrieval with experience layer support:
        - Base: structural + reasoning Jaccard (from integration genomes)
        - Fusion: keyword (registry) + graph signals (adjacency/recency/swarm_trust from graph signal integration)
          + recency (manifest last_improved) + schema page_type boost (genome/synthesis-artifact/dream-observation)
        - Coordinates with synthesis (drive.think paths) + typed edges + durable dream ingestion.
        Uses fuse_graph_signals_into_scores when KG available. Non-breaking; falls back gracefully.

        Correlation ID is automatically carried (or provisioned) for tracing through
        retrieval + hybrid fusion.
        """
        # Observability: auto-provision correlation ID for this query (visible downstream to think/synthesis).
        _cid = get_correlation_id() or new_correlation_id()

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
        page_type_map: dict[str, str] = {}
        relevance_map: dict[str, dict[str, Any]] = {}
        for g in cands:
            rel = self._compute_relevance(g, task_desc)
            relevance_map[g.genome_id] = rel
            # Apply min_score to the new hybrid relevance if provided (overrides legacy min_score filter somewhat)
            if query.min_score and rel["hybrid"] < query.min_score:
                continue
            scored.append((rel["hybrid"], g))
            # Early page_type for hybrid fusion (schema integration)
            try:
                pt = self.infer_page_type_for_genome(g)
                if pt:
                    page_type_map[g.genome_id] = getattr(pt, "name", str(pt))
            except Exception:
                pass

        # === Hybrid Fusion: graph signals + recency + schema page_type boosts ===
        # Pulls from swarm KG (populated by graph signal integration persistence) + schema pack.
        # Fuses into final scores for higher precision on integration-genomes, synthesis artifacts, experience genomes, etc.
        try:
            if scored and get_knowledge_graph_for_swarm and compute_graph_signals:
                swarm_ctx = self.swarm_id or get_current_swarm_id() or "hybrid-retrieval"
                kg = get_knowledge_graph_for_swarm(swarm_ctx)
                # Prepare base scores and entities (use genome_id as key for signals)
                base_scores = {g.genome_id: sc for sc, g in scored}
                query_entities = list(base_scores.keys())
                # Edge meta hint from manifests for recency
                edge_meta = {}
                now = time.time()
                for sc, g in scored:
                    gid = g.genome_id
                    ts = None
                    li = getattr(g.manifest, "last_improved", None)
                    if li:
                        try:
                            ts = (
                                li.timestamp()
                                if hasattr(li, "timestamp")
                                else float(li)
                                if isinstance(li, (int, float))
                                else None
                            )
                        except Exception:
                            ts = None
                    if ts is None:
                        cr = getattr(g.manifest, "created", None)
                        try:
                            ts = (
                                cr.timestamp()
                                if cr and hasattr(cr, "timestamp")
                                else float(cr)
                                if isinstance(cr, (int, float))
                                else None
                            )
                        except Exception:
                            ts = None
                    if ts is None:
                        ts = now - 86400 * 30
                    edge_meta[gid] = {
                        "timestamp": ts,
                        "source_type": page_type_map.get(gid, "genome"),
                    }
                # Compute signals (includes recency, swarm_trust, source_boost via page_type)
                signals = compute_graph_signals(
                    kg, query_entities, swarm_context=swarm_ctx, edge_meta=edge_meta
                )
                if self._rrf_fusion_enabled():
                    scored = fuse_scored_with_rrf(
                        scored,
                        relevance_map,
                        signals,
                        page_type_map,
                        edge_meta,
                    )
                else:
                    self._apply_additive_fusion(scored, signals, page_type_map)
            elif self._rrf_fusion_enabled() and scored:
                scored = fuse_scored_with_rrf(
                    scored,
                    relevance_map,
                    {},
                    page_type_map,
                    {},
                )
        except Exception as _fuse_err:
            # Graceful: retrieval still works with base hybrid
            logger.debug(
                "Phase2 hybrid fusion skipped: %s",
                _fuse_err,
                extra={"correlation_id": get_correlation_id()},
            )
        # end Phase 2 fusion

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

        # Phase 2: exercise infer_page_type_for_genome + get_active_schema_pack on query path.
        # Result annotation: attach _page_type (runtime attr, non-breaking for Genome pydantic model).
        # This makes schema runtime-influential for downstream (think, synthesis, TUI).
        try:
            _pack = self.get_active_schema_pack()
            for g in results:
                try:
                    pt = self.infer_page_type_for_genome(g)
                    if pt is not None:
                        ptn = getattr(pt, "name", str(pt))
                        setattr(g, "_page_type", ptn)
                        # also stash on manifest for visibility in some paths
                        try:
                            if not hasattr(g.manifest, "page_type") or not g.manifest.page_type:
                                g.manifest.page_type = ptn  # type: ignore[attr-defined]
                        except Exception:
                            pass
                except Exception:
                    continue
        except Exception:
            pass

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

    # --- Synthesis ("think") layer with experience layer wiring: cited answers + explicit gaps ---
    def think(
        self,
        question: str,
        *,
        max_genomes: int = 8,
        min_score: float = 0.0,
        # Experience layer wiring: when True (default),
        # strongly prefers living-experience / experience-genome results so the fused
        # One Experience is the Conductor's daily single source of truth entry point.
        prefer_experience_layer: bool = True,
        # Stabilization: if experience layer lookup fails, fall back gracefully instead of blowing up.
        experience_layer_fallback: bool = True,
    ) -> "SynthesisResult":  # noqa: F821
        """
        Production role-swarm think convenience for agents.

        Native to AgentDrive:
        - Retrieval: uses DriveQuery + reasoning-powered ranking (get_dna_for_task style)
        - Graph: rebuilds SimpleGraph from persisted knowledge_graph_edge events in the ingest log
          + live extraction from the retrieved genomes via link_extraction
        - Synthesis: calls run_synthesis which surfaces genome **framework steps**, typed
          **graph relationships** (depends_on, references, ...), multi-hop paths, and
          honest gap analysis (missing relations, stale genomes, low connectivity, etc.)
        - Citations: full Citation objects with .render() + result.render_citations()

        Example usage by agents / harnesses:
            with using_swarm("my-swarm"):
                drive = get_default_drive()
                result = drive.think("How do we handle secret rotation in the pool?")
                print(result.answer)
                print(result.render_citations())
                for g in result.gaps:
                    print("GAP:", g.description, "→", g.suggested_action)

        All work is automatically shared via the swarm's central Drive + knowledge_graph.

        Correlation ID flows from caller context (or is auto-generated) and is visible
        to the internal run_synthesis call for full trace continuity.
        """
        from agentdrive.knowledge_graph import (
            GraphEdge,
            SimpleGraph,
            extract_from_genome,
            load_graph_from_drive_events,
        )
        from agentdrive.synthesis import SynthesisResult, run_synthesis

        # Observability for experience layer v3: ensure correlation ID for the entire
        # Drive.think + synthesis path (candidate selection, Gap objects + contradictions,
        # fusion_checkpoint). Propagates from DurableJobSupervisor stabilization jobs too.
        _cid = get_correlation_id() or new_correlation_id()
        logger.debug(
            "drive_think_start_synthesis_path",
            extra={
                "correlation_id": _cid,
                "question_len": len(question or ""),
                "swarm_id": getattr(self, "swarm_id", None),
                "component": "Drive.think",
            },
        )

        # 1. Retrieval via existing Drive intelligence (respects sharing policy etc.)
        q = DriveQuery(
            task_description=question,
            limit=max_genomes,
            min_score=min_score,
            include_reasoning=True,
        )
        genomes: list[Genome] = self.query(q)

        # 2. Build rich in-memory graph for this synthesis call
        graph = SimpleGraph()

        # a) From durable ingest log (populated on every ingest, including kg edges we now persist)
        try:
            kg_events = [
                e for e in (self._ingest_log or []) if e.get("kind") == "knowledge_graph_edge"
            ]
            if kg_events:
                g_from_log = load_graph_from_drive_events(kg_events)
                for e in getattr(g_from_log, "_edges", []):
                    graph.add_edge(e)
        except Exception:
            pass

        # b) Live extraction + edges from the genomes we just retrieved (guarantees coverage)
        for g in genomes:
            try:
                _, edges = extract_from_genome(g)
                for te in edges:
                    graph.add_edge(
                        GraphEdge(
                            source=te.source,
                            target=te.target,
                            relation=te.relation,
                            weight=getattr(te, "confidence", 1.0),
                            metadata={"provenance": getattr(te, "provenance", None)},
                        )
                    )
            except Exception:
                continue

        # 3. Normalize genomes for the synthesis engine (pass real objects so it can introspect steps)
        # run_synthesis accepts both; passing Genome objects gives best framework step access.
        available_for_synth = genomes if genomes else []

        # Phase 2 safe schema page type annotation (charter deep wire; delegates to schema_packs, no new methods needed)
        think_source_page_types: dict[str, str] = {}
        try:
            from agentdrive.schema_packs import load_active_pack

            pack = load_active_pack()
            for g in genomes:
                try:
                    gid = getattr(g, "genome_id", str(getattr(g, "id", "g")))
                    cand_path = f"genomes/{gid.split('@')[0] if '@' in gid else gid}"
                    inferred = (
                        pack.resolve_type(cand_path) if hasattr(pack, "resolve_type") else None
                    )
                    if inferred:
                        ptn = getattr(inferred, "name", "genome")
                        think_source_page_types[gid] = ptn
                        setattr(g, "_page_type", ptn)
                except Exception:
                    pass
        except Exception:
            pass

        # 3b. Consume durable dream outputs (durable dream ingestion): scan role-swarm dream job stores + central dreams/
        # Treat completed phase results + promoted observations (from diary, promotions, runs, checkpoints)
        # as first-class "dream_observation" sources with citation type "dream".
        dream_sources: list[dict[str, Any]] = []
        try:
            from agentdrive.constants import get_agentdrive_home

            home = get_agentdrive_home()
            # Example role-swarm dream_jobs (DurableDreamRunner persistence under swarms/<swarm>/drive/dream_jobs)
            # In production any swarm using durable jobs will have its outputs discovered via central or explicit scan.
            dream_job_swarm = home / "swarms" / "dream-engine" / "drive" / "dream_jobs"
            if dream_job_swarm.exists():
                for jf in dream_job_swarm.glob("*.json") or []:
                    try:
                        data = json.loads(jf.read_text(encoding="utf-8"))
                        if data.get("status") in ("completed", "COMPLETED") or "result" in data:
                            dream_sources.append(
                                {
                                    "id": f"dreamjob-{data.get('id', jf.stem)}",
                                    "page_type": "dream-observation",
                                    "content": str(data.get("result") or data.get("summary", ""))[
                                        :400
                                    ],
                                    "source": "dream-engine/DurableDreamRunner",
                                    "phase": data.get("phase"),
                                }
                            )
                    except Exception:
                        continue
            # Central dreams: runs, promotions (pattern/memory), diary, checkpoints as high-signal obs
            central_dreams = home / "dreams"
            # Recent runs status + manifest
            for run_dir in (
                (central_dreams / "runs").glob("dream-*")
                if (central_dreams / "runs").exists()
                else []
            ):
                try:
                    st = (run_dir / "status.json").read_text(encoding="utf-8")
                    if "committed" in st or "completed" in st.lower():
                        dream_sources.append(
                            {
                                "id": run_dir.name,
                                "page_type": "dream-observation",
                                "content": f"Loom dream run {run_dir.name} committed with phases",
                                "source": "central_dreams/runs",
                                "kind": "dream-run",
                            }
                        )
                except Exception:
                    pass
            # Promoted observations (high value, from durable dream production)
            for prom_lane in ["pattern", "memory"]:
                pdir = central_dreams / "promotions" / prom_lane
                if pdir.exists():
                    for pf in list(pdir.glob("*.json"))[:3]:
                        try:
                            pdata = json.loads(pf.read_text(encoding="utf-8"))
                            cand = pdata.get("candidate", {})
                            if cand:
                                dream_sources.append(
                                    {
                                        "id": cand.get("candidate_id", pf.stem),
                                        "page_type": "dream-observation",
                                        "content": f"Promoted {prom_lane}: {cand.get('kind', 'obs')} score={cand.get('total_score', 0):.2f} from {cand.get('source_substrates', [])}",
                                        "source": f"central_dreams/promotions/{prom_lane}",
                                        "kind": "promoted-obs",
                                    }
                                )
                        except Exception:
                            pass
            # Diary entries as consolidated summaries
            diary = central_dreams / "diary" / "dreams.jsonl"
            if diary.exists():
                for line in list(diary.read_text(encoding="utf-8").splitlines())[-2:]:
                    if line.strip():
                        try:
                            drec = json.loads(line)
                            if drec.get("phase") in ("deep", "rem"):
                                dream_sources.append(
                                    {
                                        "id": f"dream-diary-{drec.get('run_id', 'x')}",
                                        "page_type": "dream-observation",
                                        "content": drec.get("summary", "")[:300],
                                        "source": "central_dreams/diary",
                                        "kind": "dream-diary",
                                    }
                                )
                        except Exception:
                            pass
        except Exception:
            pass
        dream_sources = dream_sources[:5]  # limit

        # 4. Run the improved synthesis (steps + relations + smart gaps + citations + dreams + schema + KG)
        # Correlation ID flows in for full trace (DurableJobSupervisor -> drive.think -> synthesis inner -> recon delta)
        logger.debug(
            "drive_think_invoking_synthesis",
            extra={"correlation_id": _cid, "dream_sources_count": len(dream_sources)},
        )
        result: SynthesisResult = run_synthesis(
            question,
            available_genomes=available_for_synth,
            graph=graph,
            max_genomes=max_genomes,
            dream_sources=dream_sources,
            use_kg_fusion=True,
            swarm_context=getattr(self, "swarm_id", None) or "synthesis",
        )
        logger.debug(
            "drive_think_synthesis_complete",
            extra={
                "correlation_id": get_correlation_id(),
                "gaps_in_result": len(getattr(result, "gaps", [])),
                "contradictions_in_result": len(getattr(result, "contradictions", [])),
            },
        )

        # Surface explicit synthesis damage signals (from HealingFactor integration) for regenerative diagnosis
        try:
            if hasattr(result, "damage_signals") and result.damage_signals:
                result.warnings.append(
                    f"synthesis_damage_detected: {len(result.damage_signals)} clusters — HealingFactor candidate"
                )
                # Minor wiring: emit HealingSignalEvent so Regenerative HealingFactor Operator (experience layer
                # regeneration coordinator) can trigger autonomous _diagnose + _generate_regeneration_proposals +
                # _execute under DurableJobSupervisor healing phase with schema-pack page types (healing-damage etc).
                cid = get_correlation_id() or new_correlation_id()
                emit(
                    HealingSignalEvent(
                        signal_type="synthesis_contradiction_cluster_damage",
                        correlation_id=cid,
                        context={
                            "damage_signals": result.damage_signals[:3],
                            "gaps_count": len(getattr(result, "gaps", [])),
                            "contradictions_count": len(getattr(result, "contradictions", [])),
                            "source_component": "drive_think",
                            "swarm_context": getattr(self, "swarm_id", "healing-regeneration"),
                        },
                        source_component="synthesis",
                        recommended_priority="high",
                    )
                )
        except Exception:
            pass
        # Closed-loop calibration note: drive.think now benefits from auto-calib state from contradiction detection
        try:
            result.warnings.append(
                "calibration: contradictions trigger auto weight/boost/recency adjustments (hybrid fusion + graph signals)"
            )
        except Exception:
            pass

        # Experience Layer wiring: if prefer_experience_layer,
        # the result is now explicitly the living experience entry point. High-value graph signal integration
        # + calibration outputs are auto fused in via KG + page_type + promotion paths.
        if prefer_experience_layer:
            try:
                result.warnings.append(
                    "experience-layer: fused living-experience genome family is the primary daily Conductor interface. "
                    "New Conductors start from agentdrive-experience-v1 (or latest). "
                    "Strong KG 'is_primary_entry_for' edges wire experience as natural drive.think entry. "
                    "Forks/evolution proposals supported; auto-incorporates graph signal integration + calibration outputs."
                )
                if not hasattr(result, "_experience_layer"):
                    setattr(
                        result,
                        "_experience_layer",
                        {
                            "primary_genome": "agentdrive-experience-v1",
                            "family": "living-experience-genome-family",
                            "prefer_experience_layer": True,
                            "wired_as_entry": True,
                            "swarm": "experience-layer",
                        },
                    )
            except Exception as e:
                if experience_layer_fallback:
                    logger.debug(
                        "Experience layer attachment failed (graceful fallback enabled): %s",
                        e,
                        extra={"correlation_id": get_correlation_id()},
                    )
                else:
                    raise AgentDriveDriveError(f"Experience layer wiring failed: {e}") from e

        # Attach drive context + richer fusion note (non-breaking; full _hybrid_fusion on genomes + kg_fusion_signals on result)
        try:
            result.warnings.append(f"drive={self.name} swarm={self.swarm_id}")
            # Propagate hybrid metadata summary to result for query/think paths
            if not hasattr(result, "_fusion_metadata"):
                setattr(
                    result,
                    "_fusion_metadata",
                    {
                        "hybrid_enhanced": True,
                        "signals_used": [
                            "gbrain_signal_score",
                            "recency",
                            "swarm_trust",
                            "source_boost",
                            "page_type",
                            "dream-observation",
                            "living-experience",
                            "experience-observation",
                            "experience-genome",
                        ],
                        "graph_signal_integration": True,
                        "experience_layer": True,
                    },
                )
        except Exception:
            pass

        return result

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
                # tolerate str or other (from genome authoring variance); skip or treat as text via _collect
                continue
            try:
                # support both flat and nested (from PatternMatch etc)
                p_ints = p.get("intents") or (p.get("signature") or {}).get("intents") or []
                p_flds = p.get("fields") or (p.get("signature") or {}).get("fields") or []
                io = _jaccard(
                    list(task_tokens), p_ints if isinstance(p_ints, (list, tuple)) else []
                )
                fo = _jaccard([], p_flds if isinstance(p_flds, (list, tuple)) else [])
                pscore = 0.75 * io + 0.25 * fo
                if pscore > 0.1 and pscore > reasoning_score:
                    reasoning_score = pscore
                    sig = p.get("signature") or {}
                    fid = p.get("framework_id") or (
                        sig.get("framework_id", "pattern") if isinstance(sig, dict) else "pattern"
                    )
                    reason_reasons.append(f"pattern_recognized_match({pscore:.2f}): {fid}")
            except Exception:
                continue  # robust to any authoring variance in integration genomes

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

        pack_name = getattr(self.schema_pack, "name", "none")
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
            # Schema pack page-type integration
            "schema_pack": pack_name,
            "schema_pack_active": pack_name,
            # Phase 2: include full schema_stats / page_type_distribution (TUI/CLI ready)
            "schema_stats": self.get_schema_stats(),
        }

    def get_ingest_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent ingest events (newest first) from the persistent on-disk JSONL log."""
        hist = list(reversed(self._ingest_log[-limit:]))
        return hist

    # --- Knowledge Graph integration (graph signal integration) ---
    # Every Drive now exposes first-class access to its typed persistent graph.
    # Callers use these for "find genomes related to X via Y", experience layer wiring, hybrid fusion, etc.

    def get_knowledge_graph(self) -> "SimpleGraph":  # noqa: F821
        """Return the live knowledge graph for this drive (loaded from knowledge/edges.jsonl)."""
        from agentdrive.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore(drive_path=self.drive_path, swarm_id=self.swarm_id)
        return store.load_as_simple_graph()

    def query_knowledge_graph(
        self,
        start: str,
        *,
        max_depth: int = 3,
        relation_filter: set[str] | None = None,
        top_k: int = 20,
    ) -> list["GraphPath"]:  # noqa: F821
        """Convenience multi-hop query with scoring. Delegates to the persistent graph."""
        g = self.get_knowledge_graph()
        return g.find_paths(
            start, max_depth=max_depth, relation_filter=relation_filter, top_k=top_k
        )

    def find_genomes_related_to(
        self,
        entity: str,
        via: list[str] | None = None,
        max_depth: int = 2,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Graph-aware helper exposed at Drive level for easy consumption by synthesis/reasoning/role-swarms."""
        g = self.get_knowledge_graph()
        return g.find_genomes_related_to(entity, via=via, max_depth=max_depth, limit=limit)

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

    # ── Schema pack integration (page-type boosts for hybrid fusion + experience layer) ──────────────
    def infer_page_type(self, path: str | Path) -> Any | None:
        """Runtime page type inference using the active DriveSchemaPack.

        Returns a PageType (or None) for raw drive content paths, captures,
        observations, synthesis artifacts, etc. Genomes always resolve to the
        "genome" page type under the agentdrive-drive pack.

        This is the primary hook for "proper page type inference on ingest".
        """
        if self.schema_pack is None:
            try:
                from agentdrive.schema_packs import load_active_pack

                self.schema_pack = load_active_pack()
            except Exception:
                return None
        try:
            return self.schema_pack.resolve_type(str(path))
        except Exception:
            # Fallback to simple get for older packs
            try:
                return self.schema_pack.get_type_for_path(str(path))
            except Exception:
                return None

    def infer_page_type_for_genome(self, genome: Genome) -> Any | None:
        """Convenience: genomes are always classified under the pack's 'genome' type."""
        # Use the pack's own resolution on a conventional path; guarantees consistency.
        return self.infer_page_type(f"genomes/{genome.manifest.id or 'unknown'}")

    def get_active_schema_pack(self) -> Any | None:
        """Expose the pack for synthesis / TUI / agents that want role-swarm calibration and experience layer flows."""
        if self.schema_pack is None:
            try:
                from agentdrive.schema_packs import load_active_pack

                self.schema_pack = load_active_pack()
            except Exception:
                return None
        return self.schema_pack

    def get_schema_stats(self) -> dict[str, Any]:
        """Lightweight 'schema_stats' / page_type_distribution for TUI/CLI (Phase 2).

        Exercises get_active_schema_pack + leverages ingest_log (already records
        page_type on every ingest via infer_page_type_for_genome). No heavy walks.
        """
        from collections import Counter

        pack = self.get_active_schema_pack()  # exercise the getter
        pt_counter = Counter(
            e.get("page_type") for e in (self._ingest_log or []) if e.get("page_type")
        )
        pack_info: dict[str, Any] = {
            "name": getattr(pack, "name", None) if pack else None,
            "version": getattr(pack, "version", None) if pack else None,
            "num_page_types": len(getattr(pack, "page_types", [])) if pack else 0,
        }
        distribution = dict(pt_counter.most_common(15))
        return {
            "active_pack": pack_info,
            "page_type_distribution": distribution,
            "typed_ingest_events": sum(pt_counter.values()),
            "distinct_page_types_seen": len([k for k in pt_counter if k]),
            "schema_pack": pack_info.get("name"),
        }

    # ── Production stabilization: clean shutdown support ───────────────────
    def close(self) -> None:
        """Best-effort release of resources (content store, etc.)."""
        try:
            if hasattr(self, "content_store") and hasattr(self.content_store, "close"):
                self.content_store.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


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
        """Create the isolated dir tree (idempotent). Returns the Drive/ path.

        Now also ensures objects/ + experience layer seed for empty-drive
        self-healing parity with global Drive initialization.
        """
        p = get_swarm_drive_path(swarm_id, subagent_id)
        try:
            p.mkdir(parents=True, exist_ok=True)
            for sub in ("genomes", "objects"):
                (p / sub).mkdir(exist_ok=True)
            # Touch ingest log defensively (AgentDrive will also do it)
            ingest = p / "ingest.jsonl"
            if not ingest.exists():
                ingest.touch(exist_ok=True)
        except Exception:
            pass
        # The subsequent AgentDrive() ctor will run the full _ensure_experience_layer_seed
        # + home ensure + recovery logic. We keep provision minimal but safe.
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
    """Always returns the root (non-scoped) pool, regardless of current context/env ids.

    First-run / empty-drive safe via the Self-Healing First-Run & Experience Seed
    Operator (bootstrap): AgentDrive.__init__ now guarantees expanded defensive
    healing — minimal KG index, living-experience v3 seed (page type), recon state,
    trust identity, full dir structure. For role-swarm self-host users: new
    AgentDrive instances start coherent; experience layer present from first think;
    defensive healing for production reliability.
    """
    global default_pool
    if default_pool is None:
        default_pool = AgentDrive()  # no ids => global path + registry
    return default_pool


def get_default_drive() -> AgentDrive:
    """
    Returns the appropriate pool for current context:
    - If AGENTDRIVE_SWARM_ID / AGENTDRIVE_SUBAGENT_ID (env or using_swarm() context) are set,
      returns (and auto-creates) the isolated per-subagent pool under swarms/.
    - Otherwise the global ~/.agentdrive/drive .

    First-run and empty-drive resilient via expanded self-healing (drive/bootstrap.py
    Self-Healing First-Run & Experience Seed Operator): full directory structure,
    minimal KG index bootstrap, experience layer v3 seed genome + living-experience
    observation (page type for fusion), basic reconciliation state, and trust
    self-identity placeholder — all before onboarding.

    For AgentDrive role-swarm users who self-host: new instances start coherent,
    experience layer present from first think, defensive healing for production
    reliability. AGENTDRIVE_INSTANCE_NAME (env) is honored from first access onward.
    """
    swarm_id = get_current_swarm_id()
    subagent_id = get_current_subagent_id()

    if swarm_id is not None or subagent_id is not None:
        return get_swarm_drive_manager().get_pool(swarm_id or "default", subagent_id)

    return get_global_drive()


# Back-compat: old direct assignment still works for global
# Users / tests that did default_pool = AgentDrive() continue to affect global.
