"""
Contract-first operation definitions for AgentDrive.

Single source of truth for CLI surfaces, MCP tool mapping, and tools-json export
(gbrain operations.ts pattern).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

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
        kwargs.get("question")
        or kwargs.get("text")
        or "What should I know about this AgentDrive?"
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
    from agentdrive.drive.drive import get_default_drive

    pool = get_default_drive()
    stats = pool.get_pool_stats()
    return _success(
        operation="pool_status",
        dry_run=bool(kwargs.get("dry_run", False)),
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
    from agentdrive.registry import GenomeRegistry
    from agentdrive.reconciliation import ReconciliationRunner

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
    return _success(operation="patterns_list", dry_run=bool(kwargs.get("dry_run", False)), patterns=rows, count=len(rows))


def _handler_patterns_show(**kwargs: Any) -> dict[str, Any]:
    name = kwargs.get("pattern_name") or kwargs.get("name") or kwargs.get("text")
    if not name:
        return {"success": False, "error": "pattern_name is required", "operation": "patterns_show"}

    from agentdrive.patterns import PatternNotFoundError, get_pattern

    try:
        record = get_pattern(str(name))
    except PatternNotFoundError:
        return {"success": False, "error": f"pattern not found: {name}", "operation": "patterns_show"}

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
        return {"success": False, "error": "pattern_name is required", "operation": "patterns_apply"}
    if bool(kwargs.get("dry_run", False)):
        return _dry_plan("patterns_apply", pattern_name=str(name), input_preview=input_text[:200])

    from agentdrive.patterns import PatternNotFoundError, apply_pattern

    try:
        prompt = apply_pattern(str(name), input_text)
    except PatternNotFoundError:
        return {"success": False, "error": f"pattern not found: {name}", "operation": "patterns_apply"}
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
        imported = [import_fabric_pattern(fabric_root, str(pattern_name), dest_root, overwrite=overwrite)]
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

    results = run_dream_cycle(dry_run=dry_run, ack_phases=ack_phases or None, acquire_lock=not dry_run)
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
    return _success(operation="dream_status", dry_run=bool(kwargs.get("dry_run", False)), status=status)


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
    return _success(operation="experience_graph_context_pack", swarm_id=effective, context_pack=pack)


def _handler_experience_graph_record_reasoning(**kwargs: Any) -> dict[str, Any]:
    swarm_id = kwargs.get("swarm_id")
    cycle_id = kwargs.get("cycle_id")
    reasoning = kwargs.get("reasoning")
    dry_run = bool(kwargs.get("dry_run", False))
    effective, _ = _integrated_recorder(swarm_id)

    if reasoning is None:
        reasoning = {
            "summary": str(kwargs.get("summary") or kwargs.get("text") or "ops-registry dry reasoning"),
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


def _handler_learnings_log(**kwargs: Any) -> dict[str, Any]:
    from agentdrive.learnings import LearningsStore

    dry_run = bool(kwargs.get("dry_run", False))
    entry = {
        "type": str(kwargs.get("type", "pattern")),
        "key": str(kwargs.get("key") or "ops-registry-entry"),
        "insight": str(kwargs.get("insight") or kwargs.get("text") or "ops registry learning entry"),
        "confidence": int(kwargs.get("confidence", 5)),
        "source": str(kwargs.get("source", "observed")),
        "skill": str(kwargs.get("skill", "harness")),
    }
    if dry_run:
        return _dry_plan("learnings_log", entry=entry)

    store = LearningsStore(slug=kwargs.get("slug"))
    record = store.log(entry)
    return _success(operation="learnings_log", slug=store.slug, record=record)


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

    base_prompt = str(kwargs.get("base_prompt") or kwargs.get("prompt") or "You are an AgentDrive agent.")
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
        examples=["think(question='How should I structure long-horizon agent memory?')", "think with dry_run first to plan"],
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
        name="learnings_log",
        description="Append one gstack-style operational learning entry",
        category="learnings",
        read_only=False,
        cli_command="agentdrive learnings log",
        mcp_tool="agentdrive_learnings_log",
        when_to_use="Call after any non-trivial task (success or failure). The entries become queryable by future think / retrieval and improve the model's own long-term performance on this user's problems.",
        examples=["learnings_log(task='debugged MCP tool schema', outcome={'quality': 0.85, 'key_observation': '...'})"],
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
]

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
    "learnings_log": _handler_learnings_log,
    "learnings_list": _handler_learnings_list,
    "harness_compose": _handler_harness_compose,
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
        return _HANDLERS[name](**kwargs)
    except Exception as exc:
        return {
            "success": False,
            "operation": name,
            "error": str(exc),
            "error_type": type(exc).__name__,
        }


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