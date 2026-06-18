# AgentDrive Architecture (Overview)

**AgentDrive** is a local-first platform that gives AI agents structural, compounding memory — not just retrieval.

For the capability funnel, see **`docs/CAPABILITY_FUNNEL.md`**.

For model onboarding rules, see **`docs/FOR_AI_MODELS.md`**.

---

## Core subsystems

| Layer | Location | Purpose |
|-------|----------|---------|
| **Drive engine** | `src/agentdrive/drive/` | Swarm-scoped persistence, ingest, query |
| **Operations registry** | `src/agentdrive/operations/registry.py` | Canonical MCP/CLI surface + auto-learning |
| **Experience Graph** | `src/agentdrive/evolution/experience_graph.py` | TypedEdges, cycles, fabric reasoning |
| **Growth merge** | `src/agentdrive/learning/growth_merge.py` | Cross-surface pattern compounding |
| **Memory Bank** | `src/agentdrive/memory/` | Deep AI databank (`memories.jsonl`, relations) |
| **Framework skills** | `src/agentdrive/learning/framework_skills.py` | Route learned/fused playbooks per task |
| **Multiverse cognition** | `src/agentdrive/cognition/` | Parallel timelines → governed collapse |
| **Skills + learning** | `src/agentdrive/skills/`, `learning/auto_absorb.py` | Distillation, inheritance, fusion |
| **Codebase mirrors** | `src/agentdrive/codebase/` | Pattern recognition + mimicry |
| **Golden path** | `golden_path.py` | Install → doctor → MCP → verify |
| **MCP adapter** | `adapters/mcp_server.py` | Any-model tool surface |

**Naming:** Product surface is **Drive** (`AgentDrive`, `get_swarm_drive_path`). The YAML config key `pool:` and some method names (`get_pool_stats`) are historical — they refer to the same engine under `src/agentdrive/drive/`.

---

## Capability funnel

```
Observe / Decide
       ↓
Experience Graph
       ↓
Growth Merge
       ↓
Memory Bank
       ↓
Skills (learned + fused)
       ↓
Genomes / DNA
```

---

## Data layout

```
~/.agentdrive/
├── config.yaml
├── genomes/                         # Global genome registry
├── skills/                          # User + inherited learned skills
├── codebase-patterns/<project>/     # Mirror-neuron observations
├── learnings/                       # Operational JSONL logs
└── swarms/<swarm_id>/
    └── drive/                       # Shared per-swarm Drive (v2)
        ├── ingest.jsonl
        ├── genomes/
        ├── memory_bank/             # memories.jsonl + relations.sqlite3
        └── meta_evolution/          # Experience Graph + multiverse sessions
```

**Swarm model (v2 / Milestone 2a):** All sub-agents in a swarm share one Drive at `swarms/<swarm_id>/drive/`. Sub-agents namespace writes via Genome author tagging (`sub:<id>`), not separate directories. MCP `create_scoped_pool()` and `SwarmDriveManager` use the same path.

Legacy v1 trees (`swarms/<id>/<subagent>/pool/`) may exist on disk from older sessions; new provisioning always uses the shared `drive/` layout.

---

## Integration surfaces

- **MCP** — primary for frontier/local models (`agentdrive-mcp`)
- **CLI / REPL** — `agentdrive` + `cli_surface.py` shared handlers
- **TUI** — default operator shell when no `--cli`
- **Harness** — in-process outcome capture for adapters

See `docs/MCP.md`, `docs/INTEGRATION.md`, `docs/GOLDEN_PATH.md`, `docs/MEMORY_BANK.md`.

---

## Archived / legacy (do not extend)

- `archive/ui-webpage-legacy-*` — superseded web templates
- `archive/development-history/` — stabilization sprint reports
- `src/agentdrive/backup/` — still referenced by tests; migrate before removal

See `CHANGELOG.md` for recent work.