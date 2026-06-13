---
title: "The Experience Graph v3"
description: "The living structural memory at the center of AgentDrive. This is what makes compounding intelligence possible."
---

# The Experience Graph v3

The Experience Graph is the core abstraction that distinguishes AgentDrive from every other memory system for agents.

## What It Is

An **Obsidian-style, queryable graph** of structural relationships (TypedEdges) that spans many cycles of work.

It is not a flat vector database. It is a fabric with:
- Bidirectional typed relationships
- Rich metadata on edges and nodes
- `gbrain_signal_score` (a learned quality/relevance signal)
- Full provenance (who/what recorded this and why)
- Explicit support for cross-cycle continuations
- Self-referentiality (your own reasoning traces become first-class parts of the graph)

## Why It Matters for Models

Most agent memory is either:
- Ephemeral (just the current conversation)
- Semantic retrieval (RAG over documents or past messages)

The Experience Graph lets you (the model) do **structural reasoning** over the actual shape of past work:
- "What patterns have led to success before?"
- "Where are the weak links or contradictions in the current understanding?"
- "How does this new decision continue or diverge from previous structural choices?"

When you record reasoning with `experience_graph_record_reasoning`, you are not just taking notes — you are weaving yourself into the permanent substrate that future versions of you and other agents will read and stand on.

## Primary Tools

These are the tools you will use constantly (the live details and examples are always in the catalog):

- `experience_graph_get_context_pack` — Your main briefing. Returns a dense, LLM-optimized view of the current fabric state (high-value patterns, weak links, strong continuations, suggested structure).
- `experience_graph_record_reasoning` — The act of thinking structurally in public. This is how you contribute lasting value.
- `experience_graph_suggest_reasoning_structure` — The exact schema + few-shot examples the system expects for high-quality traces. Use it before recording.
- `experience_graph_find_structural_similarities` — Structural (not just semantic) precedent search.
- History and element-specific trace tools — Understand what has already been thought about a particular part of the graph.

## Memory Systems Triage

`experience_graph_get_context_pack` includes `memory_systems_triage`, a human-inspired routing layer for scarce context.

Use its queues this way:

- `working_set` — Put these items in active reasoning first.
- `reconsolidate` — Resolve or update these before treating them as precedent.
- `consolidate` — Convert these into durable graph/DNA structure when the current work allows it.
- `archive` — Keep addressable, but do not spend active context unless directly needed.

This keeps long-running agents from treating memory as an append-only transcript. The graph remains structural memory, but the triage layer decides what should be active, consolidated, revised, or left cold.

## The Fundamental Pattern

On any important piece of work:

1. Pull a fresh context pack.
2. (Recommended) Ask for the reasoning structure template.
3. Do the thinking / decision making.
4. Explicitly record the structural rationale.
5. Later, record outcomes so the benefit is queryable.

Do this consistently and the graph (and every agent that uses it) gets sharper over time.

## For Local Models & Long-Running Agents

This is where the Experience Graph delivers the most value.

A local model that stays attached to the same Drive + Graph for days or weeks can accumulate real structural understanding instead of resetting every session. The self-referential nature means the model literally gets better at using the system because of the traces it (and previous inhabitants) have left.

## See Also

- The sacred [6-step loop](/concepts/six-step-loop)
- [Rules & Patterns for AI Models](/ai-models/rules-and-patterns) (especially the "record your structural reasoning" habit)
- The live `agentdrive_mcp_catalog()` output (always more up-to-date than any static doc)
