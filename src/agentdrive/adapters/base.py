"""
SavantAdapter — Base Protocol and Implementation for Multi-Model Pool Integration.

This is the universal contract that every model-specific adapter (Grok, Claude, Codex, ...)
must satisfy. It abstracts:

- Obtaining a (possibly scoped) AgentDrive for the current task / swarm / sub-agent.
- Automatic detection of swarm/sub-agent identity from environment (set by parent
  spawner or by the adapter's patched spawn mechanism).
- Creating Harness instances already bound to the right pool.
- User-controlled settings lookup (isolation, auto-ingest, sharing).

Any AI that can import Python (or call out via tools/MCP) can use this directly.
Model-specific adapters add the "glue" for that model's sub-agent spawning story
(e.g. wrapping `spawn_subagent` in the Grok build system).

Key environment variables for automatic scoping (injected by adapters into children):
    AGENTDRIVE_SWARM_ID      — identifies the parent swarm / mission
    AGENTDRIVE_SUBAGENT_ID   — unique id for this sub-agent within the swarm
    AGENTDRIVE_HOME          — optional override (inherited)

Usage (universal, works for any model):

    from agentdrive.adapters import get_scoped_pool, Harness  # or from agentdrive import ...

    pool = get_scoped_pool()                    # auto-scoped if env present
    harness = Harness(agent_id="my-sub-007", pool=pool)
    with harness.task_context("the sub-task"):
        dna = harness.pull_relevant_dna()
        ...
        harness.record_outcome({...})

User instruction example the model should receive:
    "For the rest of this session and every sub-agent you create, use the Savant
     Pool system. Activate it with: from agentdrive.adapters import activate_for_grok_build;
     activate_for_grok_build(swarm_id='research-2026-05'). All your children will
     automatically receive their own isolated DNA pools."
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from agentdrive.constants import get_swarms_dir
from agentdrive.drive.drive import AgentDrive, get_default_drive
from agentdrive.drive.settings import (
    DriveSettings,
    get_effective_drive_settings,
)
from agentdrive.harness.harness import Harness
from agentdrive.registry import GenomeRegistry

logger = logging.getLogger(__name__)


class SavantAdapter(Protocol):
    """Protocol defining the integration surface for any AI model / agent runtime.

    Implementations:
    - SavantAdapterBase (universal fallback)
    - GrokBuildSavantAdapter (Grok build system + spawn_subagent)
    - ClaudeCodeSavantAdapter
    - CodexSavantAdapter
    """

    def get_name(self) -> str:
        """Short identifier, e.g. 'grok-build', 'claude-code'."""
        ...

    def get_pool(self, swarm_id: str | None = None, subagent_id: str | None = None) -> AgentDrive:
        """Return a AgentDrive, creating a scoped one if swarm/sub ids supplied."""
        ...

    def get_scoped_pool(self) -> AgentDrive:
        """Return the Drive appropriate for the *current* execution context.

        Auto-detects SAVANT_* env vars (or equivalent runtime context).
        This is the method sub-agents should primarily call.
        """
        ...

    def get_harness(self, agent_id: str) -> Harness:
        """Convenience: return a harness already wired to the correct (scoped) pool."""
        ...

    def get_settings(self, swarm_id: str | None = None) -> DriveSettings:
        """Return the user-controlled settings that apply here."""
        ...

    def activate(self, swarm_id: str | None = None, **options: Any) -> None:
        """One-time activation for the current model session.

        For Grok etc. this typically:
        - Sets process env for auto-detection
        - Patches the model's native sub-agent spawner (so children inherit scope)
        - Optionally starts or connects to the local MCP server
        """
        ...

    def health(self) -> bool:
        """Quick check that the adapter + backing pool/registry are usable."""
        ...


@dataclass
class SavantContext:
    """Lightweight carrier of swarm identity that can be passed to children."""

    swarm_id: str | None = None
    subagent_id: str | None = None
    parent_agent_id: str | None = None
    extra: dict[str, Any] = None  # type: ignore[assignment]

    def as_env(self) -> dict[str, str]:
        env: dict[str, str] = {}
        if self.swarm_id:
            env["AGENTDRIVE_SWARM_ID"] = self.swarm_id
        if self.subagent_id:
            env["AGENTDRIVE_SUBAGENT_ID"] = self.subagent_id
        if self.parent_agent_id:
            env["SAVANT_PARENT_AGENT_ID"] = self.parent_agent_id
        return env


class SavantAdapterBase:
    """Concrete base implementation. Safe default for any model.

    Model-specific adapters should subclass and override:
    - get_name
    - activate (to do the spawn patching + env injection)
    - optionally get_pool for custom scoping rules
    """

    def __init__(
        self,
        name: str = "universal",
        default_swarm_id: str | None = None,
        default_subagent_id: str | None = None,
    ):
        self._name = name
        self._default_swarm = default_swarm_id
        self._default_sub = default_subagent_id
        self._activated = False
        logger.debug("SavantAdapterBase initialized (%s)", name)

    def get_name(self) -> str:
        return self._name

    def detect_context(self) -> SavantContext:
        """Detect current swarm/sub from environment (or internal defaults)."""
        swarm, sub = detect_swarm_context()
        return SavantContext(
            swarm_id=swarm or self._default_swarm,
            subagent_id=sub or self._default_sub,
        )

    def get_pool(self, swarm_id: str | None = None, subagent_id: str | None = None) -> AgentDrive:
        ctx = self.detect_context()
        swarm = swarm_id or ctx.swarm_id
        sub = subagent_id or ctx.subagent_id
        return create_scoped_pool(swarm, sub)

    def get_scoped_pool(self) -> AgentDrive:
        return self.get_pool()

    def get_harness(self, agent_id: str) -> Harness:
        pool = self.get_scoped_pool()
        return Harness(agent_id=agent_id, pool=pool)

    def get_settings(self, swarm_id: str | None = None) -> DriveSettings:
        ctx = self.detect_context()
        sid = swarm_id or ctx.swarm_id
        return get_effective_drive_settings(sid)

    def activate(self, swarm_id: str | None = None, **options: Any) -> None:
        """Base activation: just ensure env + defaults are set for this process.

        Subclasses (Grok etc.) do the heavy lifting of patching their spawner here.
        """
        if swarm_id:
            os.environ["AGENTDRIVE_SWARM_ID"] = swarm_id
            self._default_swarm = swarm_id
        if options.get("subagent_id"):
            os.environ["AGENTDRIVE_SUBAGENT_ID"] = options["subagent_id"]
            self._default_sub = options["subagent_id"]

        self._activated = True
        logger.info(
            "SavantAdapterBase activated (swarm=%s, sub=%s)",
            self._default_swarm,
            self._default_sub,
        )

    def health(self) -> bool:
        try:
            p = self.get_scoped_pool()
            _ = p.get_pool_stats()
            return True
        except Exception as exc:
            logger.warning("Adapter health check failed: %s", exc)
            return False


# ------------------------------------------------------------------
# Free functions (the most common things models will call)
# ------------------------------------------------------------------


def detect_swarm_context() -> tuple[str | None, str | None]:
    """Return (swarm_id, subagent_id) by inspecting standard env vars.

    These vars are set either by the user's shell, by a parent Savant-aware
    spawner, or by the adapter's patched spawn_subagent / equivalent.
    """
    swarm = (
        os.environ.get("AGENTDRIVE_SWARM_ID")
        or os.environ.get("SAVANT_SWARM")
        or os.environ.get("SWARM_ID")
    )
    sub = (
        os.environ.get("AGENTDRIVE_SUBAGENT_ID")
        or os.environ.get("SAVANT_SUB_AGENT_ID")
        or os.environ.get("SAVANT_AGENT_ID")
        or os.environ.get("SUBAGENT_ID")
    )
    return swarm, sub


def create_scoped_pool(
    swarm_id: str | None = None,
    subagent_id: str | None = None,
    registry_root: Path | str | None = None,
) -> AgentDrive:
    """Create or return a properly isolated AgentDrive for a swarm/sub-agent.

    Genomes live under ~/.agentdrive/swarms/<swarm>/<sub>/genomes (fully isolated DNA)
    Ingest log + drive metadata under .../pool

    If neither id is given, returns the global default pool.
    """
    if not swarm_id and not subagent_id:
        return get_default_drive()

    # Compute directories consistently with constants.get_swarm_drive_path
    # but also give each scope its own GenomeRegistry root.
    if swarm_id:
        base = get_swarms_dir() / swarm_id
    else:
        base = get_swarms_dir() / "default"

    if subagent_id:
        base = base / subagent_id

    genomes_root = Path(registry_root) if registry_root else (base / "genomes")
    drive_path = base / "pool"  # matches get_swarm_drive_path semantics

    genomes_root.mkdir(parents=True, exist_ok=True)
    drive_path.mkdir(parents=True, exist_ok=True)

    registry = GenomeRegistry(root=genomes_root)
    name = f"swarm:{swarm_id or 'default'}"
    if subagent_id:
        name += f":sub:{subagent_id}"

    logger.debug(
        "Creating scoped AgentDrive name=%s genomes=%s drive_path=%s",
        name,
        genomes_root,
        drive_path,
    )
    return AgentDrive(registry=registry, name=name, drive_path=drive_path)


def get_savant_pool(swarm_id: str | None = None, subagent_id: str | None = None) -> AgentDrive:
    """Convenience alias used by __init__.py and models."""
    return create_scoped_pool(swarm_id, subagent_id)


def get_scoped_pool() -> AgentDrive:
    """The single most important helper for sub-agents.

    Call this inside any agent (parent or child) — it does the right thing
    based on the environment the spawner (or adapter.activate) set up.
    """
    swarm, sub = detect_swarm_context()
    return create_scoped_pool(swarm, sub)


# Convenience re-export of harness creator that respects scope
def create_harness(
    agent_id: str, swarm_id: str | None = None, subagent_id: str | None = None
) -> Harness:
    pool = create_scoped_pool(swarm_id, subagent_id)
    return Harness(agent_id=agent_id, pool=pool)


__all__ = [
    "SavantAdapter",
    "SavantAdapterBase",
    "SavantContext",
    "detect_swarm_context",
    "create_scoped_pool",
    "get_savant_pool",
    "get_scoped_pool",
    "create_harness",
]
