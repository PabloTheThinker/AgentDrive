# AgentDrive Capability Funnel

**Single mental model for how intelligence compounds in AgentDrive.**

Public product: **AgentDrive**. Internal engine modules still use historical names (`pool/`, `AgentDrivePool`) — treat **Drive** as the product-facing term and **Pool** as the persistence/query engine behind it.

---

## The funnel (one direction, no shortcuts)

```
Observe / Decide
       ↓
Experience Graph (structural memory + reasoning traces)
       ↓
Skills (distilled, invocable playbooks)
       ↓
Genomes / DNA (versioned, promotable capability packages)
```

Everything that matters should eventually flow **down** this funnel. Retrieval can jump levels (e.g. `agentdrive_think` pulls DNA + graph), but **writes** should land at the right tier so future cycles inherit structure, not noise.

---

## Tier 1 — Observe / Decide

**What happens:** Tasks arrive; models reason; multiverse holds competing paths; execution produces outcomes.

| Surface | Role |
|---------|------|
| MCP / CLI `run_operation` | Canonical execution + auto-learning hook |
| `experience_graph_get_context_pack` | Briefing before non-trivial work |
| `experience_graph_record_reasoning` | Explicit structural decision traces |
| `multiverse_parent_decision` / `external_parent_decision` | Competing-path collapse → graph DNA |
| `codebase_observe_file` / `codebase_mimic` | Mirror-neuron pattern capture before coding |
| Harness / scanners | Outcome capture from agent runs |

**Write target:** Observations, TypedEdges, multiverse sessions, fabric reasoning — all via the Experience Graph recorder.

**Do not:** Skip graph writes and jump straight to “save a skill” — you lose provenance and cross-cycle linkage.

---

## Tier 2 — Experience Graph

**What it is:** The living structural memory — TypedEdges, cycles, coherence signals, parent fabric reasoning, multiverse sessions.

| Tool | When |
|------|------|
| `experience_graph_get_context_pack` | Start of serious tasks |
| `experience_graph_suggest_reasoning_structure` | Before `record_reasoning` |
| `experience_graph_record_reasoning` | After important decisions |
| `experience_graph_find_structural_similarities` | Reuse prior decision shapes |

**Automatic path:** `AGENTDRIVE_AUTO_LEARN=1` (default) absorbs lightweight reasoning + high-signal ops via `auto_absorb` — check `auto_learning` on results.

**Quality bar:** Traces should cite fabric elements considered, expected lift, and attribution (`program_id`, constitution refs).

---

## Tier 3 — Skills

**What it is:** Distilled, invocable instructions — Hermes-style inheritance, MCP session distillation, codebase writing guides.

| Source | Mechanism |
|--------|-----------|
| Parent MCP sessions | `auto_absorb` → `mcp-auto-learning` skills |
| Explicit distillation | `agentdrive_review_inherited_skills` / assimilate |
| Codebase mirrors | Observe → motor programs → `codebase_mimic` |
| Bundled + user | `skills/registry.py`, `run_skill()` |

**Invoke:** CLI `/skill`, REPL, MCP catalog skills, pawn role injection.

**Promotion rule:** Skills that prove repeatable and high-signal should be candidates for Genome packaging (Tier 4).

---

## Tier 4 — Genomes / DNA (Drive Pool engine)

**What it is:** Versioned capability packages — frameworks, reasoning patterns, tool strategies, evaluations.

| API | Role |
|-----|------|
| `agentdrive_think` | Cited synthesis from Drive + graph (mandatory gaps) |
| `agentdrive_pool_query` / Drive `query()` | Semantic retrieval |
| `ingest` / `propose_improvement` | Promotion and evolution |
| Registry | `~/.agentdrive/genomes/<id>/<version>/` |

**Pool vs Drive:** Same engine. **Drive** = product + swarm-scoped directories (`get_swarm_drive_path`). **Pool** = historical module name for ingest log + query (`pool/ingest.jsonl`).

---

## Swarm scoping (orthogonal to the funnel)

Each swarm gets isolated storage:

```
~/.agentdrive/swarms/<swarm_id>/
├── drive/          # Experience Graph + meta_evolution + multiverse sessions
└── <subagent_id>/pool/   # Per-sub-agent DNA (when isolation_level=subagent)
```

The funnel runs **per swarm**. Cross-swarm sharing is policy-gated (`docs/SETTINGS.md`).

---

## The sacred 6-step loop (execution wrapper)

All serious work wraps the funnel:

1. **Experience** — context arrives  
2. **Overseer** — metacognition + graph briefing  
3. **Parent** — explicit reasoning (`record_reasoning`, multiverse collapse)  
4. **Steering** — user/Council/Guardian gates  
5. **Execution** — harness, MCP ops, code changes  
6. **Write-back** — graph → skills → DNA as appropriate  

See `docs/FOR_AI_MODELS.md` for model-facing rules.

---

## What to use when (quick routing)

| Intent | Start here |
|--------|------------|
| "What do we already know?" | `experience_graph_get_context_pack` → `agentdrive_think` |
| "Which path should we take?" | `external_parent_decision` (MCP model) or `multiverse_parent_decision` (local LLM) |
| "How is this repo written?" | `codebase_register_project` → `codebase_observe_file` → `codebase_mimic` |
| "Remember this outcome" | Harness `record_outcome` → auto-ingest → graph trace |
| "Reusable playbook" | Distill skill → promote to Genome when stable |
| "Health / wiring" | `agentdrive_doctor`, `golden_path verify` |

---

## Related docs

- `docs/FOR_AI_MODELS.md` — canonical model onboarding  
- `docs/MULTIVERSE_COGNITION.md` — parallel timeline decisions  
- `docs/POOL.md` — Drive pool engine (DNA storage)  
- `docs/SKILLS-LIBRARY.md` — skills + inheritance  
- `docs/GOLDEN_PATH.md` — operator install → verify loop