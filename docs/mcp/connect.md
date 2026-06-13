---
title: "Connecting Clients"
description: "How to wire Grok, Claude, Cursor, Continue, local models, and custom agents to your AgentDrive via MCP."
---

# Connecting Clients

Run `agentdrive mcp config` (or `--client claude` / `cursor` / `generic`) for the exact block for your machine.

Full details and client-specific recipes live in:

- [MCP Overview](/mcp/overview)
- [For Claude, Cursor, Codex-style](/mcp/for-claude-cursor-codex)

Models themselves can generate the freshest config by calling `agentdrive_get_mcp_config_snippet(client=...)`.