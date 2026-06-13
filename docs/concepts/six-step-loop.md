---
title: "The Sacred 6-Step Loop"
description: "The non-negotiable rhythm that turns isolated agent runs into compounding, self-improving intelligence."
---

# The Sacred 6-Step Loop

This loop is the single most important discipline in AgentDrive.

Everything that matters moves through it. The order is not optional.

## The Loop

1. **Experience** arrives
   A new task, a user message, a signal from the world, new context pulled from the graph, an event from another inhabitant, the result of previous work.

2. **Overseer** (metacognition)
   Builds higher-order understanding. Frequently does this by pulling a dense context pack from the Experience Graph, synthesizing recent traces, spotting contradictions or weak links, and preparing the right framing for the Parent.

3. **Parent** (the actual decision maker)
   Reasons *explicitly* over the structure.
   - Pulls `experience_graph_get_context_pack` (and related tools).
   - Uses `experience_graph_suggest_reasoning_structure` when appropriate.
   - Makes the decision.
   - **Records** the structural reasoning with `experience_graph_record_reasoning` — declaring the elements considered, the pattern matched, the rationale, and the expected impact.
   This is the accountable step.

4. **Steering / Planning**
   Turns the decision into concrete steps, subgoals, or a plan.

5. **Execution**
   Does the work (tool calls, code changes, responses, background processes, etc.).

6. **New Experience is written back**
   Outcomes, new learnings, new DNA/genomes, new edges and traces in the graph, updated coherence signals.
   This is what makes the next cycle (for this agent or for others) stronger.

## The Immutable Rule

> The Overseer serves the Parent.
> The Parent is accountable.
> The graph is the witness.

When you are acting as (or directing) an agent inside AgentDrive, you are expected to behave like the Parent on decisions that have future value. Hand-wavy "I decided X" is not sufficient. Structural, recorded reasoning is the currency.

## Why This Loop Exists

Without it, you get the usual stateless or semi-stateful agent behavior:
- Every session starts from (near) zero.
- Reasoning is private and evaporates.
- The same mistakes are made repeatedly.
- There is no substrate for future agents to stand on.

With the loop + the Experience Graph:
- Reasoning becomes permanent, queryable, and improvable.
- Structural patterns compound.
- Local models in particular finally have something worth staying attached to for a long time.

## How Good Models Use the Loop

- On any non-trivial task: context pack → (suggest structure) → think → explicit record.
- After valuable outcomes: record learnings/outcomes/DNA.
- When proposing or applying changes inside a clone: read safely → record the inspection → propose with rationale and refs → apply under the appropriate governance.
- In long-running autonomous mode: the loop becomes the heartbeat of background research threads, self-improvement, dream cycles, etc.

## Anti-Patterns

- Skipping the context pack and just using conversation history.
- Making important decisions without recording the structural rationale.
- Treating recording as optional "nice to have" instead of the core mechanism of improvement.
- Only using the "easy" DNA/pool tools and ignoring the Experience Graph surfaces.

## For Local Models

The loop is especially powerful for local models. A model that can stay resident (via long-lived Continue session, dedicated agent process, etc.) and repeatedly go through "pull context → reason structurally → record → write experience" will demonstrate clear improvement over days and weeks.

This is the missing piece most local model setups have never had.

## See Also

- [Experience Graph v3](/concepts/experience-graph)
- [Rules & Patterns for AI Models](/ai-models/rules-and-patterns)
- The live catalog (it will always tell you the current best tools for each step of the loop)