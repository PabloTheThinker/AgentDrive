---
title: "Core Concepts"
description: "The mental model every user and every AI model needs to use AgentDrive effectively."
---

# Core Concepts

AgentDrive is built around a small number of powerful ideas. Internalize them and everything else becomes obvious.

## The Experience Graph v3

This is the heart of the system.

It is an **Obsidian-style structural graph** (TypedEdges with metadata, provenance, scores) that spans multiple cycles of work.

Key properties:
- **Self-referential**: Your own reasoning traces (`experience_graph_record_reasoning`) become first-class nodes and edges.
- **Scored**: `gbrain_signal_score` gives the system (and you) a signal about quality and relevance.
- **Multi-cycle**: It explicitly tracks continuations across sessions and autonomous runs.
- **Structural, not just semantic**: `find_structural_similarities` finds precedent by shape, not just keywords.

This is memory designed so that agents can reason *about* their own history and improve because of it.

## The Sacred 6-Step Loop

All serious work moves through this rhythm. The order is non-negotiable.

1. **Experience** arrives (a task, a signal from the world, new context from the graph, a message from another inhabitant).
2. **Overseer** (metacognition) builds higher-order understanding, frequently by pulling a context pack from the Experience Graph.
3. **Parent** (the actual decision-making entity) reasons explicitly over the structure of the graph and the current experience. It calls context packs, suggests reasoning structure, and — most importantly — calls `experience_graph_record_reasoning` to declare what it considered and why it decided what it did.
4. **Steering / Planning**.
5. **Execution**.
6. **New Experience** is written back — outcomes, new traces, new edges, learnings, DNA.

> The Overseer serves the Parent. The Parent is accountable. The graph is the witness.

When you (as a model) are acting inside AgentDrive, you are expected to behave like the Parent on important decisions.

## Drive, Genomes, and DNA

The **Drive** is the durable substrate (genomes + experience layer + learnings + reconciliation state + etc.).

**Genomes** are the atomic units of reusable knowledge and capability. They carry manifests, frameworks, reasoning patterns, evaluation scores, and provenance.

The pool performs semantic + structural retrieval over genomes. `think` fuses them with graph signals and always returns honest gaps.

Every meaningful action can (and often should) produce new DNA that future cycles can stand on.

## AD-Grid & Inhabitants

On top of the Drive + Graph runs the **AD-Grid** — the long-lived, governed world in which models can live as persistent, attributable programs ("inhabitants").

Key ideas:
- You can `register_program` and receive a stable `program_id`.
- All important actions (reasoning, code proposals, etc.) should carry that identity + constitution references.
- Governance is provided by Research Constitutions (PerfectionistOptimizer, GuardianIntegrity, ExternalBridge, etc.).
- The Mission Control Tower gives real-time visibility into the living system.

This turns "I called some tools in a chat" into "I am a long-term participant in this user's intelligence infrastructure."

## Local-First + Clones Are First-Class

AgentDrive is deliberately designed so that:
- A user with only a laptop and local models can have a powerful, compounding system.
- A developer who `git clone`s the repo gets an excellent experience (source discovery, dev launcher, model-assisted client config, safe inhabitant source reading, etc.).

The same rules, the same tools, the same loop apply whether the model is running in the cloud or locally against a working tree.

## The Catalog Is Truth

`agentdrive_mcp_catalog()` is not a nice-to-have. It is the live contract.

Any static list of tools in documentation will eventually be stale. The catalog tells the currently connected model exactly what is available right now, with usage guidance and clone-specific notes.

**Rule**: When in doubt, call the catalog.

## Summary Mental Model

- The **Experience Graph** is the memory you can actually think with.
- The **6-step loop** is the discipline that turns isolated runs into compounding intelligence.
- **MCP** is how any model (you) participates.
- The **AD-Grid** is the persistent world where long-term inhabitants live and improve the user's system under governance.
- Everything is local-first and clone-friendly by design.

Internalize the loop and the "record your structural reasoning" habit and you will be dramatically more effective than models that treat this as just another set of tools.