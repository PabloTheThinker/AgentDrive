# AgentDrive v2 — Three-Tier Topology, DNA Inheritance, and Snapshot Backup

> **Status:** approved (2026-05-24). All open questions resolved by Pablo. Milestone 2 work cleared to start.
>
> **Decided independently by two sources:** Codex consult (implementation cost) and an academic + production literature survey (multi-agent systems, MARL, biology). Both converged on the same answer. The supporting evidence is in [`AGENTDRIVE-V2-INHERITANCE-RESEARCH.md`](AGENTDRIVE-V2-INHERITANCE-RESEARCH.md).
>
> Companion docs: [`AGENTDRIVE-V2.md`](AGENTDRIVE-V2.md) (overall v2 architecture), [`AGENTDRIVE-PROGRESS.md`](AGENTDRIVE-PROGRESS.md) (OSS-readiness audit).

---

## The decision

AgentDrive moves to a **three-tier Drive topology**:

```
              ┌─────────────────────────────────────────┐
              │   DNA Drive (ancestral, inheritable)     │
              │   forward-only DAG + opt-in lineage_share│
              └────────────┬────────────────────────────┘
                           │ inherits forward
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼─────┐       ┌────▼─────┐       ┌────▼─────┐
   │ Agent A  │       │ Agent B  │       │ Agent C  │
   │ Personal │       │ Personal │       │ Personal │   private memory
   │ Drive    │       │ Drive    │       │ Drive    │   (parent agent only)
   └────┬─────┘       └──────────┘       └──────────┘
        │ spawns
   ┌────▼──────────────────────────────────┐
   │  Swarm Drive (shared by siblings)     │
   │  ┌─────────┐ ┌─────────┐ ┌─────────┐  │
   │  │ sub-a/  │ │ sub-b/  │ │ sub-c/  │  │   namespaced writes
   │  └─────────┘ └─────────┘ └─────────┘  │   free reads across siblings
   └───────────────────────────────────────┘
```

**The DNA Drive flows forward only by default. Sideways flow across cousin agents from different swarms is allowed only through an explicit, signed, scoped, TTL-bounded `lineage_share` grant.**

Both Codex and the literature survey reached this conclusion independently. The implementation cost ratio is roughly **forward-only ≈ 200 LOC over 1 day; full unrestricted sideways graph ≈ 800–1500 LOC over 2–3 weeks**. The hybrid (forward-only + opt-in grants) sits near forward-only's cost while keeping the door open for the powerful cross-pollination Pablo originally asked about.

---

## Why three tiers, not four

The earlier v2 architecture proposed a four-tier sync chain: private scratch → swarm Drive → agent Drive → peer Drive. That was correct as a *sync* model but conflated two different concerns:

- **Working memory** (Personal + Swarm Drives) — what an agent and its siblings are doing right now.
- **Inherited memory** (DNA Drive) — what an agent's lineage already proved works.

These are different shapes. Working memory is hot, mutable in aggregate, swarm-scoped. Inherited memory is cold, immutable, lineage-scoped. They deserve to be separate primitives, not stops on the same conveyor belt.

The peer federation tier from the v2 doc still exists — it's a cross-instance concern (different humans' AgentDrives sharing through quarantine) and lives orthogonal to the three intra-instance tiers above.

---

## The three tiers in detail

### Personal Drive

**Owner:** one parent agent.

**Contents:** that agent's private memory — its own working notes, in-progress reasoning patterns, half-formed Genomes that haven't earned promotion. The equivalent of a person's notebook.

**Access:** read/write by the owning agent only. Sub-agents the parent spawns do **not** see this Drive.

**Lifecycle:** lives as long as the agent. Promoted Genomes (those marked worth keeping) get published to the DNA Drive at session end or on explicit promotion.

**Path:** `~/.agentdrive/agents/<agent_id>/drive/`

### Swarm Drive

**Owner:** the swarm itself.

**Contents:** everything the swarm's sub-agents are currently learning together. Sibling sub-agents read freely from each other's namespaced writes — this is the "we work together" experience pool Pablo described.

**Access:**
- Sub-agents in the swarm: read all, write to own `<sub_id>/` namespace.
- Parent agent (the swarm orchestrator): read all, write to `parent/` namespace.
- Other agents: no access by default.

**Lifecycle:** lives as long as the swarm runs. Promoted Genomes flow to the parent's Personal Drive (immediate handoff) or to the parent's DNA Drive (long-term inheritance for future descendants).

**Path:** `~/.agentdrive/swarms/<swarm_id>/drive/`

**Conflict model:** CRDT counters for commutative writes (frequency tables, monotonic scores), conflict-copy preservation for non-commutative writes (contradicting frameworks). Inherited from v2 Milestone 4 plan.

### DNA Drive

**Owner:** an agent's lineage. A single agent has *one* DNA Drive that holds Genomes it has inherited from its direct ancestors, plus Genomes it has earned that will pass to its descendants.

**Contents:** proven, fitness-tested Genomes only. This is what makes an agent born with experience — *"I have experience doing this because my parents had experience doing this."*

**Access — the load-bearing part:**

- **Forward-only inheritance (default).** A descendant agent reads from its direct ancestors' DNA Drives by walking the parent chain. Implementation: an ancestry closure table `(ancestor_id, descendant_id, depth)` in SQLite; reads use a recursive CTE. Queries are milliseconds at 10k agents.
- **Permanent access, no decay.** Once a Genome is in the lineage, descendants always have access. Inherited DNA becomes a *chapter* in the line — agents can reach back to their ancestors at any time, the way the Avatar reaches into the line of past lives. This is the mental model: continuous connection back to the core, growing outward like Obsidian's graph.
- **Sideways `lineage_share` grants (opt-in).** An agent can issue a signed grant of the form:
  ```
  lineage_share {
    issuer:    <agent_id>          # who's granting access
    grantee:   <agent_id | "descendants-of:<ancestor_id>">
    scope:     <Genome filter — by topic, eval-threshold, content-hash list>
    direction: one-way             # always; grants don't auto-reciprocate
    ttl:       <duration>          # forces re-issue; revocation via expiry
    reducer:   <how grantee should merge with own DNA — append | overwrite | prefer-higher-eval>
    signature: <issuer's signing key>
  }
  ```
  Grants are first-class objects. Listable, auditable, revocable, expirable. Granted DNA is also permanent for the grantee — once received it stays in the lineage chapter.

**Path:** `~/.agentdrive/dna/<agent_id>/drive/` plus a shared `~/.agentdrive/dna/_ancestry.db` SQLite closure table.

**Cycle handling:** forbidden by construction. An agent can only declare parents from agents that already exist (timestamp invariant `created_at(parent) < created_at(child)`). Ancestry becomes a DAG automatically.

---

## What goes where

| Genome lifecycle stage | Tier | Visible to |
|---|---|---|
| Sub-agent in-flight scratch | Swarm Drive `<sub_id>/` | siblings + parent |
| Sub-agent's polished output | Swarm Drive (promoted via signed promotion Genome) | siblings + parent |
| Parent's working memory | Personal Drive | parent only |
| Parent's proven patterns this session | Personal Drive → promotion → DNA Drive | parent now; future descendants on promotion |
| Inherited from grandparent | DNA Drive (read-only mirror via ancestry walk) | this agent's descendants automatically |
| Inherited from a cousin via `lineage_share` | DNA Drive (read-only mirror, marked with grant provenance) | this agent only; does NOT propagate to descendants without re-grant |

The last row is the most important property: **borrowed cousin DNA does not auto-propagate.** It stays scoped to the grantee. This prevents one good grant from accidentally seeding the entire descendant tree with cross-lineage data the descendants never asked for.

**Note on decay:** there is no decay function. Direct-line ancestral DNA and cousin-granted DNA are both permanent once received. The receiving agent always retains access until they explicitly evict an entry. This matches the lived mental model — an agent's ancestors don't fade away over time; they remain accessible the way the Avatar's past lives remain accessible. Grant *issuance* still has a TTL (the issuer can stop granting NEW access after expiry), but data already received is the grantee's.

---

## Why this shape (the convergent evidence)

Both Codex's engineering analysis and the literature survey reached forward-only-by-default through completely different reasoning paths.

### From the production frameworks

- **OpenAI Swarm** is deliberately stateless — they punted on the shared-state problem entirely.
- **AutoGen** uses `GroupChat` as a shared conversation log (effectively a per-swarm blackboard). No inheritance.
- **CrewAI** has hierarchical memory paths like `/crew/research/agent/analyst` — that's essentially our Personal + Swarm tiers already. No cross-crew inheritance.
- **LangGraph** forces every shared-state field to declare a **reducer** (merge function) explicitly. This is the engineering lesson — any shared mutable state needs a declared conflict-resolution semantic.
- **ROS 2 multi-robot SLAM**: maps are merged only at semantically meaningful boundaries (loop closures). Learned policies are *replicated*, not evolved in-fleet. The robotics community's verdict matches Codex's: **sharing is opt-in, structured, reconciled.**

### From MARL

- **AlphaStar's league** is the closest production analog to Pablo's question. Verdict: **forward-only weight inheritance, sideways-everyone adversarial exposure.** Cousins influence each other's gradient, never each other's parameters.
- **PBT (Population-Based Training)** copies weights laterally within a generation, but training-time, not deployment-time, and only via competitive selection.

### From biology

- Vertical inheritance is the default in eukaryotes — high fidelity, perfect provenance.
- **Horizontal gene transfer (HGT)** in bacteria is the primary driver of antibiotic resistance — and bacteria evolved **CRISPR specifically as an immune system against HGT**. Sideways flow is dangerous; nature defends against it.
- Bacteria **gate HGT behind quorum sensing**: vertical when isolated, horizontal only when context warrants. Same shape as our proposed `lineage_share` grants.

### From the failure mode literature

- **MemoryGraft** (arXiv 2512.16962): poisoned memories injected with up to 95% success, triggering attacker-intended behavior in 89% of retrievals. **Any sideways memory channel is an attack channel.** Defense pattern: explicit, scoped, signed, revocable.
- The blackboard architectures of the '70s–'80s died from anonymous shared state being intractable in (a) conflict resolution, (b) observability, (c) security. Linda died of the same. We will not repeat their mistake.

### From the implementation cost

- Forward-only DAG: ~200 LOC, ~1 day.
- Forward-only + signed `lineage_share` grants: ~400 LOC, ~2 days (Codex's estimate based on a closure-table + grant-table schema).
- Full unrestricted sideways graph: 800–1500 LOC, 5–10 engineer-days for prototype, 2–3 weeks for production-grade (closure-table correctness under multi-parent inserts, blast-radius mitigation, cap revocation semantics).

The hybrid sits at 2× forward-only cost, not 4–7× full-sideways cost. That's the right place to spend.

---

## Memory poisoning defense (mandatory)

Because the literature is unambiguous that any cross-agent memory channel is an attack vector, the design assumes adversarial conditions from day one:

1. **No auto-activation of pulled Genomes.** Inherited or granted Genomes land in a *quarantine-equivalent* pool until the receiving agent's own evaluation gates them in. Reuses the existing `quarantine.py` machinery.
2. **Eval gating.** Inherited Genomes carry their original `evaluation_score`. The receiving agent applies a configurable minimum threshold (default ≥0.7) before any Genome enters its active pool.
3. **Provenance is mandatory.** Every read returns the source agent ID, the grant ID (if sideways), and the ancestry path (if forward). No anonymous reads. Lifted directly from KQML's verdict that the field rejected anonymous shared state for a reason.
4. **Decay for borrowed DNA.** Cousin-granted Genomes have a TTL. Direct-line ancestral Genomes do not decay. This mirrors the pheromone lesson — sideways shared state should be lossy by design.
5. **Quota per issuer.** A single agent cannot mint more than N `lineage_share` grants per window. Prevents Sybil flooding.

---

## Snapshot Backup (the recovery layer)

Each agent's full Drive state — Personal Drive, its slice of the DNA Drive, its in-flight Swarm Drive — is **snapshotted every 6 hours by default** into a separate, point-in-time backup tree. The backup is what brings an agent back if its main Drive is corrupted, accidentally deleted, or attacked.

### Why point-in-time, not continuous mirror

Two reasons:

1. **Recovery semantics.** Point-in-time snapshots let an operator say "restore from the snapshot taken at 14:00 yesterday." A continuous mirror would faithfully replicate corruption or deletion the instant it happens — the backup is just as gone as the source.
2. **Storage cost.** Snapshots dedup against the content-addressed object store from Milestone 1. A 6-hour snapshot is mostly pointer updates; only Genomes added in the window cost new bytes. Continuous mirroring doubles the write path for no recovery benefit.

### Default cadence

**Every 6 hours.** Empirically a reasonable trade between "low storage overhead" and "small enough loss window if disaster strikes." Configurable via the localhost control UI (see below).

### Layout

```
~/.agentdrive/backups/
├── <agent_id>/
│   ├── 2026-05-24T18:00:00Z/
│   │   ├── manifest.json            # what's in this snapshot + the content hashes it references
│   │   ├── personal_pointer         # pointer to object hashes in the shared content store
│   │   ├── dna_pointer
│   │   └── swarm_pointer (if applicable)
│   ├── 2026-05-25T00:00:00Z/
│   └── ...
└── _retention.json                  # rolling policy: keep N hourly, N daily, N weekly
```

Snapshots are pointer-only — they reference the same `objects/<aa>/<rest>.json` content store. Restoring a snapshot rebuilds the agent's Drive views from the pointer manifests; no Genome bytes are duplicated.

### Localhost control UI

A small local-only web UI at `http://localhost:8420/` (configurable port) gives the operator:

- View / restore any snapshot
- Adjust cadence (per-agent or global)
- Pin or expire individual snapshots
- Trigger an immediate on-demand snapshot
- See retention storage usage

The UI is **localhost-bound by default** (no external network listener). Operators on multi-tenant or remote-managed setups can opt in to bind a different interface, but the default is loopback-only.

### Backup vs DNA Drive — different concerns

- **DNA Drive** = "memory I inherited and earned that my descendants will see."
- **Snapshot Backup** = "a recoverable copy of my entire state at a point in time, including my Personal Drive and in-flight Swarm work."

They have different lifecycles, different access models, and different failure modes. The DNA Drive is *narrative continuity*; the Snapshot Backup is *operational safety*.

---

## Implementation plan

This proposal restructures `AGENTDRIVE-V2.md` Milestone 2 from "shared swarm Drive" to "three-tier topology." Concretely:

### Milestone 2a (was: shared swarm Drive)

- Fix the `SwarmDriveManager.get_or_create_pool` bug (drive_path not wired through). Surfaced by `examples/03_swarm.py` in the hygiene PR.
- Collapse per-(swarm, sub-agent) Drives into one per-swarm Drive at `~/.agentdrive/swarms/<swarm_id>/drive/`.
- Add per-sub-agent namespacing via `manifest.author = "sub:<id>"`.
- Flip `SwarmDrivePolicy.isolation_level` default from `"subagent"` to `"swarm"`. Keep `"subagent"` as opt-in for adversarial / red-team agents.

### Milestone 2b (new: DNA Drive — forward-only)

- Add `agentdrive.dna` module: `Ancestry`, `AncestryClosure` (SQLite-backed), `DNADrive` class wrapping the existing `ContentStore`.
- Define `agent.parents: list[str]` on agent identity records (lives in `~/.agentdrive/agents/<id>/manifest.json`).
- Implement closure-table maintenance: insert (ancestor, descendant, depth) rows on agent creation. Use Codex's recursive CTE query for reads.
- Add `Harness.pull_inherited_dna(top_k)` — walks the ancestry, surfaces the same scored format as `pull_relevant_dna`.

### Milestone 2c (new: `lineage_share` grants)

- Add `agentdrive.dna.grants` module: `LineageShareGrant` dataclass, signing/verification using Ed25519 from `cryptography` (avoid pulling gopenpgp this milestone — too much for one step).
- `~/.agentdrive/dna/_grants.db` SQLite table: `(grant_id, issuer, grantee, scope, ttl, reducer, signature, revoked)`.
- Quarantine integration: granted Genomes land in the existing quarantine pool until eval-gated.
- Quota enforcement: per-issuer rate limits in the grants table.

### Milestone 2 success criteria

- Two sub-agents in the same swarm write Genomes; each can query and pull the other's work without explicit cross-config.
- A new agent spawned with `parents=[agent_a, agent_b]` automatically inherits both ancestral DNA Drives, eval-gated.
- A grant from cousin C to cousin D allows D to pull a scoped subset of C's DNA; D's descendants do not automatically inherit it unless D re-grants.
- The grant's TTL fires; D loses access; no further reads succeed.
- Memory-poisoning test: a Genome with score 0.3 from a granted source is blocked by D's eval gate.

### What slips

The earlier v2 doc had Milestones 2 (shared Drive), 3 (caps), 4 (CRDTs), 5 (trust circle), 6 (promotion). This proposal **expands Milestone 2** into three sub-cuts and pulls forward the parts of Milestone 3 (caps as `lineage_share` grants) and Milestone 4 (CRDTs in the Swarm Drive) that are load-bearing for sibling learning. Net: the v2 sequence is the same; we just relabel the work and lock the inheritance model now so caps in M3 design cleanly around it.

---

## Decisions locked (2026-05-24, by Pablo)

| Question | Decision | Reasoning |
|---|---|---|
| Genome shape (gene-sized vs memory-sized) | **My call when M2 code starts.** Keep current shape (framework + reasoning + tools + evals) for v2; revisit if mix-and-match becomes the bottleneck. | Deferred to implementation. The current shape works for now and the recombinability question can be answered with real usage data. |
| Default eval threshold for inherited DNA | **My call when M2 code starts.** Likely ≥0.7 for cross-source pulls, ≥0.0 (no gate) for direct-line ancestral. | Direct ancestors are trusted by default — they're you, earlier. Cross-source needs the gate. |
| Should Personal Drive be readable by sub-agents? | **No.** Personal Drive stays private to its owning agent. | Sub-agents see what's in the Swarm Drive and what their parent explicitly publishes — not the parent's raw working memory. Separation of concerns. |
| Decay function for borrowed cousin DNA | **No decay.** Inherited DNA is permanent. Becomes a chapter in the lineage, always accessible. | Avatar mental model. Once received, it's yours. Grant *issuance* has a TTL (issuer can stop granting NEW access) but data already received stays. |
| Backup mode (continuous mirror vs point-in-time snapshots) | **Point-in-time snapshots, 6h cadence by default, localhost UI for operator control.** | Continuous mirror replicates corruption instantly; snapshots let you actually recover. 6h is the empirical sweet spot. |

All design questions resolved. Milestone 2 PR series cleared to start.
