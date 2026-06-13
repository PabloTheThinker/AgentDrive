---
title: "MCP Overview"
description: "Model Context Protocol is the universal, first-class interface for every model — frontier or local — to AgentDrive."
---

# MCP Overview

MCP (Model Context Protocol) is how **every** model talks to AgentDrive.

It is not a secondary API. It is the primary surface that the internal Parent, Overseer, Council, and autonomous inhabitants all use.

Any MCP-capable client (Claude Desktop, Cursor, Continue.dev, custom agents, direct stdio, HTTP/SSE in dev, etc.) gets the same tools.

## What You Get Through MCP

- The full Experience Graph v3 tool suite (`experience_graph_get_context_pack`, `record_reasoning`, structural similarity, history, reasoning structure suggestions, etc.).
- Core DNA/pool/operations tools (think, pool query, doctor, learnings, reconcile, dream, patterns, etc.).
- Inhabitant code agency tools (read source safely, propose changes, apply under governance).
- AD-Grid registration and council activity visibility (`register_program`, `get_council_activity`).
- The live self-describing catalog (`agentdrive_mcp_catalog`).
- Helper for self-configuration (`agentdrive_get_mcp_config_snippet`).

All tools return clean JSON. Many support `dry_run`. Read-only vs mutating is annotated where the protocol supports it.

## Core Principle for Models

**Call the catalog first.**

`agentdrive_mcp_catalog(format="full")` is the live source of truth for the exact surface available in this session, including any clone/dev-specific sections and usage guidance.

Never rely on a static list in your training data. The surface evolves and the catalog tells you the current reality (including `when_to_use` and examples for the most important tools).

## Connection Modes

- **stdio** (default, recommended for most clients): The client spawns `agentdrive-mcp`.
- **HTTP / SSE / streamable-http**: Useful for development, remote agents, or custom harnesses. Run with `--transport streamable-http --port 9876`.

The launcher resolver is smart:
- Prefers a real `agentdrive-mcp` binary on PATH.
- Falls back to the per-user `~/.agentdrive/venv`.
- Falls back to `python -m agentdrive.adapters.mcp_server` (perfect for clones after `pip install -e ".[mcp]"`).

## For Clones (git clone + dev)

This is explicitly supported and delightful.

After `cd` into the clone and `pip install -e ".[mcp]"`:
- The MCP server runs against your local source.
- `inhabitant_read_source` discovers the local tree.
- The catalog surfaces a dedicated dev/clone setup section.
- Connected models can call `agentdrive_get_mcp_config_snippet(...)` to help the human wire their other clients (Claude, Cursor, etc.) to this exact clone.

See the [AI Models → Local Models & Cloned Setups](/ai-models/local-models) page for the full story.

## Server Instructions (What the Model Sees on Connect)

When the MCP server starts, it sends a rich set of instructions that include:
- The requirement to call the catalog first.
- The sacred 6-step loop.
- Guidance for clones.
- Code agency rules.
- AD-Grid inhabitant expectations.

These instructions are deliberately written to be consumed by the model. They are part of the "rules" layer.

## Next

- [Connect your client](/mcp/connect)
- [Tools reference (or just call the catalog)](/mcp/tools-reference)
- [Specific recipes for Claude, Cursor, Codex-style](/mcp/for-claude-cursor-codex)
- The full **[Rules for AI Models](/ai-models/rules-and-patterns)**

MCP is not "integration." It is how intelligence lives in the Drive.