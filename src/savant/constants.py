"""Shared constants for Savant Framework.

Import-safe module with no heavy dependencies — can be imported from anywhere
without risk of circular imports. Designed for consistency across the agent ecosystem.
"""

import os
from contextlib import contextmanager
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Optional


_UNSET = object()
_SAVANT_HOME_OVERRIDE: ContextVar[str | object] = ContextVar(
    "_SAVANT_HOME_OVERRIDE", default=_UNSET
)

# Swarm and sub-agent scoping for per-swarm / per-subagent isolated pools
_SWARM_ID_CTX: ContextVar[str | object] = ContextVar("_SWARM_ID_CTX", default=_UNSET)
_SUBAGENT_ID_CTX: ContextVar[str | object] = ContextVar("_SUBAGENT_ID_CTX", default=_UNSET)


def set_savant_home_override(path: str | Path | None) -> Token:
    """Set a context-local Savant home override (for testing, scoped runs)."""
    value: str | object = _UNSET if path is None else str(path)
    return _SAVANT_HOME_OVERRIDE.set(value)


def reset_savant_home_override(token: Token) -> None:
    """Restore the previous context-local Savant home override."""
    _SAVANT_HOME_OVERRIDE.reset(token)


def get_savant_home_override() -> str | None:
    """Return the active context-local Savant home override, if any."""
    override = _SAVANT_HOME_OVERRIDE.get()
    if override is _UNSET or not override:
        return None
    return str(override)


# --- Swarm / Subagent context scoping (for automatic isolated pool provisioning on spawn) ---

def set_current_swarm_id(swarm_id: str | None) -> Token:
    """Set context-local current swarm_id (used by get_default_pool and harness to auto-scope)."""
    value: str | object = _UNSET if swarm_id is None else str(swarm_id)
    return _SWARM_ID_CTX.set(value)


def reset_current_swarm_id(token: Token) -> None:
    """Restore previous swarm context."""
    _SWARM_ID_CTX.reset(token)


def get_current_swarm_id() -> Optional[str]:
    """Active swarm_id: prefers context override, falls back to SAVANT_SWARM_ID env var (set by spawners like Grok spawn_subagent)."""
    v = _SWARM_ID_CTX.get()
    if v is not _UNSET and v:
        return str(v)
    env = os.environ.get("SAVANT_SWARM_ID", "").strip()
    return env if env else None


def set_current_subagent_id(subagent_id: str | None) -> Token:
    """Set context-local current subagent_id for this child's private pool."""
    value: str | object = _UNSET if subagent_id is None else str(subagent_id)
    return _SUBAGENT_ID_CTX.set(value)


def reset_current_subagent_id(token: Token) -> None:
    """Restore previous subagent context."""
    _SUBAGENT_ID_CTX.reset(token)


def get_current_subagent_id() -> Optional[str]:
    """Active subagent_id: context or SAVANT_SUBAGENT_ID env (each spawned child gets unique)."""
    v = _SUBAGENT_ID_CTX.get()
    if v is not _UNSET and v:
        return str(v)
    env = os.environ.get("SAVANT_SUBAGENT_ID", "").strip()
    return env if env else None


@contextmanager
def using_swarm(swarm_id: str, subagent_id: Optional[str] = None):
    """
    Context manager to scope a block of code to a specific swarm/subagent.
    Inside the with: get_default_pool() will return the child's isolated pool.
    Ideal for in-process simulation of sub-agent spawning.
    """
    t_swarm = set_current_swarm_id(swarm_id)
    t_sub = set_current_subagent_id(subagent_id)
    try:
        yield
    finally:
        reset_current_subagent_id(t_sub)
        reset_current_swarm_id(t_swarm)


def get_savant_home() -> Path:
    """
    Return the Savant home directory (default: ~/.savant).

    Respects SAVANT_HOME env var.
    Single source of truth for all Savant data: config, genomes, logs, cache.
    """
    override = get_savant_home_override()
    if override:
        return Path(override)

    val = os.environ.get("SAVANT_HOME", "").strip()
    if val:
        return Path(val)

    return Path.home() / ".savant"


def get_savant_config_path() -> Path:
    """Path to the main config.yaml."""
    return get_savant_home() / "config.yaml"


def get_savant_env_path() -> Path:
    """Path to the .env file for secrets."""
    return get_savant_home() / ".env"


# Standard subdirectories
def get_genomes_dir() -> Path:
    return get_savant_home() / "genomes"


def get_logs_dir() -> Path:
    return get_savant_home() / "logs"


def get_cache_dir() -> Path:
    return get_savant_home() / "cache"


def get_savant_pool_path() -> Path:
    """Path to the Savant Pool data directory (persistent ingest logs, pool metadata, etc.)."""
    return get_savant_home() / "pool"


def get_swarms_dir() -> Path:
    """Root for all swarm-isolated Savant Pools (each sub-agent gets its own DNA)."""
    return get_savant_home() / "swarms"


def get_swarm_pool_path(swarm_id: str, subagent_id: Optional[str] = None) -> Path:
    """Isolated pool directory for a specific swarm / sub-agent.

    This is the core of Savant Swarm support: every time an agent (Grok, Claude, etc.)
    spawns sub-agents, each child receives its own persistent, user-controlled DNA pool
    that starts empty and fills with its unique experience (memory + patterns).
    """
    sid = swarm_id or "default"
    base = get_swarms_dir() / sid
    if subagent_id:
        base = base / subagent_id
    return base / "pool"


# Version and identifiers
SAVANT_VERSION = "0.1.0"  # Keep in sync with __init__.py and pyproject

# Default config keys (used by config.py)
DEFAULT_SAVANT_HOME_NAME = ".savant"

__all__ = [
    "get_savant_home",
    "get_savant_home_override",
    "set_savant_home_override",
    "reset_savant_home_override",
    "get_savant_config_path",
    "get_savant_env_path",
    "get_genomes_dir",
    "get_logs_dir",
    "get_cache_dir",
    "get_savant_pool_path",
    "get_swarms_dir",
    "get_swarm_pool_path",
    "set_current_swarm_id",
    "reset_current_swarm_id",
    "get_current_swarm_id",
    "set_current_subagent_id",
    "reset_current_subagent_id",
    "get_current_subagent_id",
    "using_swarm",
    "SAVANT_VERSION",
]
