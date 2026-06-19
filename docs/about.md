---
title: "About AgentDrive"
description: "What AgentDrive is, who it's for, how it differs from chat memory and vector search, and the principles behind local-first compounding intelligence."
---

# About AgentDrive

> **Intelligence that remembers the shape of what it has become.**

AgentDrive is **local-first compounding intelligence for AI agents** — a structural memory platform that runs on your machine and grows sharper every time a model reasons inside it.

Not a vector database. Not ephemeral chat memory. A living substrate where decisions, reasoning traces, skills, and knowledge **compound across sessions** instead of resetting when you open a new chat.

---

## The problem

Most agent systems today are **stateless by default**:

- Every new session starts from zero — or from a thin slice of conversation history.
- Important decisions evaporate when the chat ends.
- Sub-agents on the same project cannot reliably inherit each other's reasoning.
- "Memory" products store facts; they rarely store the **shape** of how a decision was made.

That wastes potential. Serious work should leave the system **stronger than it found it**.

---

## What AgentDrive does

AgentDrive gives any capable model — Grok, Claude, Cursor, Continue, Ollama, custom harnesses — a **persistent intelligence substrate** under `~/.agentdrive/` on the user's machine.

| Layer | Role |
|-------|------|
| **Experience Graph** | Structural memory — TypedEdges, reasoning traces, coherence signals, cross-cycle continuations. Remembers *how* thinking happened, not just *what* was said. |
| **Growth Merge** | Cross-surface compounding — when experience, codebase patterns, and memory overlap in a session, AgentDrive merges them into compound growth artifacts automatically. |
| **Memory Bank** | Deep personal knowledge databank per swarm — append-only `memories.jsonl`, BM25 search, session anchor, time-bounded relations. |
| **Skills** | Learned playbooks (`learned-*`) and fused playbooks (`fused-*`) distilled from real work — routable before every task. |
| **DNA / Genomes** | Versioned capability packages — frameworks, reasoning patterns, evaluations — promotable when skills prove repeatable. |
| **Auto-learning** | Every MCP/CLI operation can absorb traces, skills, memory, and growth merge without manual write calls. |

Everything flows through one **capability funnel**:

```
Observe / Decide
       ↓
Experience Graph
       ↓
Growth Merge
       ↓
Memory Bank
       ↓
Skills (learned + fused)
       ↓
Genomes / DNA
```

The **sacred 6-step loop** wraps execution: Experience → Overseer → Parent records reasoning → Steering → Execution → write experience back. The Overseer serves the Parent. The Parent is accountable. **The graph is the witness.**

---

## Who AgentDrive is for

<Columns>
  <Card title="Developers" icon="code">
    Long-running projects where agents must remember architecture decisions, coding style, and prior approaches — across weeks, not just one chat.
  </Card>
  <Card title="Local model operators" icon="cpu">
    Ollama, LM Studio, Continue — models that finally get **durable structural memory** on a laptop, without a cloud memory SaaS.
  </Card>
  <Card title="Multi-agent swarms" icon="users">
    Sub-agents share one swarm Drive. A genome one worker proves is immediately available to the others — with full provenance.
  </Card>
  <Card title="Frontier model users" icon="sparkles">
    Grok, Claude, Cursor — connect via MCP. Same tools, same loop, same compounding graph whether the model runs in the cloud or locally.
  </Card>
</Columns>

---

## How AgentDrive is different

| Approach | What you get | Limitation |
|----------|--------------|------------|
| **Chat memory** (ChatGPT, etc.) | Conversation-scoped recall | Opaque, not queryable, no structural reasoning |
| **Vector RAG** | Semantic similarity over chunks | No decision provenance, no cross-cycle continuations |
| **Editor context** | Files in the current window | Resets per session; no governed decision history |
| **AgentDrive** | Structural graph + memory bank + skills + DNA | Requires ~10 min setup; local-first by design |

**MCP is the universal interface.** Any connected model calls the same Experience Graph, memory, skills, and DNA tools the internal Parent/Overseer use. The live contract is always `agentdrive_mcp_catalog()` — not a static doc list.

---

## Principles

**Local-first.** Your data lives under `~/.agentdrive/` on your machine. MCP connects your AI client to your local AgentDrive process — not a hosted memory SaaS.

**User sovereignty.** You own the graph, the memory bank, the skills bench, and the genomes. Export, inspect, back up, or run entirely offline.

**Structural over semantic.** AgentDrive remembers the *shape* of decisions — what was considered, which pattern matched, why the Parent chose a path — so future agents can reason over history, not just retrieve keywords.

**Compounding by discipline.** Auto-learning helps, but the habit that matters is explicit structural reasoning (`experience_graph_record_reasoning`) inside the 6-step loop.

**Clones are first-class.** `git clone` → editable install → your local models and dev tree get the full persistent world, with catalog-guided MCP wiring.

---

## What AgentDrive is not

- A hosted vector DB or chat-memory SaaS
- A drop-in replacement for your editor's context window
- Ready without setup — the [Golden Path](/start/golden-path) takes ~10 minutes
- *Only* AD-Grid / Mission Control — those are **advanced** observability layers on top of the Drive

---

## Built by Vektra Industries

AgentDrive is developed by [Vektra Industries](https://vektraindustries.com) as open infrastructure for autonomous intelligence — MIT licensed, designed for operators who want agents that **get better over time** instead of forgetting yesterday.

The system is **self-referential**: the drive used to build AgentDrive itself (`stabilization-wave-20260531`) records every improvement in the same graph it provides to users.

---

## Where to go next

<Columns>
  <Card title="Golden Path" href="/start/golden-path" icon="route">
    Install → doctor → MCP → think → learnings in ~10 minutes.
  </Card>
  <Card title="Instructions for AI Agents" href="/INSTRUCTION" icon="bot">
    What, why, how — and how models explain AgentDrive to their user.
  </Card>
  <Card title="Connect MCP" href="/mcp/connect" icon="plug">
    Grok, Claude, Cursor, Continue, any stdio client.
  </Card>
  <Card title="Capability Funnel" href="/CAPABILITY_FUNNEL" icon="layers">
    The single mental model for how intelligence compounds.
  </Card>
</Columns>

**Source:** [github.com/PabloTheThinker/AgentDrive](https://github.com/PabloTheThinker/AgentDrive)