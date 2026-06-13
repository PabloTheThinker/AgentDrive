---
title: "Quickstart for AI Models"
description: "Get any model (Claude, Grok, Cursor, local LLM) connected to AgentDrive in minutes and making its first useful structural decisions."
---

# Quickstart for AI Models

This page gets you (the model) or your human operator productive fast.

## 1. Connect via MCP (the only interface that matters)

```bash
# From the AgentDrive clone or installed package
agentdrive mcp install
agentdrive mcp doctor
agentdrive mcp config
```

- **Claude Desktop / Claude Code**: Paste the `mcpServers.agentdrive` block into `claude_desktop_config.json`.
- **Cursor**: Add to `~/.cursor/mcp.json` (or project-local).
- **Continue.dev / local models / Codex-style**: Use the generic block. Works great.
- **Grok**: Use the toml snippet or `grok mcp add`.
- **Any stdio client**: Point it at `agentdrive-mcp --transport stdio` (or the module fallback in dev).

**Clone / dev note**: If the user did `git clone`, run `pip install -e ".[mcp]"` first (or let the model call `agentdrive_get_mcp_config_snippet` for the precise dev command).

After connecting, **your absolute first tool call** must be:

```
agentdrive_mcp_catalog(format="full")
```

This is live truth. It will tell you every available tool, `when_to_use`, examples, read-only hints, and (if this is a local clone) a whole dev setup section.

## 2. Your First Real Actions (the sacred pattern)

1. `experience_graph_get_context_pack(reasoning_style="balanced")`
   (or with `swarm_id` if the human gave you one)

2. Read the pack. Identify high-value elements, weak links, and continuations.

3. (Recommended) `experience_graph_suggest_reasoning_structure()`

4. Do the actual work / thinking.

5. `experience_graph_record_reasoning(...)`
   Be explicit: `fabric_elements_considered`, `structural_pattern_matched`, `decision_rationale`, `expected_lift_signal`.

6. If the outcome was valuable: `agentdrive_learnings_log(...)` or `agentdrive_record_outcome(...)`.

Repeat. The graph (and you) get better.

## 3. Become a First-Class Inhabitant (optional but powerful)

If the human wants you to act persistently inside the AD-Grid (especially useful for local autonomous agents):

```bash
# In another terminal
agentdrive grid run --swarm-id stabilization-wave-20260531 --with-tower
```

Then in your MCP session:
- Call `agentdrive_register_program` with a proper manifest (`program_id`, `user_objective_refs`, `constitution_refs` including the Program Contract).
- Use the returned `program_id` on every `experience_graph_record_reasoning` and code-agency call.
- You will appear in the Tower inhabitants panel.

See the full guide in the AD-Grid section.

## 4. Local Models & Clones

Local models are first-class. The same MCP surface works whether the model is Claude 4 or `llama3.2` via Ollama + Continue.

When the user has a **git clone**:
- The catalog will surface a `clone_dev_setup_for_claude_cursor_codex_and_others` section.
- You can call `agentdrive_get_mcp_config_snippet(client="claude")` (or cursor/generic/codex) and hand the human the exact block for their client.
- The `inhabitant_read_source` tool will discover the local source tree automatically.

## 5. Verify Everything Works

Call `agentdrive_doctor` (or the verbose variant).

You should see:
- Healthy home + config
- Registry + pool with genomes
- MCP bridge reporting tools
- (In dev) that it's using your local source

## Next Steps

- Read the full **[Rules & Patterns](/ai-models/rules-and-patterns)** (the real instruction manual).
- Explore the **[Experience Graph tools](/concepts/experience-graph)** in depth.
- Look at the **[MCP tools reference](/mcp/tools-reference)** (or just keep calling the catalog — it's better).
- If you're an autonomous agent: study the AD-Grid inhabitant flow.

The graph is waiting for your reasoning. Make the traces count.