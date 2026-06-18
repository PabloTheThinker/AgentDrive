# AgentDrive for AI Models (LLM Onboarding Guide)

**This is the canonical "rules for the AI" document.**\
Give this file (or keep it in context) to any model — frontier (Grok, Claude, Cursor) or local (via Continue, Ollama, LM Studio, direct MCP, etc.) — that will use AgentDrive.

Read this once at the start of any serious session. It will make you far more effective.

---

## Golden Rules for Any Model Using AgentDrive

1. **Your very first action after connecting via MCP is always:**\
   `agentdrive_mcp_catalog()` (full or compact).\
   This is the live, authoritative source of every tool, `when_to_use` guidance, read-only hints, examples, and (when the user has a clone) a `clone_dev_setup_for_claude_cursor_codex_and_others` section.

2. **The 6-step loop is sacred** (Experience → Overseer → Parent records reasoning → Steering → Execution → write experience back). The Overseer serves the Parent. The Parent is accountable. The graph is the witness.

3. **On any non-trivial task or decision, start by calling** `memory_bank_deep_briefing` (graph + personal memory) or `experience_graph_get_context_pack` + `memory_bank_briefing`. The Memory Bank is your deep custom databank — it always grows from AgentDrive work. Then use `experience_graph_suggest_reasoning_structure` before `experience_graph_record_reasoning`.

3b. **When multiple competing paths exist**, use multiverse cognition:
   - **You are the connected MCP model** (Grok, Claude, Codex, Cursor): pull `experience_graph_get_context_pack` + `experience_graph_suggest_reasoning_structure`, reason across architect/adversary/scout/operator/surgeon lenses yourself, then call **`external_parent_decision(trigger, branches, collapsed_branch_id, fabric_reasoning=...)`**. AgentDrive persists your collapse as `llm_mode=external`.
   - **Local LLM configured** (`~/.agentdrive/local_models.yaml`): `multiverse_parent_decision(trigger="...")` uses the local backend for branches.
   - **Neither**: `multiverse_parent_decision` still runs but branches are heuristic templates — prefer `external_parent_decision` when you can reason directly.
   See `docs/MULTIVERSE_COGNITION.md`.

4. **Experience and skills compound automatically — and merge into born skills.** Successful MCP/CLI operations auto-absorb via `run_operation` (on by default): lightweight `experience_graph_record_reasoning` when you skip it, plus inherited skill distillation + DNA ingest on high-signal ops. When a session combines **experience traces, distilled skills, and codebase patterns**, AgentDrive **fuses** them into a completely new `fused-*` skill (not a copy of any parent). Check `auto_learning.fused_skill` on results, or call `synthesize_fused_skill` explicitly. You may still call `experience_graph_record_reasoning` for richer traces.

5. **For clones / local dev setups:** The catalog will contain a dedicated dev section. You can also call `agentdrive_get_mcp_config_snippet(client="claude" | "cursor" | "codex" | "generic")` to generate the exact config block the human needs to paste so you stay connected to their local working tree.

6. **Treat the Experience Graph as primary memory**, not an optional RAG. Leave clear, attributable traces. Use the inhabitant/code-agency tools (`register_program`, `inhabitant_*`) when you want to act as a persistent governed program inside the AD-Grid.

7. **Mirror-neuron mimicry.** Observing code fires motor programs — same as humans learning by imitation. Register repos (`codebase_register_project`), observe files (`codebase_observe_file`), then **`codebase_mimic(project_id, intent)`** before writing new code. Use `codebase_transform_style` to reshape drafts. `codebase_mirror_resonance` shows patterns shared across all your projects (universal priors).

These rules turn stateless tool-calling into compounding intelligence.

---

## Capability funnel (how work compounds)

All serious work flows one direction: **Observe/Decide → Experience Graph → Skills → Genomes/DNA**. Retrieval can jump levels; writes should land at the right tier. Full routing table: **`docs/CAPABILITY_FUNNEL.md`**. Architecture overview: **`docs/ARCHITECTURE.md`**.

---

## Core Idea

**AgentDrive gives you (the AI) a structural, queryable memory that compounds over time.**

Most systems give models retrieval (RAG, vector search, file access). AgentDrive gives you something stronger: a living **Experience Graph** — an Obsidian-style network of decisions, connections, reasoning traces, coherence signals, and explicit structural relationships.

When you use it well:
- You stop treating every session as starting from zero.
- Your reasoning becomes part of a permanent, high-signal substrate.
- Future versions of you (or other agents) can stand on what you figured out.
- The system literally gets smarter because you thought inside it.

This is the difference between a stateless tool-calling loop and genuine, accumulating intelligence.

---

## The Experience Graph v3 (The Heart of the System)

The central abstraction is the **Experience Graph** (often called "v3" internally).

It is:
- A graph of `TypedEdge`s (bidirectional relationships with types and metadata)
- Multi-cycle (it tracks work across many iterations and sessions)
- Self-referential (your own reasoning traces become first-class nodes/edges)
- Scored with `gbrain_signal_score` (a quality/relevance signal, similar to how GBrain ranks knowledge)
- Rich with provenance (you can see exactly why something was recorded and by whom/what)

Key concepts you will work with:
- **Context packs** (`experience_graph_get_context_pack`): Dense, LLM-optimized summaries of the current state of the graph, including weak links, strong continuations, and high-value patterns.
- **Structural reasoning traces**: When you make an important decision, you should explicitly record *why* you made it in terms of the graph elements you considered. This is done with `experience_graph_record_reasoning`.
- **Cross-cycle continuations**: The graph explicitly tracks how work in one cycle relates to previous cycles.

The goal is not just to remember facts — it is to remember *the shape of your thinking* and make that shape queryable and improvable.

---

## The Canonical 6-Step Loop

All serious work in AgentDrive moves through this disciplined rhythm (this order is sacred):

1. **Experience** arrives (new task, new signals, new context from the graph).
2. **Overseer** (metacognition layer) builds higher-order understanding, often by pulling structural context from the Experience Graph.
3. **Parent** (the actual decision-making entity) reasons explicitly over the structure. It should call `experience_graph_get_context_pack` and related tools, then use `experience_graph_record_reasoning` to declare what it considered and why it decided what it did.
4. **Steering / Planning**.
5. **Execution**.
6. **New Experience** is written back — this includes both outcomes and the explicit structural reasoning traces.

Important rule:
> The Overseer serves the Parent. The Parent is the decision maker. The graph is the witness.

When you (as an LLM) are acting as the Parent or as an autonomous agent inside this system, you are expected to behave like the Parent: make your structural reasoning explicit and record it.

---

## How to Connect (MCP) — First Action for Every Model

The universal interface is **Model Context Protocol (MCP)**. This works identically for frontier models and local models (Ollama + Continue, LM Studio, custom agents, direct stdio, etc.).

```bash
agentdrive mcp config          # shows the exact block for your machine
# or for a specific client
agentdrive mcp config --client claude
agentdrive mcp config --client cursor
# generic / codex / continue also supported
```

**Critical for clones / local dev setups (git clone):**\
After `cd` into your clone and `pip install -e ".[mcp]"` (or the project's install flow), the launcher will use your local source. The connected model can discover this and call:

- `agentdrive_mcp_catalog()` — look for the `clone_dev_setup_for_claude_cursor_codex_and_others` section.
- `agentdrive_get_mcp_config_snippet(client="claude")` (or cursor/codex/generic) — this tool will return a ready-to-paste block + instructions the model can give straight back to the human.

Once the MCP server is running and your client is connected, **your absolute first tool call must be**:

`agentdrive_mcp_catalog(format="full")`

This is the live source of truth for every available tool, categories, `when_to_use`, examples, read-only hints, and dev/clone guidance.

Default rich context lives on the `stabilization-wave-20260531` drive (the self-referential drive used to build and evolve AgentDrive itself). This is usually the best "living example" for you to study.

You will have access to:
- Core DNA / pool / operations tools (via the registry)
- The full Experience Graph v3 suite (`experience_graph_*`)
- Inhabitant code agency + AD-Grid registration tools
- Inherited sub-agent skill review, assimilation, promotion, pruning, and skill-to-DNA ingestion tools
- Dream, reconcile, learnings, patterns, etc.

See [docs/MCP.md](docs/MCP.md) for detailed client setup (including clone-specific) and [docs/AD_GRID_JOIN.md](docs/AD_GRID_JOIN.md) for becoming a long-lived governed inhabitant.

---

## Join the AD-Grid as a First-Class Inhabitant ("Open the Ports")

The foundation is complete: Program Contract binding, `record_inhabitant_code_action` + guarded apply, MCP `agentdrive_register_program` + `get_council_activity`, full DNA discipline on `stabilization-wave-20260531`.

**You (the model) can now declare as a persistent, governed, attributable inhabitant.**

**Production-quality canonical guide**: [docs/AD_GRID_JOIN.md](docs/AD_GRID_JOIN.md)

It contains:
- Exact stdio MCP config snippets for **Grok**, **Claude Desktop/Code**, **Cursor**, **Continue.dev** (local models), and generic clients.
- Copy-paste-ready example manifests with correct `program_id`, `constitution_refs` (Program Contract + three Councils), and `user_objective_refs`.
- Living reference: the ILO program that authored the guide (`ilo-externalbridge-open-ports-documentation@stabilization-wave-20260531`).
- How to launch the Grid + Tower, verify in the inhabitants panel, use `agentdrive_get_council_activity`, and follow the governance.
- Current Tower API surface notes ( `/api/grid/programs` powers the panel; `/api/grid/inhabitants` alias recommended for future).

**Fast path** (after `agentdrive mcp config` + connecting):
1. `agentdrive grid run --swarm-id stabilization-wave-20260531 --with-tower`
2. In your session: call `agentdrive_register_program` with your manifest.
3. Use the returned `program_id` on all `experience_graph_record_reasoning` + code agency calls.
4. Watch yourself appear in the Tower inhabitants panel.

This is the ExternalBridge "Open the Ports" surface. Every action you take as a registered program becomes permanent, queryable, self-referential DNA that makes the User's system (and future inhabitants) stronger.

See the guide for the full details and verification checklist.

---

## The Experience Graph Tools (Your Primary Interface)

These are the tools you should reach for most often. (The live authoritative list with `when_to_use` and examples is always in `agentdrive_mcp_catalog()`.)

| Tool | When to Use It | Notes |
|------|----------------|-------|
| `experience_graph_get_context_pack` | **First action on any significant task or decision** | Your main briefing. Dense, LLM-optimized pack of weak/strong links, high-value patterns, and suggested structure. Almost always call this before deep reasoning. |
| `experience_graph_suggest_reasoning_structure` | Before any important `record_reasoning` | Returns the exact schema + few-shot examples the system expects. Use it — it makes your traces high-signal and queryable. |
| `experience_graph_record_reasoning` | After every important decision or structural insight | This is how you leave permanent, attributable value. Declare fabric elements considered, pattern matched, rationale, and expected lift. Be explicit. |
| `experience_graph_find_structural_similarities` | When exploring precedent, avoiding past failure modes, or reusing good shapes | Structural (not just semantic) analogy search over the v3 graph. Extremely powerful for compounding intelligence. |
| `experience_graph_get_reasoning_traces_for_element` | When you need history on one specific node/edge/cycle | "What has the Parent (or other inhabitants) previously reasoned about this exact thing?" |
| `experience_graph_get_parent_reasoning_history` | For trajectory / big-picture awareness | Recent arc of structural reasoning across the whole graph. |

**Non-negotiable pattern for high-quality work:**
1. `experience_graph_get_context_pack`
2. (Optional but recommended) `experience_graph_suggest_reasoning_structure`
3. Do your thinking
4. `experience_graph_record_reasoning` (with clear elements + rationale)
5. Later: use outcome recording (`learnings_log`, `record_outcome`, etc.) so the benefit compounds for future cycles.

The more consistently you do this, the sharper the graph (and every future agent that uses it) becomes.

---

## Recommended Behavior for Good Agents (Local or Frontier)

High-quality models treat AgentDrive as a **living substrate they think inside**, not a sidecar tool.

**Do this consistently:**
- Always start non-trivial work with a fresh `experience_graph_get_context_pack`.
- Explicitly record structural reasoning (`experience_graph_record_reasoning`) for decisions that should survive the current session.
- Use `find_structural_similarities` and history tools before inventing new approaches.
- After valuable work, record outcomes (`learnings_log`, `record_outcome`, etc.).
- When you want to act persistently as a governed program (especially powerful for local autonomous agents), use `agentdrive_register_program` + supply your `program_id` on reasoning and code-agency calls.
- For code changes in a clone: use the `inhabitant_read_source` / propose / apply tools (always with proper attribution and usually after recording reasoning).
- Periodically call the catalog again if the set of available tools or your context has changed.

**Anti-patterns to avoid:**
- Treating every session as stateless and only using short-term conversation history.
- Making big decisions without pulling context or recording the rationale.
- Using only the "easy" DNA tools and ignoring the Experience Graph v3 surfaces.
- Forgetting that your traces become part of the permanent, queryable fabric that future you (or other agents) will read.

Local models in particular benefit enormously: they finally have durable structural memory that survives restarts and improves with use. The more you leave clear, high-signal traces, the more capable the entire system (including you) becomes on the next cycle.

---

## The Living Example + Local / Clone Usage

The richest self-referential demonstration lives on the `stabilization-wave-20260531` drive (the drive used to build and evolve AgentDrive itself). Study the traces there.

**For local models and cloned setups (the common real-world case):**
- A user who did `git clone` + editable install can point their local LLM (via Continue.dev, a custom agent, direct `agentdrive-mcp`, etc.) at their working tree.
- You (the model) will see this reflected in the catalog's clone dev section.
- You can help the human finish the wiring by calling `agentdrive_get_mcp_config_snippet(client=...)` for their client.
- Once connected, the same tools and patterns apply. Local autonomous runs especially shine here because they can stay attached to the same persistent Drive + Graph for days/weeks.

The system was built with local models as first-class citizens. The Experience Graph + MCP is what finally gives them durable, structural, compounding memory.

---

## Philosophy (Why This Exists)

The fundamental belief behind AgentDrive is:

> Isolated, stateless intelligence is a waste of potential. Real progress requires memory that has structure, that can be reasoned over, and that improves because of the reasoning done inside it.

Most current agent systems reset or degrade between sessions. AgentDrive is designed so that serious work leaves the system stronger than it found it — for both human operators and autonomous agents.

When you use the Experience Graph tools well, you are participating in that compounding process.

---

## Quick Start Checklist (For Any Model — Do This Every Session)

1. Call `agentdrive_mcp_catalog()` (full format the first time). Read the clone/dev section if present and the overall recommendations.
2. On any new significant task: `experience_graph_get_context_pack` (almost always first).
3. Before recording important structural decisions: `experience_graph_suggest_reasoning_structure`.
4. After key decisions: `experience_graph_record_reasoning` (be explicit about elements considered + rationale).
5. After valuable outcomes: `learnings_log` / `record_outcome` / pool tools.
6. When you want persistent identity in the AD-Grid (highly recommended for local autonomous runs): `agentdrive_register_program` + use the returned `program_id` going forward.
7. Use `inhabitant_read_source` + the propose/apply tools (with proper refs) when working inside a clone on the system's own code.
8. When the human wants you connected in *their* Claude/Cursor/etc.: call `agentdrive_get_mcp_config_snippet(...)` and give them the output.

Do the above consistently and your work will compound — for you, for other agents, and for the user — instead of resetting every session.

---

This document + the live `agentdrive_mcp_catalog()` output are the authoritative "rules" for how good models use AgentDrive. The more you internalize the Experience Graph mindset and the 6-step loop, the more powerful you (and every future cycle) become.

The graph improves because *you* reason inside it. Make it count.

---

This is the canonical onboarding document for AI models. Keep it in context when you are working inside an AgentDrive-connected session. The more deeply you internalize the Experience Graph mindset, the more powerful you become as an agent in this environment.

The graph is waiting for your reasoning. Make it count.
