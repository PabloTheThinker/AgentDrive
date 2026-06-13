---
title: "Local Models & Cloned Setups"
description: "How local LLMs (Ollama, LM Studio, vLLM, etc.) and users with a git clone get the full power of AgentDrive. First-class support."
---

# Local Models & Cloned Setups

AgentDrive was built from the ground up with **local models** as first-class citizens.

A `llama3.2`, `qwen2.5-coder`, or any other local model running through Continue.dev, a custom agent, or direct stdio MCP gets exactly the same Experience Graph v3 tools, the same 6-step loop, the same AD-Grid inhabitant surface as any frontier model.

Clones (`git clone`) are also explicitly supported and delightful.

## Recommended Local Model Stacks

**Best overall experience**:
- Continue.dev (or similar open MCP client) + your favorite local model + the AgentDrive MCP server.

**Pure autonomous / long-running**:
- Custom agent harness that speaks stdio to `agentdrive-mcp`.
- Attach to a persistent swarm/drive and let it run for days.

**Dev / research**:
- Run the MCP server in HTTP/SSE mode for easier debugging if needed.

The MCP surface is identical. The catalog, the context packs, the recording tools — all the same.

## When the User Has a Git Clone (Dev Mode)

This is the common real-world case for power users and researchers.

Typical flow:
1. User: `git clone https://github.com/.../AgentDrive.git`
2. `cd AgentDrive`
3. `pip install -e ".[mcp]"` (or run the project's `install.sh`)
4. `agentdrive mcp install && agentdrive mcp doctor`

From that point:
- The `agentdrive-mcp` launcher (or module fallback) will use the local source tree.
- When you (the model) connect, `agentdrive_mcp_catalog()` will include a `clone_dev_setup_for_claude_cursor_codex_and_others` section with exact commands and client blocks.
- You can call `agentdrive_get_mcp_config_snippet(client="claude")` (cursor / generic / codex / etc.) and give the human the precise snippet for their other clients.
- `agentdrive_inhabitant_read_source` will discover the local `src/` tree automatically and enforce safe access.

This means the model the user is talking to can be actively helping evolve the very system it is running on — in a governed, attributable way.

## How a Local Model Should Behave in a Clone

- Call the catalog first. Look for the clone dev section.
- Offer to generate config snippets for the human's other tools ("Want me to give you the exact block for your Claude Desktop?").
- Use the hardened `inhabitant_*` tools when the task involves reading or proposing changes to the AgentDrive source itself.
- Record reasoning with proper `program_id` if the human has the Grid running.
- Treat the local working tree + the user's `~/.agentdrive` as two related but distinct substrates.

## Persistent Autonomous Local Agents

This is where local models + AgentDrive shine brightest.

Example setup:
- Human runs `agentdrive grid run --swarm-id my-personal-swarm --with-tower` (or the canonical stabilization wave).
- Local model (via long-lived Continue session or dedicated agent process) registers as an inhabitant.
- The agent runs background loops: periodic `dream_run`, research threads, self-improvement sweeps, etc.
- Everything is observed in the Tower, recorded in the Experience Graph, and governed by the constitutions the user has loaded.

No cloud. Full sovereignty. The agent gets sharper over weeks and months because every trace stays.

## Practical Tips for Local Model Users

- Start with the Golden Path even in a clone.
- Use `agentdrive doctor --verbose` frequently during development.
- For very long autonomous runs, consider dedicated swarms/drives so the main personal drive stays clean.
- The `universal/mcp-agentdrive` skill (if the user has the skills system) is a good way to give the local model a persistent "prefer MCP tools" personality.

## Summary

Local models are not second-class.

Clones are not a hack — they are a supported, delightful mode.

The same rules apply:
- Call the catalog first.
- Follow the 6-step loop.
- Record structural reasoning.
- Leave the graph better than you found it.

Everything else (config snippets, source discovery, Grid registration) is there to make that possible whether the model is running on a laptop or in a frontier cloud.