# AgentDrive

<p align="center">
  <img src="assets/agentdrive-hero-1920x1080.jpg" alt="AgentDrive — Structural Experience Graph for Autonomous Agents" width="100%">
</p>

**Intelligence that remembers the shape of what it has become.**

AgentDrive is a structural memory system for agents that must grow from their own decisions. Not a vector store. Not a document dump. A living graph where every connection, every hesitation, every breakthrough is recorded with provenance and weight — and can be reasoned over directly by the agents themselves.

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

## Autonomy That Compounds

The intended use is non-stop autonomous agents running on local models.

Give an agent a Research Constitution and a connection to the Experience Graph. Let it run. It will gather structural context, make decisions it can explain, write the reasoning back into the graph, and get measurably sharper over time.

No cloud dependency. No stateless tool-calling loops. Just continuous, grounded work that leaves a richer substrate for the next cycle.

This is what local models have been missing: a memory they can actually think with.

### Use With Any AI CLI (Grok, Claude, Cursor, Local Models)

AgentDrive speaks the Model Context Protocol natively.

```bash
agentdrive mcp install   # one command: pip [mcp] + write client configs
agentdrive mcp doctor    # verify 25+ tools + resolved launcher
agentdrive mcp config    # show paste-ready snippets for your machine
```

Works after `pip install agentdrive[mcp]`, the root `install.sh`, or `git clone` + `pip install -e ".[mcp]"`. The config resolver picks the right binary or Python module fallback automatically.

Once connected, your model gets the full Experience Graph v3 surfaces (the same ones used internally by the Parent and Overseer) plus DNA tools — complete with gbrain scoring and provenance.

See [docs/MCP.md](docs/MCP.md) for connection details and [docs/FOR_AI_MODELS.md](docs/FOR_AI_MODELS.md) for the dedicated onboarding guide written specifically for AI models. The latter is the single best document to give any LLM when you want it to deeply understand and use the system effectively from the start.

## Start Here

**One-liner (recommended):**

```bash
curl -fsSL https://vektraindustries.com/agentdrive/install.sh | bash
```

With options:

```bash
curl -fsSL https://vektraindustries.com/agentdrive/install.sh | bash -s -- --dev
```

After install:

```bash
agentdrive doctor
agentdrive mcp config
```

See [docs/MCP.md](docs/MCP.md) for connection details across Grok / Claude / Cursor / Continue.dev, and [docs/FOR_AI_MODELS.md](docs/FOR_AI_MODELS.md) for the dedicated LLM onboarding guide.

See [docs/MCP.md](docs/MCP.md) for the exact flow for your client.

The stabilization-wave-20260531 drive contains the living record of the system being used to build itself.

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
