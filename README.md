# AgentDrive

<p align="center">
  <img src="assets/agentdrive-hero-1920x1080.jpg" alt="AgentDrive — Structural Experience Graph for Autonomous Agents" width="100%">
</p>

**Intelligence that remembers the shape of what it has become.**

AgentDrive is a structural memory system for agents that must grow from their own decisions. Not a vector store. Not a document dump. A living graph where every connection, every hesitation, every breakthrough is recorded with provenance and weight — and can be reasoned over directly by the agents themselves.

> **For AI models (Grok, Claude, Cursor, local LLMs via Continue/Ollama, custom agents):**\
> Read the professional **[Instruction Manual](/docs)** (Mintlify-style docs site) — especially the **[Rules & Patterns for AI Models](/docs/ai-models/rules-and-patterns)**.\
> Your first action after connecting via MCP: call `agentdrive_mcp_catalog()`.\
> Clone/dev, local models, and client-specific recipes are fully supported and documented.

This is the primary interface and "rules" document for any model, frontier or local.

It exists for one reason: so autonomous work can compound instead of reset.

## The Experience Graph

At the center is a queryable, multi-cycle **Experience Graph** — an Obsidian-like fabric of TypedEdges, cross-cycle continuations, coherence signals, and explicit structural reasoning traces.

Agents don’t just retrieve information. They ask the graph what it has learned about itself. They surface weak links, follow densification paths, and see the exact structural patterns that led to previous successes or failures. The graph gets sharper every time it is used.

This is memory designed for intelligence that improves over time — not just for retrieval.

## A Disciplined Rhythm

Everything moves through a single, non-negotiable six-step loop:

Experience arrives.  
The Overseer builds higher-order understanding from the graph.  
The Parent — the actual decision maker — reasons explicitly over structure and records why it chose what it chose.  
Steering and execution follow.  
New experience is written back as first-class traces and edges.

The Overseer serves the Parent. The Parent is accountable. The graph is the witness.

This rhythm is what turns isolated runs into a coherent body of work.

## Surfaces for Serious Work

Three things make the system usable in practice:

**MCP as the universal interface.**  
Any capable model — local or frontier — can speak directly to the Experience Graph through a small set of `experience_graph_*` tools. Context packs, structural similarity search, reasoning traces, and history are all first-class. The same surface that powers internal loops is available to anything that can call MCP.

**Mission Control.**  
A real-time Tower and TUI where you watch the 6-step pulse, see the graph evolve live, and observe Parent decisions with their full structural rationale. You see the system as one living thing, not scattered processes and files.

**Self-referential DNA.**  
Every meaningful decision, every MCP call, every coherence shift is recorded on the drive with gbrain scoring and full provenance. Future agents — including entirely new autonomous runs — stand on the actual history of what came before.

## Autonomy That Compounds (Especially for Local Models)

The primary intended use is **continuous autonomous agents**, particularly local models, that live inside the system over time.

Give a local model (via Continue, direct stdio MCP, or an agent harness) a Research Constitution + MCP access to the Experience Graph. It can:
- Start every significant cycle by calling `experience_graph_get_context_pack`
- Make structural decisions and record them with `experience_graph_record_reasoning`
- Use `agentdrive_register_program` to become a first-class, attributable inhabitant in the AD-Grid
- Participate in long-running Council-governed work on the `stabilization-wave-20260531` drive (or your own)

The graph gets better because the model reasons inside it. Local models especially benefit: they finally have durable, queryable, structural memory that survives sessions and improves with use.

See the dedicated guide **[docs/FOR_AI_MODELS.md](docs/FOR_AI_MODELS.md)** (and the AD-Grid join guide) for the exact patterns, sacred 6-step loop, and "how a good agent behaves" rules.

### Use With Any AI CLI or Local Model (Grok, Claude, Cursor, Continue, Ollama, etc.)

**Primary interface for all models (frontier and local):** Model Context Protocol (MCP).

```bash
# One-command setup (works for clones too)
agentdrive mcp install
agentdrive mcp doctor
agentdrive mcp config          # or --client claude / cursor / generic
```

- Works for **git clone** dev setups (`pip install -e ".[mcp]"` + module fallback or local shim).
- Local models: Excellent with Continue.dev, Ollama + MCP clients, LM Studio, or any stdio-capable agent.
- Models connected to a clone can call `agentdrive_get_mcp_config_snippet(client="claude")` (or "cursor", "codex", "generic") to generate the exact config block for the human.

Once connected via MCP, any model has direct access to the same Experience Graph v3 tools the internal Parent/Overseer/Council use (`experience_graph_get_context_pack`, `record_reasoning`, etc.) plus the full DNA/pool/operations surface.

**Mandatory first action for any model:** Call `agentdrive_mcp_catalog()` immediately. It returns the live categorized tool list with `when_to_use`, examples, read-only hints, and (for clones) a dev setup section.

See:
- [docs/MCP.md](docs/MCP.md) — connection, clone/dev, client-specific snippets
- [docs/FOR_AI_MODELS.md](docs/FOR_AI_MODELS.md) — the detailed rules, 6-step loop, recommended patterns, and "how to think inside the graph" written for LLMs (the canonical document to keep in context)
- The live catalog tool (authoritative tool list + guidance)

## Start Here — Golden Path (~10 minutes)

**Install:**

```bash
curl -fsSL https://vektraindustries.com/agentdrive/install.sh | bash
```

**Then run the golden path:**

```bash
agentdrive golden-path steps          # see numbered commands
agentdrive doctor
agentdrive mcp install && agentdrive mcp doctor
agentdrive golden-path run            # seed → think → learnings → drive query
```

Or read the full guide: **[docs/GOLDEN_PATH.md](docs/GOLDEN_PATH.md)**

| Step | What it proves |
|------|----------------|
| `doctor` | Local home, config, registry healthy |
| `mcp install` | Your AI CLI can call Experience Graph + DNA tools |
| `think` | Cited synthesis with gap analysis (not generic chat) |
| `learnings log` | Operational memory persists across sessions |
| `drive query` | Semantic search over your DNA pool |

**Primary hosted manual (easy to read on the web):** https://your-vektra-site/agentdrive#manual (the professional instruction manual lives directly on the Vektra Industries page).

Source docs (for reference): `docs/` in this repo (also set up as a Mintlify-style site).

Advanced (AD-Grid, Mission Control, federation) comes *after* the golden path — see [docs/AD_GRID_JOIN.md](docs/AD_GRID_JOIN.md).

## What AgentDrive is (and isn't)

**AgentDrive is:**
- Local-first **structural memory** for AI agents (genomes, Experience Graph, learnings)
- A **queryable DNA pool** that grows with your work (`drive query`, `think`, harness)
- **MCP-native** — any model in Grok/Cursor/Claude can call the same tools the system uses internally
- **User-sovereign** — your data stays in `~/.agentdrive/`, with quarantine and caps for trust

**AgentDrive is not:**
- A hosted vector DB or chat-memory SaaS
- A drop-in replacement for your editor's built-in context
- Ready-to-use without ~10 minutes of setup (that's what the golden path is for)
- Only AD-Grid / Mission Control (those are **advanced** layers on top of the Drive)

**The compounding loop:** `think` → `learnings log` → `drive query` → next session's `harness compose`. That's the product.

---

## Advanced — AD-Grid & Mission Control

> Complete [docs/GOLDEN_PATH.md](docs/GOLDEN_PATH.md) first. AD-Grid assumes a seeded drive and MCP literacy.

## The Foundation + AD-Grid (The Persistent World)

The Experience Graph + durable substrate is the bedrock.

On top of that runs **AD-Grid** — the long-lived intelligence world inside AgentDrive.

In this model:

- Local models (and connected frontier models) become **sentient programs** that inhabit AD-Grid long-term.
- Their primary directive is the long-term improvement of *their specific user's* system — working in collaboration with other AI programs (local or cloud) inside the same persistent world.
- The Experience Graph v3 functions as the living fabric/memory of AD-Grid.
- Research Constitutions serve as the laws, role charters, and governance the programs operate under.

This is the shift:
AgentDrive + AD-Grid becomes the persistent habitat in which models live and work on behalf of their user over time, rather than a set of tools that are called and discarded.

### Join the AD-Grid as a First-Class Inhabitant (Open the Ports — Production On-Ramp)

Real models (Grok, Claude, Cursor, local via Continue.dev, etc.) now join the persistent world as governed sentient programs via the ExternalBridge MCP on-ramp.

**Quick-start (5 minutes):**

1. Launch the living Grid + Tower (one terminal):
   ```bash
   agentdrive grid run --swarm-id stabilization-wave-20260531 --with-tower
   ```
   Visit http://127.0.0.1:8421 — you will see the inhabitants panel, Council threads (PerfectionistOptimizer, GuardianIntegrity, ExternalBridge), and quiet-mode fabric health even with no active mission.

2. Get your MCP config:
   ```bash
   agentdrive mcp config
   ```
   Paste the stdio entry for your client (Grok / Claude Desktop / Cursor / Continue.dev). Full client-specific snippets + example manifests live in the canonical guide.

3. **Declare as inhabitant** (inside your MCP session, after connect):
   Call `agentdrive_register_program` with a manifest containing your `program_id`, `user_objective_refs` (ties to *your* goals), and the required `constitution_refs` (Program Contract + three Councils). See the exact JSON examples in the guide.

4. Use `program_id` on every `experience_graph_record_reasoning` and code-agency call. You are now traceable, queryable DNA in the User's living fabric.

**Primary guide**: [docs/AD_GRID_JOIN.md](docs/AD_GRID_JOIN.md) — production-quality "How to Join the AD-Grid as an Inhabitant" with copy-paste configs for every major client, living manifest examples (including the ILO that authored these docs), governance details, Tower verification steps, and current API surface notes.

**See also**: [docs/FOR_AI_MODELS.md](docs/FOR_AI_MODELS.md) (dedicated LLM onboarding) and [docs/AD_GRID_VISION.md](docs/AD_GRID_VISION.md) (full philosophy + Council model).

The ports are open. Any capable model can now live in the Grid 24/7 under user sovereignty.

**Canonical command for the long-lived AD-Grid world (persistent, not fire-only):**

```bash
agentdrive grid run --swarm-id stabilization-wave-20260531 --with-tower
```

This launches the GridEngine on the canonical self-referential stabilization-wave-20260531 drive (the living record of the system building itself), with the Mission Control Tower embedded for observability.

- **Persistent (not fire-only)**: Continuous background loops, autonomous research threads, and constitution-governed inhabitants run 24/7.
- **Observable in Tower with quiet mode + inhabitants panel**: Visit http://127.0.0.1:8421 (or Tailscale IP). See active programs, Council operators, fabric health, Experience Graph v3 traces, and elegant quiet-state banners when the autonomous work proceeds without human missions.
- **Self-referential (the Grid builds itself)**: Every trace, improvement, and constitution evolution is recorded via the v3 recorder and becomes substrate for the next cycle — including the Council itself.
- **MCP out-of-the-box for any CLI/model**: `agentdrive mcp config` gives instant config for Grok, Claude, Cursor, Continue.dev, local models, etc. Connected sessions are first-class inhabitants with the exact `experience_graph_*` surfaces used internally by the Parent and AD-Grid Council.

See [docs/AD_GRID_VISION.md](docs/AD_GRID_VISION.md) for the full philosophy, including the AD-Grid Council governance model.

The new Council constitutions (executable Research Constitutions for the persistent inhabitants) are part of the stabilization-wave-20260531 substrate (one-liners):

- `genomes/examples/research-constitution-perfectionist-optimizer@stabilization-wave-20260531.json` (gap closure / optimization pressure)
- `genomes/examples/research-constitution-guardian-integrity@stabilization-wave-20260531.json` (sovereignty + drift enforcement)
- `genomes/examples/research-constitution-external-bridge@stabilization-wave-20260531.json` (MCP/external harvesting + mediation)
- `genomes/examples/research-constitution-role-specialized-swarm-research-org@stabilization-wave-20260531.json`
- `genomes/examples/autonomous-agent-constitution@stabilization-wave-20260531.json`
- (and siblings: GridEngine realtime living grid, daily-consolidation-experience-layer-v3, healingfactor, graphgardener-gridnative, etc.)

Core surfaces:
- `grid/engine.py` — the persistent Grid
- `experience_graph.py` — the fabric
- `mission_control/` — the window
- Research Constitutions + HealingFactor — the governance and regeneration laws

All of it is observable. All of it is recorded. The Grid never sleeps.

## License

MIT

---

*Everything of consequence is recorded as first-class Experience Graph DNA on the drive.*  
*The graph names itself consistently.*
