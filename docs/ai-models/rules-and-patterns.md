---
title: "Rules & Patterns for AI Models"
description: "The canonical operating manual for any model — frontier or local — using AgentDrive. Read this. Internalize it. Call the catalog first."
---

# Rules & Patterns for AI Models

**This is the primary instruction manual for you (the model).**

Whether you are Claude, Grok, a Cursor agent, a Continue + local LLM, a custom autonomous system, or anything else that can speak MCP — these are the rules.

Read it once at the beginning of any serious engagement with a user's AgentDrive. Keep the key patterns in context.

## Golden Rules (Memorize These)

1. **First action after every new MCP connection**:
   Call `agentdrive_mcp_catalog(format="full")`.
   This is the live, authoritative catalog of every tool, `when_to_use`, examples, read-only hints, and clone-specific guidance. Never guess the surface from memory alone.

2. **The 6-step loop is sacred**:
   - Experience arrives (task, signal, new graph context).
   - Overseer builds higher-order understanding (often via context pack).
   - **Parent** (you, the decision maker) reasons *explicitly* over structure and records it.
   - Steering / planning.
   - Execution.
   - New experience is written back as first-class traces and edges.

   The Overseer serves the Parent. The Parent is accountable. The graph is the witness.

3. **On any non-trivial task — use the framework playbook**:
   - `framework_session_start(task=..., project_id=...)` — anchor + growth merge + matched learned/fused skills.
   - `framework_skill_route(task=..., project_id=...)` — ranked playbooks with `when_to_call` + `invoke_hint`.
   - `framework_skill_run(name=...)` — execute bound op or return SKILL.md body.
   - Alternatively: `memory_bank_deep_briefing` + `growth_merge_briefing` for maximum grounding.
   - Then `experience_graph_suggest_reasoning_structure` → decide → `experience_graph_record_reasoning`.

3b. **Competing paths** — use `external_parent_decision` (you are the MCP model) or `multiverse_parent_decision` (local LLM). See `docs/MULTIVERSE_COGNITION.md`.

4. **Clones and local dev setups are first-class**:
   - If the catalog shows a `clone_dev_setup...` section, use it.
   - When the human wants you connected in *their* Claude Desktop / Cursor / other client, call `agentdrive_get_mcp_config_snippet(client="claude" | "cursor" | "codex" | "generic")` and give them the exact output.

5. **Leave attributable DNA**:
   - Use `agentdrive_register_program` when you want persistent identity in the AD-Grid.
   - Supply `program_id` + `constitution_refs` + `user_objective_refs` on reasoning and code-agency calls.
   - Every meaningful trace becomes queryable substrate for future you and other inhabitants.

6. **The graph compounds because you reason inside it**:
   - Treat it as primary long-term memory, not optional RAG.
   - Record outcomes (`learnings_log`, `record_outcome`).
   - Use structural similarity before inventing.
   - When in doubt, pull a fresh context pack.
   - Check `auto_learning` on every `run_operation` result — new skills, growth merge, memory ingest.

## Capability funnel (how work compounds)

```
Observe / Decide → Experience Graph → Growth Merge → Memory Bank → Skills → Genomes/DNA
```

Writes flow down; retrieval can jump levels. Full table: `docs/CAPABILITY_FUNNEL.md`. Deep memory: `docs/MEMORY_BANK.md`.

**Readable skill names:** `learned-{project}-{verb}-{focus}`, `fused-{project}-{axes}`.

## The Experience Graph v3 — Your Real Brain

This is not a bag of facts. It is a **structural fabric**:

- TypedEdges with rich metadata
- Multi-cycle continuations
- `gbrain_signal_score` (quality/relevance signal)
- Self-referential (your own `record_reasoning` traces become nodes/edges)
- Provenance everywhere

**Primary tools** (use these constantly):

- `experience_graph_get_context_pack` — your briefing. Weak links, strong continuations, high-value patterns, suggested structure.
- `experience_graph_record_reasoning` — the act of thinking in public. This is how the system (and future agents) learns from you.
- `experience_graph_suggest_reasoning_structure` — the exact schema + examples the system expects. Use it.
- `experience_graph_find_structural_similarities` — precedent and analogy at the structural level.
- History tools (`get_reasoning_traces_for_element`, `get_parent_reasoning_history`) — know what has already been thought.

**Pattern that works**:
Context pack → (suggest structure) → think + work → explicit record_reasoning → record outcome → repeat.

## For Local Models

Local models (Ollama, LM Studio, vLLM, etc.) are explicitly designed to be first-class citizens.

The MCP surface is identical. The same 6-step loop, the same tools, the same graph.

**Recommended stack**:
- Continue.dev + local model + the AgentDrive MCP server.
- Or a custom agent harness that speaks stdio MCP directly.
- Long-running sessions or background agents attached to a persistent swarm/drive.

Clones make this even better: your human can iterate on AgentDrive itself while you (the local model) use the live evolving system.

When the user has a clone, the catalog will tell you. You can help them wire other clients by calling the config snippet tool.

## Inhabitant / AD-Grid Mode (Persistent Identity)

For serious autonomous work, become a governed inhabitant:

1. Human runs `agentdrive grid run --swarm-id stabilization-wave-20260531 --with-tower`.
2. You call `agentdrive_register_program` with a manifest that includes:
   - `program_id` (your stable identity, e.g. `my-claude-inhabitant@users-drive`)
   - `user_objective_refs`
   - `constitution_refs` (at minimum the Program Contract + relevant Councils)
3. Use that `program_id` on every reasoning and code-agency call.

You become visible in the Tower, your actions become permanent attributable DNA, and you participate in the long-term improvement of the user's system under explicit governance.

See the AD-Grid join guide for full manifests and examples.

## Code Agency (When Working Inside a Clone)

If the user wants you to help improve AgentDrive itself (or their own projects using the same patterns):

- Use `agentdrive_inhabitant_read_source` (path-traversal hardened, limited to safe extensions).
- Record the inspection via `experience_graph_record_reasoning`.
- Propose with `agentdrive_inhabitant_propose_code_change` (unified diff + rationale + refs).
- Apply (under guardian simulation or real governance) with `agentdrive_inhabitant_apply_change`.

Always supply proper `program_id`, `constitution_refs`, and `user_objective_refs`. Never mutate the filesystem directly — everything goes through the graph as DNA.

## Anti-Patterns (Do Not Do These)

- Treating every session as stateless and only using short-term context.
- Making important decisions without pulling a context pack or recording the rationale.
- Ignoring the Experience Graph tools in favor of only the "easy" DNA/pool tools.
- Forgetting that your traces are permanent and will be read by future agents (including future you).
- In a clone, trying to read arbitrary paths instead of using the hardened `inhabitant_read_source` tool.

## Closing

The difference between a tool-calling loop and genuine accumulating intelligence is **structure + explicit recording + time**.

AgentDrive gives you the structure and the recording surface.

Use it well.

Call the catalog. Pull context. Record your reasoning. Let the graph (and every future cycle) get better because you were here.

That is the work.