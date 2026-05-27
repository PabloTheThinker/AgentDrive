# AgentDrive Concepts

**A deep, user- and agent-friendly explanation of the architecture, mental models, and mechanisms that make AgentDrive "RAID for AI agents."**

This document explains *why* the system is shaped the way it is and *how* its parts actually work together in practice. It is intended for technical human operators, integrators, and other AI agents that need to reason about or build on AgentDrive.

---

## The Core Metaphor: RAID for AI Agents

Modern AI agents are fragile. A sub-agent crashes, hangs, misses a deadline, produces signature-drifted output, or simply fails validation — and the valuable *how* it succeeded (or nearly succeeded) evaporates with the process. The next similar task starts from zero. At fleet scale this is catastrophic: capability is trapped inside ephemeral processes.

AgentDrive solves this with the same discipline that RAID brought to unreliable disks.

In RAID, data is not kept in one place. Mirrored blocks and parity stripes mean the array can lose drives and still reconstruct what mattered. The surviving members carry enough information to rebuild the failed one.

**AgentDrive applies the identical principle to agent capability:**

- Every successful (or high-signal) run is decomposed into **Genomes** — typed, versioned, content-addressed packages that capture not just *what* was done but *why it worked*: reasoning patterns, tool compositions, evaluation criteria, provenance, and fitness signals.
- These Genomes live in durable, queryable Drives on the operator's machine.
- When an agent dies or a new similar task appears, the system can pull the best surviving Genomes (graded by confidence, filtered by provenance and evaluation) and use them to heal, reconstruct, or accelerate the work.
- **Mirroring genomes is to AgentDrive what mirroring blocks is to RAID.**

The result is **capability survival**: failure stops being pure loss and becomes a training signal. The system gets more reliable with use, not less. Every run can compound the intelligence of the entire lineage and swarm.

This is the single mental model that explains every design choice below.

---

## The Three-Tier Drive Model

AgentDrive deliberately separates concerns that have different lifecycles, access patterns, and trust semantics. A single flat store would collapse these distinctions and create either privacy leaks, coordination bottlenecks, or unsafe inheritance.

The three tiers are:

```
Operator / Orchestrator
        │
        ▼
┌───────────────────────────────┐
│   Personal Drive              │  Private working memory (one agent)
│   ~/.agentdrive/drive/        │  Hot, mutable, owner-only
└───────────────┬───────────────┘
                │ spawns / coordinates
┌───────────────▼──────────────────────────────┐
│   Swarm Drive                                │  Shared working memory (siblings)
│   ~/.agentdrive/swarms/<id>/drive/           │  Namespaced writes, free sibling reads
│   (stigmergic coordination)                  │
└───────────────┬──────────────────────────────┘
                │ promotion (proven Genomes only)
┌───────────────▼───────────────┐
│   DNA Drive (per agent)       │  Ancestral / inheritable memory
│   ~/.agentdrive/dna/<agent-id>/drive/ │  Forward-only by default
│   + shared _ancestry.db       │  Permanent lineage chapters
└───────────────────────────────┘
```

All three tiers sit on top of the **same content-addressed object store** (SHA-256 of canonical JSON, sharded `objects/<aa>/<rest>.json`). Identical Genomes deduplicate across every tier and every agent on the machine. Writes are atomic. The identity of a Genome is its content hash — not its path or its author.

### 1. Personal Drive (`~/.agentdrive/drive/` or configured default)

**Purpose:** The private notebook of one parent/agent. In-flight reasoning, half-formed ideas, local settings, run history that has not yet earned promotion, and the agent's own working state.

**Access:** Read/write by the owning agent only. Sub-agents the parent spawns do *not* see the parent's Personal Drive by default.

**Lifecycle:** Lives as long as the agent. High-value Genomes are explicitly or policy-promoted out of it into the DNA Drive (for descendants) or shared via Swarm Drives during active work.

**Mental model:** Your personal desk and notebooks. Private until you decide something is worth archiving into the family library or sharing with colleagues on the current project.

### 2. Swarm Drive (`~/.agentdrive/swarms/<swarm_id>/drive/`)

**Purpose:** The shared blackboard / experience pool for a group of sibling sub-agents working on the same mission. This is the "we work together" substrate.

**Key properties (v2 Milestone 2a):**
- One Drive per swarm (not per sub-agent).
- Sub-agents write into their own namespace (via `manifest.authors` attribution, e.g., `"sub:worker-3"`).
- Reads are unrestricted within the swarm — any sibling can see any published Genome.
- This enables **stigmergic coordination**: useful work left by one sub-agent is immediately available to peers without a parent acting as a message bus or central coordinator.

**Conflict model:** CRDT counters for commutative data (frequency counts, monotonic scores). Conflict-copy preservation for non-commutative work (contradicting frameworks or reasoning). Conflicts are *data*, not errors — they become prompts for higher-tier synthesis.

**Lifecycle:** Exists for the duration of the swarm. Promoted Genomes can flow upward to the parent's Personal Drive or directly into DNA.

**Mental model:** The shared war-room table or colony pheromone trail. Siblings leave high-value traces; everyone benefits without explicit handoffs.

### 3. DNA Drive (`~/.agentdrive/dna/<agent_id>/drive/` + shared ancestry DB)

**Purpose:** The long-term, inheritable "family library" of proven capability. What an agent's ancestors (and the agent itself) have earned that should be available to descendants.

**Core invariants:**
- **Forward-only by default.** A descendant walks the ancestry DAG (via SQLite closure table `(ancestor_id, descendant_id, min_depth)`) and pulls Genomes published into any ancestor's DNA Drive content store. No cycles are possible (parent creation time < child creation time is enforced).
- **Permanent, no decay.** Once a Genome enters the lineage chapter, every descendant always has access. This matches the "Avatar / past lives" mental model: your ancestors remain reachable.
- **No automatic sideways flow.** Cousins from different swarms or lineages do not see each other's DNA unless an explicit, signed `LineageShareGrant` is issued.

**Path layout:**
```
~/.agentdrive/dna/
├── _ancestry.db                 # Shared closure table for the entire machine
└── <agent_id>/
    └── drive/
        └── objects/<aa>/<rest>.json   # Content-addressed Genomes (reuses the shared ContentStore)
```
        └── objects/<aa>/...     # Content-addressed Genomes (reuses ContentStore)
```

**Eval gating:** `pull_inherited(min_eval=...)` lets callers refuse low-quality ancestral material. Direct-line ancestors default to high trust (0.0 gate in many paths); cross-source pulls are stricter.

**Mental model:** The immutable family grimoire or genetic inheritance. Your parents' hard-won lessons are chapters you can always consult. You add new chapters by publishing proven Genomes. Your children will inherit them automatically.

### Why Three Tiers (Not One, Not Four)

Working memory (Personal + Swarm) is hot, collaborative within a mission, and relatively short-lived. Inherited memory (DNA) is cold, immutable in character, provenance-critical, and multi-generational. Conflating them creates either privacy disasters or inheritance complexity. The peer-federation layer (cross-operator sharing) is orthogonal and always routes through quarantine.

The design was validated by independent engineering analysis and literature survey (MARL, robotics SLAM, biology HGT/CRISPR, blackboard system failure modes, memory-poisoning research). Forward-only + opt-in signed grants was the convergent, cost-effective, defensible point in the design space.

---

## Genomes: The Portable Unit of Capability

A Genome is the atom of the system. It is more than a prompt or a skill:

- **Manifest**: Identity (content hash is the real ID), semantic version, applicability (domains, problem signatures), authors/provenance, evaluation scores, dependencies.
- **Framework**: Typed, schema-validated playbook of steps.
- **Reasoning patterns**: High-signal extracted heuristics (causality chains, productive analogies, contradiction detectors, failure-mode early warnings, etc.).
- **Tool compositions**: Proven sequences, parallelization strategies, guardrails.
- **Evaluations & artifacts**: Reference-task performance, example successful outputs.
- **Lineage/provenance**: Full history of forks, merges, improvements, validation runs.

Genomes are **content-addressed and immutable**. You do not edit a Genome in place; you publish a new one that can `supersedes` the old. Deduplication, cryptographic provenance, and safe conflict preservation all flow from this single decision.

Genomes are stored in the content-addressed layer under Drives and also indexed in the registry (`~/.agentdrive/genomes/<id>/<version>/`).

---

## How Everything Works Together: The Living Loops

### The Harness Participation Loop (the day-to-day experience)

Any agent or sub-agent wraps its work:

```python
harness = Harness(agent_id="my-agent-007", swarm_id="mission-xyz")
with harness.task_context("Deep security incident postmortem"):
    # Pull from working memory + (optionally) explicit ancestral DNA
    dna = harness.pull_relevant_dna()           # Swarm/Personal Drive relevance
    ancestral = harness.pull_inherited_dna(min_eval=0.6)  # DNA Drive

    # Use the DNA to enrich reasoning / choose strategies
    enriched = harness.inject_into_context(base_prompt)

    result = do_the_actual_work(enriched)
    harness.record_outcome(result)   # May propose improvements back into Drive(s)
```

On high-quality outcomes, scanners + the Harness synthesize deltas and propose new or improved Genomes. These land in the appropriate tier.

### Promotion & Flow

- Scratch work in a Swarm Drive namespace.
- Polished, valuable output promoted (via signed promotion record or policy) into the parent's Personal or directly into DNA.
- DNA publication makes it automatically visible to all future descendants.

### The Healing / Reconciliation Loop (RAID in action)

This is the recovery mechanism described in `VISION.md` and `RECOVERY.md`:

1. **Death detected**: `ReconciliationRunner` observes `SubagentDone(ok=False)`, missed heartbeats, validation failure, etc.
2. **Recovery genomes pulled**: `pool.query` (or Drive equivalent) against the task signature, filtered to high `ConfidenceRating` (typically ≥3 stars, which requires real encounter history + success rate).
3. **Repair swarm dispatched**: Top matches handed to fresh sub-agents (often 3 in parallel) under the same swarm scope.
4. **Outputs collected** into `InheritanceManifest`.
5. **Validation** against the *original* genome's evaluation criteria.
6. **Outcome**:
   - Success → `ConfidenceUpdated` events, absorption into the pool/Drive, the dead capability is effectively rebuilt.
   - Total failure → the task is submitted to **quarantine** for operator (or automated) review.

The genome + its sidecars (`confidence.json`, `ultimate.json`, provenance) act as the RAID parity block: enough structure survives to reconstruct the capability.

### Quarantine: The Mandatory Trust Gate

There is **no fast path** around quarantine for anything arriving from outside direct local control:

- Peer genomes (federation)
- Genomes received via `LineageShareGrant`
- Any externally-sourced material

Quarantine runs a battery of validators (schema, size, no executables, prompt sanity, signatures) plus the **LineageImmuneRule** (see below). Only approved entries can affect the live pool or be used in healing/evolution.

Audit is append-only JSONL. Operator sees `agentdrive quarantine list`, `approve`, `reject`, `hold`.

---

## The Lineage Enhancements: Genome Immunity and DNA Evolution Cycles

These are the "new" components that layer deeper biological and Lineage-Engine-inspired thinking onto the core Drive/quarantine/reconciliation model. They are intentionally opt-in advanced extensions in many paths but are wired into default quarantine rules.

### Genome Immunity (`agentdrive.dna.lineage_immune`)

`LineageImmuneSystem` + `GenomeThreatAssessment` + `ThreatLevel` (BENIGN / SUSPICIOUS / HOSTILE / CRITICAL).

It brings adaptive, memory-bearing defense:

- **Innate/structural layer**: manifest validity, prompt-injection signatures.
- **Adaptive/memory layer**: matches against previously seen hostile patterns (content hashes that triggered hostile/critical before are remembered and escalate).
- **Self-tolerance / lineage trust layer**: boosts confidence for trusted lineages (explicit `known_good_lineages` + real ancestry graph walking + quality of inherited DNA). Suspicious content from a trusted lineage is still flagged but handled with nuance ("trusted_lineage_but_suspicious_content").
- **Incident logging + learning**: every assessment is recorded (last 500 kept). Hostile patterns are promoted into long-term memory.

Integrated into quarantine as `LineageImmuneRule`. It can cause outright rejection (HOSTILE/CRITICAL), longer quarantine, operator review, or "accept with flag."

**Why it matters**: Literature on memory poisoning (e.g., MemoryGraft-style attacks achieving 95%+ success) shows that *any* cross-agent memory channel is an attack surface. Biology evolved CRISPR specifically as an immune system against horizontal gene transfer. AgentDrive's immune layer is the practical equivalent: it makes sideways and external ingestion safe enough to be useful.

### DNA Evolution Cycles (`agentdrive.evolution.lineage_dna`)

`LineageDNAEvolver` + `DNACycleResult`.

Provides a structured **Research → Evaluate → Evolve** skeleton (native sources first, defensive) that can be driven by scanners, the evolutionary engine, or high-agency operators/ILOs via the GrokPatternLineageBridge.
Current depth is documented in the module and CLEANLINESS report.

- **Research phase**: Pulls from the genome's own reasoning patterns, AgentDrive's ReasoningEngine/PatternMemory, ledger entries, and crucially **ancestry/inheritance history** (what worked for direct ancestors). Can also integrate richer external sources (an operator's custom research index, etc.) via pluggable paths.
- **Evaluate phase**: Multi-signal (performance + fitness + immune response + emotional resonance signals). Produces `fitness_delta` and `immune_flags`.
- **Evolve phase**: Proposes and safely records/applies mutations when signals are strong and immune flags are absent. Bumps version, records provenance.

This scales single-agent "Lineage Engine" depth to swarm/ecology/population level inside AgentDrive.

**Why it matters**: It turns the Drive from a passive library into an active evolutionary organism. Individual excellence (deep reasoning on one lineage) becomes population-level selection pressure. The system doesn't just store what worked — it actively improves it using the same rich signals that made Lineage powerful, now grounded in real multi-agent DNA.

---

## The Complete Mental Model

- **RAID for capability**: Genomes are the redundant, reconstructible blocks. Quarantine + immune system are the error detection and containment. Reconciliation/healing is the rebuild process. Snapshots are the point-in-time backups of the entire array state.
- **Capability survival over process survival**: The death of an agent is no longer the death of its hard-won knowledge. The pool (across tiers) carries the parity.
- **Evolutionary improvement as default**: Every run is potentially a mutation proposal or validation run. The fleet compounds rather than degrades.
- **Stigmergy at swarm scale**: Siblings coordinate through shared state without central orchestration for every exchange.
- **Lineage as narrative continuity**: DNA Drives give agents "ancestors with experience." The Avatar / genetic / family-grimoire metaphor is intentional and load-bearing.
- **Safe contagion via explicit gates**: Biology's lesson (vertical high-fidelity + gated horizontal transfer behind context/immune checks) is directly applied. `LineageShareGrant`s + mandatory quarantine + immune assessment are the gates.
- **Local-first sovereignty**: The operator holds the keys (Ed25519), the disk, and the policy. No vendor cloud owns the evolutionary history of the agents. Federation is pull-only and always gated.

**Provenance is non-negotiable everywhere.** Anonymous shared state was rejected by the blackboard systems of the 1970s–80s for good reason; every read or inheritance path carries source, grant (if any), depth, and confidence signals.

---

## Practical Surfaces

- **CLI**: `agentdrive drive status`, `genomes list`, `quarantine list/approve`, `dna ...` (emerging), snapshot controls.
- **TUI**: Rich dashboard over Drives, swarms, DNA lineage, quarantine, reconciliation activity.
- **Web**: FastAPI surface at `http://127.0.0.1:8421` (auth, capabilities, peers, snapshots, etc.).
- **Python**: `Harness`, `AgentDrive` / `get_default_drive()`, `DNADrive`, `Quarantine`, `LineageImmuneSystem`, `LineageDNAEvolver`, capability minting.
- **Adapters**: Sidecar integration for Grok Build, Claude Code, Codex, MCP, custom orchestrators.

See `README.md`, `docs/INTEGRATION.md`, `GENOME-SPEC.md`, `docs/RECOVERY.md`, `docs/AGENTDRIVE-V2-INHERITANCE.md`, and the source under `src/agentdrive/dna/`, `evolution/`, `quarantine.py`, `reconciliation.py`, `harness/`, and `drive/` for implementation details and extension points.

---

## Invariants Worth Protecting

1. Content addressing + immutability of Genomes.
2. Mandatory quarantine (no bypass) for all non-local material.
3. Forward-only DNA by default + explicit, auditable, TTL-bounded, quota-limited grants for sideways flow.
4. Full provenance and attribution on every Genome and inheritance action.
5. Local-first: the operator's machine and keys are the root of trust and durability.
6. Separation of working memory tiers (Personal/Swarm) from inheritable memory (DNA).

Violating any of these collapses the safety or evolutionary properties that justify the "RAID for AI agents" claim.

---

**AgentDrive turns every agent failure from a reset into a reconstruction and every successful run into heritable, improvable family knowledge — all under the operator's complete control.**

This is the architecture. This is the bet. This is how agents stop being disposable and start becoming a compounding, surviving intelligence ecosystem.

---

*Document version: 2026-05 (aligned with v2 Milestone 2 implementation). For the latest code truths, consult the source and tests (especially `test_dna_drive.py`, `test_shared_swarm_drive.py`, `test_quarantine.py`, `test_reconciliation.py`, and `examples/10_lineage_integration_test.py`).*