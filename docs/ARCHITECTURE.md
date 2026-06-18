# AgentDrive Architecture (Overview)

**AgentDrive** is a local-first platform that gives AI agents structural, compounding memory — not just retrieval.

For the single capability funnel (Observe → Graph → Skills → Genomes), see **`docs/CAPABILITY_FUNNEL.md`**.

For model onboarding rules, see **`docs/FOR_AI_MODELS.md`**.

---

## Core subsystems (what stays)

| Layer | Location | Purpose |
|-------|----------|---------|
| **Drive engine** | `src/agentdrive/drive/` | Swarm-scoped persistence, ingest, query |
| **Operations registry** | `src/agentdrive/operations/registry.py` | Canonical MCP/CLI surface + auto-learning |
| **Experience Graph** | `src/agentdrive/evolution/experience_graph.py` | TypedEdges, cycles, fabric reasoning |
| **Multiverse cognition** | `src/agentdrive/cognition/` | Parallel timelines → governed collapse |
| **Memory Bank** | `src/agentdrive/memory/` | Deep AI databank + graph memory triage |
| **Skills + learning** | `src/agentdrive/skills/`, `learning/auto_absorb.py` | Distillation, inheritance, auto-absorb, fusion |
| **Codebase mirrors** | `src/agentdrive/codebase/` | Pattern recognition + mimicry |
| **Golden path** | `golden_path.py` | Install → doctor → MCP → verify |
| **Event bus + sessions** | `events.py`, `session_events.py` | TUI/CLI observability |
| **MCP adapter** | `adapters/mcp_server.py` | Any-model tool surface |

Historical module names (`pool/`, `AgentDrivePool`) remain in code; product docs use **Drive**.

---

## Data layout

```
~/.agentdrive/
├── config.yaml
├── genomes/                    # Global genome registry
├── swarms/<swarm_id>/
│   ├── drive/                  # Graph + multiverse + meta_evolution
│   │   └── memory_bank/        # Deep AI memory databank (memories.jsonl)
│   └── <subagent_id>/pool/     # Isolated sub-agent DNA (optional)
├── codebase-patterns/<project>/  # Mirror-neuron observations
└── agents/<agent>/sessions/    # Chat session event logs
```

---

## Integration surfaces

- **MCP** — primary for frontier/local models (`agentdrive-mcp`)
- **CLI / REPL** — `agentdrive` + `cli_surface.py` shared handlers
- **TUI** — default operator shell when no `--cli`
- **Harness** — in-process outcome capture for adapters

See `docs/MCP.md`, `docs/INTEGRATION.md`, `docs/GOLDEN_PATH.md`.

---

## Archived / legacy (do not extend)

- `archive/ui-webpage-legacy-*` — superseded web templates
- `archive/development-history/` — stabilization sprint reports, stale `BUILD_STATUS.md` / `MISSION_PLAN.md`
- `src/agentdrive/backup/` — still referenced by tests; migrate before removal

---

## Consolidation direction

1. One capability funnel (documented in `CAPABILITY_FUNNEL.md`)
2. Pool → Drive naming in user-facing docs (code rename is incremental)
3. Split `cli.py` / `mcp_server.py` into focused modules
4. Expand multiverse + graph test coverage

See `CHANGELOG.md` Unreleased for recent work.