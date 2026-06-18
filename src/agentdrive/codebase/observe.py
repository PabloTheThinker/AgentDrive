"""Observe files and accumulate codebase writing patterns."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentdrive.codebase.analyzer import analyze_content
from agentdrive.codebase.framework import crystallize_framework
from agentdrive.codebase.registry import (
    append_observation,
    bump_observation,
    get_project,
    register_project,
)
from agentdrive.utils.safe_paths import safe_join

logger = logging.getLogger(__name__)


def _record_mirror_trace(project_id: str, path: str, mirror_result: dict[str, Any]) -> None:
    """Write mirror-neuron firing into the Experience Graph (observation → motor link)."""
    if not mirror_result.get("motors_fired"):
        return
    try:
        from agentdrive.operations.registry import _integrated_recorder  # noqa: PLC2701

        _, recorder = _integrated_recorder(None)
        recorder.record_parent_fabric_reasoning(
            cycle_id=f"mirror-{project_id}-{int(__import__('time').time())}",
            reasoning={
                "summary": f"Mirror neurons fired on {path}",
                "structural_pattern_matched": "mirror-neuron-mimicry",
                "fabric_elements_considered": [
                    f"codebase:{project_id}",
                    f"file:{path}",
                    *(mirror_result.get("pattern_keys") or [])[:5],
                ],
                "decision_rationale": (
                    f"Observed code primed {mirror_result.get('motors_fired')} motor programs "
                    "for future mimicry (mirror-neuron coupling)."
                ),
                "expected_lift_signal": 0.1,
                "llm_mode": "mirror_neuron",
                "mirror_neurons": mirror_result,
            },
        )
    except Exception:
        logger.debug("mirror trace record failed", exc_info=True)


_ALLOWED_EXT = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".md",
    ".json",
    ".yaml",
    ".yml",
}


def _resolve_under_project(project_id: str, rel_path: str) -> Path:
    project = get_project(project_id)
    if project is None:
        raise KeyError(f"Unknown project: {project_id}. Register with codebase_register_project.")
    rel = (rel_path or "").strip().lstrip("/")
    parts = [p for p in rel.split("/") if p and p not in (".", "..")]
    if not parts:
        raise ValueError("Empty path")
    return safe_join(project.root, *parts)


def observe_file(
    *,
    project_id: str,
    path: str,
    max_lines: int = 400,
    content: str | None = None,
    auto_register_root: str | None = None,
) -> dict[str, Any]:
    """Read (or accept) a file under a registered project and learn its patterns."""
    if get_project(project_id) is None:
        if not auto_register_root:
            raise KeyError(f"Unknown project: {project_id}")
        register_project(project_id=project_id, root=auto_register_root)

    full_path = _resolve_under_project(project_id, path)
    if full_path.suffix.lower() not in _ALLOWED_EXT:
        return {
            "success": False,
            "error": f"Extension {full_path.suffix} not allowed",
            "project_id": project_id,
        }
    if content is None:
        if not full_path.is_file():
            return {"success": False, "error": f"File not found: {path}", "project_id": project_id}
        raw = full_path.read_text(encoding="utf-8", errors="replace")
        lines = raw.splitlines()[:max_lines]
        content = "\n".join(lines)

    rel = path.strip().lstrip("/")
    signals = analyze_content(path=rel, content=content)
    observation = {
        **signals.to_dict(),
        "observed_at": datetime.now(UTC).isoformat(),
        "source": "codebase_observe",
    }
    append_observation(project_id, observation)
    bump_observation(project_id)

    mirror_result: dict[str, Any] = {}
    try:
        from agentdrive.codebase.mirrors import ingest_observation_mirror

        mirror_result = ingest_observation_mirror(
            project_id,
            path=rel,
            content=content,
            observation=observation,
        )
        _record_mirror_trace(project_id, rel, mirror_result)
    except Exception:
        logger.debug("mirror neuron ingest failed", exc_info=True)

    framework = crystallize_framework(project_id)

    return {
        "success": True,
        "project_id": project_id,
        "path": rel,
        "language": signals.language,
        "frameworks": signals.frameworks,
        "signals": signals.signals,
        "files_observed": framework.get("file_count", 0),
        "patterns_count": len(framework.get("patterns") or []),
        "crystallized": bool(framework.get("crystallized_at")),
        "framework": framework if framework.get("crystallized_at") else None,
        "mirror_neurons": mirror_result,
    }


def observe_text(
    *,
    project_id: str,
    path: str,
    content: str,
) -> dict[str, Any]:
    """Observe in-memory content (e.g. from inhabitant_read_source) without disk read."""
    return observe_file(project_id=project_id, path=path, content=content)


def auto_observe_inhabitant_read(
    *,
    rel_path: str,
    content: str,
    project_id: str = "agentdrive",
    package_root: str | None = None,
) -> dict[str, Any] | None:
    """Hook for inhabitant_read_source — learn AgentDrive (or package) writing style."""
    try:
        if package_root and get_project(project_id) is None:
            register_project(project_id=project_id, root=package_root)
        return observe_text(project_id=project_id, path=rel_path, content=content)
    except Exception:
        logger.debug("auto_observe_inhabitant_read failed", exc_info=True)
        return None


def observe_from_absolute(
    *,
    project_id: str,
    absolute_path: str,
    max_lines: int = 400,
    auto_register_root: str | None = None,
) -> dict[str, Any]:
    """Observe using an absolute path — derives project-relative path when possible."""
    resolved = Path(absolute_path).expanduser().resolve()
    project = get_project(project_id)
    if project is None:
        root = auto_register_root or str(resolved.parent)
        register_project(project_id=project_id, root=root)
        project = get_project(project_id)
    assert project is not None
    try:
        rel = str(resolved.relative_to(Path(project.root).resolve()))
    except ValueError:
        rel = resolved.name
    content = resolved.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()[:max_lines]
    return observe_file(
        project_id=project_id,
        path=rel,
        content="\n".join(lines),
    )
