---
title: "MCP for Claude, Cursor, Codex-style & Other Clients"
description: "Exact recipes and gotchas for the most common clients when connecting to AgentDrive, including clone/dev setups."
---

# MCP for Claude, Cursor, Codex-style & Other Clients

This page gives concrete, copy-paste-ready instructions for the clients people actually use with AgentDrive.

The single source of truth is always what `agentdrive mcp config --client <name>` (or the model calling `agentdrive_get_mcp_config_snippet`) tells you for *your* machine.

## Claude Desktop / Claude Code

1. Run `agentdrive mcp config --client claude` (or let the connected model call `agentdrive_get_mcp_config_snippet(client="claude")`).
2. Paste the `mcpServers.agentdrive` object into your `claude_desktop_config.json`.
   - Linux: usually `~/.config/claude/claude_desktop_config.json`
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
3. **Fully quit and restart Claude Desktop** (not just reload).
4. In a new conversation, ask Claude to use the AgentDrive tools or simply have it call `agentdrive_mcp_catalog()` as its first action.

**Clone note**: If you're in a git clone, the generated block (or the snippet tool) will often prefer the local shim or module. The model can detect this via the catalog and surface the right dev commands.

## Cursor

1. `agentdrive mcp config --client cursor` or have the model call the snippet tool with `client="cursor"`.
2. Add/replace in `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` in the project root.
3. Reload the Cursor window (Cmd/Ctrl+Shift+P → "Reload Window") or restart Cursor.
4. In Agent mode or with tools enabled, the model should see the AgentDrive tools.

Cursor works especially well with the "any model" story because you can point it at strong local models while still giving it the full Experience Graph surface.

## Continue.dev & Codex-style / Plugin Agents

Continue.dev is one of the best ways to use strong local models with AgentDrive.

1. Use the generic block: `agentdrive mcp config --client generic`.
2. Or ask the connected model: `agentdrive_get_mcp_config_snippet(client="generic")` or `client="codex"`.
3. Place the `mcpServers.agentdrive` entry in your Continue config (usually under the `mcp` or `mcpServers` key depending on version).
4. Restart the Continue extension / VS Code / JetBrains as appropriate.

The same generic block works for many other "Codex-style", plugin-based, or custom MCP clients.

## Pure stdio / Custom Agents / Local Harnesses

```bash
agentdrive-mcp --transport stdio
# or the explicit module form (great in clones)
python -m agentdrive.adapters.mcp_server --transport stdio
```

Any agent that can spawn a stdio MCP server and speak the protocol can use the full surface.

## HTTP / SSE Modes (Dev & Remote)

```bash
agentdrive-mcp --transport streamable-http --port 9876
```

Useful when:
- You're debugging the server itself.
- You have a remote or containerized setup.
- You're building a custom multi-agent system that talks over the network.

Most "normal" users and local model users should stick to stdio.

## Pro Tips

- After any config change, **fully restart the client application**. Many clients only read MCP config at startup.
- Have the model call `agentdrive_mcp_catalog()` and `agentdrive_doctor()` as part of its own health check when a session starts.
- In a clone, lean on the model: "Give me the exact config block for my Claude so I can talk to this local AgentDrive."
- The `universal/mcp-agentdrive` skill (if the user has the skills layer) is a good way to bias a model toward preferring the MCP tools over its own built-in skills.

## See Also

- [MCP Overview](/mcp/overview)
- [Connect page](/mcp/connect)
- [Rules for AI Models](/ai-models/rules-and-patterns) — especially the clone and local model sections.
- The live catalog and `get_mcp_config_snippet` tool (the model can generate the freshest instructions itself).

The goal is that any model, once wired, can help its own human finish the wiring for other surfaces. That is the AgentDrive way.