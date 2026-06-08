"""
Canonical golden path for AgentDrive first-run.

Install → doctor → mcp → seed → think → learnings → drive query

Used by ``agentdrive golden-path``, ``examples/00_golden_path.sh``, and docs/GOLDEN_PATH.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentdrive import get_agentdrive_home
from agentdrive.operations import run_operation


@dataclass(frozen=True)
class GoldenStep:
    """One step in the golden path."""

    id: str
    title: str
    command: str
    description: str
    optional: bool = False


GOLDEN_STEPS: tuple[GoldenStep, ...] = (
    GoldenStep(
        id="install",
        title="Install",
        command="curl -fsSL https://vektraindustries.com/agentdrive/install.sh | bash",
        description="Creates ~/.agentdrive/venv, installs agentdrive[mcp], shims agentdrive + agentdrive-mcp.",
    ),
    GoldenStep(
        id="doctor",
        title="Health check",
        command="agentdrive doctor",
        description="Verify home directory, config, registry, and MCP bridge readiness.",
    ),
    GoldenStep(
        id="mcp",
        title="Wire MCP",
        command="agentdrive mcp install && agentdrive mcp doctor",
        description="Install [mcp] extra and merge configs for Grok, Cursor, Claude, Continue.",
    ),
    GoldenStep(
        id="seed",
        title="Experience seed",
        command="agentdrive reconcile seed-experience-v3",
        description="Bootstrap experience layer v3 (auto-runs on first Drive access; explicit if doctor shows empty).",
        optional=True,
    ),
    GoldenStep(
        id="think",
        title="First synthesis",
        command='agentdrive think "What does my AgentDrive contain after first install?"',
        description="Cited Drive.think with mandatory gap analysis — proves synthesis + experience layer.",
    ),
    GoldenStep(
        id="learnings",
        title="Record learning",
        command='agentdrive learnings log --key golden-path --insight "Completed first-run golden path"',
        description="Append gstack-style operational memory that harness and future sessions can reuse.",
    ),
    GoldenStep(
        id="query",
        title="Query Drive",
        command='agentdrive drive query "dedup identical agent outputs"',
        description="Semantic genome search — the persistent DNA pool answering a real task.",
    ),
)


def step_by_id(step_id: str) -> GoldenStep | None:
    for step in GOLDEN_STEPS:
        if step.id == step_id:
            return step
    return None


def _seed_present() -> bool:
    home = get_agentdrive_home()
    markers = [
        home / "genomes" / "living-experience-seed-v3.json",
        home / "drive" / "genomes" / "living-experience-seed-v3.json",
    ]
    if any(p.is_file() for p in markers):
        return True
    try:
        from agentdrive.drive.drive import get_default_drive

        stats = get_default_drive().get_pool_stats()
        return int(stats.get("total_genomes") or stats.get("genome_count") or 0) > 0
    except Exception:
        return False


def verify_step(step_id: str) -> dict[str, Any]:
    """Check whether a golden-path step appears satisfied."""
    step = step_by_id(step_id)
    if step is None:
        return {"success": False, "step": step_id, "error": f"unknown step: {step_id}"}

    if step_id == "install":
        home = get_agentdrive_home()
        ok = home.is_dir()
        return {
            "success": ok,
            "step": step_id,
            "title": step.title,
            "detail": f"home={home}" if ok else "AGENTDRIVE_HOME not initialized",
        }

    if step_id == "doctor":
        result = run_operation("doctor")
        return {
            "success": bool(result.get("success")),
            "step": step_id,
            "title": step.title,
            "detail": result.get("summary") or result.get("error") or "doctor completed",
            "result": result,
        }

    if step_id == "mcp":
        from agentdrive.adapters.mcp_config import run_mcp_doctor

        report = run_mcp_doctor()
        ok = bool(report.get("ok"))
        return {
            "success": ok,
            "step": step_id,
            "title": step.title,
            "detail": f"tools={report.get('tool_count', 0)}",
            "report": report,
        }

    if step_id == "seed":
        ok = _seed_present()
        return {
            "success": ok,
            "step": step_id,
            "title": step.title,
            "optional": True,
            "detail": "experience seed or genomes present" if ok else "empty registry — run seed-experience-v3",
        }

    if step_id == "think":
        result = run_operation("think", question="Golden path verification", dry_run=True)
        return {
            "success": bool(result.get("success")),
            "step": step_id,
            "title": step.title,
            "detail": "think dry-run ok" if result.get("success") else result.get("error"),
        }

    if step_id == "learnings":
        from agentdrive.learnings import LearningsStore

        store = LearningsStore()
        count = store.count()
        return {
            "success": count > 0,
            "step": step_id,
            "title": step.title,
            "detail": f"{count} learnings (slug={store.slug})",
        }

    if step_id == "query":
        result = run_operation(
            "pool_query",
            task="dedup identical agent outputs",
            limit=3,
            dry_run=True,
        )
        return {
            "success": bool(result.get("success")),
            "step": step_id,
            "title": step.title,
            "detail": "drive query dry-run ok" if result.get("success") else result.get("error"),
        }

    return {"success": False, "step": step_id, "error": "unhandled step"}


def verify_all(*, include_optional: bool = True) -> dict[str, Any]:
    """Verify every golden-path step."""
    checks: list[dict[str, Any]] = []
    for step in GOLDEN_STEPS:
        if step.optional and not include_optional:
            continue
        checks.append(verify_step(step.id))

    required = [c for c in checks if not step_by_id(c["step"]).optional]  # type: ignore[arg-type]
    optional = [c for c in checks if step_by_id(c["step"]).optional]  # type: ignore[arg-type]
    required_ok = all(c.get("success") for c in required)
    optional_ok = all(c.get("success") for c in optional) if optional else True

    return {
        "success": required_ok and optional_ok,
        "required_pass": required_ok,
        "optional_pass": optional_ok,
        "steps": checks,
        "passed": sum(1 for c in checks if c.get("success")),
        "total": len(checks),
    }


def run_walkthrough(
    *,
    dry_run: bool = False,
    stop_on_fail: bool = True,
    skip_install: bool = True,
) -> dict[str, Any]:
    """Execute golden-path operations (install step is verify-only unless skip_install=False)."""
    results: list[dict[str, Any]] = []

    for step in GOLDEN_STEPS:
        if step.id == "install":
            if skip_install:
                check = verify_step("install")
                results.append({**check, "action": "verify"})
                if stop_on_fail and not check.get("success"):
                    break
            continue

        if step.id == "doctor":
            result = run_operation("doctor")
            entry = {"step": step.id, "title": step.title, "success": result.get("success"), "result": result}
            results.append(entry)
            if stop_on_fail and not result.get("success"):
                break
            continue

        if step.id == "mcp":
            from agentdrive.adapters.mcp_config import run_mcp_doctor

            report = run_mcp_doctor()
            entry = {
                "step": step.id,
                "title": step.title,
                "success": bool(report.get("ok")),
                "report": report,
                "note": "Run agentdrive mcp install if doctor fails",
            }
            results.append(entry)
            if stop_on_fail and not entry["success"]:
                break
            continue

        if step.id == "seed":
            if _seed_present():
                results.append(
                    {
                        "step": step.id,
                        "title": step.title,
                        "success": True,
                        "skipped": True,
                        "detail": "seed already present",
                    }
                )
                continue
            if dry_run:
                result = run_operation("reconcile_seed", dry_run=True)
            else:
                result = run_operation("reconcile_seed")
            entry = {"step": step.id, "title": step.title, "success": result.get("success"), "result": result}
            results.append(entry)
            if stop_on_fail and not result.get("success"):
                break
            continue

        if step.id == "think":
            kwargs: dict[str, Any] = {
                "question": "What does my AgentDrive contain after first install?",
            }
            if dry_run:
                kwargs["dry_run"] = True
            result = run_operation("think", **kwargs)
            entry = {"step": step.id, "title": step.title, "success": result.get("success"), "result": result}
            results.append(entry)
            if stop_on_fail and not result.get("success"):
                break
            continue

        if step.id == "learnings":
            if dry_run:
                result = run_operation(
                    "learnings_log",
                    dry_run=True,
                    key="golden-path",
                    insight="Golden path walkthrough (dry-run)",
                )
            else:
                result = run_operation(
                    "learnings_log",
                    key="golden-path",
                    insight="Completed AgentDrive golden path walkthrough",
                    type="operational",
                    source="observed",
                )
            entry = {"step": step.id, "title": step.title, "success": result.get("success"), "result": result}
            results.append(entry)
            if stop_on_fail and not result.get("success"):
                break
            continue

        if step.id == "query":
            kwargs = {"task": "dedup identical agent outputs", "limit": 3}
            if dry_run:
                kwargs["dry_run"] = True
            result = run_operation("pool_query", **kwargs)
            entry = {"step": step.id, "title": step.title, "success": result.get("success"), "result": result}
            results.append(entry)
            if stop_on_fail and not result.get("success"):
                break
            continue

    success = all(r.get("success") for r in results)
    return {
        "success": success,
        "dry_run": dry_run,
        "steps": results,
        "passed": sum(1 for r in results if r.get("success")),
        "total": len(results),
    }