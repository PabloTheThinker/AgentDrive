"""Cross-agent inheritance manifest — sub-agent learnings ferried home.

When a sub-agent finishes a mission, it can drop an *inheritance manifest*
on disk summarising what it learned: genomes it pulled, genomes it created,
outcomes it logged. The parent agent reads the manifest, absorbs the new
genomes into its pool (subject to consent), and an audit-trail event fires
so the absorption is legible in the chat ribbon.

This module is data + events only. It does NOT run quarantine — that is a
separate concern handled by ``agentdrive.quarantine`` (built in parallel). See
the open design question in the cover note about whether auto-absorb
should route through quarantine first.

Layout on disk::

    ~/.agentdrive/inheritance/<swarm_id>/<subagent_id>.json
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from agentdrive.constants import get_agentdrive_home
from agentdrive.events import (
    InheritanceAbsorbed,
    InheritanceReceived,
    SkillAssimilated,
    SubagentDone,
    emit,
    subscribe,
)

if TYPE_CHECKING:
    from agentdrive.drive.drive import AgentDrive

logger = logging.getLogger(__name__)

_SKILL_BLOCK_RE = re.compile(
    r"```(?:agentdrive-skill|agentdrive_skill)\s*\n(.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)
_SKILL_BLOCK_SPLIT_RE = re.compile(r"\n---\s*\n", re.DOTALL)
_MAX_RESULT_EVIDENCE_CHARS = 240


def _extend_raw_skill_candidates(target: list[Any], value: Any) -> None:
    if not value:
        return
    if isinstance(value, (list, tuple)):
        target.extend(value)
    else:
        target.append(value)


# ─────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class InheritedSkillCandidate:
    """A reusable playbook a sub-agent proposes back to its parent."""

    name: str
    description: str = ""
    body: str = ""
    tags: list[str] = field(default_factory=list)
    operation: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: Any) -> InheritedSkillCandidate | None:
        if isinstance(raw, cls):
            return raw
        if not isinstance(raw, dict):
            return None
        name = str(raw.get("name") or raw.get("skill") or "").strip()
        body = str(raw.get("body") or raw.get("playbook") or raw.get("steps") or "").strip()
        if not name or not body:
            return None
        tags = raw.get("tags") or []
        if isinstance(tags, str):
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        elif isinstance(tags, list):
            tag_list = [str(t).strip() for t in tags if str(t).strip()]
        else:
            tag_list = []
        return cls(
            name=name,
            description=str(raw.get("description") or "").strip(),
            body=body,
            tags=tag_list,
            operation=(
                str(raw.get("operation") or raw.get("agentdrive_operation") or "").strip() or None
            ),
            evidence=dict(raw.get("evidence") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InheritanceManifest:
    """A single sub-agent's report of what it learned in one mission."""

    subagent_id: str = ""
    swarm_id: str = ""
    genomes_pulled: list[str] = field(default_factory=list)
    genomes_created: list[str] = field(default_factory=list)
    skills_created: list[InheritedSkillCandidate] = field(default_factory=list)
    outcomes_logged: list[dict[str, Any]] = field(default_factory=list)
    duration_s: float = 0.0
    created_at: str = field(default_factory=_utc_now_iso)

    def to_json(self) -> str:
        payload = asdict(self)
        payload["skills_created"] = [s.to_dict() for s in self.skills_created]
        return json.dumps(payload, indent=2, default=str)

    @classmethod
    def from_json(cls, data: str | bytes) -> InheritanceManifest:
        raw = json.loads(data)
        skills = [
            skill
            for skill in (
                InheritedSkillCandidate.from_raw(s) for s in raw.get("skills_created", []) or []
            )
            if skill is not None
        ]
        return cls(
            subagent_id=str(raw.get("subagent_id", "") or ""),
            swarm_id=str(raw.get("swarm_id", "") or ""),
            genomes_pulled=list(raw.get("genomes_pulled", []) or []),
            genomes_created=list(raw.get("genomes_created", []) or []),
            skills_created=skills,
            outcomes_logged=list(raw.get("outcomes_logged", []) or []),
            duration_s=float(raw.get("duration_s", 0.0) or 0.0),
            created_at=str(raw.get("created_at", "") or _utc_now_iso()),
        )


def extract_skill_candidates_from_result(
    result: Any,
    *,
    task: str = "",
) -> list[InheritedSkillCandidate]:
    """Extract explicit AgentDrive skill proposals from a sub-agent result.

    Sub-agents can return fenced blocks shaped like::

        ```agentdrive-skill
        name: incident-retrospective-playbook
        description: Reusable incident review handoff
        tags: [incident, retrospective]
        ---
        # Incident Retrospective Playbook
        ...
        ```

    The parser is intentionally opt-in. We do not turn every long sub-agent
    response into a skill, because that would pollute the parent bench with
    low-signal transcript fragments.
    """
    raw_candidates: list[Any] = []
    text_parts: list[str] = []
    if isinstance(result, dict):
        _extend_raw_skill_candidates(raw_candidates, result.get("skills_created"))
        _extend_raw_skill_candidates(raw_candidates, result.get("agentdrive_skills"))
        for key in ("result", "summary", "text", "content", "output"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                text_parts.append(value)
    elif isinstance(result, (list, tuple)):
        for item in result:
            if isinstance(item, dict):
                raw_candidates.append(item)
            elif isinstance(item, str):
                text_parts.append(item)
    elif isinstance(result, str):
        text_parts.append(result)
    elif result is not None:
        text_parts.append(str(result))

    candidates: list[InheritedSkillCandidate] = []
    for raw in raw_candidates:
        candidate = InheritedSkillCandidate.from_raw(raw)
        if candidate is not None:
            candidates.append(candidate)

    for text in text_parts:
        candidates.extend(_extract_skill_blocks(text, task=task))

    deduped: dict[str, InheritedSkillCandidate] = {}
    for candidate in candidates:
        key = candidate.name.strip().lower()
        if key and key not in deduped:
            deduped[key] = candidate
    return list(deduped.values())


def _extract_skill_blocks(text: str, *, task: str = "") -> list[InheritedSkillCandidate]:
    candidates: list[InheritedSkillCandidate] = []
    for match in _SKILL_BLOCK_RE.finditer(text):
        block = match.group(1).strip()
        header_text = ""
        body = block
        parts = _SKILL_BLOCK_SPLIT_RE.split(block, maxsplit=1)
        if len(parts) == 2:
            header_text, body = parts[0].strip(), parts[1].strip()
        meta: dict[str, Any] = {}
        if header_text:
            try:
                loaded = yaml.safe_load(header_text) or {}
                if isinstance(loaded, dict):
                    meta = loaded
            except yaml.YAMLError:
                logger.debug("Failed to parse inherited skill block header", exc_info=True)

        evidence = dict(meta.get("evidence") or {})
        if task and "source_task" not in evidence:
            evidence["source_task"] = task[:_MAX_RESULT_EVIDENCE_CHARS]
        evidence.setdefault("source", "subagent_result")
        raw = {
            "name": meta.get("name") or meta.get("skill"),
            "description": meta.get("description") or "",
            "tags": meta.get("tags") or [],
            "operation": meta.get("operation") or meta.get("agentdrive_operation"),
            "body": body,
            "evidence": evidence,
        }
        candidate = InheritedSkillCandidate.from_raw(raw)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def write_subagent_result_manifest(
    *,
    swarm_id: str,
    subagent_id: str,
    task: str,
    result: Any,
    duration_s: float = 0.0,
) -> InheritanceManifest | None:
    """Merge explicit skill proposals from a sub-agent result into its manifest.

    This is the runtime ferry between Hermes-style sub-agent handoffs and the
    parent AgentDrive skill pool. It writes before ``SubagentDone`` so the
    existing inheritance subscriber can absorb the manifest normally.
    """
    skills = extract_skill_candidates_from_result(result, task=task)
    if not skills:
        return None

    path = manifest_path(swarm_id, subagent_id)
    manifest: InheritanceManifest
    if path.is_file():
        try:
            manifest = InheritanceManifest.from_json(path.read_text(encoding="utf-8"))
        except Exception:
            logger.debug("Failed to merge existing inheritance manifest %s", path, exc_info=True)
            manifest = InheritanceManifest(subagent_id=subagent_id, swarm_id=swarm_id)
    else:
        manifest = InheritanceManifest(subagent_id=subagent_id, swarm_id=swarm_id)

    manifest.subagent_id = manifest.subagent_id or subagent_id
    manifest.swarm_id = manifest.swarm_id or swarm_id
    if duration_s:
        manifest.duration_s = max(float(manifest.duration_s or 0.0), float(duration_s))

    existing = {skill.name.strip().lower() for skill in manifest.skills_created}
    for skill in skills:
        key = skill.name.strip().lower()
        if key and key not in existing:
            manifest.skills_created.append(skill)
            existing.add(key)

    _write_manifest(manifest)
    return manifest


@dataclass
class InheritanceResult:
    """Outcome of recording (and optionally absorbing) a manifest."""

    manifest: InheritanceManifest
    genomes_absorbed: list[str] = field(default_factory=list)
    genomes_rejected: list[str] = field(default_factory=list)
    skills_absorbed: list[str] = field(default_factory=list)
    skills_rejected: list[str] = field(default_factory=list)
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
    skill_outcome_success: bool | None = None,
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
        ``agentdrive quarantine approve``. Set this in peer-federation adapters
        and any other code path that receives DNA from outside the local
        instance.

    If ``skill_outcome_success`` is supplied, every installed inherited skill
    also records one usage outcome. The successful ``SubagentDone`` hook passes
    ``True`` here, giving the curation loop evidence that the playbook came from
    a completed child task. Manual manifest imports leave it unset unless the
    caller has its own outcome signal.

    Each absorbed genome triggers the existing ``PoolIngest`` event with
    ``source="inheritance:<subagent_id>"`` so subscribers can render it on
    the audit ribbon. A summary ``InheritanceReceived`` event fires once
    the manifest has been processed.
    """
    _write_manifest(manifest)

    absorbed: list[str] = []
    rejected: list[str] = []
    skills_absorbed: list[str] = []
    skills_rejected: list[str] = []
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

        for skill in manifest.skills_created:
            key = f"skill:{skill.name}"
            if quarantine_external:
                skills_rejected.append(skill.name)
                reasons[key] = "external inherited skills require review before install"
                continue
            try:
                from agentdrive.skills.registry import install_inherited_skill

                install_inherited_skill(
                    name=skill.name,
                    description=skill.description,
                    body=skill.body,
                    tags=skill.tags,
                    operation=skill.operation,
                    swarm_id=manifest.swarm_id,
                    source_subagent_id=manifest.subagent_id,
                    update_existing=True,
                )
                skills_absorbed.append(skill.name)
                if skill_outcome_success is not None:
                    try:
                        from agentdrive.skills.usage import record_skill_run

                        record_skill_run(
                            skill.name,
                            success=bool(skill_outcome_success),
                            source=(
                                f"inheritance:{manifest.swarm_id or 'default'}:"
                                f"{manifest.subagent_id or 'subagent'}"
                            ),
                        )
                    except Exception:
                        logger.debug(
                            "Failed to record inherited skill outcome for %s",
                            skill.name,
                            exc_info=True,
                        )
                try:
                    emit(
                        InheritanceAbsorbed(
                            skill_name=skill.name,
                            source_subagent_id=manifest.subagent_id,
                            parent_pool=getattr(target_pool, "name", "main"),
                            swarm_id=manifest.swarm_id or None,
                            subagent_id=manifest.subagent_id or None,
                        )
                    )
                except Exception:
                    logger.debug("Failed to emit skill InheritanceAbsorbed", exc_info=True)
            except Exception as exc:
                skills_rejected.append(skill.name)
                reasons[key] = f"skill install failed: {str(exc)[:80]}"

    try:
        emit(
            InheritanceReceived(
                genomes_absorbed=list(absorbed),
                genomes_rejected=list(rejected),
                skills_absorbed=list(skills_absorbed),
                skills_rejected=list(skills_rejected),
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
        skills_absorbed=skills_absorbed,
        skills_rejected=skills_rejected,
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
            skill_outcome_success=True,
        )
    except Exception:
        logger.debug(
            "record_manifest failed for %s/%s",
            manifest.swarm_id,
            manifest.subagent_id,
            exc_info=True,
        )
        return

    _auto_assimilate_completed_skills(manifest, target_pool=target)


def _auto_assimilate_completed_skills(
    manifest: InheritanceManifest,
    *,
    target_pool: AgentDrive,
) -> None:
    """Run the gated parent-bench assimilation pass for completed child skills."""
    if not manifest.skills_created:
        return
    flag = os.environ.get("AGENTDRIVE_AUTO_ASSIMILATE_SKILLS", "1").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return
    try:
        from agentdrive.skills.curation import assimilate_inherited_skills

        report = assimilate_inherited_skills(
            target_drive=target_pool,
            ingest_dna=True,
            prune=False,
            include_promoted=False,
            skill_names=[skill.name for skill in manifest.skills_created],
        )
    except Exception:
        logger.debug(
            "auto skill assimilation failed for %s/%s",
            manifest.swarm_id,
            manifest.subagent_id,
            exc_info=True,
        )
        return

    promoted = [item.name for item in report.promoted]
    dna_genomes = [item.genome_id for item in report.dna_exports]
    pruned = [item.get("skill_name", "") for item in report.pruned if item.get("skill_name")]
    if not (promoted or dna_genomes or pruned or report.errors):
        return
    try:
        emit(
            SkillAssimilated(
                promoted_skills=promoted,
                dna_genomes=dna_genomes,
                pruned_skills=pruned,
                errors=list(report.errors),
                swarm_id=manifest.swarm_id or None,
                subagent_id=manifest.subagent_id or None,
            )
        )
    except Exception:
        logger.debug("Failed to emit SkillAssimilated", exc_info=True)


# Subscribe once at import time. Using try/except so an import-order quirk
# never breaks downstream callers.
try:
    _INHERITANCE_SUBSCRIPTION = subscribe(_on_subagent_done, [SubagentDone])
except Exception:
    logger.debug("Failed to subscribe inheritance hook", exc_info=True)
    _INHERITANCE_SUBSCRIPTION = None


__all__ = [
    "InheritedSkillCandidate",
    "InheritanceManifest",
    "InheritanceResult",
    "extract_skill_candidates_from_result",
    "write_subagent_result_manifest",
    "record_manifest",
    "list_manifests",
    "load_manifest",
    "manifest_path",
    "INHERITANCE_DIR_NAME",
]
