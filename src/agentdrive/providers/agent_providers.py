"""Per-agent provider resolution for the Agent Drive chat surface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import agentdrive.providers.builtins  # noqa: F401 - register built-in providers
from agentdrive.constants import get_agentdrive_home
from agentdrive.providers.base import ProviderProfile, list_available
from agentdrive.utils.safe_paths import PathTraversalError, safe_name


def _config_path(agent_id: str, home: Path | None = None) -> Path:
    # Prevent path traversal via untrusted agent_id coming from web routes / user input.
    safe_id = safe_name(agent_id)
    return (home or get_agentdrive_home()) / "agents" / safe_id / "providers.json"


def _load_agent_provider_config(agent_id: str, home: Path | None = None) -> dict[str, Any]:
    if not agent_id:
        return {}
    try:
        path = _config_path(agent_id, home)
    except PathTraversalError:
        return {}
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def resolve_agent_providers(agent_id: str, home: Path | None = None) -> list[ProviderProfile]:
    """Return the available providers allowed for ``agent_id``.

    Missing config, an empty allow-list, or ``["*"]`` means "all providers that
    are currently available" where availability is still determined by the
    registry profile's ``has_key()`` behavior.
    """
    available = list_available()
    config = _load_agent_provider_config(agent_id, home)
    allow = config.get("providers")
    if not isinstance(allow, list) or not allow or "*" in allow:
        return available

    allowed_names = {str(name).lower() for name in allow}
    return [profile for profile in available if profile.name.lower() in allowed_names]


def resolve_agent_default(agent_id: str, home: Path | None = None) -> tuple[str, str] | None:
    """Return the initial provider/model selection for ``agent_id``."""
    providers = resolve_agent_providers(agent_id, home)
    if not providers:
        return None

    config = _load_agent_provider_config(agent_id, home)
    default = config.get("default")
    if isinstance(default, dict):
        provider_name = str(default.get("provider") or "")
        model = str(default.get("model") or "")
        for profile in providers:
            if profile.name == provider_name:
                return profile.name, model or profile.default_model

    first = providers[0]
    return first.name, first.default_model
