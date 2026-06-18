"""
Contract-first operation definitions for AgentDrive.

Single source of truth for CLI surfaces, MCP tool mapping, and tools-json export
(gbrain operations.ts pattern).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OperationSpec:
    """Declarative contract for one AgentDrive operation.

    Used for CLI surfaces, MCP tool registration, and self-describing catalogs
    exposed to any AI model via MCP.
    """

    name: str
    description: str
    category: str
    read_only: bool
    cli_command: str | None = None
    mcp_tool: str | None = None
    # Rich metadata to help arbitrary AI models (Claude, Grok, Cursor, local LLMs, custom agents) decide when/how to call
    when_to_use: str = ""
    examples: list[str] | None = None  # short natural language or arg examples


OperationHandler = Callable[..., dict[str, Any]]

# ---------------------------------------------------------------------------
# Thin handler wrappers (dispatch targets)
# ---------------------------------------------------------------------------


def _success(**payload: Any) -> dict[str, Any]:
    return {"success": True, **payload}


def _dry_plan(operation: str, **plan: Any) -> dict[str, Any]:
    return {"success": True, "dry_run": True, "operation": operation, **plan}


def _handler_think(**kwargs: Any) -> dict[str, Any]:
    question = str(
        kwargs.get("question") or kwargs.get("text") or "What should I know about this AgentDrive?"
    )
    dry_run = bool(kwargs.get("dry_run", False))
    if dry_run:
        return _dry_plan(
            "think",
            question=question,
            prefer_experience_layer=bool(kwargs.get("prefer_experience_layer", True)),
        )

    from agentdrive.drive.drive import get_default_drive
    from agentdrive.synthesis.engine import _ensure_mandatory_gaps

    drive = get_default_drive()
    result = drive.think(
        question,
        prefer_experience_layer=bool(kwargs.get("prefer_experience_layer", True)),
    )
    payload = result.to_mcp_dict() if hasattr(result, "to_mcp_dict") else {"answer": str(result)}
    payload = _ensure_mandatory_gaps(payload, question)
    return _success(operation="think", question=question, result=payload)


def _handler_pool_query(**kwargs: Any) -> dict[str, Any]:
    task = str(kwargs.get("task") or kwargs.get("task_description") or kwargs.get("text") or "")
    limit = int(kwargs.get("limit", 5))
    min_score = float(kwargs.get("min_score", 0.0))
    dry_run = bool(kwargs.get("dry_run", False))
    if not task:
        return {"success": False, "error": "task is required", "operation": "pool_query"}
    if dry_run:
        return _dry_plan("pool_query", task=task, limit=limit, min_score=min_score)

    from agentdrive.drive.drive import DriveQuery, get_default_drive

    pool = get_default_drive()
    genomes = pool.query(
        DriveQuery(task_description=task, limit=limit, min_score=min_score, domains=[])
    )
    results = []
    for g in genomes[:limit]:
        rel = pool._compute_relevance(g, task)  # noqa: SLF001 — stable internal helper
        results.append(
            {
                "genome_id": g.genome_id,
                "relevance": rel,
                "framework_steps": (g.framework or {}).get("steps", [])[:5] if g.framework else [],
            }
        )
    return _success(operation="pool_query", task=task, count=len(results), results=results)


def _handler_pool_status(**kwargs: Any) -> dict[str, Any]:
    dry_run = bool(kwargs.get("dry_run", False))
    if dry_run:
        return _success(operation="pool_status", dry_run=True, stats={})

    from agentdrive.drive.drive import get_default_drive

    pool = get_default_drive()
    stats = pool.get_pool_stats()
    return _success(
        operation="pool_status",
        dry_run=False,
        stats=stats,
    )


def _handler_pool_stats(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.drive.drive import get_default_drive

    pool = get_default_drive()
    stats = pool.get_pool_stats()
    reg_details: dict[str, Any] = {}
    try:
        reg = pool.registry
        if hasattr(reg, "get_registry_stats"):
            reg_details = reg.get_registry_stats()
    except Exception as exc:
        reg_details = {"error": str(exc)}
    return _success(
        operation="pool_stats",
        dry_run=bool(kwargs.get("dry_run", False)),
        stats=stats,
        registry=reg_details,
    )


def _handler_ingest_genome(**kwargs: Any) -> dict[str, Any]:
    genome_dir = kwargs.get("genome_dir") or kwargs.get("path")
    dry_run = bool(kwargs.get("dry_run", False))
    if not genome_dir:
        return {"success": False, "error": "genome_dir is required", "operation": "ingest_genome"}

    gdir = Path(str(genome_dir)).expanduser().resolve()
    if not gdir.is_dir():
        return {
            "success": False,
            "error": f"genome_dir not found: {gdir}",
            "operation": "ingest_genome",
        }
    if dry_run:
        return _dry_plan("ingest_genome", genome_dir=str(gdir), would_ingest=True)

    from agentdrive.drive.drive import get_default_drive
    from agentdrive.genome.models import Genome

    pool = get_default_drive()
    genome = Genome.load(gdir)
    result = pool.ingest(genome, source="ops-ingest", actor="ops-registry")
    return _success(
        operation="ingest_genome",
        accepted=result.accepted,
        genome_id=result.genome_id,
        reason=result.reason,
        new_version=result.new_version,
    )


def _handler_reconcile_scan(**kwargs: Any) -> dict[str, Any]:
    dry_run = bool(kwargs.get("dry_run", False))
    if dry_run:
        return _dry_plan("reconcile_scan", would_scan=True)

    from agentdrive.drive.drive import get_default_drive
    from agentdrive.reconciliation import ReconciliationRunner
    from agentdrive.registry import GenomeRegistry

    pool = get_default_drive()
    registry = pool.registry if hasattr(pool, "registry") else GenomeRegistry()
    report = ReconciliationRunner(registry=registry, pool=pool).scan_once()
    return _success(
        operation="reconcile_scan",
        since=report.since,
        until=report.until,
        duration_ms=report.duration_ms,
        new_genomes=list(report.new_genomes),
        updated_genomes=list(report.updated_genomes),
        new_ingest_events=report.new_ingest_events,
        pending_quarantine=report.pending_quarantine,
    )


def _handler_reconcile_seed(**kwargs: Any) -> dict[str, Any]:
    dry_run = bool(kwargs.get("dry_run", False))
    if dry_run:
        return _dry_plan("reconcile_seed", would_seed_experience_v3=True)

    from agentdrive.drive.bootstrap import ensure_experience_layer_seed
    from agentdrive.drive.drive import get_default_drive

    pool = get_default_drive()
    seed_path = ensure_experience_layer_seed(pool.drive_path, getattr(pool, "swarm_id", None))
    return _success(
        operation="reconcile_seed",
        drive_path=str(pool.drive_path),
        seed_observation=str(seed_path),
        status="created_or_repaired",
    )


def _handler_reconcile_status(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.constants import get_agentdrive_home
    from agentdrive.reconciliation import STATE_FILENAME

    state_path = get_agentdrive_home() / STATE_FILENAME
    dry_run = bool(kwargs.get("dry_run", False))
    if not state_path.is_file():
        return _success(
            operation="reconcile_status",
            dry_run=dry_run,
            state_path=str(state_path),
            exists=False,
            message="No reconciliation state yet; run reconcile_scan first.",
        )
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"success": False, "operation": "reconcile_status", "error": str(exc)}
    known_ids = list(state.get("known_genome_ids") or [])
    markers = dict(state.get("known_markers") or {})
    return _success(
        operation="reconcile_status",
        dry_run=dry_run,
        state_path=str(state_path),
        last_scan=state.get("last_scan_iso"),
        known_genomes=len(known_ids),
        ultimate_markers=sum(1 for m in markers.values() if m.get("ultimate")),
    )


def _handler_doctor(**kwargs: Any) -> dict[str, Any]:
    verbose = bool(kwargs.get("verbose", False))
    dry_run = bool(kwargs.get("dry_run", False))
    checks = ["home", "config", "pool", "registry", "reconciliation", "workers"]
    if verbose:
        checks.extend(["learnings", "sprint_checkpoints", "dream_lock"])

    if dry_run:
        return _dry_plan("doctor", verbose=verbose, checks=checks)

    from agentdrive.constants import get_agentdrive_home

    home = get_agentdrive_home()
    snapshot: dict[str, Any] = {
        "home": str(home),
        "home_exists": home.is_dir(),
        "config_exists": (home / "config.yaml").is_file(),
        "checks": checks,
        "verbose": verbose,
    }
    try:
        from agentdrive.drive.drive import get_default_drive

        pool = get_default_drive()
        snapshot["pool_stats"] = pool.get_pool_stats()
    except Exception as exc:
        snapshot["pool_error"] = str(exc)
    return _success(operation="doctor", snapshot=snapshot)


def _handler_doctor_verbose(**kwargs: Any) -> dict[str, Any]:
    kwargs = {**kwargs, "verbose": True}
    return _handler_doctor(**kwargs)


def _handler_sprint_ship(**kwargs: Any) -> dict[str, Any]:
    dry_run = bool(kwargs.get("dry_run", False))
    pytest_path = str(kwargs.get("pytest_path", "tests"))
    reset = bool(kwargs.get("reset", False))
    ack_ids = list(kwargs.get("ack_ids") or kwargs.get("ack") or [])
    if isinstance(ack_ids, str):
        ack_ids = [ack_ids]

    from agentdrive.sprint import run_ship_chain

    results = run_ship_chain(
        dry_run=dry_run,
        ack_ids=ack_ids or None,
        pytest_path=pytest_path,
        reset=reset,
    )
    return _success(
        operation="sprint_ship",
        dry_run=dry_run,
        steps=[
            {
                "step_id": r.step_id,
                "name": r.name,
                "success": r.success,
                "message": r.message,
                "detail": r.detail,
            }
            for r in results
        ],
    )


def _handler_sprint_status(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.sprint import CheckpointStore

    chain_id = str(kwargs.get("chain_id", "ship"))
    store = CheckpointStore(chain_id=chain_id)
    pending = store.list_pending()
    return _success(
        operation="sprint_status",
        dry_run=bool(kwargs.get("dry_run", False)),
        chain_id=chain_id,
        pending=pending,
        count=len(pending),
    )


def _handler_patterns_list(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.patterns import list_patterns

    patterns = list_patterns()
    rows = [
        {
            "name": p.name,
            "source": p.source,
            "version": p.manifest.version if p.manifest else None,
            "path": str(p.path),
        }
        for p in patterns
    ]
    return _success(
        operation="patterns_list",
        dry_run=bool(kwargs.get("dry_run", False)),
        patterns=rows,
        count=len(rows),
    )


def _handler_patterns_show(**kwargs: Any) -> dict[str, Any]:
    name = kwargs.get("pattern_name") or kwargs.get("name") or kwargs.get("text")
    if not name:
        return {"success": False, "error": "pattern_name is required", "operation": "patterns_show"}

    from agentdrive.patterns import PatternNotFoundError, get_pattern

    try:
        record = get_pattern(str(name))
    except PatternNotFoundError:
        return {
            "success": False,
            "error": f"pattern not found: {name}",
            "operation": "patterns_show",
        }

    manifest = record.manifest
    return _success(
        operation="patterns_show",
        dry_run=bool(kwargs.get("dry_run", False)),
        name=record.name,
        source=record.source,
        path=str(record.path),
        id=manifest.id if manifest else record.name,
        version=manifest.version if manifest else None,
        description=(record.framework or {}).get("description") if record.framework else None,
    )


def _handler_patterns_apply(**kwargs: Any) -> dict[str, Any]:
    name = kwargs.get("pattern_name") or kwargs.get("name") or kwargs.get("text")
    input_text = str(kwargs.get("input") or kwargs.get("input_text") or "")
    if not name:
        return {
            "success": False,
            "error": "pattern_name is required",
            "operation": "patterns_apply",
        }
    if bool(kwargs.get("dry_run", False)):
        return _dry_plan("patterns_apply", pattern_name=str(name), input_preview=input_text[:200])

    from agentdrive.patterns import PatternNotFoundError, apply_pattern

    try:
        prompt = apply_pattern(str(name), input_text)
    except PatternNotFoundError:
        return {
            "success": False,
            "error": f"pattern not found: {name}",
            "operation": "patterns_apply",
        }
    return _success(operation="patterns_apply", pattern_name=str(name), prompt=prompt)


def _handler_patterns_import_fabric(**kwargs: Any) -> dict[str, Any]:
    dry_run = bool(kwargs.get("dry_run", False))
    limit = int(kwargs.get("limit", 10))
    pattern_name = kwargs.get("pattern")
    overwrite = bool(kwargs.get("overwrite", False))
    source = kwargs.get("source")

    if dry_run:
        return _dry_plan(
            "patterns_import_fabric",
            source=source,
            pattern=pattern_name,
            limit=limit,
            overwrite=overwrite,
        )

    from agentdrive.constants import get_agentdrive_home
    from agentdrive.patterns.fabric_import import (
        import_fabric_corpus,
        import_fabric_pattern,
        resolve_fabric_root,
    )

    fabric_root = resolve_fabric_root(source)
    dest_root = get_agentdrive_home() / "patterns"
    if pattern_name:
        imported = [
            import_fabric_pattern(fabric_root, str(pattern_name), dest_root, overwrite=overwrite)
        ]
    else:
        imported = import_fabric_corpus(fabric_root, limit=limit, overwrite=overwrite)
    return _success(
        operation="patterns_import_fabric",
        source=str(fabric_root),
        imported=[str(p) for p in imported],
        count=len(imported),
    )


def _handler_dream_run(**kwargs: Any) -> dict[str, Any]:
    dry_run = bool(kwargs.get("dry_run", False))
    ack_phases = list(kwargs.get("ack_phases") or kwargs.get("ack") or [])
    if isinstance(ack_phases, str):
        ack_phases = [ack_phases]

    from agentdrive.dreaming.cycle import run_dream_cycle

    results = run_dream_cycle(
        dry_run=dry_run, ack_phases=ack_phases or None, acquire_lock=not dry_run
    )
    return _success(
        operation="dream_run",
        dry_run=dry_run,
        phases=[
            {
                "phase_id": r.phase_id,
                "phase_name": r.phase_name,
                "success": r.success,
                "message": r.message,
                "duration_ms": r.duration_ms,
            }
            for r in results
        ],
    )


def _handler_dream_status(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.dreaming.cycle import get_dream_cycle_status

    status = get_dream_cycle_status()
    return _success(
        operation="dream_status", dry_run=bool(kwargs.get("dry_run", False)), status=status
    )


def _handler_cap_mint_mission(**kwargs: Any) -> dict[str, Any]:
    command = str(kwargs.get("command", "*"))
    dry_run = bool(kwargs.get("dry_run", False))
    if dry_run:
        return _dry_plan("cap_mint_mission", command=command)

    from agentdrive.mission_control.authz import mint_mission_control_cap

    cap_id = mint_mission_control_cap(command=command)
    return _success(operation="cap_mint_mission", cap_id=cap_id, command=command)


def _integrated_recorder(swarm_id: str | None):
    from agentdrive.system.integrated_real_time_evolution_system import (
        IntegratedRealTimeEvolutionSystem,
    )

    effective = swarm_id or "stabilization-wave-20260531"
    return effective, IntegratedRealTimeEvolutionSystem(swarm_id=effective).recorder


def _handler_experience_graph_context_pack(**kwargs: Any) -> dict[str, Any]:
    swarm_id = kwargs.get("swarm_id")
    reasoning_style = str(kwargs.get("reasoning_style", "balanced"))
    lookback_days = int(kwargs.get("lookback_days", 7))
    max_tokens = int(kwargs.get("max_tokens", 1800))
    dry_run = bool(kwargs.get("dry_run", False))
    effective, _ = _integrated_recorder(swarm_id)
    if dry_run:
        return _dry_plan(
            "experience_graph_context_pack",
            swarm_id=effective,
            reasoning_style=reasoning_style,
            lookback_days=lookback_days,
            max_tokens=max_tokens,
        )

    _, recorder = _integrated_recorder(swarm_id)
    pack = recorder.get_fabric_context_pack(
        reasoning_style=reasoning_style,
        lookback_days=lookback_days,
        max_tokens=max_tokens,
    )
    return _success(
        operation="experience_graph_context_pack", swarm_id=effective, context_pack=pack
    )


def _handler_experience_graph_record_reasoning(**kwargs: Any) -> dict[str, Any]:
    swarm_id = kwargs.get("swarm_id")
    cycle_id = kwargs.get("cycle_id")
    reasoning = kwargs.get("reasoning")
    dry_run = bool(kwargs.get("dry_run", False))
    effective, _ = _integrated_recorder(swarm_id)

    if reasoning is None:
        reasoning = {
            "summary": str(
                kwargs.get("summary") or kwargs.get("text") or "ops-registry dry reasoning"
            ),
            "elements": list(kwargs.get("elements") or []),
        }
    if not isinstance(reasoning, dict):
        return {
            "success": False,
            "error": "reasoning must be a dict",
            "operation": "experience_graph_record_reasoning",
        }
    if dry_run:
        return _dry_plan(
            "experience_graph_record_reasoning",
            swarm_id=effective,
            cycle_id=cycle_id,
            reasoning_preview=str(reasoning)[:300],
        )

    _, recorder = _integrated_recorder(swarm_id)
    trace_slug = recorder.record_parent_fabric_reasoning(cycle_id=cycle_id, reasoning=reasoning)
    return _success(
        operation="experience_graph_record_reasoning",
        swarm_id=effective,
        trace_slug=trace_slug,
        recorded=True,
    )


def _handler_experience_graph_suggest_reasoning(**kwargs: Any) -> dict[str, Any]:
    swarm_id = kwargs.get("swarm_id")
    dry_run = bool(kwargs.get("dry_run", False))
    effective, recorder = _integrated_recorder(swarm_id)
    if dry_run:
        return _dry_plan("experience_graph_suggest_reasoning", swarm_id=effective)
    structure = recorder.suggest_fabric_reasoning_structure()
    return _success(
        operation="experience_graph_suggest_reasoning",
        swarm_id=effective,
        structure=structure,
    )


def _multiverse_engine(swarm_id: str | None, **engine_kwargs: Any):
    from agentdrive.cognition import MultiverseEngine

    effective, recorder = _integrated_recorder(swarm_id)
    return effective, MultiverseEngine(recorder, **engine_kwargs)


def _handler_multiverse_run_full(**kwargs: Any) -> dict[str, Any]:
    trigger = str(kwargs.get("trigger") or kwargs.get("text") or kwargs.get("question") or "")
    if not trigger:
        return {"success": False, "error": "trigger is required", "operation": "multiverse_run_full"}

    n_branches = int(kwargs.get("n_branches", kwargs.get("branches", 7)))
    forward_steps = kwargs.get("forward_steps")
    program_id = kwargs.get("program_id")
    dry_run = bool(kwargs.get("dry_run", False))
    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))

    if dry_run:
        return _dry_plan(
            "multiverse_run_full",
            swarm_id=effective,
            trigger=trigger[:200],
            n_branches=n_branches,
            forward_steps=forward_steps,
        )

    engine_kwargs: dict[str, Any] = {}
    if program_id:
        engine_kwargs["program_id"] = str(program_id)
    if kwargs.get("user_objective_refs"):
        engine_kwargs["user_objective_refs"] = list(kwargs["user_objective_refs"])

    _, engine = _multiverse_engine(kwargs.get("swarm_id"), **engine_kwargs)
    session = engine.run_full(
        trigger,
        n_branches=n_branches,
        forward_steps=int(forward_steps) if forward_steps is not None else None,
    )
    fabric_reasoning = engine.to_fabric_reasoning(session)
    _, recorder = _integrated_recorder(kwargs.get("swarm_id"))
    trace_slug = recorder.record_parent_fabric_reasoning(session.cycle_id, fabric_reasoning)

    return _success(
        operation="multiverse_run_full",
        swarm_id=effective,
        session=engine.to_mcp_dict(session),
        fabric_reasoning_trace_slug=trace_slug,
    )


def _handler_multiverse_get_session(**kwargs: Any) -> dict[str, Any]:
    session_id = str(kwargs.get("session_id") or "")
    if not session_id:
        return {"success": False, "error": "session_id is required", "operation": "multiverse_get_session"}

    dry_run = bool(kwargs.get("dry_run", False))
    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    if dry_run:
        return _dry_plan("multiverse_get_session", swarm_id=effective, session_id=session_id)

    _, engine = _multiverse_engine(kwargs.get("swarm_id"))
    session = engine.get_session(session_id)
    if session is None:
        return {
            "success": False,
            "error": f"session not found: {session_id}",
            "operation": "multiverse_get_session",
        }
    return _success(
        operation="multiverse_get_session",
        swarm_id=effective,
        session=engine.to_mcp_dict(session),
    )


def _handler_multiverse_list_sessions(**kwargs: Any) -> dict[str, Any]:
    limit = int(kwargs.get("limit", 10))
    dry_run = bool(kwargs.get("dry_run", False))
    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    if dry_run:
        return _dry_plan("multiverse_list_sessions", swarm_id=effective, limit=limit)

    _, engine = _multiverse_engine(kwargs.get("swarm_id"))
    sessions = engine.list_sessions(limit=limit)
    return _success(
        operation="multiverse_list_sessions",
        swarm_id=effective,
        count=len(sessions),
        sessions=[engine.to_mcp_dict(s) for s in sessions],
        briefing_context=engine.briefing_context(limit=min(limit, 5)),
    )


def _handler_multiverse_parent_decision(**kwargs: Any) -> dict[str, Any]:
    """Integrated loop hook: multiverse pipeline + record_parent_decision."""
    trigger = str(kwargs.get("trigger") or kwargs.get("text") or kwargs.get("question") or "")
    if not trigger:
        return {
            "success": False,
            "error": "trigger is required",
            "operation": "multiverse_parent_decision",
        }

    dry_run = bool(kwargs.get("dry_run", False))
    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    if dry_run:
        return _dry_plan(
            "multiverse_parent_decision",
            swarm_id=effective,
            trigger=trigger[:200],
            n_branches=int(kwargs.get("n_branches", kwargs.get("branches", 7))),
        )

    from agentdrive.system.integrated_real_time_evolution_system import (
        IntegratedRealTimeEvolutionSystem,
    )

    system = IntegratedRealTimeEvolutionSystem(swarm_id=effective)
    payload = system.run_multiverse_parent_decision(
        trigger,
        n_branches=int(kwargs.get("n_branches", kwargs.get("branches", 7))),
        forward_steps=int(kwargs["forward_steps"]) if kwargs.get("forward_steps") is not None else None,
        program_id=kwargs.get("program_id"),
        user_objective_refs=list(kwargs["user_objective_refs"])
        if kwargs.get("user_objective_refs")
        else None,
        record_decision=not bool(kwargs.get("skip_record", False)),
        durable=bool(kwargs.get("durable", False)),
        densify_invariants=not bool(kwargs.get("skip_densify", False)),
        use_llm=not bool(kwargs.get("heuristic_only", False)),
    )
    return _success(operation="multiverse_parent_decision", swarm_id=effective, result=payload)


def _unwrap_mcp_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested ``arguments`` dicts from auto-registered MCP tool calls."""
    nested = kwargs.get("arguments")
    if isinstance(nested, dict):
        merged = dict(nested)
        merged.update({k: v for k, v in kwargs.items() if k != "arguments"})
        return merged
    return kwargs


def _handler_external_parent_decision(**kwargs: Any) -> dict[str, Any]:
    """MCP frontier/local chat models submit multiverse branches; AgentDrive records collapse."""
    kwargs = _unwrap_mcp_kwargs(dict(kwargs))
    trigger = str(kwargs.get("trigger") or kwargs.get("text") or kwargs.get("question") or "")
    branches = kwargs.get("branches")
    collapsed_branch_id = str(kwargs.get("collapsed_branch_id") or "")
    if not trigger:
        return {
            "success": False,
            "error": "trigger is required",
            "operation": "external_parent_decision",
        }
    if not isinstance(branches, list) or not branches:
        return {
            "success": False,
            "error": "branches must be a non-empty list",
            "operation": "external_parent_decision",
        }
    if not collapsed_branch_id:
        return {
            "success": False,
            "error": "collapsed_branch_id is required",
            "operation": "external_parent_decision",
        }

    dry_run = bool(kwargs.get("dry_run", False))
    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    if dry_run:
        return _dry_plan(
            "external_parent_decision",
            swarm_id=effective,
            trigger=trigger[:200],
            branch_count=len(branches),
            collapsed_branch_id=collapsed_branch_id,
            reasoning_provider=kwargs.get("reasoning_provider", "mcp-external"),
        )

    from agentdrive.system.integrated_real_time_evolution_system import (
        IntegratedRealTimeEvolutionSystem,
    )

    system = IntegratedRealTimeEvolutionSystem(swarm_id=effective)
    payload = system.run_external_parent_decision(
        trigger,
        branches,
        collapsed_branch_id=collapsed_branch_id,
        invariants=list(kwargs["invariants"]) if kwargs.get("invariants") else None,
        collapse_reason=str(kwargs.get("collapse_reason") or ""),
        collapse_policy=str(kwargs["collapse_policy"]) if kwargs.get("collapse_policy") else None,
        reasoning_provider=str(kwargs.get("reasoning_provider") or "mcp-external"),
        convergence_points=list(kwargs["convergence_points"])
        if kwargs.get("convergence_points")
        else None,
        divergence_points=list(kwargs["divergence_points"])
        if kwargs.get("divergence_points")
        else None,
        fabric_reasoning=dict(kwargs["fabric_reasoning"])
        if isinstance(kwargs.get("fabric_reasoning"), dict)
        else None,
        program_id=kwargs.get("program_id"),
        user_objective_refs=list(kwargs["user_objective_refs"])
        if kwargs.get("user_objective_refs")
        else None,
        record_decision=not bool(kwargs.get("skip_record", False)),
        densify_invariants=not bool(kwargs.get("skip_densify", False)),
    )
    return _success(operation="external_parent_decision", swarm_id=effective, result=payload)


def _handler_multiverse_reopen_stale(**kwargs: Any) -> dict[str, Any]:
    max_age = float(kwargs.get("max_age_hours", 24.0))
    dry_run = bool(kwargs.get("dry_run", False))
    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    if dry_run:
        return _dry_plan("multiverse_reopen_stale", swarm_id=effective, max_age_hours=max_age)

    from agentdrive.system.integrated_real_time_evolution_system import (
        IntegratedRealTimeEvolutionSystem,
    )

    reopened = IntegratedRealTimeEvolutionSystem(swarm_id=effective).reopen_stale_multiverse_sessions(
        max_age_hours=max_age
    )
    return _success(
        operation="multiverse_reopen_stale",
        swarm_id=effective,
        reopened_count=len(reopened),
        reopened_session_ids=reopened,
    )


def _handler_multiverse_densify(**kwargs: Any) -> dict[str, Any]:
    session_id = str(kwargs.get("session_id") or "")
    if not session_id:
        return {"success": False, "error": "session_id is required", "operation": "multiverse_densify"}
    dry_run = bool(kwargs.get("dry_run", False))
    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    if dry_run:
        return _dry_plan("multiverse_densify", swarm_id=effective, session_id=session_id)

    from agentdrive.system.integrated_real_time_evolution_system import (
        IntegratedRealTimeEvolutionSystem,
    )

    result = IntegratedRealTimeEvolutionSystem(swarm_id=effective).densify_multiverse_invariants(
        session_id
    )
    return _success(operation="multiverse_densify", swarm_id=effective, result=result)


def _handler_learnings_log(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.learnings import LearningsStore

    kwargs = _unwrap_mcp_kwargs(dict(kwargs))
    dry_run = bool(kwargs.get("dry_run", False))
    outcome = kwargs.get("outcome")
    if isinstance(outcome, dict):
        kwargs.setdefault("insight", outcome.get("key_observation") or outcome.get("insight"))
        kwargs.setdefault("confidence", outcome.get("confidence", 5))
    entry = {
        "type": str(kwargs.get("type", "pattern")),
        "key": str(kwargs.get("key") or kwargs.get("task") or "ops-registry-entry"),
        "insight": str(
            kwargs.get("insight")
            or kwargs.get("text")
            or (isinstance(outcome, dict) and outcome.get("key_observation"))
            or "ops registry learning entry"
        ),
        "confidence": int(kwargs.get("confidence", 5)),
        "source": str(kwargs.get("source", "observed")),
        "skill": str(kwargs.get("skill", "harness")),
    }
    if dry_run:
        return _dry_plan("learnings_log", entry=entry)

    store = LearningsStore(slug=kwargs.get("slug"))
    record = store.log(entry)
    result = _success(operation="learnings_log", slug=store.slug, record=record)
    try:
        from agentdrive.memory.ingest import ingest_from_learning

        effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
        mem = ingest_from_learning(record, swarm_id=effective)
        if mem:
            result["memory"] = mem
    except Exception:
        pass
    return result


def _handler_learnings_list(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.learnings import LearningsStore

    store = LearningsStore(slug=kwargs.get("slug"))
    limit = int(kwargs.get("limit", 20))
    entries = store.list_recent(limit=limit)
    return _success(
        operation="learnings_list",
        dry_run=bool(kwargs.get("dry_run", False)),
        slug=store.slug,
        count=store.count(),
        entries=entries,
    )


def _handler_harness_compose(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.harness import Harness

    base_prompt = str(
        kwargs.get("base_prompt") or kwargs.get("prompt") or "You are an AgentDrive agent."
    )
    task = str(kwargs.get("task") or kwargs.get("text") or "")
    dry_run = bool(kwargs.get("dry_run", False))
    agent_id = str(kwargs.get("agent_id", "ops-registry"))

    if dry_run:
        return _dry_plan(
            "harness_compose",
            agent_id=agent_id,
            task=task or None,
            base_prompt_preview=base_prompt[:200],
        )

    harness = Harness(agent_id=agent_id)
    if task:
        harness.current_task = task
    composed = harness.compose_context(
        base_prompt,
        slug=kwargs.get("slug"),
        strategy=kwargs.get("strategy"),
        context=kwargs.get("context"),
        pattern=kwargs.get("pattern"),
        session_id=kwargs.get("session_id"),
        input_text=kwargs.get("input_text"),
    )
    return _success(
        operation="harness_compose",
        agent_id=agent_id,
        task=task or None,
        composed_prompt=composed,
        pulled_dna_count=len(harness.pulled_dna),
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

OPERATIONS: list[OperationSpec] = [
    OperationSpec(
        name="think",
        description="Cited Drive.think synthesis with mandatory gap analysis",
        category="synthesis",
        read_only=True,
        cli_command="agentdrive think",
        when_to_use="Use for any non-trivial question where you need fused evidence from the pool + Experience Graph + honest gap reporting. Always call with prefer_experience_layer=True unless you explicitly want pure LLM mode.",
        examples=[
            "think(question='How should I structure long-horizon agent memory?')",
            "think with dry_run first to plan",
        ],
        mcp_tool="agentdrive_think",
    ),
    OperationSpec(
        name="pool_query",
        description="Semantic search across the Drive for relevant genomes",
        category="drive",
        read_only=True,
        cli_command="agentdrive drive query",
        when_to_use="First-line retrieval before any synthesis or planning. Returns ranked genomes with relevance scores and framework steps. Prefer over raw vector search when you want Drive-native DNA packets.",
        examples=["pool_query(task='self-healing patterns for distributed agents', limit=6)"],
        mcp_tool="agentdrive_pool_query",
    ),
    OperationSpec(
        name="pool_status",
        description="Current status of the active AgentDrive pool",
        category="drive",
        read_only=True,
        cli_command="agentdrive drive status",
        mcp_tool="agentdrive_pool_status",
    ),
    OperationSpec(
        name="pool_stats",
        description="Detailed pool statistics including registry metrics",
        category="drive",
        read_only=True,
        cli_command="agentdrive drive stats",
        mcp_tool="agentdrive_pool_stats",
    ),
    OperationSpec(
        name="ingest_genome",
        description="Ingest a genome directory into the local Drive",
        category="drive",
        read_only=False,
        cli_command="agentdrive drive ingest",
        mcp_tool="agentdrive_ingest_genome",
    ),
    OperationSpec(
        name="reconcile_scan",
        description="Run a single reconciliation scan over the local Drive",
        category="reconcile",
        read_only=True,
        cli_command="agentdrive reconcile run",
        mcp_tool="agentdrive_reconcile_scan",
    ),
    OperationSpec(
        name="reconcile_seed",
        description="Bootstrap or repair the experience layer v3 seed genome",
        category="reconcile",
        read_only=False,
        cli_command="agentdrive reconcile seed-experience-v3",
        mcp_tool="agentdrive_reconcile_seed",
    ),
    OperationSpec(
        name="reconcile_status",
        description="Show persisted reconciliation state from disk",
        category="reconcile",
        read_only=True,
        cli_command="agentdrive reconcile status",
        mcp_tool="agentdrive_reconcile_status",
    ),
    OperationSpec(
        name="doctor",
        description="Diagnose AgentDrive installation, config, pool, and registry health",
        category="system",
        read_only=True,
        cli_command="agentdrive doctor",
        when_to_use="Call at the start of any session or when the user complains about missing data/tools. Also great for models to self-check their environment before heavy work.",
        examples=["doctor(verbose=True)"],
        mcp_tool="agentdrive_doctor",
    ),
    OperationSpec(
        name="doctor_verbose",
        description="Doctor health check with extra subsystem diagnostics",
        category="system",
        read_only=True,
        cli_command="agentdrive doctor --verbose",
        mcp_tool="agentdrive_doctor_verbose",
    ),
    OperationSpec(
        name="sprint_ship",
        description="Run the gstack-style reconcile → test → think_gaps ship chain",
        category="sprint",
        read_only=False,
        cli_command="agentdrive sprint ship",
        mcp_tool="agentdrive_sprint_ship",
    ),
    OperationSpec(
        name="sprint_status",
        description="List pending sprint checkpoints awaiting acknowledgement",
        category="sprint",
        read_only=True,
        cli_command="agentdrive sprint status",
        mcp_tool="agentdrive_sprint_status",
    ),
    OperationSpec(
        name="patterns_list",
        description="List Fabric-style pattern-as-genome catalog entries",
        category="patterns",
        read_only=True,
        cli_command="agentdrive patterns list",
        mcp_tool="agentdrive_patterns_list",
    ),
    OperationSpec(
        name="patterns_show",
        description="Show metadata and system.md preview for one pattern",
        category="patterns",
        read_only=True,
        cli_command="agentdrive patterns show",
        mcp_tool="agentdrive_patterns_show",
    ),
    OperationSpec(
        name="patterns_apply",
        description="Compose a pattern prompt with optional {{input}} substitution",
        category="patterns",
        read_only=True,
        cli_command="agentdrive patterns apply",
        mcp_tool="agentdrive_patterns_apply",
    ),
    OperationSpec(
        name="patterns_import_fabric",
        description="Import Fabric patterns into the ~/.agentdrive/patterns overlay",
        category="patterns",
        read_only=False,
        cli_command="agentdrive patterns import-fabric",
        mcp_tool="agentdrive_patterns_import_fabric",
    ),
    OperationSpec(
        name="dream_run",
        description="Execute the phased dream maintenance cycle",
        category="dreaming",
        read_only=False,
        cli_command="agentdrive dream run",
        mcp_tool="agentdrive_dream_run",
    ),
    OperationSpec(
        name="dream_status",
        description="Return dream cycle lock and last audit log snapshot",
        category="dreaming",
        read_only=True,
        cli_command="agentdrive dream status",
        mcp_tool="agentdrive_dream_status",
    ),
    OperationSpec(
        name="cap_mint_mission",
        description="Mint a Mission Control capability for mutating commands",
        category="mission_control",
        read_only=False,
        cli_command="agentdrive cap mint-mission",
        mcp_tool="agentdrive_cap_mint_mission",
    ),
    OperationSpec(
        name="experience_graph_context_pack",
        description="Dense Experience Graph context pack for Parent-style briefings",
        category="experience_graph",
        read_only=True,
        cli_command="agentdrive graph context-pack",
        mcp_tool="experience_graph_get_context_pack",
    ),
    OperationSpec(
        name="experience_graph_record_reasoning",
        description="Record explicit structural reasoning into the Experience Graph",
        category="experience_graph",
        read_only=False,
        cli_command="agentdrive graph record",
        mcp_tool="experience_graph_record_reasoning",
    ),
    OperationSpec(
        name="experience_graph_suggest_reasoning",
        description="Return schema and examples for authoring reasoning traces",
        category="experience_graph",
        read_only=True,
        cli_command="agentdrive graph suggest",
        mcp_tool="experience_graph_suggest_reasoning_structure",
    ),
    OperationSpec(
        name="multiverse_run_full",
        description="Run full multiverse cognition: spawn branches, simulate, extract invariants, stress-test, collapse, record fabric reasoning",
        category="multiverse",
        read_only=False,
        when_to_use="Call on any non-trivial Parent decision where multiple competing paths exist. Spawns Cognitive Agent Team role branches, holds superposition, collapses to one governed path, and writes Experience Graph DNA.",
        examples=[
            'multiverse_run_full(trigger="How should we ship feature X?", n_branches=7)',
        ],
        mcp_tool="multiverse_run_full",
    ),
    OperationSpec(
        name="multiverse_get_session",
        description="Return a persisted multiverse session by id",
        category="multiverse",
        read_only=True,
        cli_command="agentdrive multiverse status",
        mcp_tool="multiverse_get_session",
    ),
    OperationSpec(
        name="multiverse_list_sessions",
        description="List recent multiverse sessions and briefing context",
        category="multiverse",
        read_only=True,
        cli_command="agentdrive multiverse list",
        mcp_tool="multiverse_list_sessions",
    ),
    OperationSpec(
        name="multiverse_parent_decision",
        description="Full multiverse pipeline wired into record_parent_decision (canonical Parent hook)",
        category="multiverse",
        read_only=False,
        when_to_use="Preferred entry for non-trivial Parent decisions inside the 6-step loop. Runs spawn→simulate→invariants→stress-test→collapse→record_parent_decision in one call.",
        examples=[
            'multiverse_parent_decision(trigger="How should we ship feature X?", n_branches=7)',
        ],
        cli_command="agentdrive multiverse run",
        mcp_tool="multiverse_parent_decision",
    ),
    OperationSpec(
        name="external_parent_decision",
        description="Submit externally-reasoned multiverse branches (Grok/Claude/Codex MCP) and record Parent DNA",
        category="multiverse",
        read_only=False,
        when_to_use=(
            "Use when YOU (the connected MCP model) perform multiverse branch reasoning in your own "
            "context and need AgentDrive to persist the collapse. Call after experience_graph_get_context_pack "
            "and experience_graph_suggest_reasoning_structure. Sets llm_mode=external."
        ),
        examples=[
            'external_parent_decision(trigger="...", branches=[{role, path_summary, ...}], collapsed_branch_id="branch:operator-0", reasoning_provider="grok")',
        ],
        mcp_tool="external_parent_decision",
    ),
    OperationSpec(
        name="multiverse_reopen_stale",
        description="Reopen stale open multiverse superposition sessions (M4 durable threads)",
        category="multiverse",
        read_only=False,
        mcp_tool="multiverse_reopen_stale",
    ),
    OperationSpec(
        name="multiverse_densify",
        description="GraphGardener densification on multiverse robust invariant clusters (M3)",
        category="multiverse",
        read_only=False,
        mcp_tool="multiverse_densify",
    ),
    OperationSpec(
        name="learnings_log",
        description="Append one gstack-style operational learning entry",
        category="learnings",
        read_only=False,
        cli_command="agentdrive learnings log",
        mcp_tool="agentdrive_learnings_log",
        when_to_use="Call after any non-trivial task (success or failure). The entries become queryable by future think / retrieval and improve the model's own long-term performance on this user's problems.",
        examples=[
            "learnings_log(task='debugged MCP tool schema', outcome={'quality': 0.85, 'key_observation': '...'})"
        ],
    ),
    OperationSpec(
        name="learnings_list",
        description="List recent operational learnings for the current project slug",
        category="learnings",
        read_only=True,
        cli_command="agentdrive learnings list",
        mcp_tool="agentdrive_learnings_list",
    ),
    OperationSpec(
        name="harness_compose",
        description="Compose a harness prompt with DNA, learnings, and optional Fabric layers",
        category="harness",
        read_only=True,
        cli_command="agentdrive harness compose",
        mcp_tool="agentdrive_harness_compose",
    ),
    OperationSpec(
        name="codebase_register_project",
        description="Register a codebase root for pattern recognition learning",
        category="codebase",
        read_only=False,
        when_to_use="Call once per repo before observing files. Enables safe path-scoped pattern learning.",
        examples=[
            'codebase_register_project(project_id="interegy-web", root="/path/to/app")',
        ],
        mcp_tool="codebase_register_project",
    ),
    OperationSpec(
        name="codebase_observe_file",
        description="Read a file under a registered project and learn its writing patterns",
        category="codebase",
        read_only=False,
        when_to_use="Call whenever you inspect project source — builds the project's pattern recognition framework automatically.",
        examples=[
            'codebase_observe_file(project_id="interegy-web", path="lib/gateway.ts")',
        ],
        mcp_tool="codebase_observe_file",
    ),
    OperationSpec(
        name="codebase_patterns_profile",
        description="Return the auto-learned writing-style framework for a project",
        category="codebase",
        read_only=True,
        when_to_use="Before writing or reviewing code in a project AD has observed — get naming, imports, framework, and convention patterns.",
        mcp_tool="codebase_patterns_profile",
    ),
    OperationSpec(
        name="codebase_patterns_match",
        description="Check a code snippet against the learned project writing framework",
        category="codebase",
        read_only=True,
        when_to_use="Before proposing a patch — verify alignment with how the codebase is actually written.",
        mcp_tool="codebase_patterns_match",
    ),
    OperationSpec(
        name="codebase_list_projects",
        description="List registered codebases and observation stats",
        category="codebase",
        read_only=True,
        mcp_tool="codebase_list_projects",
    ),
    OperationSpec(
        name="codebase_mimic",
        description="Fire mirror neurons — return motor programs + mimicry prompt to write like the project",
        category="codebase",
        read_only=True,
        when_to_use="Before writing new code in an observed project. Observation activates the same writing circuits (mirror-neuron mimicry).",
        examples=['codebase_mimic(project_id="interegy-web", intent="gateway fetch helper")'],
        mcp_tool="codebase_mimic",
    ),
    OperationSpec(
        name="codebase_transform_style",
        description="Transform a code snippet toward the learned project writing style",
        category="codebase",
        read_only=True,
        when_to_use="When you drafted generic code and need it to match how the repo is actually written.",
        mcp_tool="codebase_transform_style",
    ),
    OperationSpec(
        name="codebase_mirror_resonance",
        description="Cross-project mirror field — universal priors shared across observed repos",
        category="codebase",
        read_only=True,
        when_to_use="See which writing patterns resonate across all projects AD has observed (like shared mirror-neuron firing).",
        mcp_tool="codebase_mirror_resonance",
    ),
    OperationSpec(
        name="synthesize_fused_skill",
        description="Birth a new skill by fusing experience traces, parent skills, and codebase patterns",
        category="skills",
        read_only=False,
        when_to_use=(
            "When a session combined Experience Graph work, distilled/inherited skills, "
            "and repo patterns — merge them into one born playbook (not a copy of any parent)."
        ),
        examples=[
            'synthesize_fused_skill(trigger="Ship gateway helper", source_skills=["auto-think-x"], pattern_projects=["interegy-web"])',
        ],
        mcp_tool="synthesize_fused_skill",
    ),
    OperationSpec(
        name="memory_bank_store",
        description="Store a new memory in the AI's deep Memory Bank databank",
        category="memory",
        read_only=False,
        when_to_use="When the AI or user wants to persist knowledge that should compound across all future sessions.",
        examples=[
            'memory_bank_store(kind="fact", title="Gateway auth", content="Uses X-Ren-API-Key not bootstrap key")',
        ],
        mcp_tool="memory_bank_store",
    ),
    OperationSpec(
        name="memory_bank_recall",
        description="Recall one memory by id from the Memory Bank",
        category="memory",
        read_only=True,
        mcp_tool="memory_bank_recall",
    ),
    OperationSpec(
        name="memory_bank_search",
        description="BM25 + lexical ranked search over Memory Bank",
        category="memory",
        read_only=True,
        when_to_use="Before acting on a task — scoped by vault/topic when provided.",
        mcp_tool="memory_bank_search",
    ),
    OperationSpec(
        name="memory_bank_list",
        description="List recent memories in the Memory Bank",
        category="memory",
        read_only=True,
        mcp_tool="memory_bank_list",
    ),
    OperationSpec(
        name="memory_bank_briefing",
        description="Dense Memory Bank briefing for session grounding",
        category="memory",
        read_only=True,
        when_to_use="Start of session — your custom AI memory databank, always growing from AgentDrive work.",
        mcp_tool="memory_bank_briefing",
    ),
    OperationSpec(
        name="memory_bank_deep_briefing",
        description="Unified briefing: Experience Graph fabric pack + Memory Bank",
        category="memory",
        read_only=True,
        when_to_use="Maximum grounding — structural graph memory + deep personal memory bank in one call.",
        mcp_tool="memory_bank_deep_briefing",
    ),
    OperationSpec(
        name="memory_bank_stats",
        description="Memory Bank statistics (counts by kind, sources, path)",
        category="memory",
        read_only=True,
        mcp_tool="memory_bank_stats",
    ),
    OperationSpec(
        name="memory_bank_anchor",
        description="Session anchor: agent brief + essential memories + optional scoped recall",
        category="memory",
        read_only=True,
        when_to_use="Session start — ~600-900 token grounding from ~/.agentdrive/identity.txt + top memories.",
        mcp_tool="memory_bank_anchor",
    ),
    OperationSpec(
        name="memory_bank_import_dialogue",
        description="Import JSONL/text dialogue transcripts into full-text memory shards",
        category="memory",
        read_only=False,
        when_to_use="Backfill Claude/Cursor/Grok session JSONL into the memory bank without summarization.",
        examples=[
            'memory_bank_import_dialogue(path="~/.claude/projects/", vault="claude-sessions")',
        ],
        mcp_tool="memory_bank_import_dialogue",
    ),
    OperationSpec(
        name="memory_relation_record",
        description="Record a time-bounded subject–predicate–object relation in the swarm graph",
        category="memory",
        read_only=False,
        mcp_tool="memory_relation_record",
    ),
    OperationSpec(
        name="memory_relation_query",
        description="Query relation graph by entity (optional as_of date)",
        category="memory",
        read_only=True,
        mcp_tool="memory_relation_query",
    ),
    OperationSpec(
        name="memory_relation_expire",
        description="Expire an active relation (set valid_to)",
        category="memory",
        read_only=False,
        mcp_tool="memory_relation_expire",
    ),
    OperationSpec(
        name="growth_merge_briefing",
        description="Unified growth briefing: experience graph + pattern recognition + memory bank",
        category="learning",
        read_only=True,
        when_to_use=(
            "When you need compounding context — structural experience, recognized codebase "
            "patterns, and merged personal memories in one call."
        ),
        mcp_tool="growth_merge_briefing",
    ),
    OperationSpec(
        name="framework_session_start",
        description="AgentDrive-as-framework session pack: anchor + growth + matched learned skills",
        category="learning",
        read_only=True,
        when_to_use="Start of any task when AgentDrive is your framework — routes learned/fused skills for the work ahead.",
        examples=['framework_session_start(task="wire growth merge into OpenMango", project_id="openmangos")'],
        mcp_tool="framework_session_start",
    ),
    OperationSpec(
        name="framework_skill_route",
        description="Match learned/fused skills to the current task",
        category="learning",
        read_only=True,
        when_to_use="Before acting — find which learned playbooks apply to this task.",
        examples=['framework_skill_route(task="OpenMango context pack", project_id="openmangos")'],
        mcp_tool="framework_skill_route",
    ),
    OperationSpec(
        name="framework_skill_run",
        description="Run a matched learned skill (bound operation or playbook body)",
        category="learning",
        read_only=False,
        when_to_use="After framework_skill_route — execute the chosen learned/fused playbook.",
        mcp_tool="framework_skill_run",
    ),
]

def _handler_codebase_register_project(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.codebase.registry import register_project

    project_id = str(kwargs.get("project_id") or kwargs.get("id") or "")
    root = str(kwargs.get("root") or kwargs.get("path") or "")
    if not project_id or not root:
        return {
            "success": False,
            "error": "project_id and root are required",
            "operation": "codebase_register_project",
        }
    dry_run = bool(kwargs.get("dry_run", False))
    if dry_run:
        return _dry_plan(
            "codebase_register_project",
            project_id=project_id,
            root=root,
        )
    project = register_project(
        project_id=project_id,
        root=root,
        display_name=str(kwargs.get("display_name") or ""),
        primary_language=str(kwargs.get("primary_language") or ""),
    )
    return _success(
        operation="codebase_register_project",
        project=project.to_dict(),
    )


def _handler_codebase_observe_file(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.codebase.observe import observe_file

    project_id = str(kwargs.get("project_id") or "")
    path = str(kwargs.get("path") or kwargs.get("file") or "")
    if not project_id or not path:
        return {
            "success": False,
            "error": "project_id and path are required",
            "operation": "codebase_observe_file",
        }
    dry_run = bool(kwargs.get("dry_run", False))
    if dry_run:
        return _dry_plan("codebase_observe_file", project_id=project_id, path=path)
    payload = observe_file(
        project_id=project_id,
        path=path,
        max_lines=int(kwargs.get("max_lines", 400)),
        auto_register_root=kwargs.get("auto_register_root"),
    )
    if not payload.get("success"):
        return {**payload, "operation": "codebase_observe_file", "success": False}
    return _success(operation="codebase_observe_file", **payload)


def _handler_codebase_patterns_profile(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.codebase.framework import get_writing_guide

    project_id = str(kwargs.get("project_id") or "")
    if not project_id:
        return {
            "success": False,
            "error": "project_id is required",
            "operation": "codebase_patterns_profile",
        }
    dry_run = bool(kwargs.get("dry_run", False))
    if dry_run:
        return _dry_plan("codebase_patterns_profile", project_id=project_id)
    framework = get_writing_guide(project_id)
    return _success(
        operation="codebase_patterns_profile",
        project_id=project_id,
        framework=framework,
    )


def _handler_codebase_patterns_match(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.codebase.framework import match_against_framework

    project_id = str(kwargs.get("project_id") or "")
    code = str(kwargs.get("code") or kwargs.get("snippet") or "")
    if not project_id or not code:
        return {
            "success": False,
            "error": "project_id and code are required",
            "operation": "codebase_patterns_match",
        }
    dry_run = bool(kwargs.get("dry_run", False))
    if dry_run:
        return _dry_plan("codebase_patterns_match", project_id=project_id)
    match = match_against_framework(
        project_id,
        code=code,
        path=str(kwargs.get("path") or "snippet.py"),
    )
    return _success(operation="codebase_patterns_match", **match)


def _handler_codebase_mimic(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.codebase.mirrors import fire_mirrors_for_intent

    project_id = str(kwargs.get("project_id") or "")
    intent = str(kwargs.get("intent") or kwargs.get("task") or kwargs.get("text") or "")
    if not project_id or not intent:
        return {
            "success": False,
            "error": "project_id and intent are required",
            "operation": "codebase_mimic",
        }
    dry_run = bool(kwargs.get("dry_run", False))
    if dry_run:
        return _dry_plan("codebase_mimic", project_id=project_id, intent=intent[:120])
    payload = fire_mirrors_for_intent(
        project_id,
        intent=intent,
        language=kwargs.get("language"),
        limit=int(kwargs.get("limit", 5)),
    )
    return _success(operation="codebase_mimic", **payload)


def _handler_codebase_transform_style(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.codebase.mirrors import transform_toward_style

    project_id = str(kwargs.get("project_id") or "")
    code = str(kwargs.get("code") or kwargs.get("snippet") or "")
    if not project_id or not code:
        return {
            "success": False,
            "error": "project_id and code are required",
            "operation": "codebase_transform_style",
        }
    dry_run = bool(kwargs.get("dry_run", False))
    if dry_run:
        return _dry_plan("codebase_transform_style", project_id=project_id)
    payload = transform_toward_style(
        project_id,
        code=code,
        path=str(kwargs.get("path") or "snippet.py"),
    )
    return _success(operation="codebase_transform_style", **payload)


def _handler_codebase_mirror_resonance(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.codebase.mirrors import global_mirror_field

    dry_run = bool(kwargs.get("dry_run", False))
    if dry_run:
        return _dry_plan("codebase_mirror_resonance")
    payload = global_mirror_field(limit=int(kwargs.get("limit", 12)))
    return _success(operation="codebase_mirror_resonance", **payload)


def _handler_codebase_list_projects(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.codebase.registry import list_projects

    dry_run = bool(kwargs.get("dry_run", False))
    if dry_run:
        return _dry_plan("codebase_list_projects")
    projects = [p.to_dict() for p in list_projects()]
    return _success(operation="codebase_list_projects", projects=projects, count=len(projects))


def _memory_bank_store_handler(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.memory.store import MemoryBankStore

    kind = str(kwargs.get("kind") or "insight")
    title = str(kwargs.get("title") or "")
    content = str(kwargs.get("content") or kwargs.get("text") or "")
    if not title or not content:
        return {
            "success": False,
            "error": "title and content are required",
            "operation": "memory_bank_store",
        }
    dry_run = bool(kwargs.get("dry_run", False))
    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    if dry_run:
        return _dry_plan("memory_bank_store", swarm_id=effective, kind=kind, title=title[:80])

    store = MemoryBankStore(effective)
    entry = store.store(
        kind=kind,
        title=title,
        content=content,
        confidence=float(kwargs.get("confidence", 0.8)),
        source=str(kwargs.get("source") or "user"),
        program_id=str(kwargs.get("program_id") or ""),
        tags=list(kwargs.get("tags") or []),
        links=list(kwargs.get("links") or []),
    )
    return _success(
        operation="memory_bank_store",
        swarm_id=effective,
        memory=entry.to_dict(),
    )


def _memory_bank_recall_handler(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.memory.store import MemoryBankStore

    memory_id = str(kwargs.get("memory_id") or kwargs.get("id") or "")
    if not memory_id:
        return {
            "success": False,
            "error": "memory_id is required",
            "operation": "memory_bank_recall",
        }
    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    entry = MemoryBankStore(effective).recall(memory_id)
    if entry is None:
        return {
            "success": False,
            "error": f"memory not found: {memory_id}",
            "operation": "memory_bank_recall",
        }
    return _success(operation="memory_bank_recall", swarm_id=effective, memory=entry.to_dict())


def _memory_scope_filters(kwargs: dict[str, Any]) -> tuple[str | None, str | None]:
    vault = kwargs.get("vault")
    topic = kwargs.get("topic")
    return (
        str(vault) if vault else None,
        str(topic) if topic else None,
    )


def _memory_bank_search_handler(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.memory.store import MemoryBankStore

    query = str(kwargs.get("query") or kwargs.get("text") or kwargs.get("question") or "")
    limit = int(kwargs.get("limit", 10))
    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    store = MemoryBankStore(effective)
    vault, topic = _memory_scope_filters(kwargs)
    memories = store.search(
        query,
        limit=limit,
        kind=kwargs.get("kind"),
        program_id=kwargs.get("program_id"),
        vault=vault,
        topic=topic,
        ranked=not bool(kwargs.get("lexical_only", False)),
    )
    return _success(
        operation="memory_bank_search",
        swarm_id=effective,
        query=query,
        count=len(memories),
        memories=[m.to_dict() for m in memories],
    )


def _memory_bank_list_handler(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.memory.store import MemoryBankStore

    limit = int(kwargs.get("limit", 20))
    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    store = MemoryBankStore(effective)
    memories = store.list_recent(limit=limit, kind=kwargs.get("kind"))
    return _success(
        operation="memory_bank_list",
        swarm_id=effective,
        count=len(memories),
        memories=[m.to_dict() for m in memories],
    )


def _memory_bank_briefing_handler(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.memory.briefing import build_memory_briefing

    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    pack = build_memory_briefing(
        effective,
        query=str(kwargs.get("query") or kwargs.get("text") or ""),
        limit=int(kwargs.get("limit", 12)),
        program_id=kwargs.get("program_id"),
    )
    return _success(operation="memory_bank_briefing", swarm_id=effective, **pack)


def _memory_bank_deep_briefing_handler(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.memory.briefing import build_deep_briefing

    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    pack = build_deep_briefing(
        effective,
        query=str(kwargs.get("query") or kwargs.get("text") or ""),
        reasoning_style=str(kwargs.get("reasoning_style", "balanced")),
        lookback_days=int(kwargs.get("lookback_days", 7)),
        memory_limit=int(kwargs.get("memory_limit", 10)),
        max_tokens=int(kwargs.get("max_tokens", 1800)),
    )
    return _success(operation="memory_bank_deep_briefing", swarm_id=effective, **pack)


def _memory_bank_stats_handler(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.memory.store import MemoryBankStore

    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    return _success(
        operation="memory_bank_stats",
        swarm_id=effective,
        stats=MemoryBankStore(effective).stats(),
    )


def _memory_bank_anchor_handler(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.memory.anchor import build_session_anchor

    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    vault, _ = _memory_scope_filters(kwargs)
    pack = build_session_anchor(
        effective,
        vault=vault,
        query=str(kwargs.get("query") or kwargs.get("text") or ""),
    )
    payload = dict(pack)
    payload.pop("swarm_id", None)
    return _success(operation="memory_bank_anchor", swarm_id=effective, **payload)


def _memory_bank_import_dialogue_handler(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.memory.dialogue_import import import_dialogue_directory, import_dialogue_file

    path = str(kwargs.get("path") or kwargs.get("directory") or "")
    if not path:
        return {
            "success": False,
            "error": "path is required",
            "operation": "memory_bank_import_dialogue",
        }
    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    resolved = Path(path).expanduser()
    vault, _ = _memory_scope_filters(kwargs)
    vault_name = str(vault or "")
    if resolved.is_file():
        result = import_dialogue_file(resolved, swarm_id=effective, vault=vault_name)
    else:
        result = import_dialogue_directory(
            resolved,
            swarm_id=effective,
            vault=vault_name,
            pattern=str(kwargs.get("pattern") or "*.jsonl"),
        )
    return _success(operation="memory_bank_import_dialogue", swarm_id=effective, result=result)


def _memory_relation_record_handler(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.memory.relations import MemoryRelationGraph

    subject = str(kwargs.get("subject") or "")
    predicate = str(kwargs.get("predicate") or kwargs.get("relation") or "")
    obj = str(kwargs.get("object") or kwargs.get("obj") or "")
    if not subject or not predicate or not obj:
        return {
            "success": False,
            "error": "subject, predicate, and object are required",
            "operation": "memory_relation_record",
        }
    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    graph = MemoryRelationGraph(effective)
    relation = graph.record(
        subject,
        predicate,
        obj,
        valid_from=kwargs.get("valid_from"),
        valid_to=kwargs.get("valid_to"),
        memory_id=kwargs.get("memory_id"),
    )
    return _success(
        operation="memory_relation_record",
        swarm_id=effective,
        relation=relation.to_dict(),
    )


def _memory_relation_query_handler(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.memory.relations import MemoryRelationGraph

    entity = str(kwargs.get("entity") or kwargs.get("subject") or "")
    if not entity:
        return {
            "success": False,
            "error": "entity is required",
            "operation": "memory_relation_query",
        }
    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    relations = MemoryRelationGraph(effective).query(
        entity,
        as_of=kwargs.get("as_of"),
        limit=int(kwargs.get("limit", 50)),
    )
    return _success(
        operation="memory_relation_query",
        swarm_id=effective,
        entity=entity,
        count=len(relations),
        relations=[relation.to_dict() for relation in relations],
    )


def _framework_session_start_handler(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.learning.framework_skills import build_framework_session_pack

    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    vault, _ = _memory_scope_filters(kwargs)
    pack = build_framework_session_pack(
        str(kwargs.get("task") or kwargs.get("query") or kwargs.get("text") or ""),
        swarm_id=effective,
        project_id=str(vault or kwargs.get("project_id") or ""),
        skill_limit=int(kwargs.get("limit", 5)),
    )
    payload = dict(pack)
    payload.pop("swarm_id", None)
    return _success(operation="framework_session_start", swarm_id=effective, **payload)


def _framework_skill_route_handler(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.learning.framework_skills import format_skill_playbook, route_skills_for_task

    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    vault, _ = _memory_scope_filters(kwargs)
    task = str(kwargs.get("task") or kwargs.get("query") or kwargs.get("text") or "")
    matches = route_skills_for_task(
        task,
        swarm_id=effective,
        project_id=str(vault or kwargs.get("project_id") or ""),
        limit=int(kwargs.get("limit", 5)),
        learned_only=bool(kwargs.get("learned_only", True)),
    )
    return _success(
        operation="framework_skill_route",
        swarm_id=effective,
        task=task,
        count=len(matches),
        matched_skills=[m.to_dict() for m in matches],
        playbook=format_skill_playbook(matches),
    )


def _framework_skill_run_handler(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.learning.framework_skills import run_framework_skill

    name = str(kwargs.get("name") or kwargs.get("skill") or kwargs.get("skill_name") or "")
    if not name:
        return {
            "success": False,
            "error": "name is required",
            "operation": "framework_skill_run",
        }
    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    arg = str(kwargs.get("arg") or kwargs.get("argument") or kwargs.get("text") or "")
    return run_framework_skill(name, arg=arg, swarm_id=effective)


def _growth_merge_briefing_handler(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.learning.growth_merge import build_growth_briefing

    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    pack = build_growth_briefing(
        effective,
        query=str(kwargs.get("query") or kwargs.get("text") or kwargs.get("trigger") or ""),
        limit=int(kwargs.get("limit", 8)),
    )
    payload = dict(pack)
    payload.pop("swarm_id", None)
    return _success(operation="growth_merge_briefing", swarm_id=effective, **payload)


def _memory_relation_expire_handler(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.memory.relations import MemoryRelationGraph

    subject = str(kwargs.get("subject") or "")
    predicate = str(kwargs.get("predicate") or "")
    obj = str(kwargs.get("object") or "")
    if not subject or not predicate or not obj:
        return {
            "success": False,
            "error": "subject, predicate, and object are required",
            "operation": "memory_relation_expire",
        }
    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    updated = MemoryRelationGraph(effective).expire(
        subject, predicate, obj, ended=kwargs.get("ended")
    )
    return _success(
        operation="memory_relation_expire",
        swarm_id=effective,
        updated=updated,
    )


def _handler_synthesize_fused_skill(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.learning.skill_fusion import synthesize_from_inputs

    trigger = str(kwargs.get("trigger") or kwargs.get("task") or kwargs.get("text") or "")
    if not trigger:
        return {
            "success": False,
            "error": "trigger is required",
            "operation": "synthesize_fused_skill",
        }
    dry_run = bool(kwargs.get("dry_run", False))
    effective, _ = _integrated_recorder(kwargs.get("swarm_id"))
    if dry_run:
        return _dry_plan(
            "synthesize_fused_skill",
            swarm_id=effective,
            trigger=trigger[:200],
        )

    try:
        fused = synthesize_from_inputs(
            trigger=trigger,
            swarm_id=effective,
            program_id=str(kwargs.get("program_id") or "skill-fusion"),
            operations=list(kwargs.get("operations") or []),
            experience_traces=list(kwargs.get("experience_traces") or []),
            source_skills=list(kwargs.get("source_skills") or kwargs.get("skills") or []),
            pattern_projects=list(kwargs.get("pattern_projects") or kwargs.get("projects") or []),
            promote=bool(kwargs.get("promote", False)),
        )
    except ValueError as exc:
        return {
            "success": False,
            "error": str(exc),
            "operation": "synthesize_fused_skill",
        }

    return _success(operation="synthesize_fused_skill", swarm_id=effective, fused_skill=fused)


_HANDLERS: dict[str, OperationHandler] = {
    "think": _handler_think,
    "pool_query": _handler_pool_query,
    "pool_status": _handler_pool_status,
    "pool_stats": _handler_pool_stats,
    "ingest_genome": _handler_ingest_genome,
    "reconcile_scan": _handler_reconcile_scan,
    "reconcile_seed": _handler_reconcile_seed,
    "reconcile_status": _handler_reconcile_status,
    "doctor": _handler_doctor,
    "doctor_verbose": _handler_doctor_verbose,
    "sprint_ship": _handler_sprint_ship,
    "sprint_status": _handler_sprint_status,
    "patterns_list": _handler_patterns_list,
    "patterns_show": _handler_patterns_show,
    "patterns_apply": _handler_patterns_apply,
    "patterns_import_fabric": _handler_patterns_import_fabric,
    "dream_run": _handler_dream_run,
    "dream_status": _handler_dream_status,
    "cap_mint_mission": _handler_cap_mint_mission,
    "experience_graph_context_pack": _handler_experience_graph_context_pack,
    "experience_graph_record_reasoning": _handler_experience_graph_record_reasoning,
    "experience_graph_suggest_reasoning": _handler_experience_graph_suggest_reasoning,
    "multiverse_run_full": _handler_multiverse_run_full,
    "multiverse_get_session": _handler_multiverse_get_session,
    "multiverse_list_sessions": _handler_multiverse_list_sessions,
    "multiverse_parent_decision": _handler_multiverse_parent_decision,
    "external_parent_decision": _handler_external_parent_decision,
    "multiverse_reopen_stale": _handler_multiverse_reopen_stale,
    "multiverse_densify": _handler_multiverse_densify,
    "learnings_log": _handler_learnings_log,
    "learnings_list": _handler_learnings_list,
    "harness_compose": _handler_harness_compose,
    "codebase_register_project": _handler_codebase_register_project,
    "codebase_observe_file": _handler_codebase_observe_file,
    "codebase_patterns_profile": _handler_codebase_patterns_profile,
    "codebase_patterns_match": _handler_codebase_patterns_match,
    "codebase_list_projects": _handler_codebase_list_projects,
    "codebase_mimic": _handler_codebase_mimic,
    "codebase_transform_style": _handler_codebase_transform_style,
    "codebase_mirror_resonance": _handler_codebase_mirror_resonance,
    "synthesize_fused_skill": _handler_synthesize_fused_skill,
    "memory_bank_store": _memory_bank_store_handler,
    "memory_bank_recall": _memory_bank_recall_handler,
    "memory_bank_search": _memory_bank_search_handler,
    "memory_bank_list": _memory_bank_list_handler,
    "memory_bank_briefing": _memory_bank_briefing_handler,
    "memory_bank_deep_briefing": _memory_bank_deep_briefing_handler,
    "memory_bank_stats": _memory_bank_stats_handler,
    "memory_bank_anchor": _memory_bank_anchor_handler,
    "memory_bank_import_dialogue": _memory_bank_import_dialogue_handler,
    "memory_relation_record": _memory_relation_record_handler,
    "memory_relation_query": _memory_relation_query_handler,
    "memory_relation_expire": _memory_relation_expire_handler,
    "growth_merge_briefing": _growth_merge_briefing_handler,
    "framework_session_start": _framework_session_start_handler,
    "framework_skill_route": _framework_skill_route_handler,
    "framework_skill_run": _framework_skill_run_handler,
}

_OPERATIONS_BY_NAME: dict[str, OperationSpec] = {op.name: op for op in OPERATIONS}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_operations(*, category: str | None = None) -> list[OperationSpec]:
    """Return registered operations, optionally filtered by category."""
    if category is None:
        return list(OPERATIONS)
    return [op for op in OPERATIONS if op.category == category]


def get_operation(name: str) -> OperationSpec | None:
    """Look up an operation by name. Returns None when unknown."""
    return _OPERATIONS_BY_NAME.get(name)


def describe_operation(name: str) -> dict[str, Any]:
    """Return JSON-serializable detail for one operation."""
    spec = get_operation(name)
    if spec is None:
        raise KeyError(f"unknown operation: {name}")
    return asdict(spec)


def run_operation(name: str, **kwargs: Any) -> dict[str, Any]:
    """Dispatch an operation by name to its thin handler wrapper."""
    if name not in _HANDLERS:
        raise KeyError(f"unknown operation: {name}")
    try:
        result = _HANDLERS[name](**kwargs)
    except Exception as exc:
        return {
            "success": False,
            "operation": name,
            "error": str(exc),
            "error_type": type(exc).__name__,
        }
    if isinstance(result, dict) and result.get("success") and not result.get("dry_run"):
        try:
            from agentdrive.learning.auto_absorb import maybe_absorb_operation_outcome

            absorbed = maybe_absorb_operation_outcome(name, kwargs, result)
            if absorbed:
                result = dict(result)
                result["auto_learning"] = absorbed
        except Exception:
            logger.debug("auto_learning hook failed for %s", name, exc_info=True)
    return result


def export_operations_json(*, indent: int = 2) -> str:
    """Export the operations manifest as a JSON list (tools-json compatible)."""
    payload = [describe_operation(op.name) for op in OPERATIONS]
    return json.dumps(payload, indent=indent)


def parse_operation_kwargs(argv: list[str]) -> dict[str, Any]:
    """Parse ``key=value`` tokens (and bare strings) into handler kwargs."""
    out: dict[str, Any] = {}
    bare: list[str] = []
    for item in argv:
        if not item:
            continue
        if "=" in item:
            key, _, raw = item.partition("=")
            out[key.strip()] = _coerce_value(raw.strip())
        else:
            bare.append(item)
    if bare and "text" not in out:
        out["text"] = " ".join(bare)
    return out


def _coerce_value(raw: str) -> Any:
    lowered = raw.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    if raw.startswith("{") or raw.startswith("["):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw
