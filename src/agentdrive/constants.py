"""Shared constants for AgentDrive.

Import-safe module with no heavy dependencies — can be imported from anywhere
without risk of circular imports. Designed for consistency across the agent ecosystem.
"""

import os
from contextlib import contextmanager
from contextvars import ContextVar, Token
from pathlib import Path

_UNSET = object()
_AGENTDRIVE_HOME_OVERRIDE: ContextVar[str | object] = ContextVar(
    "_AGENTDRIVE_HOME_OVERRIDE", default=_UNSET
)

# Swarm and sub-agent scoping for per-swarm / per-subagent isolated pools
_SWARM_ID_CTX: ContextVar[str | object] = ContextVar("_SWARM_ID_CTX", default=_UNSET)
_SUBAGENT_ID_CTX: ContextVar[str | object] = ContextVar("_SUBAGENT_ID_CTX", default=_UNSET)


def set_agentdrive_home_override(path: str | Path | None) -> Token:
    """Set a context-local Savant home override (for testing, scoped runs)."""
    value: str | object = _UNSET if path is None else str(path)
    return _AGENTDRIVE_HOME_OVERRIDE.set(value)


def reset_agentdrive_home_override(token: Token) -> None:
    """Restore the previous context-local Savant home override."""
    _AGENTDRIVE_HOME_OVERRIDE.reset(token)


def get_agentdrive_home_override() -> str | None:
    """Return the active context-local Savant home override, if any."""
    override = _AGENTDRIVE_HOME_OVERRIDE.get()
    if override is _UNSET or not override:
        return None
    return str(override)


# --- Swarm / Subagent context scoping (for automatic isolated pool provisioning on spawn) ---


def set_current_swarm_id(swarm_id: str | None) -> Token:
    """Set context-local current swarm_id (used by get_default_drive and harness to auto-scope)."""
    value: str | object = _UNSET if swarm_id is None else str(swarm_id)
    return _SWARM_ID_CTX.set(value)


def reset_current_swarm_id(token: Token) -> None:
    """Restore previous swarm context."""
    _SWARM_ID_CTX.reset(token)


def get_current_swarm_id() -> str | None:
    """Active swarm_id: prefers context override, falls back to AGENTDRIVE_SWARM_ID env var (set by spawners like Grok spawn_subagent)."""
    v = _SWARM_ID_CTX.get()
    if v is not _UNSET and v:
        return str(v)
    env = os.environ.get("AGENTDRIVE_SWARM_ID", "").strip()
    return env if env else None


def set_current_subagent_id(subagent_id: str | None) -> Token:
    """Set context-local current subagent_id for this child's private pool."""
    value: str | object = _UNSET if subagent_id is None else str(subagent_id)
    return _SUBAGENT_ID_CTX.set(value)


def reset_current_subagent_id(token: Token) -> None:
    """Restore previous subagent context."""
    _SUBAGENT_ID_CTX.reset(token)


def get_current_subagent_id() -> str | None:
    """Active subagent_id: context or AGENTDRIVE_SUBAGENT_ID env (each spawned child gets unique)."""
    v = _SUBAGENT_ID_CTX.get()
    if v is not _UNSET and v:
        return str(v)
    env = os.environ.get("AGENTDRIVE_SUBAGENT_ID", "").strip()
    return env if env else None


@contextmanager
def using_swarm(swarm_id: str, subagent_id: str | None = None):
    """
    Context manager to scope a block of code to a specific swarm/subagent.
    Inside the with: get_default_drive() will return the child's isolated pool.
    Ideal for in-process simulation of sub-agent spawning.
    """
    t_swarm = set_current_swarm_id(swarm_id)
    t_sub = set_current_subagent_id(subagent_id)
    try:
        yield
    finally:
        reset_current_subagent_id(t_sub)
        reset_current_swarm_id(t_swarm)


def get_agentdrive_home() -> Path:
    """
    Return the Savant home directory (default: ~/.agentdrive).

    Respects AGENTDRIVE_HOME env var.
    Single source of truth for all Savant data: config, genomes, logs, cache.
    """
    override = get_agentdrive_home_override()
    if override:
        return Path(override)

    val = os.environ.get("AGENTDRIVE_HOME", "").strip()
    if val:
        return Path(val)

    return Path.home() / ".agentdrive"


def get_savant_config_path() -> Path:
    """Path to the main config.yaml."""
    return get_agentdrive_home() / "config.yaml"


def get_savant_env_path() -> Path:
    """Path to the .env file for secrets."""
    return get_agentdrive_home() / ".env"


# Standard subdirectories
def get_genomes_dir() -> Path:
    return get_agentdrive_home() / "genomes"


def get_logs_dir() -> Path:
    return get_agentdrive_home() / "logs"


def get_cache_dir() -> Path:
    return get_agentdrive_home() / "cache"


def get_default_drive_path() -> Path:
    """Path to the AgentDrive data directory (persistent ingest logs, drive metadata, etc.)."""
    return get_agentdrive_home() / "drive"


def get_swarms_dir() -> Path:
    """Root for all swarm-isolated AgentDrives (each sub-agent gets its own DNA)."""
    return get_agentdrive_home() / "swarms"


def get_swarm_drive_path(swarm_id: str, subagent_id: str | None = None) -> Path:
    """Path to the shared Drive for a swarm.

    AgentDrive v2 (Milestone 2a): all sub-agents in the same swarm share one
    Drive at ``<swarms>/<swarm_id>/drive/``. Sub-agents namespace their writes
    via the Genome author field (``manifest.authors[*].id = "sub:<sub_id>"``);
    reads are unrestricted across siblings. This is the "we work together"
    experience pool — the sibling-learning primitive Pablo asked for.

    ``subagent_id`` is accepted for backwards compatibility with v1 callers
    but is now informational. It does NOT affect the returned path. Code that
    needs per-sub-agent isolation should ingest with explicit author tagging
    and filter via ``DriveQuery`` instead. Sub-agent membership is tracked in
    ``SwarmDriveManager.list_active_swarms()``.
    """
    from agentdrive.utils.safe_paths import safe_join

    sid = swarm_id or "default"
    # Untrusted ``swarm_id`` is a tagged input source for CodeQL — validate
    # the joined path stays under the swarms root before any I/O happens.
    return safe_join(get_swarms_dir(), sid, "drive")


# Version and identifiers
SAVANT_VERSION = "0.2.0"  # Keep in sync with __init__.py and pyproject

# Default config keys (used by config.py)
DEFAULT_SAVANT_HOME_NAME = ".agentdrive"

__all__ = [
    "get_agentdrive_home",
    "get_agentdrive_home_override",
    "set_agentdrive_home_override",
    "reset_agentdrive_home_override",
    "get_savant_config_path",
    "get_savant_env_path",
    "get_genomes_dir",
    "get_logs_dir",
    "get_cache_dir",
    "get_default_drive_path",
    "get_swarms_dir",
    "get_swarm_drive_path",
    "set_current_swarm_id",
    "reset_current_swarm_id",
    "get_current_swarm_id",
    "set_current_subagent_id",
    "reset_current_subagent_id",
    "get_current_subagent_id",
    "using_swarm",
    "SAVANT_VERSION",
]
