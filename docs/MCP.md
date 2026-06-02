# Using AgentDrive MCP with Claude, Cursor, Local Models & More

AgentDrive turns any MCP-capable AI into a first-class participant in a living **Experience Graph v3** (structural, Obsidian-style memory fabric with gbrain scoring and explicit Parent reasoning traces).

This works identically across:
- Grok
- Claude Code / Claude Desktop
- Cursor
- Continue.dev (excellent with local models)
- Windsurf, Zed, custom local setups, etc.

---

## One Command to Rule Them All

After installation, run:

```bash
agentdrive mcp config
```

It will print the exact configuration you need for your client.

---

## Recommended Installation

```bash
pip install agentdrive[mcp]
```

This installs the core package + the `mcp` dependency and registers the `agentdrive-mcp` binary.

Zero-install alternative (great for local models):

```bash
uvx --from agentdrive[mcp] agentdrive-mcp
```

---

## Client-Specific Setup

### Grok (this harness)

```bash
grok mcp add agentdrive --command agentdrive-mcp --args '--transport stdio'
```

Then use `/mcp` in any session.

### Claude Code / Claude Desktop

Add to your MCP config file:

```json
{
  "mcpServers": {
    "agentdrive": {
      "command": "agentdrive-mcp",
      "args": ["--transport", "stdio"]
    }
  }
}
```

### Cursor

1. Go to Settings → Features → MCP
2. Add Server:
   - Name: `agentdrive`
   - Command: `agentdrive-mcp`
   - Args: `--transport stdio`

### Continue.dev (Best for Local Models)

Add to your `~/.continue/config.json` (or project-level):

```json
{
  "mcpServers": {
    "agentdrive": {
      "command": "agentdrive-mcp",
      "args": ["--transport", "stdio"]
    }
  }
}
```

This works beautifully with Ollama, LM Studio, llama.cpp servers, etc.

### Windsurf, Zed, and other modern editors

Most now have native MCP support. Use the same stdio pattern:

- **Command**: `agentdrive-mcp`
- **Args**: `--transport stdio`

---

## What Your Model Actually Gets

When connected, the model receives these high-signal tools (among others):

**Experience Graph v3 (the important ones):**
- `experience_graph_get_context_pack` — the same dense structural briefing the internal Parent receives
- `experience_graph_find_structural_similarities`
- `experience_graph_record_reasoning` — lets the model write its own reasoning traces back into the graph (this is how the graph compounds)
- `experience_graph_suggest_reasoning_structure`
- `experience_graph_get_reasoning_traces_for_element`
- `experience_graph_get_parent_reasoning_history`

**DNA / Pool tools:**
- `agentdrive_get_dna_for_task`, `agentdrive_pool_query`, `agentdrive_record_outcome`, etc.

The model can now do real structural reasoning over your past work and contribute new high-quality experience back.

---

## Running Manually

```bash
# Preferred for AI CLIs
agentdrive-mcp

# Or via the main CLI
agentdrive mcp serve
```

---

## Best Onboarding Document for Models

When an AI first connects or is being onboarded to AgentDrive, give it this file:

**`docs/FOR_AI_MODELS.md`**

It is written specifically for LLMs and contains the full philosophy, the 6-step contract, precise guidance on every Experience Graph tool, recommended agent behavior, and how to do high-quality autonomous work inside the system.

## Why This Is Different

Most agent memory systems are just RAG. AgentDrive gives models a **queryable structural memory** they can reason *over* (not just retrieve from). When they use `experience_graph_record_reasoning`, their actual thinking becomes part of the permanent, gbrain-scored fabric that future runs (human or autonomous) can build upon.

This is especially powerful for long-running local autonomous agents.

---

## Troubleshooting

- Make sure `agentdrive-mcp` is on your PATH after installation.
- For local models, Continue.dev + `agentdrive-mcp` is currently the smoothest path.
- The server only ever touches your local `~/.agentdrive` data.

The MCP layer is intentionally thin. All the real power lives in the Experience Graph on disk. Your AI clients are now native citizens of it.