# AgentDrive Swarms — Shared Drive & Collective Growth

> **Terminology:** **Drive** is the product primitive (`AgentDrive`, `get_swarm_drive_path`).
> YAML config may still use the key `pool:` — same engine under `agentdrive.drive`.
> See `docs/CAPABILITY_FUNNEL.md`.

When any AI system spawns sub-agents, all children in the same swarm share one **persistent AgentDrive** at:

```
~/.agentdrive/swarms/<swarm_id>/drive/
```

This is sibling learning (v2 / Milestone 2a): sub-agents compound intelligence together while namespacing contributions via Genome author tagging.

---

## Shared swarm Drive (v2)

| Concept | Behavior |
|---------|----------|
| **Path** | `swarms/<swarm_id>/drive/` — one per swarm, not per sub-agent |
| **Memory Bank** | `drive/memory_bank/memories.jsonl` — grows from auto-learning |
| **Experience Graph** | `drive/meta_evolution/` — structural traces, multiverse sessions |
| **Attribution** | `ingest(subagent_id=...)` stamps `sub:<id>` on Genome authors |
| **Query** | `drive.writers()`, `drive.genomes_by_subagent(sid)` |

MCP `create_scoped_pool()`, `get_default_drive()`, and `SwarmDriveManager.get_or_create_pool()` all resolve to this path.

---

## Quickstart

```python
import os
from agentdrive import Harness
from agentdrive.drive.swarm_manager import get_swarm_drive_manager
from agentdrive.drive.settings import get_effective_drive_settings

swarm_id = os.environ.get("AGENTDRIVE_SWARM_ID", "demo-swarm-001")
sub_id = os.environ.get("AGENTDRIVE_SUBAGENT_ID", "worker-1")

mgr = get_swarm_drive_manager()
drive = mgr.get_or_create_pool(swarm_id=swarm_id, subagent_id=sub_id)

settings = get_effective_drive_settings(swarm_id=swarm_id, subagent_id=sub_id)
print("Effective settings:", settings)

harness = Harness(agent_id=f"{swarm_id}:{sub_id}", pool=drive)
```

See `examples/03_swarm.py` for a full sibling-learning demo.

---

## Isolation & sharing

Configured via `SwarmDrivePolicy` and `docs/SETTINGS.md`:

- **swarm** (default): Shared Drive; siblings read each other's work; writes tagged by author.
- **subagent**: Opt-in air-gap — construct `AgentDrive(drive_path=...)` with a custom path for adversarial children.
- **Sharing policies:** `none`, `read`, `selective`, `full` + `allow_upward_proposals`.

---

## Knowledge flow

- **Bottom-up:** Sub-agent proposes high-signal genomes to parent via promotion/inheritance.
- **Lateral:** Siblings query the same Drive; filter by `genomes_by_subagent()`.
- **Top-down:** Parent seeds genomes into swarm Drive before spawn.
- **Cross-swarm:** Peer federation + quarantine gate (`docs/INTEGRATION.md`).

---

## Lifecycle example

1. Parent starts mission with `swarm_id="mission-xyz"`.
2. Spawns workers with unique `AGENTDRIVE_SUBAGENT_ID` values.
3. Each worker calls `get_or_create_pool("mission-xyz", sub_id)` — same Drive instance.
4. Auto-learning grows Memory Bank + learned skills on the shared swarm.
5. Parent reviews proposals, promotes stable playbooks to genomes.

---

## Legacy v1 paths

Older sessions may have `swarms/<id>/<subagent>/pool/` trees on disk. New provisioning always uses `swarms/<id>/drive/`. Migration is optional — legacy trees are not read by current code.

---

**AgentDrive swarms turn every spawned child from a disposable worker into a contributor to a shared, compounding intelligence substrate.**