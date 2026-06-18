# AgentDrive Memory Bank

**Deep persistent memory for the AI** — a custom knowledge databank that always grows and integrates with every AgentDrive layer.

---

## What it is

The Memory Bank is not a replacement for the Experience Graph, skills, or learnings. It is the **unified recall layer** where atomic memories from all surfaces compound into one queryable personal databank:

```
Experience Graph ──┐
Skills / born skills ──┤
Learnings ─────────────┼──► Memory Bank ──► briefing / search / recall
Codebase patterns ─────┤
Auto-absorb ops ───────┘
```

**Storage (per swarm):**

```
~/.agentdrive/swarms/<swarm_id>/drive/memory_bank/
├── memories.jsonl      # append-only atomic memories
├── stats.json          # write stats by kind/source
└── relations.sqlite3   # time-bounded entity relations
```

---

## Memory kinds

| Kind | Typical source |
|------|----------------|
| `fact` | User or model explicit store |
| `procedure` | How-to playbooks |
| `insight` | `think`, reasoning traces |
| `decision` | Multiverse collapse, parent decisions |
| `pattern` | Codebase observe/mimic |
| `born_skill` | Skill fusion synthesis |
| `learning` | `learnings_log` |
| `episode` | Outcomes, harness runs, dialogue import |
| `preference` | User-stated prefs |
| `relationship` | Entity links |

---

## Scoping model

AgentDrive organizes memories by **vault** (workspace/project) and **topic** (thematic lane):

| Field | Meaning |
|-------|---------|
| `vault` | Workspace or project bucket (e.g. `interegy`, `claude-sessions`) |
| `topic` | Thematic lane within a vault (e.g. `auth`, `deploy`) |
| `origin_path` | Source file for imported dialogue shards |
| `shard_index` | Position when long text is split into shards |
| `preserves_source` | `true` when content is stored without summarization |

---

## Search and ranking

`memory_bank_search` uses **BM25 + lexical ranking** over the active candidate set — no embedding required. Scope with `vault` and `topic` params before acting on a task.

---

## MCP / CLI operations

| Op | When |
|----|------|
| `memory_bank_anchor` | **Session start** — agent brief + essential memories + optional scoped recall (~600–900 tokens) |
| `memory_bank_briefing` | Dense personal memory pack |
| `memory_bank_deep_briefing` | Maximum grounding — fabric context pack + memory bank |
| `memory_bank_search` | Before acting — pull relevant memories for the task |
| `memory_bank_store` | Explicit persist — user or model stores knowledge |
| `memory_bank_recall` | Fetch one memory by id |
| `memory_bank_list` | Browse recent memories |
| `memory_bank_stats` | Counts, kinds, paths |
| `memory_bank_import_dialogue` | Backfill JSONL/text session exports into full-text shards |
| `memory_relation_record` | Record subject–predicate–object relation with optional validity window |
| `memory_relation_query` | Query relations by entity (optional `as_of` date) |
| `memory_relation_expire` | Close an active relation (`valid_to`) |

---

## Automatic growth (default on)

`AGENTDRIVE_AUTO_MEMORY_BANK=1` (default) ingests from:

- Every successful `run_operation` via `auto_absorb`
- Born skill fusion
- `learnings_log`

Check `auto_learning.memory` on operation results.

Disable: `AGENTDRIVE_AUTO_MEMORY_BANK=0`

---

## Session checklist (models)

1. `memory_bank_deep_briefing` or `experience_graph_get_context_pack` + `memory_bank_briefing`
2. Work (think, multiverse, codebase, skills)
3. Auto-ingest grows the bank; explicit `memory_bank_store` for high-value facts
4. `memory_bank_search` before similar future tasks

---

## Related

- `docs/CAPABILITY_FUNNEL.md` — where memory bank sits in the stack
- `docs/FOR_AI_MODELS.md` — model golden rules
- `docs/SKILLS-LIBRARY.md` — born skills also become memories