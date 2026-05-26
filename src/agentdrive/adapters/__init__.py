"""
Agent Drive Adapters — Multi-Model Integration for AgentDrives

This package enables *any* AI model or agent system (Grok Build, Claude Code,
Codex, Cursor, custom agents, etc.) to participate in the Agent Drive ecosystem of
shared, evolving agent DNA (Genomes) stored in user-owned Pools — including
automatic scoping for swarms and sub-agents.

Core value:
- User tells their model: "use your AgentDrive for this swarm"
- The model activates the appropriate adapter.
- All work (and sub-agent work) pulls relevant DNA, contributes improvements back.
- Sub-agents automatically receive isolated, persistent, user-controlled AgentDrives
  via environment variables (AGENTDRIVE_SWARM_ID, AGENTDRIVE_SUBAGENT_ID) or explicit context.

Universal access:
- Direct Python API (any model that can exec Python or has tool access)
- MCP server (stdio for Claude Desktop / Cursor / Codex MCP clients, or HTTP)

See individual adapter modules for model-specific integration points and
ready-to-paste instruction text for the user to give their AI.

Public API (recommended entry points):
    from agentdrive.adapters import (
        get_agentdrive_adapter,
        Agent DriveAdapter,
        activate_for_grok_build,
        get_scoped_pool,
    )

    # Universal
    pool = get_scoped_pool()  # auto-detects swarm/sub from env or defaults

    # Model-specific activation
    adapter = activate_for_grok_build(swarm_id="my-research-swarm")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

# Re-export for convenience
from agentdrive.drive.drive import AgentDrive
from agentdrive.drive.settings import DriveSettings, get_effective_drive_settings

from .base import (
    Agent DriveAdapter,
    Agent DriveAdapterBase,
    create_scoped_pool,
    detect_swarm_context,
    get_agentdrive_pool,
    get_scoped_pool,
)


# Model-specific adapters (import lazily to avoid heavy deps at top level)
def get_agentdrive_adapter(model: str = "auto") -> Agent DriveAdapter:
    """Factory: return the best adapter for the given model family.

    model: "grok" | "grok-build" | "claude" | "claude-code" | "codex" | "auto"
    """
    model = (model or "auto").lower()
    if model in ("grok", "grok-build", "grok_build"):
        from .grok_build_adapter import GrokBuildAgent DriveAdapter

        return GrokBuildAgent DriveAdapter()
    if model in ("claude", "claude-code", "claude_code"):
        from .claude_code_adapter import ClaudeCodeAgent DriveAdapter

        return ClaudeCodeAgent DriveAdapter()
    if model in ("codex", "openai-codex"):
        from .codex_adapter import CodexAgent DriveAdapter

        return CodexAgent DriveAdapter()
    # default / auto
    from .base import Agent DriveAdapterBase

    return Agent DriveAdapterBase()


def activate_for_grok_build(swarm_id: str | None = None, **kwargs) -> Agent DriveAdapter:
    """One-liner for Grok Build users: call this after user says 'use AgentDrive'.

    Returns the activated adapter. Automatically patches spawn_subagent if possible.
    """
    from .grok_build_adapter import GrokBuildAgent DriveAdapter, get_agentdrive_instructions_for_grok

    adapter = GrokBuildAgent DriveAdapter(swarm_id=swarm_id, **kwargs)
    adapter.activate()
    # Print user-friendly instructions the model can surface if needed
    # (models often echo this back to confirm)
    print(get_agentdrive_instructions_for_grok(swarm_id or "current-session"))
    return adapter


def activate_for_claude(swarm_id: str | None = None, **kwargs) -> Agent DriveAdapter:
    from .claude_code_adapter import ClaudeCodeAgent DriveAdapter

    adapter = ClaudeCodeAgent DriveAdapter(swarm_id=swarm_id, **kwargs)
    adapter.activate()
    return adapter


__all__ = [
    "Agent DriveAdapter",
    "Agent DriveAdapterBase",
    "get_agentdrive_adapter",
    "get_scoped_pool",
    "get_agentdrive_pool",
    "detect_swarm_context",
    "create_scoped_pool",
    "activate_for_grok_build",
    "activate_for_claude",
    "AgentDrive",
    "DriveSettings",
    "get_effective_drive_settings",
]

# Lazy submodules for direct access: from agentdrive.adapters.grok_build_adapter import ...
# (no __getattr__ needed for normal usage)
