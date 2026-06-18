"""Register codebase roots for safe pattern observation."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from agentdrive.constants import get_agentdrive_home
from agentdrive.utils.safe_paths import safe_name

logger = logging.getLogger(__name__)

_REGISTRY_NAME = "projects.yaml"


@dataclass
class CodebaseProject:
    project_id: str
    root: str
    display_name: str = ""
    primary_language: str = ""
    registered_at: str = ""
    files_observed: int = 0
    last_observed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _registry_path() -> Path:
    root = get_agentdrive_home() / "codebase-patterns"
    root.mkdir(parents=True, exist_ok=True)
    return root / _REGISTRY_NAME


def _profile_dir(project_id: str) -> Path:
    slug = safe_name(project_id)
    path = get_agentdrive_home() / "codebase-patterns" / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_registry() -> dict[str, Any]:
    path = _registry_path()
    if not path.is_file():
        return {"projects": {}}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        logger.debug("Failed to load codebase registry", exc_info=True)
        return {"projects": {}}
    if not isinstance(data, dict):
        return {"projects": {}}
    data.setdefault("projects", {})
    return data


def _save_registry(data: dict[str, Any]) -> None:
    path = _registry_path()
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def register_project(
    *,
    project_id: str,
    root: str,
    display_name: str = "",
    primary_language: str = "",
) -> CodebaseProject:
    slug = safe_name(project_id)
    resolved = Path(root).expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"Project root not found: {resolved}")

    data = _load_registry()
    projects = data["projects"]
    now = datetime.now(UTC).isoformat()
    existing = projects.get(slug) or {}
    project = CodebaseProject(
        project_id=slug,
        root=str(resolved),
        display_name=display_name or existing.get("display_name") or slug,
        primary_language=primary_language or existing.get("primary_language") or "",
        registered_at=existing.get("registered_at") or now,
        files_observed=int(existing.get("files_observed") or 0),
        last_observed_at=existing.get("last_observed_at") or "",
    )
    projects[slug] = project.to_dict()
    _save_registry(data)
    _profile_dir(slug)
    return project


def list_projects() -> list[CodebaseProject]:
    data = _load_registry()
    projects: list[CodebaseProject] = []
    for raw in (data.get("projects") or {}).values():
        if isinstance(raw, dict):
            projects.append(
                CodebaseProject(**{k: raw.get(k, "") for k in CodebaseProject.__dataclass_fields__})
            )
    return sorted(projects, key=lambda p: p.project_id)


def get_project(project_id: str) -> CodebaseProject | None:
    slug = safe_name(project_id)
    raw = (_load_registry().get("projects") or {}).get(slug)
    if not isinstance(raw, dict):
        return None
    return CodebaseProject(**{k: raw.get(k, "") for k in CodebaseProject.__dataclass_fields__})


def bump_observation(project_id: str) -> None:
    slug = safe_name(project_id)
    data = _load_registry()
    projects = data.get("projects") or {}
    raw = projects.get(slug)
    if not isinstance(raw, dict):
        return
    raw["files_observed"] = int(raw.get("files_observed") or 0) + 1
    raw["last_observed_at"] = datetime.now(UTC).isoformat()
    projects[slug] = raw
    data["projects"] = projects
    _save_registry(data)


def observations_path(project_id: str) -> Path:
    return _profile_dir(project_id) / "observations.jsonl"


def framework_path(project_id: str) -> Path:
    return _profile_dir(project_id) / "framework.json"


def append_observation(project_id: str, observation: dict[str, Any]) -> None:
    path = observations_path(project_id)
    line = json.dumps(observation, default=str)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
