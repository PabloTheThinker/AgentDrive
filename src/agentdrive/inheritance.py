"""Cross-agent inheritance manifest — sub-agent learnings ferried home.

When a sub-agent finishes a mission, it can drop an *inheritance manifest*
on disk summarising what it learned: genomes it pulled, genomes it created,
outcomes it logged. The parent agent reads the manifest, absorbs the new
genomes into its pool (subject to consent), and an audit-trail event fires
so the absorption is legible in the chat ribbon.

This module is data + events only. It does NOT run quarantine — that is a
separate concern handled by ``savant.quarantine`` (built in parallel). See
the open design question in the cover note about whether auto-absorb
should route through quarantine first.

Layout on disk::

    ~/.agentdrive/inheritance/<swarm_id>/<subagent_id>.json
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentdrive.constants import get_agentdrive_home
from agentdrive.events import (
    InheritanceAbsorbed,
    InheritanceReceived,
    SubagentDone,
    emit,
    subscribe,
)

if TYPE_CHECKING:
    from agentdrive.drive.drive import AgentDrive

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class InheritanceManifest:
    """A single sub-agent's report of what it learned in one mission."""

    subagent_id: str = ""
    swarm_id: str = ""
    genomes_pulled: list[str] = field(default_factory=list)
    genomes_created: list[str] = field(default_factory=list)
    outcomes_logged: list[dict[str, Any]] = field(default_factory=list)
    duration_s: float = 0.0
    created_at: str = field(default_factory=_utc_now_iso)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)

    @classmethod
    def from_json(cls, data: str | bytes) -> InheritanceManifest:
        raw = json.loads(data)
        return cls(
            subagent_id=str(raw.get("subagent_id", "") or ""),
            swarm_id=str(raw.get("swarm_id", "") or ""),
            genomes_pulled=list(raw.get("genomes_pulled", []) or []),
            genomes_created=list(raw.get("genomes_created", []) or []),
            outcomes_logged=list(raw.get("outcomes_logged", []) or []),
            duration_s=float(raw.get("duration_s", 0.0) or 0.0),
            created_at=str(raw.get("created_at", "") or _utc_now_iso()),
        )


@dataclass
class InheritanceResult:
    """Outcome of recording (and optionally absorbing) a manifest."""

    manifest: InheritanceManifest
    genomes_absorbed: list[str] = field(default_factory=list)
    genomes_rejected: list[str] = field(default_factory=list)
    reason_per_rejected: dict[str, str] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────
# On-disk layout
# ─────────────────────────────────────────────────────────────────────


INHERITANCE_DIR_NAME = "inheritance"


def _inheritance_root() -> Path:
    return get_agentdrive_home() / INHERITANCE_DIR_NAME


def manifest_path(swarm_id: str, subagent_id: str) -> Path:
    """Canonical path for one sub-agent's manifest under its swarm."""
    sid = swarm_id or "default"
    return _inheritance_root() / sid / f"{subagent_id}.json"


def _write_manifest(manifest: InheritanceManifest) -> Path:
    p = manifest_path(manifest.swarm_id, manifest.subagent_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(manifest.to_json(), encoding="utf-8")
    return p


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────


def _resolve_registry_path(registry: Any, genome_id: str) -> Path | None:
    """Resolve a genome id to its on-disk path, handling 'id@version' form.

    GenomeRegistry.get_genome_path takes the bare dir name and returns
    `root/<dir_name>`. Callers naturally pass the canonical `id@version`
    string, which the registry doesn't normalize — so the lookup silently
    returns None and the candidate gets dropped before reaching quarantine.
    Try the raw form first, then split on '@' and try `id/version`.
    """
    if registry is None:
        return None
    try:
        p = registry.get_genome_path(genome_id)
        if p is not None and Path(p).exists():
            return Path(p)
    except Exception:
        logger.debug("registry.get_genome_path failed for %s", genome_id, exc_info=True)
    if "@" in genome_id:
        bare, version = genome_id.split("@", 1)
        try:
            base = registry.get_genome_path(bare)
            if base is not None:
                versioned = Path(base) / version
                if versioned.exists():
                    return versioned
                if Path(base).exists():
                    return Path(base)
        except Exception:
            logger.debug("registry fallback failed for %s", genome_id, exc_info=True)
    return None


def _pool_has_genome(pool: AgentDrive, genome_id: str) -> bool:
    """Best-effort check: does the Drive already host this genome?"""
    base = genome_id.split("@", 1)[0] if "@" in genome_id else genome_id
    try:
        if hasattr(pool, "get_genome"):
            hit = pool.get_genome(genome_id) or pool.get_genome(base)
            if hit is not None:
                return True
    except Exception:
        logger.debug("pool.get_genome lookup failed for %s", genome_id, exc_info=True)
    try:
        reg = getattr(pool, "registry", None)
        if reg is None:
            return False
        for d in reg.list_genome_details():
            if genome_id in (d.get("dir_name"), d.get("genome_id"), d.get("id")):
                return True
            if d.get("id") == base:
                return True
    except Exception:
        logger.debug("registry walk failed for %s", genome_id, exc_info=True)
    return False


def _load_genome_for_absorption(source_pool: AgentDrive | None, genome_id: str):
    """Look up the genome object to absorb from the sub-agent's own pool.

    We hop through the swarm-pool manager so we don't depend on the caller
    passing in the source pool explicitly. Returns the genome or None.
    """
    if source_pool is not None:
        try:
            if hasattr(source_pool, "get_genome"):
                g = source_pool.get_genome(genome_id)
                if g is not None:
                    return g
            reg = getattr(source_pool, "registry", None)
            if reg is not None:
                return reg.get_genome(genome_id) or reg.load(genome_id.split("@", 1)[0])
        except Exception:
            logger.debug("source pool lookup failed for %s", genome_id, exc_info=True)
    return None


def record_manifest(
    manifest: InheritanceManifest,
    target_pool: AgentDrive,
    *,
    auto_absorb: bool = True,
    source_pool: AgentDrive | None = None,
    quarantine_external: bool = False,
) -> InheritanceResult:
    """Persist a manifest and optionally absorb its new genomes into a pool.

    Trust model:
      * Default (``quarantine_external=False``): all absorbable genomes
        ingest directly into ``target_pool``. Appropriate for sub-agents
        the operator spawned themselves — same trust domain.
      * ``quarantine_external=True``: incoming genomes are routed through
        ``quarantine.submit()`` instead of being ingested directly. They
        land as ``rejected`` in the result with reason
        ``"quarantined for review: <id>"`` and reach the Drive only after
        ``savant quarantine approve``. Set this in peer-federation adapters
        and any other code path that receives DNA from outside the local
        instance.

    Each absorbed genome triggers the existing ``PoolIngest`` event with
    ``source="inheritance:<subagent_id>"`` so subscribers can render it on
    the audit ribbon. A summary ``InheritanceReceived`` event fires once
    the manifest has been processed.
    """
    _write_manifest(manifest)

    absorbed: list[str] = []
    rejected: list[str] = []
    reasons: dict[str, str] = {}

    needs_quarantine = quarantine_external and source_pool is not None

    if auto_absorb:
        for gid in manifest.genomes_created:
            if _pool_has_genome(target_pool, gid):
                rejected.append(gid)
                reasons[gid] = "already in target pool"
                continue

            if needs_quarantine:
                try:
                    src_reg = getattr(source_pool, "registry", None)
                    genome_dir = _resolve_registry_path(src_reg, gid)
                    if genome_dir is None:
                        rejected.append(gid)
                        reasons[gid] = "source dir not resolvable for quarantine"
                        continue

                    from agentdrive.quarantine import get_default_quarantine

                    q = get_default_quarantine()
                    source_name = getattr(source_pool, "name", "external")
                    entry = q.submit(
                        Path(genome_dir),
                        source_peer=f"inheritance:{manifest.subagent_id}@{source_name}",
                    )
                    rejected.append(gid)
                    reasons[gid] = f"quarantined for review: {entry.quarantine_id}"
                except Exception as exc:
                    rejected.append(gid)
                    reasons[gid] = f"quarantine submit failed: {str(exc)[:80]}"
                continue

            g = _load_genome_for_absorption(source_pool, gid)
            if g is None:
                rejected.append(gid)
                reasons[gid] = "source genome not resolvable"
                continue

            try:
                target_pool.ingest(
                    g,
                    source=f"inheritance:{manifest.subagent_id}",
                    actor=manifest.subagent_id,
                )
                absorbed.append(gid)
                try:
                    emit(
                        InheritanceAbsorbed(
                            genome_id=gid,
                            source_subagent_id=manifest.subagent_id,
                            parent_pool=getattr(target_pool, "name", "main"),
                            swarm_id=manifest.swarm_id or None,
                            subagent_id=manifest.subagent_id or None,
                        )
                    )
                except Exception:
                    logger.debug("Failed to emit InheritanceAbsorbed", exc_info=True)
            except Exception as exc:
                rejected.append(gid)
                reasons[gid] = f"ingest failed: {str(exc)[:80]}"

    try:
        emit(
            InheritanceReceived(
                genomes_absorbed=list(absorbed),
                genomes_rejected=list(rejected),
                swarm_id=manifest.swarm_id or None,
                subagent_id=manifest.subagent_id or None,
            )
        )
    except Exception:
        logger.debug("Failed to emit InheritanceReceived", exc_info=True)

    return InheritanceResult(
        manifest=manifest,
        genomes_absorbed=absorbed,
        genomes_rejected=rejected,
        reason_per_rejected=reasons,
    )


def list_manifests(swarm_id: str | None = None) -> list[InheritanceManifest]:
    """Read every manifest under inheritance/, optionally filtered by swarm."""
    root = _inheritance_root()
    if not root.is_dir():
        return []

    if swarm_id:
        scopes = [root / swarm_id]
    else:
        scopes = [p for p in root.iterdir() if p.is_dir()]

    out: list[InheritanceManifest] = []
    for scope in scopes:
        if not scope.is_dir():
            continue
        for f in sorted(scope.glob("*.json")):
            try:
                out.append(InheritanceManifest.from_json(f.read_text(encoding="utf-8")))
            except Exception:
                logger.debug("Failed to parse manifest %s", f, exc_info=True)
    return out


def load_manifest(swarm_id: str, subagent_id: str) -> InheritanceManifest | None:
    """Load a single manifest, or None if not present."""
    p = manifest_path(swarm_id, subagent_id)
    if not p.is_file():
        return None
    try:
        return InheritanceManifest.from_json(p.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("Failed to load manifest at %s", p, exc_info=True)
        return None


# ─────────────────────────────────────────────────────────────────────
# Hook into SubagentDone
# ─────────────────────────────────────────────────────────────────────


def _expected_manifest_for(event: SubagentDone) -> Path | None:
    """Resolve the on-disk path where the sub-agent's manifest would live.

    Returns None if we cannot reconstruct enough identity to look it up.
    """
    sub_id = event.subagent_id
    swarm_id = event.swarm_id or "default"
    if not sub_id:
        return None
    return manifest_path(swarm_id, sub_id)


def _on_subagent_done(event: SubagentDone) -> None:
    """Auto-absorb any manifest the sub-agent dropped on a successful exit."""
    if not getattr(event, "ok", False):
        return

    path = _expected_manifest_for(event)
    if path is None:
        return
    if not path.is_file():
        logger.debug("No inheritance manifest at %s; skipping", path)
        return

    try:
        manifest = InheritanceManifest.from_json(path.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("Failed to parse inheritance manifest %s", path, exc_info=True)
        return

    # Lazy-import to dodge circular deps with pool / swarm_manager.
    try:
        from agentdrive.drive.drive import get_default_drive
    except Exception:
        logger.debug("Failed to import default pool", exc_info=True)
        return

    try:
        target = get_default_drive()
    except Exception:
        logger.debug("Failed to acquire default pool for inheritance", exc_info=True)
        return

    source_pool = None
    try:
        from agentdrive.drive.swarm_manager import get_swarm_drive_manager

        source_pool = get_swarm_drive_manager().get_or_create_pool(
            manifest.swarm_id or event.swarm_id, manifest.subagent_id
        )
    except Exception:
        logger.debug("Failed to resolve source pool for inheritance", exc_info=True)

    try:
        record_manifest(
            manifest,
            target_pool=target,
            auto_absorb=True,
            source_pool=source_pool,
        )
    except Exception:
        logger.debug(
            "record_manifest failed for %s/%s",
            manifest.swarm_id,
            manifest.subagent_id,
            exc_info=True,
        )


# Subscribe once at import time. Using try/except so an import-order quirk
# never breaks downstream callers.
try:
    _INHERITANCE_SUBSCRIPTION = subscribe(_on_subagent_done, [SubagentDone])
except Exception:
    logger.debug("Failed to subscribe inheritance hook", exc_info=True)
    _INHERITANCE_SUBSCRIPTION = None


__all__ = [
    "InheritanceManifest",
    "InheritanceResult",
    "record_manifest",
    "list_manifests",
    "load_manifest",
    "manifest_path",
    "INHERITANCE_DIR_NAME",
]
