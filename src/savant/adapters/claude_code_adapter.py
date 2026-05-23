"""
Claude Code Savant Adapter — Skeleton & Integration Guide.

Claude Code (Claude running in coding environments, Claude Desktop, Cursor with
Claude, etc.) typically connects to external tools via:

- MCP (the primary recommended path — see mcp_server.py)
- Custom tool definitions the user registers in their Claude config
- Sub-agent / "computer use" or project-level agent spawning hooks

How the user instructs Claude:

    "For this task and any sub-agents or parallel explorations you create,
     use the Savant Pool. Connect to the local Savant MCP server (usually
     started with `python -m savant.adapters.mcp_server`) or activate the
     Python adapter if you have direct execution:

     from savant.adapters.claude_code_adapter import ClaudeCodeSavantAdapter
     adapter = ClaudeCodeSavantAdapter()
     adapter.activate(swarm_id='claude-research-swarm')

     Then always pull DNA with get_scoped_pool() before big tasks and record
     outcomes afterwards."

This skeleton shows:
- How to register the Savant MCP server in claude_desktop_config.json
- A thin wrapper class the model can import when it has a Python execution tool
- Hooks for future "Claude sub-agent" spawning if Anthropic exposes one

Because Claude already has first-class MCP support, the mcp_server is often
the *only* thing needed — no Python adapter code required inside the prompt.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from savant.adapters.base import SavantAdapterBase, SavantPool

logger = logging.getLogger(__name__)


class ClaudeCodeSavantAdapter(SavantAdapterBase):
    """Lightweight adapter for Claude Code / Cursor / Claude Desktop users.

    In most cases you will not need to instantiate this at all — just run the
    Savant MCP server and add it to your MCP server list. The skeleton exists
    so that:
    1. Models that *can* exec Python have a uniform surface.
    2. Future Anthropic "Projects" or "Sub-agent" APIs can be hooked here.
    """

    def __init__(self, swarm_id: Optional[str] = None, **kwargs: Any):
        super().__init__(name="claude-code", default_swarm_id=swarm_id, **kwargs)

    def get_name(self) -> str:
        return "claude-code"

    def activate(self, swarm_id: Optional[str] = None, **options: Any) -> None:
        super().activate(swarm_id=swarm_id, **options)
        logger.info(
            "ClaudeCodeSavantAdapter activated. "
            "If you have MCP access, prefer connecting the Savant MCP server "
            "(python -m savant.adapters.mcp_server) — it gives Claude native tools "
            "for pool_query, get_dna, record_outcome, etc."
        )

    # Claude-specific future hook example
    def register_mcp_server_in_config(self, config_path: Optional[str] = None) -> str:
        """Return the JSON snippet the user should add to their Claude config
        so that Claude automatically sees the Savant tools.
        """
        snippet = """
{
  "mcpServers": {
    "savant": {
      "command": "python",
      "args": ["-m", "savant.adapters.mcp_server"],
      "env": {
        "SAVANT_HOME": "~/.savant"
      }
    }
  }
}
"""
        return snippet.strip()

    def get_pool(self, swarm_id: Optional[str] = None, subagent_id: Optional[str] = None) -> SavantPool:
        # Claude often works with long-running desktop sessions — default scoping is perfect
        return super().get_pool(swarm_id, subagent_id)


__all__ = ["ClaudeCodeSavantAdapter", "ClaudeCodeSavantAdapter as ClaudeSavantAdapter"]
