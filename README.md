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

## Start Here

```bash
# Clone
git clone https://github.com/PabloTheThinker/AgentDrive.git
cd AgentDrive

# Run the Mission Control Tower
agentdrive mission

# Or attach an autonomous agent to the live stabilization drive
# (see examples/autonomous_experience_graph_agent_loop.py)
```

The stabilization-wave-20260531 drive contains the living record of the system being used to build itself.

## The Foundation

The Experience Graph is the evolutionary layer on top of a proven durable substrate: three-tier drives, content-addressed genomes, capability-based access, quarantine, and lineage. Everything remains local-first and privacy-absolute.

The real work — the constitutions, autonomous runs, coherence lifts, and the graph itself — lives on the `stabilization-wave-20260531` drive.

Core surfaces live in:
- `experience_graph.py` — recorder and graph
- `mcp_server.py` — universal interface
- `integrated_real_time_evolution_system.py` — the 6-step engine
- `mission_control/` — Tower and TUI

All of it is observable. All of it is recorded.

## License

MIT

---

*Everything of consequence is recorded as first-class Experience Graph DNA on the drive.*  
*The graph names itself consistently.*
