"""Auto-ingest AgentDrive surfaces into the Memory Bank."""

from __future__ import annotations

import logging
import os
from typing import Any

from agentdrive.memory.store import MemoryBankStore

logger = logging.getLogger(__name__)

_OP_MEMORY_MAP: dict[str, tuple[str, str]] = {
    "think": ("insight", "Synthesis"),
    "external_parent_decision": ("decision", "Multiverse collapse"),
    "multiverse_parent_decision": ("decision", "Parent decision"),
    "experience_graph_record_reasoning": ("insight", "Structural reasoning"),
    "record_outcome": ("episode", "Outcome"),
    "learnings_log": ("learning", "Operational learning"),
    "codebase_observe_file": ("pattern", "Codebase observation"),
    "codebase_mimic": ("pattern", "Mirror-neuron mimicry"),
    "codebase_patterns_profile": ("pattern", "Writing framework"),
    "synthesize_fused_skill": ("born_skill", "Born skill"),
}


def memory_ingest_enabled() -> bool:
    raw = os.environ.get("AGENTDRIVE_AUTO_MEMORY_BANK", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _trigger_text(kwargs: dict[str, Any], result: dict[str, Any]) -> str:
    for key in ("trigger", "question", "task", "text", "title", "insight"):
        val = kwargs.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    nested = result.get("result")
    if isinstance(nested, dict):
        for key in ("trigger", "question", "directive"):
            val = nested.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


def _build_memory_from_operation(
    operation: str,
    kwargs: dict[str, Any],
    result: dict[str, Any],
    *,
    swarm_id: str,
    program_id: str,
) -> dict[str, Any] | None:
    kind, label = _OP_MEMORY_MAP.get(operation, ("insight", operation.replace("_", " ")))
    trigger = _trigger_text(kwargs, result)
    title = trigger[:120] if trigger else label

    content_parts: list[str] = []
    links: list[dict[str, str]] = []
    tags = ["auto-ingest", operation.replace("_", "-")]

    nested = result.get("result")
    if operation == "think" and isinstance(nested, dict):
        answer = str(nested.get("answer") or "")
        gaps = nested.get("gaps") or []
        if answer:
            content_parts.append(answer[:1200])
        if gaps:
            content_parts.append(f"Gaps: {gaps[0]}")
    elif operation in ("external_parent_decision", "multiverse_parent_decision") and isinstance(
        nested, dict
    ):
        decision = nested.get("decision") or {}
        directive = decision.get("directive", "") if isinstance(decision, dict) else ""
        session_id = nested.get("session_id", "")
        if directive:
            content_parts.append(f"Directive: {directive}")
        if session_id:
            content_parts.append(f"Session: {session_id}")
            links.append({"type": "multiverse_session", "id": session_id})
    elif operation == "experience_graph_record_reasoning":
        reasoning = kwargs.get("reasoning") or {}
        if isinstance(reasoning, dict):
            rationale = str(reasoning.get("decision_rationale") or reasoning.get("summary") or "")
            if rationale:
                content_parts.append(rationale[:1000])
        trace = result.get("trace_slug")
        if trace:
            links.append({"type": "fabric_trace", "id": str(trace)})
    elif operation == "learnings_log":
        insight = str(kwargs.get("insight") or "")
        key = str(kwargs.get("key") or "")
        if insight:
            content_parts.append(insight)
        if key:
            title = f"Learning: {key}"
    elif operation in ("codebase_observe_file", "codebase_mimic", "codebase_patterns_profile"):
        project_id = str(kwargs.get("project_id") or result.get("project_id") or "")
        mimic = str(result.get("mimicry_prompt") or "")
        framework = result.get("framework") or {}
        if project_id:
            tags.append(project_id)
            links.append({"type": "codebase_project", "id": project_id})
        if mimic:
            content_parts.append(mimic[:800])
        elif isinstance(framework, dict):
            patterns = framework.get("patterns") or []
            for pat in patterns[:4]:
                if isinstance(pat, dict):
                    content_parts.append(f"[{pat.get('category')}] {pat.get('rule')}")
    elif operation == "synthesize_fused_skill":
        fused = result.get("fused_skill") or {}
        axes = fused.get("axes") or []
        name = fused.get("name") or ""
        if name:
            title = f"Born skill: {name}"
            content_parts.append(f"Fused axes: {', '.join(axes)}")
            links.append({"type": "skill", "id": name})
    elif result.get("auto_learning"):
        auto = result["auto_learning"]
        if auto.get("fused_skill"):
            fused = auto["fused_skill"]
            content_parts.append(f"Born skill {fused.get('name')} from session fusion.")
            links.append({"type": "skill", "id": str(fused.get("name"))})
        if auto.get("reasoning_trace"):
            links.append({"type": "fabric_trace", "id": str(auto["reasoning_trace"])})

    if not content_parts:
        content_parts.append(f"Successful {operation}" + (f": {trigger}" if trigger else ""))

    content = "\n".join(content_parts).strip()
    if not content:
        return None

    return {
        "kind": kind,
        "title": title,
        "content": content,
        "confidence": 0.8 if operation in _OP_MEMORY_MAP else 0.65,
        "source": f"auto_absorb:{operation}",
        "program_id": program_id,
        "tags": tags,
        "links": links,
    }


def ingest_from_operation(
    operation: str,
    kwargs: dict[str, Any],
    result: dict[str, Any],
    *,
    swarm_id: str,
    program_id: str = "",
) -> dict[str, Any] | None:
    """Write a memory atom from a successful AgentDrive operation."""
    if not memory_ingest_enabled():
        return None
    if not isinstance(result, dict) or not result.get("success"):
        return None

    payload = _build_memory_from_operation(
        operation, kwargs, result, swarm_id=swarm_id, program_id=program_id
    )
    if not payload:
        return None

    store = MemoryBankStore(swarm_id)
    if store.has_similar(payload["title"], payload["content"]):
        return {"skipped": True, "reason": "similar_memory_exists"}

    entry = store.store(**payload)
    return {"memory_id": entry.memory_id, "kind": entry.kind, "title": entry.title}


def ingest_from_fused_skill(
    fused: dict[str, Any],
    *,
    swarm_id: str,
    program_id: str,
    trigger: str,
) -> dict[str, Any] | None:
    if not memory_ingest_enabled():
        return None
    name = fused.get("name") or "fused-skill"
    axes = ", ".join(fused.get("axes") or [])
    store = MemoryBankStore(swarm_id)
    title = f"Born skill memory: {name}"
    content = (
        f"Trigger: {trigger}\n"
        f"Born skill `{name}` synthesized from axes: {axes}.\n"
        f"Parent skills: {', '.join(fused.get('source_skills') or [])}\n"
        f"Pattern projects: {', '.join(fused.get('pattern_projects') or [])}"
    )
    if store.has_similar(title, content):
        return None
    entry = store.store(
        kind="born_skill",
        title=title,
        content=content,
        confidence=0.85,
        source="skill_fusion",
        program_id=program_id,
        tags=["born-skill", "fused"],
        links=[{"type": "skill", "id": name}],
    )
    return {"memory_id": entry.memory_id, "kind": entry.kind}


def ingest_from_learning(entry: dict[str, Any], *, swarm_id: str) -> dict[str, Any] | None:
    if not memory_ingest_enabled():
        return None
    key = str(entry.get("key") or "learning")
    insight = str(entry.get("insight") or "")
    if not insight:
        return None
    store = MemoryBankStore(swarm_id)
    title = f"Learning: {key}"
    if store.has_similar(title, insight):
        return None
    mem = store.store(
        kind="learning",
        title=title,
        content=insight,
        confidence=min(1.0, int(entry.get("confidence") or 5) / 10.0),
        source="learnings",
        tags=["learning", str(entry.get("type") or "operational")],
    )
    return {"memory_id": mem.memory_id}
