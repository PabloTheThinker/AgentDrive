---
title: "Installation"
description: "Multiple ways to install AgentDrive — from one-liner to full git clone dev setup. All supported."
---

# Installation

AgentDrive supports several installation paths. All of them result in a working `agentdrive` CLI and a functional MCP server that any model can connect to.

## Recommended for Most People

```bash
curl -fsSL https://vektraindustries.com/agentdrive/install.sh | bash
```

This sets up a user-level environment, the CLI, and the MCP bits.

Then run:

```bash
agentdrive doctor
agentdrive mcp install
agentdrive mcp doctor
agentdrive golden-path run
```

## Git Clone (Dev / Power User / Local Model Enthusiast)

This is the best path if you want to:
- Work on AgentDrive itself.
- Have your local models participate in evolving the system.
- Have the absolute latest behavior.

```bash
git clone https://github.com/pablothethinker/AgentDrive.git
cd AgentDrive

# Option A — project helper
./install.sh

# Option B — explicit editable
python -m pip install -e ".[mcp]"
```

Then:

```bash
agentdrive doctor
agentdrive mcp install
agentdrive mcp doctor
```

The MCP launcher will correctly prefer your local source (via the shim after editable install or the module fallback).

**Important for models**: When a model is connected to a clone, `agentdrive_mcp_catalog()` will surface clone-specific guidance, and you can call `agentdrive_get_mcp_config_snippet(...)` to help the human finish wiring their other clients.

## Other Options

- **uvx** (zero-install for a single run): `uvx --from agentdrive[mcp] agentdrive-mcp`
- **From source without install** (advanced): `python -m agentdrive.adapters.mcp_server --transport stdio`
- Per-platform detailed guides live in the full docs site structure (see `install/` pages once expanded).

## Verify

After any install path, these two commands should be happy:

```bash
agentdrive doctor --verbose
agentdrive mcp doctor
```

The second one is especially important for AI models — it proves the MCP bridge is alive and how many tools are registered.

## Next

- [Golden Path](/start/golden-path)
- [Connect your first model](/ai-models/quickstart)
- [Rules for AI Models](/ai-models/rules-and-patterns) (read this if you *are* the model)