"""
Growth merge — experience + pattern recognition + memory compounding.

When AgentDrive work spans structural experience, codebase patterns, and
distilled skills, this module recognizes recurring shapes and merges them into
one growth artifact: compound memory, relations, and optional born skills.

Same integration pattern as the Memory Bank layer: native naming, auto-ingest,
scoped vault/topic storage, and queryable briefings — not a port of external metaphors.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agentdrive.learning.auto_absorb import LearningSession

logger = logging.getLogger(__name__)

_GROWTH_VAULT = "growth"
_GROWTH_TOPIC = "merge"
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]{2,}")

_EXPERIENCE_OPS = frozenset(
    {
        "experience_graph_context_pack",
        "experience_graph_record_reasoning",
        "think",
        "external_parent_decision",
        "multiverse_parent_decision",
        "multiverse_run_full",
        "record_outcome",
        "learnings_log",
    }
)

_PATTERN_OPS = frozenset(
    {
        "codebase_observe_file",
        "codebase_patterns_profile",
        "codebase_mimic",
        "codebase_transform_style",
        "codebase_mirror_resonance",
        "codebase_patterns_match",
    }
)


def _flag(name: str, default: str = "1") -> bool:
    raw = os.environ.get(name, default).strip().lower()
    return raw not in {"0", "false", "no", "off"}


def growth_merge_enabled() -> bool:
    return _flag("AGENTDRIVE_AUTO_GROWTH_MERGE", "1") and _flag("AGENTDRIVE_AUTO_LEARN", "1")


@dataclass
class GrowthAxes:
    """Which compounding surfaces contributed to a growth merge."""

    experience: bool = False
    patterns: bool = False
    skills: bool = False
    memory: bool = False

    def present(self) -> set[str]:
        axes: set[str] = set()
        if self.experience:
            axes.add("experience")
        if self.patterns:
            axes.add("patterns")
        if self.skills:
            axes.add("skills")
        if self.memory:
            axes.add("memory")
        return axes

    def merge_ready(self) -> bool:
        return len(self.present()) >= 2


@dataclass
class RecognizedPattern:
    """A recurring structural signal detected across growth surfaces."""

    source: str
    label: str
    score: float
    evidence: str
    link_type: str = "pattern"
    link_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "label": self.label,
            "score": self.score,
            "evidence": self.evidence,
            "link_type": self.link_type,
            "link_id": self.link_id,
        }


@dataclass
class GrowthMergeRecord:
    """Unified growth artifact from a compounding session."""

    trigger: str
    swarm_id: str
    program_id: str
    axes: GrowthAxes
    operations: list[str] = field(default_factory=list)
    experience_traces: list[str] = field(default_factory=list)
    pattern_projects: list[str] = field(default_factory=list)
    source_skills: list[str] = field(default_factory=list)
    recognized_patterns: list[RecognizedPattern] = field(default_factory=list)
    memory_hits: list[dict[str, Any]] = field(default_factory=list)
    fused_skill: str | None = None
    memory_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger": self.trigger,
            "swarm_id": self.swarm_id,
            "program_id": self.program_id,
            "axes": sorted(self.axes.present()),
            "operations": self.operations,
            "experience_traces": self.experience_traces,
            "pattern_projects": self.pattern_projects,
            "source_skills": self.source_skills,
            "recognized_patterns": [p.to_dict() for p in self.recognized_patterns],
            "memory_hits": self.memory_hits,
            "fused_skill": self.fused_skill,
            "memory_id": self.memory_id,
        }


def axes_from_session(session: LearningSession) -> GrowthAxes:
    ops = [op for op, _ in session.ops]
    return GrowthAxes(
        experience=bool(session.experience_traces)
        or any(op in _EXPERIENCE_OPS for op in ops),
        patterns=bool(session.pattern_projects) or any(op in _PATTERN_OPS for op in ops),
        skills=bool(session.distilled_skills or session.referenced_skills),
        memory=bool(session.fused_skill_name),
    )


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _recognize_from_memory(
    swarm_id: str,
    trigger: str,
    *,
    limit: int = 5,
) -> tuple[list[RecognizedPattern], list[dict[str, Any]]]:
    from agentdrive.memory.store import MemoryBankStore

    if not trigger.strip():
        return [], []

    store = MemoryBankStore(swarm_id)
    hits = store.search(trigger, limit=limit)
    patterns: list[RecognizedPattern] = []
    memory_hits: list[dict[str, Any]] = []
    trigger_tokens = _tokenize(trigger)

    for hit in hits:
        memory_hits.append(
            {
                "memory_id": hit.memory_id,
                "kind": hit.kind,
                "title": hit.title,
                "vault": hit.vault,
                "topic": hit.topic,
            }
        )
        haystack = _tokenize(f"{hit.title} {hit.content} {' '.join(hit.tags)}")
        overlap = len(trigger_tokens & haystack)
        if overlap == 0:
            continue
        score = min(1.0, overlap / max(len(trigger_tokens), 1))
        patterns.append(
            RecognizedPattern(
                source="memory_bank",
                label=hit.title[:80],
                score=round(score, 3),
                evidence=f"{overlap} token overlap with prior {hit.kind}",
                link_type="memory",
                link_id=hit.memory_id,
            )
        )
    return patterns, memory_hits


def _recognize_from_codebase(project_ids: list[str]) -> list[RecognizedPattern]:
    from agentdrive.codebase.framework import get_writing_guide

    patterns: list[RecognizedPattern] = []
    for project_id in project_ids[:3]:
        try:
            framework = get_writing_guide(project_id)
        except Exception:
            logger.debug("growth merge framework load failed for %s", project_id, exc_info=True)
            continue
        for pat in (framework.get("patterns") or [])[:4]:
            if not isinstance(pat, dict):
                continue
            rule = str(pat.get("rule") or "")
            category = str(pat.get("category") or "pattern")
            if not rule:
                continue
            patterns.append(
                RecognizedPattern(
                    source="codebase",
                    label=f"{project_id}:{category}",
                    score=0.75,
                    evidence=rule[:200],
                    link_type="codebase_project",
                    link_id=project_id,
                )
            )
    return patterns


def _recognize_from_experience(
    swarm_id: str,
    trigger: str,
    traces: list[str],
) -> list[RecognizedPattern]:
    patterns: list[RecognizedPattern] = []
    for trace in traces[:5]:
        patterns.append(
            RecognizedPattern(
                source="experience_graph",
                label=trace[:80],
                score=0.82,
                evidence="Prior fabric reasoning trace in this session",
                link_type="fabric_trace",
                link_id=trace,
            )
        )

    element = _TOKEN_RE.sub("-", trigger.lower()).strip("-")[:40] or "growth-merge"
    try:
        from agentdrive.operations.registry import _integrated_recorder

        _, recorder = _integrated_recorder(swarm_id)
        matches = recorder.find_structural_similarities(element, lookback=8, min_similarity=0.55)
        for match in matches[:4]:
            patterns.append(
                RecognizedPattern(
                    source="experience_graph",
                    label=str(match.get("matched_element") or "structural_match"),
                    score=float(match.get("similarity") or 0.6),
                    evidence=str(match.get("evidence") or "structural similarity"),
                    link_type="fabric_element",
                    link_id=str(match.get("cycle_id") or element),
                )
            )
    except Exception:
        logger.debug("structural similarity recognition skipped", exc_info=True)

    return patterns


def recognize_growth_patterns(
    *,
    swarm_id: str,
    trigger: str,
    session: LearningSession | None = None,
    experience_traces: list[str] | None = None,
    pattern_projects: list[str] | None = None,
) -> list[RecognizedPattern]:
    """Detect recurring shapes across memory, codebase, and experience surfaces."""
    recognized: list[RecognizedPattern] = []
    traces = list(experience_traces or [])
    projects = list(pattern_projects or [])
    if session is not None:
        traces = list(dict.fromkeys(traces + session.experience_traces))
        projects = list(dict.fromkeys(projects + session.pattern_projects))

    mem_patterns, _ = _recognize_from_memory(swarm_id, trigger)
    recognized.extend(mem_patterns)
    recognized.extend(_recognize_from_codebase(projects))
    recognized.extend(_recognize_from_experience(swarm_id, trigger, traces))

    seen: set[str] = set()
    unique: list[RecognizedPattern] = []
    for item in sorted(recognized, key=lambda p: p.score, reverse=True):
        key = f"{item.source}|{item.label}|{item.link_id}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:12]


def _record_growth_relations(
    record: GrowthMergeRecord,
) -> list[str]:
    from agentdrive.memory.relations import MemoryRelationGraph

    graph = MemoryRelationGraph(record.swarm_id)
    relation_ids: list[str] = []
    subject = record.trigger[:80] or "growth-session"

    for pattern in record.recognized_patterns[:6]:
        if not pattern.link_id:
            continue
        rel = graph.record(
            subject,
            "recognizes",
            pattern.label[:120],
            memory_id=record.memory_id,
        )
        relation_ids.append(rel.relation_id)
    return relation_ids


def _store_growth_memory(record: GrowthMergeRecord) -> str | None:
    from agentdrive.memory.store import MemoryBankStore

    axes = ", ".join(sorted(record.axes.present()))
    lines = [
        f"Growth merge for: {record.trigger}",
        f"Axes compounded: {axes}",
        f"Operations: {', '.join(record.operations[:10])}",
    ]
    if record.experience_traces:
        lines.append(f"Experience traces: {', '.join(record.experience_traces[:5])}")
    if record.pattern_projects:
        lines.append(f"Pattern projects: {', '.join(record.pattern_projects)}")
    if record.source_skills:
        lines.append(f"Skills merged: {', '.join(record.source_skills)}")
    if record.fused_skill:
        lines.append(f"Born skill: {record.fused_skill}")

    lines.append("")
    lines.append("Recognized patterns:")
    for pat in record.recognized_patterns[:8]:
        lines.append(f"- [{pat.source}] {pat.label} ({pat.score:.0%}): {pat.evidence[:120]}")

    content = "\n".join(lines).strip()
    title = f"Growth merge: {record.trigger[:80]}" if record.trigger else "Growth merge"
    store = MemoryBankStore(record.swarm_id)
    if store.has_similar(title, content):
        return None

    links: list[dict[str, str]] = []
    for pat in record.recognized_patterns[:6]:
        if pat.link_id:
            links.append({"type": pat.link_type, "id": pat.link_id})
    if record.fused_skill:
        links.append({"type": "skill", "id": record.fused_skill})

    entry = store.store(
        kind="insight",
        title=title,
        content=content,
        confidence=0.88,
        source="growth_merge",
        program_id=record.program_id,
        tags=["growth-merge", *sorted(record.axes.present())],
        links=links,
        vault=_GROWTH_VAULT,
        topic=_GROWTH_TOPIC,
        preserves_source=False,
    )
    return entry.memory_id


def merge_session_growth(
    session: LearningSession,
    *,
    trigger: str,
    fused_skill: dict[str, Any] | None = None,
) -> GrowthMergeRecord | None:
    """Merge experience, patterns, and skills into one growth artifact."""
    if not growth_merge_enabled():
        return None

    axes = axes_from_session(session)
    if fused_skill:
        axes.memory = True
    if not axes.merge_ready():
        return None

    ops = [op for op, _ in session.ops]
    source_skills = list(dict.fromkeys(session.distilled_skills + session.referenced_skills))
    recognized = recognize_growth_patterns(
        swarm_id=session.swarm_id,
        trigger=trigger,
        session=session,
    )
    _, memory_hits = _recognize_from_memory(session.swarm_id, trigger)

    record = GrowthMergeRecord(
        trigger=trigger,
        swarm_id=session.swarm_id,
        program_id=session.program_id,
        axes=axes,
        operations=ops,
        experience_traces=list(session.experience_traces),
        pattern_projects=list(session.pattern_projects),
        source_skills=source_skills,
        recognized_patterns=recognized,
        memory_hits=memory_hits,
        fused_skill=(fused_skill or {}).get("name"),
    )

    memory_id = _store_growth_memory(record)
    if not memory_id:
        return None
    record.memory_id = memory_id
    _record_growth_relations(record)
    return record


def build_growth_briefing(
    swarm_id: str,
    *,
    query: str = "",
    limit: int = 8,
) -> dict[str, Any]:
    """Unified growth briefing: experience fabric + pattern recognition + memory bank."""
    from agentdrive.memory.briefing import build_deep_briefing
    from agentdrive.memory.store import MemoryBankStore

    deep = build_deep_briefing(swarm_id, query=query, memory_limit=limit)
    trigger = query or "session growth"
    recognized = recognize_growth_patterns(swarm_id=swarm_id, trigger=trigger)

    growth_memories = MemoryBankStore(swarm_id).search(
        query or "growth merge",
        limit=limit,
        vault=_GROWTH_VAULT,
        topic=_GROWTH_TOPIC,
    )

    pattern_lines = [
        f"- [{p.source}] {p.label} ({p.score:.0%}): {p.evidence[:100]}"
        for p in recognized[:6]
    ]
    growth_section = "\n".join(pattern_lines) if pattern_lines else "No cross-surface patterns detected yet."

    return {
        "swarm_id": swarm_id,
        "query": query,
        "axes_integrated": ["experience_graph", "codebase_patterns", "skills", "memory_bank"],
        "recognized_patterns": [p.to_dict() for p in recognized],
        "growth_memories": [m.to_dict() for m in growth_memories],
        "fabric_context_pack": deep.get("fabric_context_pack"),
        "memory_bank": deep.get("memory_bank"),
        "growth_briefing": (
            "## Growth merge (experience + patterns + memory)\n"
            f"{growth_section}\n\n"
            "## Structural memory\n"
            f"{deep.get('deep_briefing', '')[:3000]}"
        )[:6000],
        "pattern_count": len(recognized),
        "growth_memory_count": len(growth_memories),
    }


def maybe_merge_growth(
    session: LearningSession,
    *,
    trigger: str,
    fused_skill: dict[str, Any] | None = None,
    last_operation: str,
) -> dict[str, Any] | None:
    """Post-absorb hook: compound session growth when multiple axes are present."""
    if not growth_merge_enabled():
        return None
    terminal = last_operation in {
        "external_parent_decision",
        "multiverse_parent_decision",
        "codebase_mimic",
        "think",
        "record_outcome",
        "experience_graph_record_reasoning",
        "synthesize_fused_skill",
    }
    if not terminal and len(session.ops) < 3:
        return None
    record = merge_session_growth(session, trigger=trigger, fused_skill=fused_skill)
    if record is None:
        return None
    return record.to_dict()