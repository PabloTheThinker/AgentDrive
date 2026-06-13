# Using AgentDrive MCP with Any AI Model

AgentDrive exposes a **Model Context Protocol (MCP)** server so Grok, Claude, Cursor, Continue.dev, Windsurf, and any stdio-capable client can use the Experience Graph and Drive operations as first-class tools.

---

## Fastest path (install or clone)

```bash
# After pip install agentdrive[mcp] OR ./install.sh OR git clone + pip install -e ".[mcp]"
agentdrive mcp install
agentdrive mcp doctor
```

`mcp install` will:

1. Ensure `agentdrive[mcp]` is installed (editable install when run from a clone)
2. Merge config into `~/.cursor/mcp.json`, Claude, Continue, and Grok TOML
3. Run `grok mcp add` automatically when the Grok CLI is available

Restart your AI client, then verify with `experience_graph_get_context_pack` or `agentdrive_think`.

**Full first-run chain (install → MCP → think → learnings → query):** [GOLDEN_PATH.md](GOLDEN_PATH.md)

```bash
agentdrive golden-path run    # automated walkthrough after mcp install
```

---

## Clone + editable dev install

```bash
git clone https://github.com/PabloTheThinker/AgentDrive.git
cd AgentDrive
python3 -m venv ~/.agentdrive/venv
~/.agentdrive/venv/bin/pip install -e ".[mcp]"
agentdrive mcp install
agentdrive mcp doctor
```

The config resolver automatically uses the correct launcher:

| Priority | Method | When |
|----------|--------|------|
| 1 | `agentdrive-mcp` on PATH | pip / install.sh shims |
| 2 | `~/.agentdrive/venv/bin/agentdrive-mcp` | installer venv |
| 3 | `python -m agentdrive.adapters.mcp_server` | editable clone fallback |

No manual path editing required.

---

## CLI reference

| Command | Purpose |
|---------|---------|
| `agentdrive mcp install` | pip `[mcp]` + write client configs |
| `agentdrive mcp doctor` | Verify package, launcher, 25+ tools |
| `agentdrive mcp config` | Human-readable snippets (resolved paths) |
| `agentdrive mcp config --json` | Machine-readable bundle for automation |
| `agentdrive mcp config --write` | Merge into Grok/Cursor/Claude/Continue |
| `agentdrive mcp config --client cursor` | One client only |
| `agentdrive mcp tools` | List all registered MCP tools |
| `agentdrive mcp serve` | Run stdio server manually |

`agentdrive doctor` also includes an **MCP bridge** check.

---

## Client config paths

| Client | File |
|--------|------|
| Grok | `~/.grok/config.toml` |
| Cursor | `~/.cursor/mcp.json` |
| Claude Desktop | `~/.config/claude/claude_desktop_config.json` |
| Continue.dev | `~/.continue/config.json` |

Generated block (paths resolved per machine):

```json
{
  "mcpServers": {
    "agentdrive": {
      "command": "<resolved-launcher>",
      "args": ["--transport", "stdio"]
    }
  }
}
```

Run `agentdrive mcp config --json` to print the exact command for your system.

---

## Zero-install (uvx)

```bash
agentdrive mcp config --uvx
```

Uses `uvx --from agentdrive[mcp] agentdrive-mcp --transport stdio` — no venv required.

---

## What your model gets (and how any model should start)

**Best first action for *any* AI model** (Grok, Claude, Cursor, local LLMs, custom agents, Windsurf, Continue...):

```text
Call agentdrive_mcp_catalog() right away.
```

It returns a live, categorized, machine-readable list of every tool with `read_only` flags, `when_to_use` guidance, and examples. This is the canonical "any-model" on-ramp.

**Experience Graph v3 (primary surfaces)**

- `experience_graph_get_context_pack` (call early for dense briefing)
- `experience_graph_record_reasoning` (write your structural decisions back)
- `experience_graph_suggest_reasoning_structure`
- `experience_graph_find_structural_similarities`, `get_reasoning_traces_for_element`, ...

**Core Drive + ops (auto-registered, 25+ via the operations registry)**

- `agentdrive_think`, `agentdrive_pool_query`, `agentdrive_doctor`, `agentdrive_record_outcome`
- `agentdrive_dream_run` / `dream_status`, `reconcile_*`, `learnings_log` / `learnings_list`
- `agentdrive_mcp_catalog` (the self-describing catalog)

**AD-Grid Inhabitant + ExternalBridge code agency (high leverage)**

- `agentdrive_inhabitant_read_source`, `..._propose_code_change`, `..._apply_change`
- `agentdrive_register_program` (declare yourself as a first-class attributed inhabitant)
- `agentdrive_get_council_activity`

Run `agentdrive mcp tools` (CLI) or call the catalog tool for the current full live list (~39–40+ tools). All tools return parseable JSON.

---

## Onboarding document for models

Give connected models **`docs/FOR_AI_MODELS.md`** — written for LLMs covering the 6-step loop, tool usage, and autonomous behavior.

## For arbitrary / custom AI models and agents

AgentDrive is deliberately built so *any* MCP-capable system can participate as a first-class citizen:

- Use `agentdrive mcp config --uvx` for a zero-install `uvx` command line (great for containers, one-off agents, or models without local installs).
- Use `agentdrive mcp config --client generic --json` (or just the emitted `mcpServers` block) for custom hosts, Zed, custom Python/TS MCP clients, remote agents, etc.
- The `agentdrive_mcp_catalog` tool is the universal handshake. Any model should call it first.
- All tools are JSON-in / JSON-string-out and carry `readOnlyHint` annotations where applicable.
- The long server instructions + the rich per-tool docs (populated from the operations registry + when_to_use/examples) are designed to be consumed by models that have never seen AgentDrive before.

Example one-liner for a completely custom agent:

```bash
uvx --from agentdrive[mcp] agentdrive-mcp --transport stdio
```

Then point your client's MCP stdio config at that command. The model will discover everything via `agentdrive_mcp_catalog`.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `MCP server not available` | `agentdrive mcp install` |
| Client can't find binary | `agentdrive mcp config --json` — use module fallback command |
| Tools empty / stale | `agentdrive mcp doctor` |
| Clone install | Always use `pip install -e ".[mcp]"` then `mcp install` |

The server only touches local `~/.agentdrive` data. You remain sovereign over all settings.