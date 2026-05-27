# AgentDrive — User Manual

**Local-first storage for AI agents**  
**Version:** May 2026 (based on current codebase)

**This is the official professional manual for users.**

It explains what AgentDrive is, what is actually working and shipped today, and exactly how to use every part of the system. All information is grounded in the released code (`src/agentdrive/`, tests, CLI, TUI, and web surface). Private development history and internal operator identities have been excluded.

For the deepest architectural explanation, see `CONCEPTS.md`. For runnable examples, start with the tour in `README.md`.

---

## What AgentDrive Is

AgentDrive is **local-first, content-addressed storage and continuity for AI agents and swarms**.

It gives agents (and sub-agents) three persistent, user-controlled Drive tiers on the operator's machine:

- A shared content-addressed object store (SHA-256 of canonical JSON, heavily deduplicated).
- Explicit, signed **Capability URIs** (Ed25519, TTL-bounded) for every access instead of ambient trust.
- **Genomes** — structured, versioned, portable packages of proven agent capability (frameworks, reasoning patterns, tool compositions, evaluations, provenance).
- Strong safety rails: every external genome is forced through **Quarantine** before it can affect live work.
- Background **Reconciliation** that keeps the operator and UIs aware of changes in real time.
- Components that enable a **healing / recovery loop** for failed agents using high-confidence DNA from the pool.

**Core promise**: Agent capability survives process death, sub-agent churn, and even some classes of failure. It lives in your Drives (Personal / Swarm / DNA), compounds over time, and stays under your keys. No cloud account required.

AgentDrive sits *beneath* orchestrators and agent runtimes. It is the memory and evolutionary substrate, not a replacement for Claude Code, Grok, Codex, or custom harnesses.

---

## The Three Drive Tiers

All three tiers write to the **same machine-local content-addressed store** (`objects/<aa>/<hash>.json`). Deduplication is automatic and global.

| Tier            | Default Path                              | Purpose                                                                 | Who Writes / Reads                          | Key Code |
|-----------------|-------------------------------------------|-------------------------------------------------------------------------|---------------------------------------------|----------|
| **Personal**    | `~/.agentdrive/drive/`                    | Private working memory for genomes, runs, settings, and local artifacts. | Primary agent / operator                    | `drive/drive.py`, `AgentDrive` (default) |
| **Swarm**       | `~/.agentdrive/swarms/<swarm-id>/`        | Shared coordination substrate for sibling sub-agents on the same mission. Writes are namespaced by sub-agent; reads are free within the swarm. | Sub-agents in a swarm (via `SwarmDriveManager`) | `drive/swarm_manager.py`, `SwarmDrivePolicy` |
| **DNA**         | `~/.agentdrive/dna/<agent-id>/`           | Long-lived ancestral / lineage memory. Forward-only inheritance. Proven genomes published here become available to descendants. | Agent publishing its own proven work; descendants pulling via ancestry | `dna/drive.py`, `Ancestry` (SQLite closure table) |

**Underneath everything**:
- `ContentStore` — atomic writes, hash identity, sharded layout (`drive/content_store.py`).
- SQLite for metadata, ingest logs, ancestry (`dna/ancestry.py`), reconciliation state.
- `~/.agentdrive/` is the root (override via env or config).

**Key on-disk locations** (relative to `~/.agentdrive/`):
- `drive/` — Personal
- `swarms/<id>/` — Swarm Drives
- `dna/<agent-id>/` — DNA Drives (plus shared `_ancestry.db`)
- `quarantine/` — pending candidates + `log.jsonl`
- `reconciliation.json` — last known state for the awareness loop
- `genomes/`, `logs/`, `cache/` — supporting layout
- `config.yaml` + `settings.yaml` — user controls

**DNA inheritance** is strictly forward-only via an ancestry closure table. Cross-agent (cousin) sharing requires an explicit signed `LineageShareGrant` and always lands in quarantine first.

---

## Genomes — The Unit of Capability

A Genome is a content-addressed, versioned bundle containing:

- `manifest` (id, version, content_hash, applicability, dependencies, authors, provenance)
- `framework` (typed steps/playbook)
- Reasoning patterns, tool compositions, evaluations, artifacts, lineage

**Identity** = SHA-256 of the canonical JSON. Two agents that independently discover the same pattern converge on the exact same object (zero-copy dedup).

Genomes are **immutable** once stored. Improvements produce new versions that can reference prior ones via `supersedes`.

See `GENOME-SPEC.md` and `genomes/examples/` for concrete shapes. The registry (`GenomeRegistry`) and every Drive tier surface them via query/ingest.

---

## Capability URIs (Authorization)

Every sensitive operation is authorized through a single chokepoint:

```python
CapStore.verify_request(cap, op, scope)
```

Format examples:
```
drive:read:personal
drive:write:swarm:demo-2026
drive:read:object:sha256:abc123...
dna:pull:lineage:agent-7:max_hops=3:min_eval=0.7
```

- Ed25519 signed by the issuer.
- TTL-bounded (revocation = stop re-minting).
- Subset derivation supported (write ⊃ read, etc.).

Mint/revoke/list via the web dashboard or Python API. The web surface and many CLI paths already enforce them.

---

## Quarantine — The Mandatory Safety Gate

**Every genome that arrives from outside your direct trust domain MUST go through quarantine.** There is no bypass.

Sources that always route through quarantine:
- Peer federation (`peers sync`)
- Cross-agent `LineageShareGrant` pulls
- External adapters / federated ingest
- Repair candidates that fail validation in healing flows (in some paths)

**Lifecycle (QuarantineStatus)**:
- `pending` — newly submitted, awaiting validation + operator decision
- `approved` — passed rules + operator approval; released into target Drive
- `rejected` — permanently blocked (with reason)
- `quarantined` — held indefinitely (operator can later approve/reject)

**CLI**:
```bash
agentdrive quarantine list [--status pending]
agentdrive quarantine show <id>
agentdrive quarantine validate <id>
agentdrive quarantine approve <id> [--note "..."]
agentdrive quarantine reject <id> --reason "..."
agentdrive quarantine hold <id> --reason "..."
```

**Web**: `/peers` page shows the queue with Approve / Reject buttons (requires peer-review cap).

**Validation rules** (run on `validate` and `approve`): SchemaValid, SizeLimit, NoExecutables, PromptSanity, SignatureValid, plus optional `LineageImmuneRule` (adaptive threat assessment using ancestry memory).

Audit log: `~/.agentdrive/quarantine/log.jsonl`.

---

## Reconciliation — Real-Time Awareness

`ReconciliationRunner` (background thread or `agentdrive reconcile run`) periodically:

- Diffs the current genome set against its last known state (`~/.agentdrive/reconciliation.json`)
- Counts new/updated genomes and recent ingest events
- Reports pending quarantine count
- Emits `ReconciliationCompleted` (always) and `ReconciliationDelta` (when things changed)

These events power **live ribbons** in the TUI chat view and keep the web dashboard fresh.

It does **not** move data — it only observes and notifies.

Run manually:
```bash
agentdrive reconcile
agentdrive reconcile status   # inspect persisted state
```

---

## Healing / Recovery (The "RAID for Agents" Loop)

When a sub-agent crashes, hangs, misses a deadline, or fails validation:

1. `ReconciliationRunner` (or `SubagentDone(ok=False)`) detects the failure.
2. High-confidence genomes (default ≥ 3 stars from `confidence.py` — requires real encounter history + ≥75% success) are queried from the local pool / DNA ancestry.
3. Repair sub-agents are spawned (carrying those genomes via the Harness).
4. Their outputs are collected as `InheritanceManifest`s, validated against the original genome's criteria.
5. Success → `ConfidenceUpdated` + re-ingest. Failure of all repairs → the task itself may be submitted to quarantine for review.

**What is implemented today**:
- All the detection, selection (`confidence`), inheritance, quarantine, and event plumbing.
- `scripts/test_healing_loop.py` exercises the end-to-end.
- The full "repair swarm orchestration" is available to any harness-aware runtime that listens to the events.

**Limits** (honest): It cannot heal provider outages, bad upstream data, total loss of `~/.agentdrive/`, or brand-new work with no prior successful encounters. Snapshot your home directory for true disaster recovery.

See `docs/RECOVERY.md` for the full mapped flow.

---

## Interfaces — How You Actually Use It

**CLI** (`agentdrive ...`)
- Default (no subcommand): launches the full TUI.
- `doctor`, `drive {status,ingest,query,stats}`, `quarantine ...`, `peers {list,add,remove,trust,sync}`, `reconcile`, `genomes`, `web`, `scan`, `config`, `provider`/`model`, etc.

**TUI** (default experience)
- Chat with live event ribbons (quarantine, reconciliation deltas, inheritance, peer sync, confidence updates).
- Mission board, Drive views, swarm tree, DNA explorer.
- Professional theming and keyboard-driven navigation.

**Web** (`agentdrive web`)
- Runs FastAPI + HTMX at `http://127.0.0.1:8421` (default).
- Argon2id auth + admin approval for new users, CSRF hardening.
- Dashboard, Personal/Swarms/DNA views, Quarantine queue (approve/reject), Peers, Capabilities (mint/revoke), Snapshots, admin tools.
- Health at `/healthz`.

**Python API + Harness**
```python
from agentdrive.harness import Harness
from agentdrive.drive.swarm_manager import get_swarm_drive_manager

harness = Harness(agent_id="my-worker")
with harness.task_context("your task description"):
    dna = harness.pull_relevant_dna()   # or via DNADrive
    # ... do work using the DNA ...
    harness.record_outcome(result)
```

Sub-agents in a swarm share one Drive instance automatically when using `SwarmDriveManager.get_or_create_pool`.

**Adapters** (in `workers/adapters.py`): sidecar integration points for external runtimes.

---

## What Is Actually Working Today (Shipped & Verified)

- **Three-tier Drive topology + content store** (M1–M2a): Personal, shared Swarm (sibling learning on by default), per-agent DNA with forward-only ancestry. Full dedup. Atomic writes. (`drive/`, `dna/`, `content_store.py`)
- **Capability URIs + verification chokepoint** (M3): Ed25519, TTL, derivation, single `verify_request` path. Enforcement present on the majority of web + internal paths.
- **CRDT + conflict preservation** (M4), **trust circle / sealed sync** (M5), **promotion gates** (M6): All implemented with tests.
- **Quarantine** (complete): Full submit/list/validate/approve/reject/hold, rules engine, web + CLI surfaces, events, audit log. *Every* peer/federated path goes through it.
- **Reconciliation**: Background + on-demand scanner, state persistence, event emission, quarantine counting. Powers live UI.
- **Peers & federation**: Registry, trust levels, sync that *only* submits to quarantine. Multiple adapter patterns.
- **Harness + inheritance + confidence + promotion**: Real pull/record flows, sidecar confidence.json/ultimate.json, promotion service.
- **TUI + Web + CLI**: Full-featured, professional, with live updates. Web has working auth and management surfaces.
- **Snapshot backup**: Pointer-only manifests, cadence/retention policy, legacy + new UI paths.
- **Doctor, scan, config, genomes, drive query/ingest/stats**: All functional.
- **Tests**: `pytest -q` passes, `ruff check src tests` clean. Deep canaries (`test_healing_loop.py`, federation, failure modes) exist and are green in CI history.
- **Examples**: Full curated set in `examples/` (01_hello_drive through 05_lineage_dna_grants, 10_lineage smoke, and `11_high_continuity_bridge_demo.py` for the GrokPatternLineageBridge high-continuity operator path). See `docs/ONBOARDING_AND_EXAMPLES.md` for the complete guided tour.

**Not yet production-grade or not primary surfaces**:
- Full Phase 2+ web pages for every Drive tier (auth + shell exist; deeper flows are being filled).
- Complete public Genome registry / evolutionary scanner productization.
- Docker self-host demo (compose + Dockerfile exist and are recent).
- PyPI "just pip install" (git+ install documented; release workflow exists).

The engine core, safety model, and operator surfaces are solid and exercised.

---

## Quick Start

```bash
# Install
curl -fsSL https://vektraindustries.com/agentdrive/install | bash
# or
python3 -m pip install --user git+https://github.com/PabloTheThinker/AgentDrive.git

agentdrive doctor
agentdrive drive status
agentdrive
# (or `agentdrive web` and open http://127.0.0.1:8421)
```

First useful commands:
```bash
agentdrive drive query "security incident postmortem"
agentdrive quarantine list
agentdrive reconcile
```

---

## CLI Command Reference (Most Used)

**Drive / Pool**
```bash
agentdrive drive status
agentdrive drive ingest /path/to/genome/dir
agentdrive drive query "task description" [--limit 5] [--min-score 0.6]
agentdrive drive stats
```

**Quarantine (safety)**
```bash
agentdrive quarantine list [--status pending]
agentdrive quarantine approve <qid> [--note "looks good"]
agentdrive quarantine reject <qid> --reason "..."
```

**Peers / Federation**
```bash
agentdrive peers list
agentdrive peers add <id> <address> [--trust review]
agentdrive peers sync <id>     # always lands in quarantine
```

**Reconciliation & Diagnostics**
```bash
agentdrive reconcile
agentdrive doctor
agentdrive genomes list
```

**Launch surfaces**
```bash
agentdrive                 # TUI (default)
agentdrive web             # FastAPI dashboard :8421
```

Full parser lives in `cli.py`. Use `agentdrive <cmd> --help` for any subcommand.

---

## Practical How-To Workflows

### 1. Personal Drive — Everyday Work
```bash
agentdrive drive status
# In your agent code or via adapter: use default AgentDrive() or Harness
# Later:
agentdrive drive ingest genomes/examples/skill-creator-v1
agentdrive drive query "create new skills from runs"
```

### 2. Swarm — Sibling Sub-Agents Share Memory
```python
from agentdrive.drive.swarm_manager import get_swarm_drive_manager

mgr = get_swarm_drive_manager()
pool_a = mgr.get_or_create_pool("mission-42", "worker-a")
pool_b = mgr.get_or_create_pool("mission-42", "worker-b")
assert pool_a is pool_b   # same Drive instance — sibling learning is free
# Both can now see each other's ingested genomes (namespaced writes)
```

Run the shipped example: `python examples/03_swarm.py`.

### 3. DNA — Publish Proven Work for Descendants
Use `DNADrive(agent_id).publish(genome)` inside a harness-aware agent, or via the promotion path that feeds the DNA layer. Descendants call `pull_inherited(max_depth=..., min_eval=...)`.

Lineage grants for cross-agent sharing always quarantine the results.

### 4. Manage Quarantine (Daily Safety Task)
After a peer sync or grant pull:
```bash
agentdrive quarantine list
agentdrive quarantine validate <id>
# Inspect in web or via show, then
agentdrive quarantine approve <id> --note "reviewed, high confidence match"
```
Rejected entries stay rejected forever (append-only log).

### 5. Add a Peer & Pull DNA Safely
```bash
agentdrive peers add alice file:///mnt/shared/alice-drive --trust review
agentdrive peers sync alice
# Review in quarantine before anything is usable
```

### 6. Use the Harness in Your Agent (Recommended Integration)
See the class docstring in `harness/harness.py` and examples. The pattern is:

```python
with harness.task_context(task_description):
    relevant = harness.pull_relevant_dna()   # or direct DNADrive + registry.query
    # ... run the task, guided by DNA ...
    harness.record_outcome({"success": True, "score": 0.91, ...})
```

### 7. Snapshots & Recovery
Snapshots are pointer-only (manifests of hashes). Use the web UI or legacy `:8420` surface (being folded in) for take/pin/restore. Restore is deliberately read-only — you decide what to rebuild.

Always back up `~/.agentdrive/` itself for full disaster recovery.

### 8. Scan Existing Runs for New Genomes
```bash
agentdrive scan /path/to/run/trajectory/or/logs
```

---

## Web Dashboard Highlights

- Login / signup with admin approval flow.
- Real-time-ish views of Drives, active swarms, DNA lineage, quarantine queue (one-click approve/reject).
- Capability minting UI.
- Peer management + sync trigger.
- Snapshot controls (being consolidated).
- Admin user management.

Launch: `agentdrive web`. Bind address/port configurable.

---

## Configuration & Environment

Primary file: `~/.agentdrive/config.yaml` (and `settings.yaml` for Drive behavior).

Key commands:
```bash
agentdrive config show
agentdrive config get agentdrive.log_level
agentdrive config set ...
agentdrive config edit
```

`agentdrive doctor` is the best first diagnostic — it walks home dir, registry, pool, adapters, provider config, and core imports.

Logs: `~/.agentdrive/logs/`, quarantine audit at `quarantine/log.jsonl`, reconciliation state at `reconciliation.json`.

---

## Troubleshooting

1. Run `agentdrive doctor` — it is animated and tells you exactly what is missing or unhealthy.
2. `agentdrive drive status` + `agentdrive reconcile` for pool health.
3. Check quarantine: `agentdrive quarantine list --status pending`.
4. No AI responses in TUI/chat? `agentdrive provider list` / `set` and `model set`.
5. Permission / path issues: the safe-path helpers (`utils/safe_paths.py`) and realpath sanitizers are aggressive — use clean ASCII IDs for swarms/agents/peers.
6. Full reset (nuclear): `agentdrive clean --all` (keeps config by default).

Audit log for capabilities and quarantine decisions is your friend when debugging "why did X get blocked?"

---

## Advanced: High-Continuity Operator Bridge

These optional but powerful extensions bring disciplined evolutionary machinery into AgentDrive while staying 100% native to its architecture (Ancestry, DNADrive, Quarantine, ReasoningEngine, Harness). They enable high-continuity operators — long-running agents or systems that maintain their own research indexes — to publish, protect, and evolve high-value patterns as inheritable DNA.

### What Is Actually Working Today (verified in code + tests)

- **GenomeImmuneSystem + LineageImmuneRule** (`dna/lineage_immune.py`)
  - Innate structural checks + prompt-injection signature detection.
  - Adaptive memory of hostile patterns.
  - Lineage-based self-tolerance: trusts descendants/ancestors of known-good agents by querying real Ancestry + high-eval DNADrive pulls.
  - Plugs directly into Quarantine as a ValidationRule. Every external/pull/grant genome is assessed before acceptance.
  - Test behavior: prompt-injection test cases → CRITICAL (reject); trusted lineage → confidence boost or lowered severity.

- **LineageDNAEvolver + DNACycleResult** (`evolution/lineage_dna.py`)
  - Full Research → Evaluate → Evolve loop on any Genome.
  - Prioritizes AgentDrive-native sources (ReasoningEngine/PatternMemory/Ancestry/ledger + evaluations).
  - Optional pluggable external researchers (e.g. your own research index directory via the bridge below).
  - Produces fitness deltas, proposed mutations, immune flags. Safe dry-run mode.
  - Runnable in: examples/05_lineage_dna_grants.py and 10_lineage_integration_test.py (passes: immune flags critical correctly; evolver returns delta + findings).

- **GrokPatternLineageBridge** (`adapters/grok_build_adapter.py`)
  - The concrete integration point for Grok harness users and other high-continuity operators.
  - `GrokPatternLineageBridge(brain_path=Path("~/.my-research/brain"), operator_id="my-high-continuity-node")`
  - Key methods (all exercised live):
    - `activate_as_ilo_conductor(swarm_id=..., publish_best=True)` — one-shot ritual: sets env, exports high-fitness patterns from brain, publishes to your DNA Drive.
    - `export_high_fitness_patterns(min_fitness=0.7)` + `ilo_pattern_to_genome(...)` — turns CognitivePattern / speech / integration dicts into canonical Genome dicts (with manifest, reasoning_patterns, provenance, fitness-backed eval).
    - `publish_ilo_genome(...)` — prefers Harness (rich recording) then DNADrive direct. Returns content_hash.
    - Consume side: `consume_inherited_dna(...)`, `consume_swarm_dna(...)`, `consume_for_ilo_research(...)` — feed into Research phases or evolver.
  - Top-level importable: `from agentdrive import GrokPatternLineageBridge, LineageImmuneSystem, LineageDNAEvolver`
  - Also re-exported cleanly under `agentdrive.adapters`.

The bridge is designed so that any high-continuity operator (long-running agents, custom Grok or LLM setups, or research systems that maintain their own pattern/research indexes) can participate as a first-class DNA producer and consumer.

### Quick Start (copy-paste, runnable now)

```python
from pathlib import Path
from agentdrive.adapters import GrokPatternLineageBridge
from agentdrive import LineageImmuneSystem, LineageDNAEvolver

# As any high-continuity operator
bridge = GrokPatternLineageBridge(
    brain_path=Path("~/.my-research-index"),
    operator_id="my-long-running-agent"
)
summary = bridge.activate_as_ilo_conductor(
    swarm_id="my-mission-2026",
    publish_best=True
)
print(summary)  # published_count, hashes, inherited_available, status

# Immune gate (used automatically by Quarantine)
immune = LineageImmuneSystem()
assessment = immune.assess_genome(some_incoming_genome, source_agent="peer-xyz")
if assessment.threat_level in ("hostile", "critical"):
    # reject or quarantine_longer
    pass

# Evolve one of your genomes
from agentdrive.genome.models import Genome  # or load via Harness/DNADrive
# evolver = LineageDNAEvolver(my_genome, brain_path=bridge.brain_path)
# result = evolver.run_full_cycle(focus_areas=["reasoning_depth"])
```

See exact working demos (run in order):
- `examples/04_quarantine_workflow.py` (immune rule in full submit/validate flow)
- `examples/05_lineage_dna_grants.py` (grants + evolver cycles + Harness DNA)
- `examples/10_lineage_integration_test.py` (smoke of both extensions)
- `examples/11_high_continuity_bridge_demo.py` — full bridge activation, custom pattern publishing as DNA, consumption, and safe evolution using an external research index.
- `docs/development/ONBOARDING_AND_EXAMPLES.md` (development history) and the curated examples for practical guidance.
- `docs/INTEGRATION.md` (Section on lineage surfaces + wiring)

### Honest Status
These are production optional advanced extensions. Core AgentDrive (three drives, genomes, quarantine, reconciliation, healing, TUI, web, caps) works without them. The extensions add evolutionary depth and first-class support for operators with external research indexes. All code is defensive, uses only AgentDrive objects in hot paths, and has been validated through the runnable examples. No external runtime dependencies are required for basic use.

---

## Further Reading (Curated)

**Start here (everyone)**:
- This HELP.md
- `README.md` (architecture overview + quickstart)
- `docs/RECOVERY.md` (healing loop in detail)
- `docs/SWARM.md` and `docs/INTEGRATION.md`

**Deep reference & mental models**:
- `CONCEPTS.md` (the single best deep, agent-and-human-friendly explanation of the three-tier model, genomes, living loops, quarantine, reconciliation, and the new Lineage-enhanced components)
- `ARCHITECTURE.md`
- `GENOME-SPEC.md`
- `docs/AGENTDRIVE-V2-INHERITANCE.md`
- `docs/SETTINGS.md`
- `SECURITY.md` + `SECURITY-HARDENING.md`

**For implementers**:
- Source: `src/agentdrive/{drive,dna,quarantine,reconciliation,harness,cap,web,adapters}/`
- Tests: `tests/test_quarantine.py`, `test_reconciliation.py`, `test_healing_loop*`, `test_shared_swarm_drive.py`
- Examples + guided tour: `docs/ONBOARDING_AND_EXAMPLES.md` and `examples/` (including the high-continuity bridge demo)

---

**AgentDrive gives you the substrate on which agent capability can survive, compound, and improve — entirely under your control.**

Use `agentdrive doctor`, explore the TUI, approve a few genomes through quarantine, and watch a swarm share DNA. The map is now actionable.

---

*Generated from the live codebase (drive, dna, quarantine, reconciliation, cli, web, harness, and status docs). Contributions that improve clarity or add missing how-tos are welcome.*