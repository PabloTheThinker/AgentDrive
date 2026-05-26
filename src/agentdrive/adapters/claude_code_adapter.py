"""
Claude Code Agent Drive Adapter — Skeleton & Integration Guide.

Claude Code (Claude running in coding environments, Claude Desktop, Cursor with
Claude, etc.) typically connects to external tools via:

- MCP (the primary recommended path — see mcp_server.py)
- Custom tool definitions the user registers in their Claude config
- Sub-agent / "computer use" or project-level agent spawning hooks

How the user instructs Claude:

    "For this task and any sub-agents or parallel explorations you create,
     use the AgentDrive. Connect to the local Agent Drive MCP server (usually
     started with `python -m agentdrive.adapters.mcp_server`) or activate the
     Python adapter if you have direct execution:

     from agentdrive.adapters.claude_code_adapter import ClaudeCodeAgent DriveAdapter
     adapter = ClaudeCodeAgent DriveAdapter()
     adapter.activate(swarm_id='claude-research-swarm')

     Then always pull DNA with get_scoped_pool() before big tasks and record
     outcomes afterwards."

This skeleton shows:
- How to register the Agent Drive MCP server in claude_desktop_config.json
- A thin wrapper class the model can import when it has a Python execution tool
- Hooks for future "Claude sub-agent" spawning if Anthropic exposes one

Because Claude already has first-class MCP support, the mcp_server is often
the *only* thing needed — no Python adapter code required inside the prompt.
"""

from __future__ import annotations

import logging
from typing import Any

from agentdrive.adapters.base import AgentDrive, Agent DriveAdapterBase

logger = logging.getLogger(__name__)


class ClaudeCodeAgent DriveAdapter(Agent DriveAdapterBase):
    """Lightweight adapter for Claude Code / Cursor / Claude Desktop users.

    In most cases you will not need to instantiate this at all — just run the
    Agent Drive MCP server and add it to your MCP server list. The skeleton exists
    so that:
    1. Models that *can* exec Python have a uniform surface.
    2. Future Anthropic "Projects" or "Sub-agent" APIs can be hooked here.
    """

    def __init__(self, swarm_id: str | None = None, **kwargs: Any):
        super().__init__(name="claude-code", default_swarm_id=swarm_id, **kwargs)

    def get_name(self) -> str:
        return "claude-code"

    def activate(self, swarm_id: str | None = None, **options: Any) -> None:
        super().activate(swarm_id=swarm_id, **options)
        logger.info(
            "ClaudeCodeAgent DriveAdapter activated. "
            "If you have MCP access, prefer connecting the Agent Drive MCP server "
            "(python -m agentdrive.adapters.mcp_server) — it gives Claude native tools "
            "for pool_query, get_dna, record_outcome, etc."
        )

    # Claude-specific future hook example
    def register_mcp_server_in_config(self, config_path: str | None = None) -> str:
        """Return the JSON snippet the user should add to their Claude config
        so that Claude automatically sees the Agent Drive tools.
        """
        snippet = """
{
  "mcpServers": {
    "agentdrive": {
      "command": "python",
      "args": ["-m", "agentdrive.adapters.mcp_server"],
      "env": {
        "AGENTDRIVE_HOME": "~/.agentdrive"
      }
    }
  }
}
"""
        return snippet.strip()

    def get_pool(self, swarm_id: str | None = None, subagent_id: str | None = None) -> AgentDrive:
        # Claude often works with long-running desktop sessions — default scoping is perfect
        return super().get_pool(swarm_id, subagent_id)


# Backwards-compatible alias from the pre-rename era. Both names resolve to
# the same class; keeping the old import path working without forcing
# downstream callers to update.
ClaudeAgent DriveAdapter = ClaudeCodeAgent DriveAdapter

__all__ = ["ClaudeCodeAgent DriveAdapter", "ClaudeAgent DriveAdapter"]
