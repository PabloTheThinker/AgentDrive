# Savant Pool — The Living DNA Repository for AI Agents

> Part of the Savant engine — the open-source substrate behind AgentDrive. See [README](../README.md).

**The Savant Pool is the persistent, user-owned evolutionary memory system for agent intelligence.** It stores, retrieves, and evolves structured "DNA" (Genomes) — portable packages of frameworks, reasoning patterns, tool strategies, and proven outcomes that agents can pull, adapt, and improve.

Every agent and every sub-agent in a swarm participates in the pool through the **Harness**. The pool starts completely empty and grows only with real, high-signal experience from successful work.

## What the Pool Delivers

- **Collective Intelligence Without Contamination**: Agents learn from each other’s best work while keeping private experiences isolated where desired.
- **Living, Evolvable DNA**: Genomes are not static prompts or skills. They are versioned, provenance-tracked artifacts that improve over time through real usage and explicit proposals.
- **Smart Retrieval**: A hybrid relevance engine (structural applicability + deep reasoning-pattern overlap) surfaces the most useful DNA for any task.
- **Automatic Contribution**: High-quality runs automatically feed back improvements, new micro-patterns, and score adjustments.
- **Full User Sovereignty**: Every policy — isolation, auto-ingest, sharing, retention — is configurable by the owner (human or via natural-language instruction to any connected AI).

## Core Architecture

### Genomes: The DNA Units

A Genome captures a complete, transferable unit of capability:

- **Manifest**: Identity, semantic version, content hash, applicability (domains, problem signatures), evaluation scores, authors/provenance.
- **Framework**: Typed, schema-enforced playbook of steps with inputs, outputs, and rationale.
- **Reasoning Patterns**: High-signal heuristics, causal structures, contradiction detectors, analogies, postmortem templates, etc. — extracted and synthesized by Savant’s reasoning primitives.
- **Tool Compositions & Strategies**: Proven sequences, parallelization patterns, and guardrails.
- **Evaluations & Lineage**: Reference-task performance, improvement history, fork/merge records.

Genomes live in the registry (`~/.savant/genomes/`) in hierarchical `<id>/<version>/` layout and are also referenced by the pool’s ingest log.

### SavantPool Class

The central Python object (`savant.pool.SavantPool` or `get_default_pool()`):

- `ingest(genome, source, actor)` — Validates, versions, stores via registry, appends to persistent `pool/ingest.jsonl`.
- `query(PoolQuery)` or `get_relevant_dna(task, top_k)` — Returns enriched DNA packets with relevance scores and human-readable “why relevant” explanations.
- `propose_improvement(...)` — Agents/humans submit better versions.
- `get_pool_stats()`, `get_ingest_history()` — Full observability.
- Backed by `GenomeRegistry` + append-only JSONL log for robustness.

The relevance engine (in `_compute_relevance`) uses:
- **Structural score**: Domain/problem/capability keyword matches + evaluation boost.
- **Reasoning score**: Jaccard overlap on tokenized reasoning texts, framework steps, recognized patterns (inspired by `savant.reasoning.*` primitives: causality, patterns, contradictions).
- **Hybrid**: 30% structural + 70% reasoning (favors deep “why it works” signals).

### Persistence Layout

```
~/.savant/  (or $SAVANT_HOME)
├── config.yaml
├── genomes/
│   └── <genome-id>/
│       └── <version>/
│           ├── manifest.yaml
│           ├── framework.yaml
│           ├── reasoning/
│           ├── ...
├── pool/
│   ├── ingest.jsonl          # append-only audit of every contribution
│   └── (future: stats, snapshots)
├── swarms/                   # per-swarm isolation root (see SWARM.md)
│   └── <swarm-id>/
│       └── <subagent-id>/
│           └── pool/
└── logs/, cache/, ...
```

All data is local-first, portable, and fully owned by the user. No cloud dependency.

## Using the Pool

### CLI

```bash
savant pool status          # overview + recent activity
savant pool stats           # full stats + recent ingest events from JSONL
savant pool query "security incident postmortem" --limit 8
savant pool ingest /path/to/genome/dir
```

### TUI (Recommended for Exploration)

```bash
savant tui
# Then navigate to the dedicated Pool view (first-class surface)
```

The TUI Pool view shows:
- Global + per-swarm overview
- Live query with relevance explanations
- Swarm listing and switcher
- Settings editor
- Ingest / evolve actions

### Python API (for Agents & Integrations)

```python
from savant import SavantPool, get_default_pool, PoolQuery, Harness

pool = get_default_pool()  # or SavantPool(pool_dir=...) for scoped pools

# Pull DNA
dna = pool.get_relevant_dna("Analyze production database outage", top_k=5)
for pkt in dna:
    print(pkt["genome_id"], pkt["relevance_score"], pkt["why_relevant"])

# Ingest a new/improved genome (from scanner or manual construction)
result = pool.ingest(my_genome, source="rich-agent-run", actor="rich-agent-042")

# Stats & history
print(pool.get_pool_stats())
```

### The Harness (Preferred for Worker Agents)

Wrap any task with the harness for automatic pull → adapt → work → contribute:

```python
from savant import Harness

harness = Harness(agent_id="my-agent-007")

with harness.task_context("Deep security incident postmortem"):
    dna = harness.pull_relevant_dna()
    enriched_prompt = harness.inject_into_context(base_prompt, extra_instructions="...")
    result = do_actual_work(enriched_prompt)
    harness.record_outcome(result)  # auto-synthesizes deltas + proposes improvements on high-quality runs
```

`record_outcome` intelligently:
- Skips low-quality runs
- Injects new micro-patterns discovered during the run
- Bumps evaluation scores
- Calls `propose_improvement` so the pool evolves

See `examples/rich_agent_with_savant_pool.py` and `src/savant/workers/rich_agent_adapter.py` for a complete, runnable rich agent reference implementation.

## User Control & Policies

The pool never acts without explicit user permission. All behavior is governed by `PoolSettings` persisted under the `pool:` section of `~/.savant/config.yaml`.

Key controls (full reference in `docs/SETTINGS.md`):
- `isolation_level`: subagent (default) | swarm | none
- `auto_ingest_on_success` + `min_quality_for_ingest`
- `sharing_policy`: selective (default) | full | read | none
- `retention_days`, `allow_upward_proposals`

Change via:
- `savant config set pool.global.isolation_level subagent`
- TUI settings panel
- Any connected AI (Grok, Claude, …) instructed by the user: “Set Savant pool sharing_policy to full for this swarm”

The `PoolSettingsManager` and `get_effective_pool_settings(swarm_id)` provide the runtime API.

## How the Pool Grows

1. **Ingestion** — Scanners (e.g. `SavantRunScanner`, `RichRunScanner`) analyze instrumented trajectories and produce candidate Genomes → `pool.ingest()`.
2. **Harness Contributions** — Every harness-wrapped run on success can auto-propose deltas.
3. **Explicit Proposals** — `pool.propose_improvement()` from humans or agents.
4. **Fork/Merge/Evolve** — Registry + evolutionary engine operations (CLI/TUI/orchestrator).

Every contribution carries full provenance so the evolutionary tree remains auditable.

## Relationship to the Rest of Savant

- **Registry** (`GenomeRegistry`): Storage & search backend for Genomes.
- **Scanners** (`src/savant/scanners/`): Extract DNA from runs.
- **Reasoning Primitives** (`src/savant/reasoning/`): Power the relevance engine and genome synthesis (causality, contradictions, patterns, synthesizer, etc.).
- **Harness & Adapters**: The participation layer for any external agent.
- **Orchestrator** (future): Genome-aware mission dispatcher that selects and composes DNA.

The Pool is the heart of the living ecosystem — the place where individual agent experience becomes durable, shareable, and compounding intelligence.

---

**Savant Pool gives your agents (and their sub-agents) a shared, private, ever-improving brain that you fully control.** Start it empty. Watch it grow with every meaningful run.
