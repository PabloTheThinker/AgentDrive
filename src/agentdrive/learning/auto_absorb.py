"""
End-to-end automatic learning for AgentDrive operations.

Whenever an AI uses AgentDrive via MCP or CLI (``run_operation``), this module:
1. Tracks session context (context pack pulled, ops run).
2. Auto-records minimal fabric reasoning when the model did not call
   ``experience_graph_record_reasoning`` on a high-signal mutating op.
3. Distills reusable inherited skills from successful outcomes (Hermes-style ferry
   for parent MCP sessions, not only sub-agents).
4. Promotes + ingests proven auto-learned skills into DNA when enabled.

Disable with ``AGENTDRIVE_AUTO_LEARN=0`` (master switch).
Finer control: ``AGENTDRIVE_AUTO_RECORD_REASONING``, ``AGENTDRIVE_AUTO_DISTILL_SKILLS``,
``AGENTDRIVE_AUTO_ASSIMILATE_SKILLS`` (existing).
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_MCP_SUBAGENT_ID = "mcp-auto-learning"

# Ops that already write Parent DNA / fabric traces — skip duplicate auto-reasoning.
_SELF_RECORDING_OPS = frozenset(
    {
        "experience_graph_record_reasoning",
        "external_parent_decision",
        "multiverse_parent_decision",
        "multiverse_run_full",
    }
)

# Successful outcomes on these ops distill + promote skills automatically.
_HIGH_SIGNAL_OPS = frozenset(
    {
        "external_parent_decision",
        "multiverse_parent_decision",
        "experience_graph_record_reasoning",
        "think",
        "record_outcome",
        "codebase_observe_file",
        "codebase_patterns_profile",
        "codebase_mimic",
    }
)

_CODEBASE_OPS = frozenset(
    {
        "codebase_observe_file",
        "codebase_patterns_profile",
        "codebase_register_project",
        "codebase_mimic",
        "codebase_transform_style",
        "codebase_mirror_resonance",
    }
)

_MIRROR_HIGH_SIGNAL = frozenset({"codebase_mimic", "codebase_observe_file"})

# Mutating ops that benefit from a lightweight reasoning trace when none was recorded.
_AUTO_REASONING_OPS = frozenset(
    {
        "think",
        "record_outcome",
        "pool_query",
        "propose_improvement",
        "ingest_genome",
        "codebase_observe_file",
        "codebase_patterns_match",
    }
)

_SESSION_START_OPS = frozenset({"experience_graph_context_pack", "think"})

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _flag(name: str, default: str = "1") -> bool:
    raw = os.environ.get(name, default).strip().lower()
    return raw not in {"0", "false", "no", "off"}


def auto_learn_enabled() -> bool:
    return _flag("AGENTDRIVE_AUTO_LEARN", "1")


def auto_record_reasoning_enabled() -> bool:
    return auto_learn_enabled() and _flag("AGENTDRIVE_AUTO_RECORD_REASONING", "1")


def auto_distill_skills_enabled() -> bool:
    return auto_learn_enabled() and _flag("AGENTDRIVE_AUTO_DISTILL_SKILLS", "1")


def auto_assimilate_enabled() -> bool:
    return _flag("AGENTDRIVE_AUTO_ASSIMILATE_SKILLS", "1")


@dataclass
class LearningSession:
    swarm_id: str
    program_id: str
    started_at: float = field(default_factory=time.time)
    context_pack_pulled: bool = False
    reasoning_recorded: bool = False
    ops: list[tuple[str, str]] = field(default_factory=list)
    experience_traces: list[str] = field(default_factory=list)
    distilled_skills: list[str] = field(default_factory=list)
    referenced_skills: list[str] = field(default_factory=list)
    pattern_projects: list[str] = field(default_factory=list)
    fused_skill_name: str | None = None
    growth_merged: bool = False


_SESSIONS: dict[tuple[str, str], LearningSession] = {}


def _session_key(swarm_id: str, program_id: str) -> tuple[str, str]:
    return (swarm_id, program_id or _MCP_SUBAGENT_ID)


def _get_session(swarm_id: str, program_id: str | None) -> LearningSession:
    key = _session_key(swarm_id, program_id or _MCP_SUBAGENT_ID)
    session = _SESSIONS.get(key)
    if session is None:
        session = LearningSession(swarm_id=swarm_id, program_id=program_id or _MCP_SUBAGENT_ID)
        _SESSIONS[key] = session
    return session


def _effective_swarm(kwargs: dict[str, Any], result: dict[str, Any]) -> str:
    return str(
        result.get("swarm_id")
        or kwargs.get("swarm_id")
        or "stabilization-wave-20260531"
    )


def _program_id(kwargs: dict[str, Any]) -> str:
    return str(kwargs.get("program_id") or _MCP_SUBAGENT_ID)


def _trigger_text(kwargs: dict[str, Any], result: dict[str, Any]) -> str:
    for key in ("trigger", "question", "task", "text", "summary"):
        val = kwargs.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    nested = result.get("result")
    if isinstance(nested, dict):
        for key in ("trigger", "question"):
            val = nested.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


def _slugify(text: str, *, max_len: int = 36) -> str:
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or "session"


_MAX_SKILL_NAME = 64


def _op_summary(operation: str, kwargs: dict[str, Any], result: dict[str, Any]) -> str:
    trigger = _trigger_text(kwargs, result)
    if trigger:
        return f"{operation}: {trigger[:120]}"
    return operation


def _should_auto_record_reasoning(
    operation: str,
    session: LearningSession,
    result: dict[str, Any],
) -> bool:
    if not auto_record_reasoning_enabled():
        return False
    if session.reasoning_recorded:
        return False
    if operation in _SELF_RECORDING_OPS:
        return False
    if operation not in _AUTO_REASONING_OPS and operation not in _HIGH_SIGNAL_OPS:
        return False
    # Prefer recording after the model has pulled context (6-step loop grounding).
    if not session.context_pack_pulled and operation not in _HIGH_SIGNAL_OPS:
        return False
    return True


def _should_distill_skill(operation: str, result: dict[str, Any]) -> bool:
    if not auto_distill_skills_enabled():
        return False
    if operation in _HIGH_SIGNAL_OPS:
        return True
    if operation == "experience_graph_context_pack":
        return False
    return operation in _AUTO_REASONING_OPS


def _auto_record_reasoning(
    operation: str,
    kwargs: dict[str, Any],
    result: dict[str, Any],
    swarm_id: str,
    program_id: str,
) -> str | None:
    try:
        from agentdrive.operations.registry import _integrated_recorder  # noqa: PLC2701

        _, recorder = _integrated_recorder(swarm_id)
        trigger = _trigger_text(kwargs, result)
        cycle_id = f"auto-learn-{int(time.time())}"
        reasoning = {
            "summary": f"Auto-recorded from {operation}",
            "decision_rationale": (
                trigger[:500]
                if trigger
                else f"Successful {operation} without explicit record_reasoning"
            ),
            "fabric_elements_considered": [f"operation:{operation}", f"swarm:{swarm_id}"],
            "structural_pattern_matched": "mcp-auto-learning-loop",
            "expected_lift_signal": 0.08,
            "program_id": program_id,
            "llm_mode": "auto_absorb",
            "auto_learning": True,
            "operation": operation,
        }
        evidence = _extract_evidence(operation, result)
        if evidence:
            reasoning["evidence"] = evidence
        return recorder.record_parent_fabric_reasoning(cycle_id=cycle_id, reasoning=reasoning)
    except Exception:
        logger.debug("auto_record_reasoning failed for %s", operation, exc_info=True)
        return None


def _extract_evidence(operation: str, result: dict[str, Any]) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    nested = result.get("result")
    if operation == "external_parent_decision" and isinstance(nested, dict):
        decision = nested.get("decision") or {}
        if isinstance(decision, dict):
            evidence["directive"] = decision.get("directive", "")
            evidence["session_id"] = nested.get("session_id") or decision.get(
                "multiverse_session_id", ""
            )
        fabric = nested.get("fabric_reasoning") or {}
        if isinstance(fabric, dict) and fabric.get("evidence"):
            evidence.update(dict(fabric["evidence"]))
    elif operation == "multiverse_parent_decision" and isinstance(nested, dict):
        evidence["collapsed"] = nested.get("collapsed_branch_id", "")
        evidence["session_id"] = nested.get("session_id", "")
    elif operation == "think" and isinstance(nested, dict):
        gaps = nested.get("gaps") or []
        if gaps:
            evidence["gaps"] = gaps[:3]
        if nested.get("answer"):
            evidence["answer_snippet"] = str(nested["answer"])[:300]
    elif result.get("trace_slug"):
        evidence["trace_slug"] = result["trace_slug"]
    return evidence


def _build_skill_body(
    operation: str,
    kwargs: dict[str, Any],
    result: dict[str, Any],
) -> tuple[str, str]:
    from agentdrive.learning.skill_naming import learned_skill_title

    trigger = _trigger_text(kwargs, result)
    project_id = str(kwargs.get("project_id") or result.get("project_id") or "")
    intent = str(kwargs.get("intent") or kwargs.get("task") or "")
    title = learned_skill_title(
        operation,
        trigger=trigger,
        project_id=project_id,
        intent=intent,
    )
    lines = [
        f"# {title}",
        "",
        "Auto-learned playbook from a successful AgentDrive MCP/CLI session.",
        "",
        "## When to use",
        f"- Task resembles: {trigger[:200]}" if trigger else f"- Running `{operation}` with similar inputs",
        f"- Operation: `{operation}`",
        "",
        "## Steps",
        "1. Call `experience_graph_get_context_pack` before acting.",
    ]

    nested = result.get("result")
    if operation == "external_parent_decision" and isinstance(nested, dict):
        decision = nested.get("decision") or {}
        directive = decision.get("directive", "") if isinstance(decision, dict) else ""
        session_id = nested.get("session_id", "")
        if directive:
            lines.append(f"2. Follow collapsed directive: {directive}")
        if session_id:
            lines.append(f"3. Ground in multiverse session `{session_id}`.")
        lines.append("4. Re-verify with live evidence before shipping.")
    elif operation == "multiverse_parent_decision" and isinstance(nested, dict):
        collapsed = nested.get("collapsed_branch_id", "")
        if collapsed:
            lines.append(f"2. Prefer collapsed branch `{collapsed}`.")
        lines.append("3. Record reasoning or call external_parent_decision for MCP Parent path.")
    elif operation == "experience_graph_record_reasoning":
        summary = str(
            (kwargs.get("reasoning") or {}).get("summary")
            or kwargs.get("summary")
            or result.get("trace_slug")
            or ""
        )[:300]
        if summary:
            lines.append(f"2. Prior rationale: {summary}")
        lines.append("3. Extend graph with new structural traces on similar tasks.")
    elif operation == "think" and isinstance(nested, dict):
        answer = str(nested.get("answer", ""))[:400]
        if answer:
            lines.append(f"2. Prior synthesis: {answer}")
        gaps = nested.get("gaps") or []
        if gaps:
            lines.append(f"3. Known gaps to close: {gaps[0]}")
    elif operation in _CODEBASE_OPS:
        project_id = str(kwargs.get("project_id") or result.get("project_id") or "")
        framework = result.get("framework") or {}
        mimic = result.get("mimicry_prompt") or ""
        motors = result.get("motor_programs") or []
        mirror = result.get("mirror_neurons") or {}
        if project_id:
            lines.append(f"2. Project `{project_id}` — mirror-neuron mimicry (observe → fire → write).")
        if mimic:
            lines.append(f"3. Mimicry brief:\n{mimic[:500]}")
        elif motors:
            lines.append(f"3. Motor programs: {[m.get('name') for m in motors[:3]]}")
        elif mirror.get("motors_fired"):
            lines.append(f"3. Mirror neurons fired: {mirror.get('motors_fired')}")
        patterns = framework.get("patterns") if isinstance(framework, dict) else None
        if isinstance(patterns, list) and patterns:
            for pat in patterns[:3]:
                lines.append(f"   - {pat.get('rule', '')}")
        lines.append("4. Use `codebase_mimic` before writing; `codebase_transform_style` after drafting.")
    else:
        lines.append(f"2. Run `{operation}` with the same swarm/program attribution.")
        lines.append("3. Call `experience_graph_record_reasoning` for non-trivial forks.")

    lines.extend(
        [
            "",
            "## Verification",
            "- Confirm `success: true` on the operation JSON.",
            "- Check Experience Graph context pack for contradictions.",
        ]
    )
    description = (
        f"Auto-learned from {operation}"
        + (f": {trigger[:120]}" if trigger else "")
    )
    return description[:1024], "\n".join(lines)


def _distill_and_install_skill(
    operation: str,
    kwargs: dict[str, Any],
    result: dict[str, Any],
    swarm_id: str,
    program_id: str,
) -> dict[str, Any]:
    from agentdrive.learning.skill_naming import learned_skill_name
    from agentdrive.skills.registry import install_inherited_skill

    trigger = _trigger_text(kwargs, result)
    project_id = str(kwargs.get("project_id") or result.get("project_id") or "")
    intent = str(kwargs.get("intent") or kwargs.get("task") or "")
    name = learned_skill_name(
        operation,
        trigger=trigger,
        project_id=project_id,
        intent=intent,
    )
    description, body = _build_skill_body(operation, kwargs, result)
    tags = ["learned", "auto-learned", "mcp-parent", operation.replace("_", "-")]
    if project_id:
        tags.append(project_id)
    if program_id and program_id != _MCP_SUBAGENT_ID:
        tags.append(program_id)

    path = install_inherited_skill(
        name=name,
        description=description,
        body=body,
        tags=tags,
        operation=operation,
        swarm_id=swarm_id,
        source_subagent_id=_MCP_SUBAGENT_ID,
        update_existing=True,
    )

    try:
        from agentdrive.skills.usage import record_skill_run

        source = f"mcp-auto-learning:{swarm_id}"
        record_skill_run(name, success=True, source=source)
        record_skill_run(name, success=True, source=source)
    except Exception:
        logger.debug("Failed to record auto-learned skill usage for %s", name, exc_info=True)

    promoted = False
    genome_id: str | None = None
    if operation in _HIGH_SIGNAL_OPS and auto_assimilate_enabled():
        promoted, genome_id = _promote_and_ingest(name, swarm_id)

    return {
        "name": name,
        "path": str(path),
        "promoted": promoted,
        "genome_id": genome_id,
        "operation": operation,
    }


def _promote_and_ingest(skill_name: str, swarm_id: str) -> tuple[bool, str | None]:
    try:
        from agentdrive.drive.drive import get_default_drive
        from agentdrive.skills.curation import ingest_skill_as_dna, promote_inherited_skill

        promote_inherited_skill(skill_name)
        export = ingest_skill_as_dna(skill_name, target_drive=get_default_drive())
        return True, export.genome_id if export.accepted else export.genome_id
    except Exception:
        logger.debug("auto promote/ingest failed for %s", skill_name, exc_info=True)
        try:
            from agentdrive.skills.curation import assimilate_inherited_skills
            from agentdrive.drive.drive import get_default_drive

            report = assimilate_inherited_skills(
                target_drive=get_default_drive(),
                ingest_dna=True,
                skill_names=[skill_name],
            )
            if report.dna_exports:
                return True, report.dna_exports[0].genome_id
            if report.promoted:
                return True, None
        except Exception:
            logger.debug("fallback assimilate failed for %s", skill_name, exc_info=True)
    return False, None


def maybe_absorb_operation_outcome(
    operation: str,
    kwargs: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Post-handler hook: absorb experience + skills from a successful operation.

    Returns a summary dict for inclusion as ``auto_learning`` on the operation
    result, or None when nothing was absorbed.
    """
    if not auto_learn_enabled():
        return None
    if not isinstance(result, dict) or not result.get("success"):
        return None
    if result.get("dry_run"):
        return None

    swarm_id = _effective_swarm(kwargs, result)
    program_id = _program_id(kwargs)
    session = _get_session(swarm_id, program_id)
    session.ops.append((operation, _op_summary(operation, kwargs, result)))

    if operation in _SESSION_START_OPS:
        session.context_pack_pulled = True
    if operation == "experience_graph_context_pack":
        session.context_pack_pulled = True
    if operation == "experience_graph_record_reasoning":
        session.reasoning_recorded = True

    if operation in _CODEBASE_OPS:
        project_id = str(kwargs.get("project_id") or result.get("project_id") or "")
        if project_id and project_id not in session.pattern_projects:
            session.pattern_projects.append(project_id)

    for skill_key in ("skill_name", "skill"):
        skill_ref = kwargs.get(skill_key)
        if isinstance(skill_ref, str) and skill_ref.strip():
            ref = skill_ref.strip()
            if ref not in session.referenced_skills:
                session.referenced_skills.append(ref)

    absorbed: dict[str, Any] = {"operation": operation, "swarm_id": swarm_id}

    if _should_auto_record_reasoning(operation, session, result):
        trace = _auto_record_reasoning(operation, kwargs, result, swarm_id, program_id)
        if trace:
            absorbed["reasoning_trace"] = trace
            session.reasoning_recorded = True
            if trace not in session.experience_traces:
                session.experience_traces.append(trace)

    if _should_distill_skill(operation, result):
        skill_info = _distill_and_install_skill(operation, kwargs, result, swarm_id, program_id)
        absorbed["skill"] = skill_info
        skill_name = skill_info.get("name")
        if skill_name and skill_name not in session.distilled_skills:
            session.distilled_skills.append(skill_name)

    trigger = _trigger_text(kwargs, result)
    if not session.fused_skill_name:
        try:
            from agentdrive.learning.skill_fusion import maybe_fuse_session

            fused = maybe_fuse_session(session, trigger=trigger, last_operation=operation)
            if fused:
                absorbed["fused_skill"] = fused
                session.fused_skill_name = fused.get("name")
        except Exception:
            logger.debug("skill fusion hook failed for %s", operation, exc_info=True)

    try:
        from agentdrive.memory.ingest import ingest_from_operation

        mem = ingest_from_operation(
            operation,
            kwargs,
            result,
            swarm_id=swarm_id,
            program_id=program_id,
        )
        if mem and not mem.get("skipped"):
            absorbed["memory"] = mem
    except Exception:
        logger.debug("memory bank ingest failed for %s", operation, exc_info=True)

    if not session.growth_merged:
        try:
            from agentdrive.learning.growth_merge import maybe_merge_growth

            growth = maybe_merge_growth(
                session,
                trigger=trigger,
                fused_skill=absorbed.get("fused_skill"),
                last_operation=operation,
            )
            if growth:
                absorbed["growth_merge"] = growth
                session.growth_merged = True
        except Exception:
            logger.debug("growth merge hook failed for %s", operation, exc_info=True)

    if len(absorbed) <= 2:
        return None
    return absorbed


def reset_sessions() -> None:
    """Test helper — clear in-memory session tracking."""
    _SESSIONS.clear()