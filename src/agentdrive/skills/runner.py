"""Run a skill by name — shared by CLI and chat slash (Pattern 5)."""

from __future__ import annotations

from typing import Any

from agentdrive.operations import run_operation
from agentdrive.skills.registry import SkillEntry, get_skill, skill_operation_kwargs
from agentdrive.skills.usage import record_skill_run


def run_skill(name: str, arg: str = "") -> dict[str, Any]:
    """Execute a skill. Returns operation result dict or error envelope."""
    entry = get_skill(name)
    if entry is None:
        return {"success": False, "error": f"Unknown skill: {name}"}

    if entry.operation == "golden_path_verify":
        from agentdrive.golden_path import verify_all

        summary = verify_all()
        success = bool(summary.get("required_pass"))
        _record_run_safely(entry.name, success=success)
        return {
            "success": success,
            "skill": entry.name,
            "result": summary,
        }

    if entry.operation:
        kwargs = skill_operation_kwargs(entry, arg)
        result = run_operation(entry.operation, **kwargs)
        success = bool(result.get("success", False))
        _record_run_safely(entry.name, success=success)
        return {"success": success, "skill": entry.name, "result": result}

    # No bound operation — return skill body for the caller to display.
    _record_run_safely(entry.name, success=True)
    return {
        "success": True,
        "skill": entry.name,
        "description": entry.description,
        "body": entry.body,
        "hint": f"Skill '{entry.name}' has no agentdrive_operation — display body only.",
    }


def format_skill_result(result: dict[str, Any], *, preview_limit: int = 4000) -> str:
    """Plain-text summary of a run_skill result for CLI/TUI."""
    if not result.get("success"):
        return str(result.get("error") or "skill failed")

    inner = result.get("result")
    if isinstance(inner, dict):
        if inner.get("error"):
            return str(inner["error"])
        if name := inner.get("result"):
            if isinstance(name, dict):
                answer = name.get("answer") or name.get("synthesis")
                if answer:
                    return str(answer)
        if composed := inner.get("composed_prompt"):
            text = str(composed)
            return text[:preview_limit] + ("…" if len(text) > preview_limit else "")

    if body := result.get("body"):
        text = str(body)
        return text[:preview_limit] + ("…" if len(text) > preview_limit else "")

    return result.get("description") or "ok"


def _record_run_safely(name: str, *, success: bool) -> None:
    try:
        record_skill_run(name, success=success)
    except Exception:
        pass
