# AgentDrive Swarms — Per-Sub-Agent DNA Pools & Collective Growth

> AgentDrive is the product; the swarm primitives below are exposed by the
> underlying Agent Drive engine. See [README](../README.md).

When any AI system — Grok’s build tools, Claude Code, Codex, custom orchestrators, or your own agent code — spawns sub-agents, each child can (and should) receive its own **isolated Agent Drive Pool**.

This is the foundation of true swarm intelligence: every sub-agent grows its own private DNA (memory + reasoning patterns) while the collective can still benefit under explicit, user-controlled sharing rules.

## The Swarm DNA Vision

**DNA = Memory + Patterns** (evolutionary / inherited-trait metaphor — biology, not franchise).

- A parent agent maintains the “global” or family pool.
- Each spawned sub-agent gets a **private, persistent pool that starts empty**.
- The sub-agent’s lived experience — successful frameworks, extracted reasoning traces, tool compositions, outcomes, reflections — becomes its unique DNA.
- Improvements discovered by any sub-agent can be proposed upward (to parent) or shared laterally according to policy.
- The entire swarm compounds intelligence faster than any single agent could alone.

This is “Exo Labs for agent minds”: instead of wiring hardware, we wire lived experience across the swarm.

## How Sub-Agents Receive Their Own Pools

### Automatic Scoping (Architecture)

Every time a parent spawns a child:

1. The parent (or the spawning runtime) assigns a `swarm_id` (e.g., the parent mission or conversation ID) and a unique `subagent_id`.
2. The child is launched with environment or context:
   - `AGENTDRIVE_SWARM_ID`
   - `AGENTDRIVE_SUBAGENT_ID`
3. Agent Drive code (adapters, harness factory, or pool constructor) uses these to instantiate a scoped pool:

```python
from agentdrive.constants import get_swarm_pool_path
from agentdrive.pool.pool import Agent DrivePool
from agentdrive.pool.settings import get_effective_pool_settings

pool_dir = get_swarm_pool_path(swarm_id, subagent_id)
pool = Agent DrivePool(pool_dir=pool_dir, name=f"swarm-{swarm_id}-{subagent_id}")

settings = get_effective_pool_settings(swarm_id, subagent_id)
```

The pool directory is created on first use: `~/.agentdrive/swarms/<swarm_id>/<subagent_id>/pool/`.

- Starts empty (no contamination from parent or siblings).
- Grows only with this sub-agent’s own high-quality work.
- Persists across restarts and reboots — true long-term memory for that identity.

### Current Implementation Status

- Full path helpers and per-swarm settings storage exist (`constants.py`, `pool/settings.py`).
- `Agent DrivePool` accepts custom `pool_dir`.
- `PoolSettingsManager` supports global + per-swarm overrides.
- TUI and CLI recognize swarms (`pool_view.py`, `agentdrive pool swarms` planned).
- Full auto-wiring of `get_default_pool()` + harness to read env vars and select the correct directory is the next integration step (see `MISSION_PLAN.md`).

Until the final wiring, external integrators explicitly pass the scoped `Agent DrivePool` or `pool_dir` when creating harnesses/adapters for sub-agents.

## DNA as Memory + Patterns for Sub-Agents

Each sub-agent’s pool contains Genomes that encode:

- **Frameworks** it discovered or successfully applied.
- **Reasoning patterns** mined from its own trajectories (via `Agent DriveRunScanner` + reasoning engine: causality, contradictions, anomalies, synthesis).
- **Tool compositions** and guardrail sequences that worked for *its* tasks.
- **Self-evaluations** and micro-patterns it surfaced during reflection.

Because the sub-agent uses the **Harness** (or `RichAgentAdapter`), the pull-adapt-record loop happens automatically:

1. Pull the most relevant DNA from *its own* pool (or shared per policy).
2. Inject into prompts/reasoning/policy.
3. Execute rich work (tools, ledger, internal monologue).
4. Record outcome → auto-synthesize deltas → propose improvements back into its pool (and upward if allowed).

The sub-agent literally trains itself and its swarm siblings over time.

## Swarm Growth & Knowledge Flow

### Isolation Levels (User-Controlled)

See `docs/SETTINGS.md` for full details. High-level:

- **subagent** (default): Each child’s pool is completely private. No automatic sharing.
- **swarm**: Pools within the same `swarm_id` can read (or selectively share) DNA according to `sharing_policy`.
- **none**: All pools behave as one global pool (maximal sharing, minimal isolation).

### Sharing Policies

- `none`, `read`, `selective` (default), `full`
- Combined with `allow_upward_proposals` (sub-agents may propose improvements to parent/family pools).

### Knowledge Flow Patterns

- **Bottom-up**: Sub-agent discovers a breakthrough → proposes delta to parent pool.
- **Lateral**: Two sub-agents in same swarm exchange high-value genomes under selective policy.
- **Top-down**: Parent injects proven family DNA into new children at spawn time (via initial ingest or prompt injection).
- **Cross-swarm**: Explicit user-mediated or policy-gated merges (future registry federation).

The TUI Pool view provides a first-class “Swarm Overview” showing every sub-agent pool, its growth metrics, top contributors, and one-click switching.

## Example Swarm Lifecycle

1. User (or Grok) starts a complex mission: “Refactor the payment service and write full security + reliability analysis.”
2. Grok spawns 4 sub-agents with distinct roles, each receiving `swarm_id="mission-xyz-2026-05"` and unique subagent ids.
3. Each sub-agent:
   - Gets empty private pool under `~/.agentdrive/swarms/mission-xyz-2026-05/<sub-id>/pool/`
   - Begins work using Harness + RichAgentAdapter (or equivalent for its model).
   - Discovers specialized patterns (e.g., one finds a novel contradiction-detection heuristic for financial code).
4. High-quality sub-agent runs auto-ingest into its private pool and, if policy allows, propose upward.
5. Parent (or user via TUI) reviews proposals, merges the best into the family pool.
6. Future sub-agents in the same or related swarms inherit the improved DNA.
7. User can at any moment:
   - Inspect any sub-pool in TUI
   - Change isolation/sharing for the whole swarm or one sub-agent
   - Export a sub-agent’s DNA as a new published Genome

## Benefits for Power Users & Developers

- **No more “amnesia” across sub-agents**: Each keeps its hard-won expertise.
- **Controlled compounding**: You decide how much cross-pollination occurs.
- **Auditability**: Full ingest logs + provenance in every Genome.
- **Portability**: Move `~/.agentdrive/swarms/` between machines; sub-agents resume with their DNA intact.
- **Multi-model swarms**: A Grok-spawned sub-agent, a Claude sub-agent, and a local Codex worker can all participate in the same swarm family using their respective adapters.

## Getting Started with Swarms (Quickstart)

See the dedicated quickstart in the root README.md (“Getting Started with Swarms”).

Minimal manual example (until auto-env wiring is complete):

```python
import os
from agentdrive import Harness, get_swarm_pool_path
from agentdrive.pool.pool import Agent DrivePool
from agentdrive.pool.settings import get_effective_pool_settings

swarm_id = os.environ.get("AGENTDRIVE_SWARM_ID", "demo-swarm-001")
sub_id   = os.environ.get("AGENTDRIVE_SUBAGENT_ID", "worker-1")

pool_dir = get_swarm_pool_path(swarm_id, sub_id)
pool = Agent DrivePool(pool_dir=pool_dir)

settings = get_effective_pool_settings(swarm_id)
print("Effective settings for this sub-agent:", settings)

harness = Harness(agent_id=f"{swarm_id}:{sub_id}", pool=pool)
# ... use harness exactly as in single-pool usage
```

Instruct any parent agent:

> “When you spawn sub-agents for this mission, assign each a unique AGENTDRIVE_SUBAGENT_ID under swarm_id ‘payment-refactor-2026’, attach the Harness with the corresponding scoped pool, and set isolation_level=subagent with selective upward proposals.”

The Agent Drive system makes swarm-scale, self-improving, user-sovereign agent collectives practical today.

---

**Agent Drive Swarms turn every spawned child from a disposable worker into a lifelong learning citizen of your personal intelligence ecosystem.**
