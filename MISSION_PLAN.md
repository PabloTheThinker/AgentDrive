# SAVANT MISSION 2026 — Swarm DNA Pool System

**Goal**: Make Savant the independent, user-sovereign, production-grade framework for **Agent DNA Pools** — especially for agent swarms.

Every time any model (Grok, Claude, Codex, custom) spawns sub-agents, each sub-agent automatically gets its own isolated, persistent Savant Pool (DNA = memory + patterns). Pools start empty. The user is always in full control. Sub-agents learn, adapt, train, and improve both individually and as a collective.

The system must be:
- 100% Savant-branded (no external-brand pollution in core identity)
- Fully documented
- Have a first-class TUI for the Pool + swarms
- Support adapters/MCP so any model can connect
- Have rich user settings + control

## Current Status (as of latest swarm run)

- Core Genome + Pool + Harness + Reasoning primitives: strong
- TUI (including new PoolView skeleton): advanced
- CLI for pool: good
- Automatic feedback loop: working
- Smart relevance: working
- Swarm isolation helpers: started
- Branding cleanup: in progress
- Adapters: skeleton needed
- Docs: started

## Coordinated Work Packages (Swarm + Main Thread)

**Team Roles** (subagents + main Grok thread):

1. **Branding Lead** (subagent)
   - Finish renaming all remaining external-brand references in source, docs, examples, tests
   - Update class names, file names, docstrings, __init__.py exports
   - Goal: pure Savant identity in user-facing surfaces and core code

2. **Swarm Pool Core** (subagent)
   - Implement full per-swarm / per-subagent pool isolation in `pool/pool.py` + registry
   - Add `SavantSwarmPoolManager`
   - Support `swarm_id` + `subagent_id` scoping with automatic directory creation
   - Implement sharing policies (none / read / selective / full)
   - Wire into `get_default_pool()` and harness so spawned sub-agents automatically get their own pool

3. **Pool TUI Specialist** (subagent)
   - Complete `tui/views/pool_view.py` with real interactive features:
     - Browse global + all swarms
     - Query with explanations
     - Ingest / evolve / merge
     - Settings editor (user control panel)
     - Swarm browser + switcher
   - Wire fully into `app.py` dispatch + completer + help

4. **Documentation Team** (subagent or parallel)
   - `docs/POOL.md` — The Savant Pool
   - `docs/SWARM.md` — Swarm DNA & Sub-Agent Pools
   - `docs/INTEGRATION.md` — How Grok, Claude Code, Codex, etc. connect
   - `docs/SETTINGS.md` — User control & configuration
   - Overhaul root README + VISION with clean Savant voice
   - Add quickstart for "Spawn a swarm with Savant Pools"

5. **Adapters & Multi-Model Bridge** (subagent)
   - Create `src/savant/adapters/` package
   - Base `SavantAdapter` protocol
   - MCP server for pool access (stdio + HTTP)
   - Grok Build System adapter (tie into how Grok spawns subagents via spawn_subagent)
   - Example adapters for Claude Code and Codex
   - Show how any model can be instructed: "Attach to your Savant Pool for this swarm"

6. **Settings & Control** (subagent)
   - Expand config system for all pool/swarm behavior
   - CLI + TUI settings editor
   - Make it easy for the user (or any AI the user is talking to) to change pool rules

**Main Thread (Grok)** responsibilities:
- Overall architecture decisions
- Glue code & integration
- Final review of all pieces
- End-to-end demo (multi-agent swarm with private pools)
- Ensure everything is user-controllable and starts empty

## Success Criteria

- User runs `savant tui`, types `pool`, sees a beautiful dedicated view with their swarms
- When Grok (or any model) spawns sub-agents, each gets `~/.agentdrive/swarms/<swarm_id>/<subagent_id>/pool/`
- User can fully configure isolation/sharing/auto-rules via CLI/TUI or by telling the AI
- Clean, professional Savant-only language everywhere
- Comprehensive docs that a new user can follow to use with Grok build system + other models
- Adapters exist so Claude Code, Codex, etc. can participate

**Let's work as one coordinated team.** Subagents take clear, non-overlapping missions. Main thread coordinates, reviews, and ships.

Current date in mission: 2026-05-23

Mission owner: Pablo + Grok + Swarm
