# AgentDrive Integration Guide — Connecting Grok, Claude Code, Codex, and Any Model

> AgentDrive is the public product. The historical Agent Drive engine wording remains
> in a few Python class names and older design notes; new integrations should use
> the `agentdrive` package and CLI.

AgentDrive is designed as a **neutral, model-agnostic evolutionary layer**. Any agent runtime that can spawn sub-agents or execute work can participate in Drive-backed pools by using one of the provided adapters or the lightweight harness.

The goal: every time you tell Grok “use sub-agents for this task”, Claude Code “break this down across workers”, or Codex “run this analysis in parallel”, each child automatically receives its own living DNA pool.

## Core Integration Points

### 1. Python-Native (Recommended for Full Power)

Any Python-based agent or sub-agent can directly use:

- `Harness` — the simplest participation wrapper (pull DNA → adapt → record).
- `RichAgentAdapter` / `ExternalWorkerAdapter` — canonical reference implementation showing a rich, tool-using, trajectory-emitting agent.
- `AgentDrive`, `DriveQuery`, and `GenomeRegistry` for direct control.
- `AgentDriveRunScanner` (and custom scanners) to turn raw trajectories into new Genomes.

See:
- `src/agentdrive/harness/harness.py`
- `src/agentdrive/workers/rich_agent_adapter.py` (runnable demo/reference worker)
- `examples/01_hello_drive.py` (core ingest + Harness)
- `examples/02_dedup.py` (content-addressed dedup)
- `examples/03_swarm.py` (shared Swarm Drives)
- `examples/04_quarantine_workflow.py` (mandatory foreign-DNA gate + LineageImmuneRule)
- `examples/05_lineage_dna_grants.py` (DNADrive, grants, LineageImmuneSystem, LineageDNAEvolver)
- `examples/11_high_continuity_bridge_demo.py` (GrokPatternLineageBridge + activate_as_ilo_conductor for high-continuity nodes)

**Minimal integration for a sub-agent**:

```python
from agentdrive import Harness, create_harness

# In your sub-agent entrypoint
harness = create_harness(agent_id=os.environ.get("SUBAGENT_ID", "unknown"))

with harness.task_context(user_task):
    dna = harness.pull_relevant_dna()
    prompt = harness.inject_into_context(your_base_prompt)
    result = your_rich_execution_loop(prompt)   # tools, ledger, reflection...
    harness.record_outcome(result)              # feeds the pool
```

### 2. Environment-Driven Swarm Scoping

Parent runtimes pass two environment variables (or context) when launching children:

- `AGENTDRIVE_SWARM_ID` — legacy-compatible name that groups related sub-agents (e.g. one mission or conversation thread)
- `AGENTDRIVE_SUBAGENT_ID` — legacy-compatible name for this child (its private pool lives here)

AgentDrive helpers (`get_swarm_pool_path`, `get_effective_pool_settings`) automatically create and select the correct isolated pool directory and policy set.

See `docs/SWARM.md` and `src/agentdrive/constants.py`.

### 3. Adapter Pattern for External Runtimes

AgentDrive defines clean protocols:

- `AgentAdapter` / `Worker` (in `src/agentdrive/workers/base.py`) — for orchestrators that want to dispatch frameworks to external agents.
- `contribute_genome(run_data)` — feed a completed run back for scanning and ingestion.
- `as_worker()` — turn the external agent into a dispatch target.

Current reference:
- `ExternalAgentAdapter` — for external-powered processes (subprocess, ACP, or in-process).
- `RichAgentAdapter` — full harness + trajectory style (the "canonical rich worker").

Future adapters will live under `src/agentdrive/adapters/`.

### 4. MCP, stdio, HTTP, and Web Bridges

AgentDrive exposes its pool and harness capabilities via standard interfaces so non-Python models can call them as tools:

- **MCP Server** — Model Context Protocol tool server. Planned surface for pool query, harness record, settings, and Drive operations.
- **stdio / JSON-RPC** — Lightweight for local subprocess integration.
- **HTTP / SSE** — For remote or containerized sub-agents.
- **FastAPI web app** — `agentdrive web` starts the new operator surface at `http://127.0.0.1:8421`. Auth/dashboard scaffolding exists now; deeper Drive/Swarms/DNA/Snapshots/Capabilities pages are Phase 2+.

Until the dedicated MCP package is complete, any model that can shell out or call Python can invoke `agentdrive drive query "..."` and AgentDrive Python entrypoints.

Instruct the model:

> “You have access to the AgentDrive CLI and Python API. Use `agentdrive drive query` and the harness to participate in the user’s Drive for this swarm.”

### 5. Grok Build System Integration (spawn_subagent pattern)

Grok’s build / agent orchestration already supports spawning sub-agents (via `spawn_subagent` or equivalent internal mechanism).

**Recommended pattern**:

1. When the parent decides to spawn, generate a `swarm_id` (stable per top-level mission) and per-child `subagent_id`.
2. Launch the child process / container / sandbox with the two `AGENTDRIVE_*` env vars.
3. In the child’s bootstrap (or via injected system prompt + tool), ensure it:
   - Imports/uses `Harness` (if Python) **or**
   - Is told “you are participating in AgentDrive for swarm X; use the provided adapter / CLI / MCP tools to pull and record DNA”.
4. On child completion, the parent (or the child itself via harness) can trigger scanners on exported trajectories.

Because AgentDrive pools are just directories + Python objects, even a non-Python Grok sub-agent can participate by calling the AgentDrive CLI or a thin MCP wrapper.

User instruction example to Grok:

> “For all sub-agents you spawn on this task, set AGENTDRIVE_SWARM_ID to ‘user-mission-42’, give each a distinct SUBAGENT_ID, attach the Harness (or equivalent), and respect the Drive settings I have in ~/.agentdrive/config.yaml.”

### 6. Claude Code, Cursor, Windsurf, Codex, and Other IDE/Agent Runtimes

Same principles apply:

- These systems have “agent” or “sub-task” modes that can run custom code or call external tools.
- Provide a thin wrapper script or MCP server that the runtime can invoke.
- Use natural language: “Always use AgentDrive DNA injection and recording for every sub-task you create.”

### 7. Optional Deeper Lineage-Enhanced Components (Advanced)

For operators or developers who want stronger evolutionary and immune behavior on top of the base AgentDrive model, the following first-class (but opt-in) modules are available. They are **fully native** — no external Lineage Engine required — and are now exported at the top level:

```python
from agentdrive import (
    Quarantine, DNADrive, LineageImmuneSystem, ThreatLevel,
    LineageDNAEvolver, DNACycleResult,
    GrantStore, LineageShareGrant, pull_via_grant,
    ReconciliationRunner,
)
```

See the excellent runnable demos (and the full progressive guide):
- `examples/04_quarantine_workflow.py` — complete submit/validate/approve with LineageImmuneRule participating
- `examples/05_lineage_dna_grants.py` — DNADrive publish/pull, signed grants + pull_via_grant, adaptive immune assessment + memory, full Research/Evaluate/Evolve cycles, Harness DNA methods
- `examples/11_high_continuity_bridge_demo.py` — GrokPatternLineageBridge activation, custom pattern (reasoning/speech/lineage) → Genome publish, consume, safe evolver with brain_path (the dedicated ILO/Conductor power-user path)
- `docs/development/ONBOARDING_AND_EXAMPLES.md` — detailed onboarding history (see `docs/INTEGRATION.md` and examples for current guidance)

Key surfaces:
- `agentdrive.quarantine` + `LineageImmuneRule` (registered by default) — the **mandatory** gate. Every peer pull, grant result, and inheritance manifest lands here.
- `DNADrive` + `Ancestry` — forward-only ancestral memory with closure-table queries.
- `GrantStore` / `LineageShareGrant` + `pull_via_grant` — signed, scoped, TTL-bounded, quota-protected sideways (cousin) sharing. Results must still route through Quarantine.
- `LineageImmuneSystem` — adaptive threat discrimination and memory used by Quarantine/Reconciliation.
- `LineageDNAEvolver` — provides a Research→Evaluate→Evolve skeleton for any Genome using AgentDrive-native sources (with graceful degradation). See source for exact implemented depth.
- `ReconciliationRunner` — background delta scanner that emits `ReconciliationDelta` / `ReconciliationCompleted` events (powers live UIs).

These are production surfaces used by the CLI (`agentdrive quarantine`, `agentdrive reconcile`), TUI ribbons, web dashboard, and Harness. They are the "new lineage-enhanced features" referenced in the project vision.

Full details and the exact "what is working today" behavior are in the two example files above and in `docs/AGENTDRIVE-V2-INHERITANCE.md`.

Example wrapper (invoked by Claude Code’s “run in agent”):

```bash
#!/bin/bash
export AGENTDRIVE_SWARM_ID="${CLAUDE_MISSION_ID:-default}"
export AGENTDRIVE_SUBAGENT_ID="${CLAUDE_SUBTASK_ID:-$(uuidgen)}"
python -m agentdrive.workers.rich_agent_adapter --task "$*"
```

### 7. Custom Models & Local LLMs (LM Studio, Ollama, etc.)

- Run your agent loop in Python and use the harness directly (zero friction).
- Or expose AgentDrive as a set of local tools via OpenAI-compatible function calling.
- The `RichAgentAdapter` demo is deliberately model-agnostic — replace the simulated work with your actual model calls.

## Configuration for Integrations

All integration behavior is controlled in `~/.agentdrive/config.yaml`:

```yaml
pool:
  global:
    isolation_level: subagent
    auto_ingest_on_success: true
    sharing_policy: selective
  swarms:
    my-mission-123:
      isolation_level: swarm
      sharing_policy: read
```

See `docs/SETTINGS.md`.

The `as_user_instructions()` method on `PoolSettingsManager` returns ready-to-paste guidance any model can be given so it respects user sovereignty.

## Best Practices for Clean Integration

1. **Always scope by swarm + subagent** when spawning — prevents cross-contamination.
2. **Use the harness context manager** — guarantees the full pull-record loop.
3. **Export rich trajectories** — the more structure (observations, claims, reflections, tool calls), the better the scanners can extract high-quality DNA.
4. **Let the user (or parent) decide policies** — never hard-code sharing rules.
5. **Version everything** — every Genome carries content hash + full lineage.
6. **Surface AgentDrive in the UI** — the TUI/CLI and `agentdrive doctor` make the integration visible and debuggable.

## Current Status & Roadmap

**Implemented today**:
- Full Python harness + adapters + scanners
- Per-swarm directory + settings infrastructure
- CLI + TUI surfaces
- Relevance engine powered by reasoning primitives
- Runnable reference workers

**In active development**:
- Auto env-var detection in `get_default_pool()` / harness factories
- Dedicated MCP server + stdio bridge
- FastAPI web Phase 2+ pages beyond auth/dashboard shell
- Grok-specific spawn_subagent hook
- First-class Claude Code / Codex example adapters
- TUI swarm browser with live metrics

You can start using AgentDrive with any model **right now** by following the Python or CLI patterns above. The architecture is deliberately forward-compatible.

## Example End-to-End Flow (Grok + 3 Sub-Agents)

1. User: “Use a swarm of sub-agents to produce a full security + performance review of the new payments service.”
2. Grok creates `swarm_id="payments-review-20260523"`, spawns `analyst-1`, `reviewer-2`, `synthesizer-3` with proper env vars.
3. Each sub-agent bootstraps a `Harness` with its scoped pool.
4. They pull relevant family DNA (security genomes, architecture patterns) at start.
5. During work they discover new patterns and record them.
6. On completion, high-value deltas are proposed upward.
7. Grok (or user in TUI) reviews, merges the best, and the family pool is now smarter for the next payments-related mission.

This is how agent intelligence stops being ephemeral and starts compounding under your control.

---

**AgentDrive turns every model’s sub-agent capability into a participant in your personal, ever-evolving intelligence collective.**
