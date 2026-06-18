# Agent Drive Swarm Pool Architecture — Professional Design

This document captures the **professional, high-grade** architecture for the Agent Drive Swarm DNA Pool system.

## Core Philosophy (Professional Subagent Excellence)

Mature agent systems handle sub-agents with exceptional rigor:
- Explicit blocked tools (`DELEGATE_BLOCKED_TOOLS`)
- Per-child isolated context (own `task_id`, own terminal session, fresh conversation)
- ThreadPoolExecutor + initializer for safe callbacks
- Config-driven approval behavior (`delegation.subagent_auto_approve`)
- Clear depth limits and provenance
- Parent only ever sees the summary, never the child's raw intermediate state
- Global observability + control (pause, interrupt, status)

Agent Drive applies the exact same level of care to **DNA (memory + patterns)** instead of just tool execution.

## Key Components

### 1. SwarmDrivePolicy (the "blocked tools" equivalent)
Located in `swarm_policy.py`.

Defines what DNA can flow where:
- `isolation_level`
- `parent_to_child`, `child_to_parent`, `sibling_sharing`
- `min_quality_for_sharing`
- `blocked_categories`
- `max_swarm_depth`

Safe by default, explicitly relaxable by the user.

### 2. SwarmDriveManager (the active subagents registry)
Located in `swarm_manager.py`.

- Thread-safe registry of swarm members → shared `AgentDrive` per `swarm_id`
- Automatic provisioning at `~/.agentdrive/swarms/<swarm_id>/drive/` (v2 shared Drive)
- `get_or_create_pool(...)` — call when spawning any sub-agent; siblings share one instance
- `propose_dna_merge(...)` for controlled sharing
- Pause / resume capability at the swarm level

### 3. AgentDrive + Harness Integration
- `Harness` now understands swarm context (via constants or explicit `swarm_id`/`subagent_id`)
- When a harness is created inside a sub-agent, it automatically talks to the right isolated pool
- `record_outcome()` feeds improvements back into that specific pool (and optionally upward according to policy)

### 4. Settings & User Control
`settings.py` + `DriveSettingsManager`

Every policy is overridable by the owner:
- Via `~/.agentdrive/config.yaml`
- Via CLI/TUI
- Via natural language instruction to any connected AI ("For this swarm, set isolation_level to swarm and allow selective sibling sharing")

### 5. Provenance & Audit (high-grade)
Every genome that crosses a pool boundary records:
- Source swarm + sub-agent
- Policy that allowed the transfer
- Quality score at time of transfer
- Full lineage chain

This gives the user complete visibility and control.

## How Spawning a Sub-Agent Looks (Professional Flow)

```python
# Inside any orchestrator (Grok build system, custom agent, etc.)
swarm_id = current_swarm_id or generate_swarm_id()
subagent_id = f"sub-{uuid.uuid4().hex[:8]}"

# 1. Get (or create) the child's isolated DNA pool — this is the key line
child_pool = get_swarm_drive_manager().get_or_create_pool(
    swarm_id=swarm_id,
    subagent_id=subagent_id,
    policy=user_or_config_policy
)

# 2. Create the child agent with its own harness pointing at that pool
child_harness = Harness(
    agent_id=subagent_id,
    pool=child_pool,           # ← private DNA from birth
)

# 3. Spawn the actual sub-agent (whatever mechanism the host uses)
child_agent = spawn_subagent(
    task=delegated_task,
    harness=child_harness,     # ← the child now has its own living memory
    ...
)
```

The child starts with an **empty** pool and grows its own unique DNA. The parent can see high-level summaries or selected DNA according to the active `SwarmDrivePolicy`.

## Why This Is High-Grade Professional Quality

- **Predictable**: You always know which pool any piece of code is talking to.
- **Safe by default**: Sub-agents cannot accidentally pollute the parent's DNA.
- **User in control**: Every policy is visible and changeable.
- **Observable**: Active swarms, policies, and DNA provenance are queryable.
- **Composable**: Parent and children can still benefit from each other when the user allows it.
- **Professional error handling & logging** (matching high standards).

This is the foundation that lets Agent Drive turn "I spawned 7 sub-agents" into "I spawned 7 sub-agents that each developed deep, reusable expertise and the swarm as a whole became significantly smarter."

The implementation in `swarm_manager.py` + `swarm_policy.py` + `settings.py` is the professional heart of this system.
