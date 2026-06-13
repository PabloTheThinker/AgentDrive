---
title: "Getting Started"
description: "Everything you need to go from zero to a working, model-connected AgentDrive that compounds over time."
---

# Getting Started

Welcome. This section will get you (human or model) from nothing to a healthy, useful AgentDrive installation with at least one model connected and making its first structural contributions.

## Recommended Path

1. [Install AgentDrive](/start/install) (one-liner or git clone + editable — both are fully supported).
2. Run the [Golden Path](/start/golden-path) (~10 minutes). This proves the Drive, the MCP bridge, synthesis, and recording all work.
3. Connect at least one model and have it follow the [AI Models Quickstart](/ai-models/quickstart).
4. (Strongly recommended) Read the **[Rules & Patterns for AI Models](/ai-models/rules-and-patterns)** — this is the real instruction manual.

## What "Working" Looks Like

- `agentdrive doctor --verbose` is mostly green.
- `agentdrive mcp doctor` reports a healthy number of tools and a resolved launcher.
- A connected model can call `agentdrive_mcp_catalog()`, pull a context pack, and successfully record reasoning.
- You (or your autonomous agents) can start leaving traces that will be there for future cycles.

## For AI Models Reading This

If you have just been connected to a freshly installed or cloned AgentDrive:

- Your first tool call: `agentdrive_mcp_catalog(format="full")`.
- Then pull `experience_graph_get_context_pack`.
- Record at least one piece of structural reasoning before the session ends.

This proves the loop works for you.

## Where to Go Next

- Humans who want the fastest path: [Golden Path](/start/golden-path)
- Models who want the real rules: [Rules & Patterns](/ai-models/rules-and-patterns) and [Local Models & Clones](/ai-models/local-models)
- Everyone: [Core Concepts](/concepts/overview) (especially the Experience Graph and the 6-step loop)

The substrate is ready. The graph is waiting for reasoning.

Make it count.