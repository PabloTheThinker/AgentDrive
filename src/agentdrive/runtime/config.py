"""Runtime config loading and persistence."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agentdrive.constants import get_agentdrive_home
from agentdrive.runtime.base import build, is_registered
from agentdrive.utils.safe_paths import PathTraversalError, safe_join, safe_name


def runtime_config_path(agent_id: str, home: Path | None = None) -> Path:
    """Build a safe path for an agent's runtime.json.

    Uses the project's safe_name + safe_join (CodeQL-recognized sanitizers)
    to prevent path traversal from untrusted agent_id values.
    """
    try:
        safe_id = safe_name(agent_id)
        root = home or get_agentdrive_home()
        return safe_join(root / "agents", safe_id) / "runtime.json"
    except PathTraversalError as e:
        raise ValueError(f"Invalid agent_id: {e}") from e


def load_runtime_config(agent_id: str, home: Path | None = None) -> dict[str, Any]:
    if not agent_id:
        return {"kind": "model"}
    try:
        path = runtime_config_path(agent_id, home)
    except ValueError:
        return {"kind": "model"}
    if not path.exists():
        return {"kind": "model"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"kind": "model"}
    if not isinstance(data, dict):
        return {"kind": "model"}
    kind = str(data.get("kind") or "model").strip().lower()
    return {**data, "kind": kind}


def write_runtime_config(
    agent_id: str,
    config: dict[str, Any],
    home: Path | None = None,
) -> Path:
    if not isinstance(config, dict):
        raise ValueError("runtime config must be a JSON object")
    kind = str(config.get("kind") or "").strip().lower()
    if not kind:
        raise ValueError("runtime kind is required")
    if not is_registered(kind):
        raise ValueError(f"unknown agent runtime kind: {kind}")

    clean = {**config, "kind": kind}
    path = runtime_config_path(agent_id, home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(clean, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.chmod(0o600)
    os.replace(tmp, path)
    path.chmod(0o600)
    return path


def resolve_adapter(agent_id: str):
    config = load_runtime_config(agent_id)
    return build(agent_id, config)
