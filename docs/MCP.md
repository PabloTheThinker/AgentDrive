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

## What your model gets

**Experience Graph v3**

- `experience_graph_get_context_pack`
- `experience_graph_record_reasoning`
- `experience_graph_find_structural_similarities`
- `experience_graph_suggest_reasoning_structure`
- …

**Drive + operations (auto-registered from registry)**

- `agentdrive_think`, `agentdrive_pool_query`, `agentdrive_doctor`
- `agentdrive_dream_run`, `agentdrive_patterns_list`, …

Run `agentdrive mcp tools` for the full list (40+ tools).

---

## Onboarding document for models

Give connected models **`docs/FOR_AI_MODELS.md`** — written for LLMs covering the 6-step loop, tool usage, and autonomous behavior.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `MCP server not available` | `agentdrive mcp install` |
| Client can't find binary | `agentdrive mcp config --json` — use module fallback command |
| Tools empty / stale | `agentdrive mcp doctor` |
| Clone install | Always use `pip install -e ".[mcp]"` then `mcp install` |

The server only touches local `~/.agentdrive` data. You remain sovereign over all settings.