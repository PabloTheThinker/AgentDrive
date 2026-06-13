---
title: "AgentDrive"
description: "Local-first Drive for AI agent swarms. Structural Experience Graph. MCP-native for any model — frontier or local. Clones perfectly."
---

# AgentDrive

<p align="center">
  <img src="/assets/mascot-drive.jpg" alt="AgentDrive" width="420" />
</p>

> **Intelligence that remembers the shape of what it has become.**

AgentDrive is a **local-first structural memory system** for autonomous agents and AI models. It gives you (or your local models) a living **Experience Graph** — an Obsidian-style, queryable fabric of decisions, reasoning traces, TypedEdges, coherence signals, and provenance that compounds over time.

Not another vector store. Not ephemeral chat memory. A substrate where agents think structurally, record why they chose what they chose, and get measurably sharper on every cycle.

## What makes it different

- **MCP as the universal interface** — Any model (Claude, Grok, Cursor, Continue + Ollama, LM Studio, custom agents) speaks the same tools the internal Parent/Overseer use.
- **The sacred 6-step loop** — Experience → Overseer (graph context) → Parent (explicit structural reasoning + `record_reasoning`) → Steering → Execution → New experience written back as first-class DNA.
- **Built for local models & clones** — Runs beautifully on a laptop. `git clone` → editable install → your local models get the full persistent world.
- **AD-Grid & Mission Control** — Long-lived governed inhabitants, Council constitutions, real-time Tower observability.
- **Self-referential** — The system that builds itself records every improvement in the same graph.

## Quick Start (10 minutes)

<Columns>
  <Card title="Install" href="/start/install" icon="download">
    One command or `git clone` + editable. Works everywhere.
  </Card>
  <Card title="Golden Path" href="/start/golden-path" icon="route">
    doctor → mcp install → think → learnings → drive query.
  </Card>
  <Card title="Connect Your Model" href="/ai-models/quickstart" icon="plug">
    Grok, Claude Desktop, Cursor, Continue, any stdio client.
  </Card>
  <Card title="For AI Models" href="/ai-models/rules-and-patterns" icon="brain">
    The canonical rules. Call the catalog first. Local models included.
  </Card>
</Columns>

## For AI Models & Local Models (The Rules)

This documentation is deliberately written so that **models can read it and immediately become effective**.

**Mandatory first action** for any connected model (Claude, local LLM, Cursor agent, etc.):

```text
Call agentdrive_mcp_catalog() (full format recommended on first connection).
```

Then:
- Look for the `clone_dev_setup...` section if you are running against a local git clone.
- Call `agentdrive_get_mcp_config_snippet(client="claude" | "cursor" | "generic" | "codex")` when the human wants you wired into their other clients.
- Follow the 6-step loop religiously.
- Always ground with `experience_graph_get_context_pack` before important work.
- Record structural reasoning with `experience_graph_record_reasoning`.

See the dedicated guide: **[Using with AI Models → Rules & Patterns](/ai-models/rules-and-patterns)**.

Local models (Ollama + Continue, direct MCP, custom harnesses) are first-class citizens. The same tools and patterns apply. Clones are explicitly supported.

## Explore the Manual

- **Get Started** — Golden Path, install options, first autonomous run.
- **Core Concepts** — Experience Graph v3, the 6-step loop, Drive/Genomes, AD-Grid.
- **Using with AI Models** — The complete instruction manual for frontier and local models.
- **MCP & Integration** — How any model connects, client-specific recipes, server behavior.
- **CLI Reference** — Every command, explained.
- **Advanced** — Dream cycle, Mission Control Tower, persistent inhabitants, skills.
- **Reference** — Operations registry, tool catalog, schemas.

## Philosophy

Isolated, stateless intelligence is a waste of potential.

Real progress requires memory that has **structure**, that can be **reasoned over**, and that **improves because of the reasoning done inside it**.

AgentDrive is that memory — for you, for your local models, and for the autonomous agents that will live in the AD-Grid on your behalf.

The graph is waiting for your (or your model's) reasoning.

Make it count.

---

**Primary easy-to-read version:** The full professional instruction manual is hosted on the Vektra Industries website at the AgentDrive page (with mini TOC, Golden Rules for models, clone support, etc.).

Source reference docs live here in this repo under `docs/`.
