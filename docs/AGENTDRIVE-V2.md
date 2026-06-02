# AgentDrive v2 — Architecture

> **Status:** proposal (2026-05-24). Not yet implemented.
> **Decision owner:** the project maintainer.
> **Implementation owner:** the runtime, once approved.

The current AgentDrive (v1) is a local-first directory per agent, with policy-gated upward sync from sub-agents to parents. It works. It is also too small. The brief for v2 came from a single observation: *sub-agents should learn from each other, not just bubble up to a parent.* That implies shared memory across siblings, and shared memory across agents implies the entire mental model of a "Drive."

This document maps how mature cloud-drive systems actually solve the same problems, picks the patterns that translate to multi-agent shared memory, names the ones that don't, and commits to a build order.

The research underneath this proposal is in [`AGENTDRIVE-V2-RESEARCH.md`](AGENTDRIVE-V2-RESEARCH.md) — every claim about ProtonDrive / Google Drive / Dropbox / iCloud / Syncthing / Resilio / Tahoe-LAFS in this doc is cited there.

---

## The load-bearing decision

**Every Genome in AgentDrive v2 is content-addressed and immutable.**

A Genome's ID is the SHA-256 of its canonical JSON. You don't update a Genome; you publish a new one that supersedes it by reference. This single choice cascades into everything else:

- **Dedup is free.** Two sub-agents that independently discover the same reasoning pattern store it once.
- **Versioning is free.** A "newer version" is a new content hash that names the old one in its `supersedes` field. The full lineage is a DAG, walkable in both directions.
- **Provenance is cryptographic.** "Agent B's outcome cites Genome `sha256:abcd…`" is verifiable forever, regardless of how the citing agent migrates or dies.
- **Capability URIs become possible.** If the address of a thing is its hash, then a capability is `agent:read:sha256:abcd…` — possession of the cap is the permission. No identity layer required.
- **Conflict-preservation is the default.** Two contradicting Genomes are two different hashes. Neither overwrites the other. Reconciliation becomes a *later* decision by a *higher-tier* agent, not a race condition.
- **Garbage collection becomes explicit.** Reference-counted, with TTL on unreferenced Genomes. No user-facing "trash."

The alternative — mutable records, ACLs, last-write-wins — buys us in-place edits and smaller footprint, at the cost of inheriting Google Docs' OT complexity and Google Drive's recurring sharing-link leaks. For a system where contradicting agent outputs are *first-class data*, immutability is the correct call.

**Nothing else in this doc can be designed coherently until this decision is locked.**

---

## v2 architecture in seven moves

Each move is a pattern lifted from a production system, adapted for agent-memory semantics.

### 1. Content-addressed Genome objects
*Source: Dropbox Magic Pocket, Tahoe-LAFS.*

Genome ID = `sha256(canonical_json(genome))`. The on-disk path becomes `objects/<prefix>/<hash>.json` (Git-style sharding). The current Genome directory layout migrates to this — the `manifest.id` field becomes the content hash, the human-readable name moves to `manifest.name`.

Mutable state (counters, indices, last-seen) lives in a separate layer (move #6, CRDT counters).

### 2. Capability URIs as the access primitive
*Source: Tahoe-LAFS, Resilio key derivation.*

Replace the current `SwarmDrivePolicy` ACL model with capability strings:

```
drive:read:sha256:abcd…           # read one Genome
drive:read:swarm:demo-2026-05/*   # read everything in a swarm
drive:write:swarm:demo-2026-05    # contribute to that swarm
drive:exec:agent:planner-7        # impersonate (parent → child handoff)
```

A capability is a signed token. Possession of the cap is authorization. No identity layer. When a parent agent spawns a sub-agent, it mints a *strict subset* of its own caps and hands them over via the spawn channel. This is how a sub-agent gets to read its siblings' work without any explicit ACL grant — the parent simply hands every sibling the same swarm-read cap.

### 3. Key/cap derivation hierarchy
*Source: Proton's key-tree-per-share, Resilio's RW→RO derivation.*

The swarm's root cap deterministically derives per-sub-agent caps; per-sub-agent caps derive per-Genome caps. A read-cap is derivable from a write-cap. Revocation becomes "rotate the key at the right level" — kill one sub-agent's whole pocket, or kill a single Genome, without touching anything else.

This is the cryptographic spine that makes the next two moves safe.

### 4. The shared swarm Drive (the core sibling-learning primitive)
*Source: ProtonDrive's share model, generalized.*

Today: each `(swarm, sub-agent)` pair gets its own isolated Drive at `~/.agentdrive/swarms/<swarm>/<sub>/drive/`.

v2: each *swarm* gets a single Drive at `~/.agentdrive/swarms/<swarm>/drive/`. Sub-agents namespace their *writes* under `objects/<hash>.json` with a `manifest.author = "sub:<id>"` attribution field. Reads are unrestricted across the swarm. Sibling learning is automatic — they're reading from the same object store.

`SwarmDrivePolicy.isolation_level` flips its default from `"subagent"` to `"swarm"`. `sibling_sharing` becomes `"read"` by default. The `"subagent"` mode stays, opt-in, for the small set of cases where you genuinely need air-gapped children (red-team agents, adversarial probes).

Each sub-agent can still keep a *private scratch* under `objects/private/<sub>/...` for half-formed work, with explicit promotion to the shared store when it's worth a sibling seeing.

### 5. Trust circle for cross-device coherence
*Source: iCloud Keychain syncing circle.*

When a user runs AgentDrive on laptop + server + phone, devices form a P-384 trust circle. New devices join via a signed voucher from an existing trusted device. Only circle members can sync agent Drives. There is no central authority — Apple's design works for us because we share Apple's constraints (private user data, no central truth, multi-device coherence).

Loss of all circle members = loss of swarm memory. This is the correct semantics for a private agent OS; we don't want a recovery backdoor.

### 6. CRDT counters where commutativity exists; conflict copies everywhere else
*Source: Syncthing's version vectors, Google Docs' OT (negative example).*

A small set of Genome types are genuinely commutative:
- frequency tables ("I observed pattern X N times")
- monotonic counters ("highest confidence score seen for hash H")
- grow-only sets ("hashes I've successfully executed")

These get a `merge_strategy: crdt-counter | crdt-set` field on the Genome schema and merge automatically across siblings with no human intervention.

Everything else (frameworks, reasoning patterns, narrative outcomes) is not commutative. When two sub-agents emit contradicting Genomes touching the same upward-sync target, both are stored with `conflict-<vector>-<author>` suffixes and surfaced to a higher-tier reconciler agent. **A conflict is a prompt for synthesis, not an error.**

OT-style server-linearized merge is explicitly off the table — it assumes a central authority and live network, neither of which match agent-spawn reality.

### 7. Tiered sync with explicit promotion gates
*Source: generalization of ProtonDrive's share-as-access-card.*

Four tiers, each a different cap level:

```
private scratch   →   shared swarm Drive   →   agent Drive   →   peer Drive
(sub-agent only)      (siblings + parent)      (whole agent)      (other humans)
```

Promotion is a deliberate, signed action: a sub-agent doesn't *bubble* its work upward, it *publishes* a promotion Genome that says "I claim hash H is worth lifting to tier T, here's why." A reviewer (human or agent) approves the promotion, which is recorded as a separate Genome. The current `auto_ingest_from_children=True` becomes an *auto-approve policy* the user installs, not a built-in behavior.

The existing peer federation (`peers.py`) is already this pattern at the top tier — quarantine-gated, signed when the trust store ships. v2 makes the same model recursive all the way down to the sub-agent level.

---

## What we keep that doesn't match the cloud-drive analogy

- **Genomes, not files.** AgentDrive's atom is structured: a manifest, a framework, optional reasoning patterns, optional outcome records. The cloud drives store opaque bytes; we store typed schemas. This is a strength — it lets us do semantic dedup (two slightly-different phrasings of the same insight collapse to one Genome) and semantic conflict resolution (two contradicting plans can be diffed, not just stored side-by-side).
- **The Harness.** Cloud drives are passive storage. Our Drive is active — the Harness runs a reconciliation routine on every task that pulls relevant DNA, records outcomes, and proposes new Genomes. Nothing in ProtonDrive does this. The Harness *uses* the cap system but is its own thing.

---

## What we explicitly do not take

| Pattern | From | Why we skip |
|---|---|---|
| Last-write-wins conflict resolution | Google Drive (binary files) | A sub-agent's hard-won insight must never be silently overwritten. Two contradicting Genomes are data about the world's contradiction, not a bug. |
| Operational Transform | Google Docs | OT requires a central authority to linearize ops. Sub-agents are spawned processes that may run offline, die early, and emit out-of-order. CRDTs where possible, conflict copies everywhere else. |
| Trash-as-undelete with quota cost | ProtonDrive | A sub-agent may emit thousands of Genomes/hour. Treating "delete" as "kept but charged against quota" produces unbounded growth. We use reference-counted GC with TTL on orphans — no user-facing trash. |
| Server-mediated revocation | Google Drive | Works only because Google holds the keys. We're local-first; revocation has to be cryptographic (key rotation at the right tier). |
| Public sharing links anyone-with-the-link | All consumer drives | Recurring data-leak vector. AgentDrive peer shares require explicit peer trust (`peers.py`) plus quarantine gating. |

---

## Feature parity table — the v2 surface

| Cloud-drive feature | AgentDrive v2 equivalent | Status |
|---|---|---|
| Local-first storage | Drive directory on disk | ✅ v1 |
| End-to-end encryption | Drive encryption-at-rest with per-tier keys | ❌ ship in v2 |
| File versioning | Genome supersedes-DAG via content hash | ❌ ship in v2 (free from move #1) |
| Trash / undelete | Reference-counted GC + TTL tombstones | ❌ ship in v2 |
| Block dedup | Content-addressed Genome objects | ❌ ship in v2 (free from move #1) |
| Sharing with role | Capability URIs (read / write / exec) | ❌ ship in v2 (move #2) |
| Sharing under E2EE | Key-derivation tree per swarm | ❌ ship in v2 (move #3) |
| Real-time collaboration | Shared swarm Drive + CRDT counters | ❌ ship in v2 (moves #4, #6) |
| Conflict resolution | CRDTs commutative; conflict copies elsewhere | ❌ ship in v2 (move #6) |
| Multi-device sync | iCloud-style P-384 trust circle | ❌ ship in v2 (move #5) |
| Web view | Out of scope for v2 | — |

---

## v2 build order

Each milestone is shippable on its own and unlocks the next.

**Milestone 1 — Content-addressed Genome objects (move #1).**
Migrate the on-disk layout to `objects/<prefix>/<hash>.json`. Rewrite Genome ID generation. Add a `supersedes` field to manifests. Add a tiny migration tool that walks the existing Drive and rewrites IDs. **Outcome:** dedup and versioning come online; nothing else in the architecture changes yet.

**Milestone 2 — Shared swarm Drive (move #4).**
Collapse the per-(swarm, sub-agent) directory to one per-swarm directory. Update `swarm_manager` to point siblings at the same Drive. Flip `SwarmDrivePolicy` defaults. Keep `isolation_level="subagent"` available for opt-in air-gapping. **Outcome:** sibling learning works; this is the visible core requested sibling-learning change.

**Milestone 3 — Capability URIs + key-derivation tree (moves #2, #3).**
Implement cap minting/verification. Derive per-sub-agent caps from swarm caps. Spawn channel hands caps to children. Rotate-at-tier revocation. **Outcome:** the security model becomes real; you can hand a sub-agent narrow access without ACL bookkeeping.

**Milestone 4 — CRDT counters + conflict copies (move #6).**
Add `merge_strategy` to the Genome schema. Implement counter / set CRDTs for the small commutative set. Wire conflict-copy emission for everything else. Surface conflicts to a `conflicts/` index. **Outcome:** sub-agents writing to the same shared swarm Drive stop stepping on each other.

**Milestone 5 — Trust circle + cross-device sync (move #5).**
P-384 device identity. Voucher-based circle join. Sync protocol between circle members. **Outcome:** AgentDrive runs coherently across laptop + server + phone without any central authority.

**Milestone 6 — Promotion gates + tiered sync (move #7).**
Formalize the four-tier promotion flow. Replace `auto_ingest_from_children=True` with explicit promotion Genomes + auto-approve policies. **Outcome:** every cross-tier transition is auditable, revocable, and a first-class object.

After Milestone 6, AgentDrive is structurally equivalent to a privacy-first cloud drive, except its atoms are typed Genomes, its sharing is capability-based, and its conflict model preserves contradiction instead of resolving it.

---

## The first cut

**Start with Milestone 1.** Content-addressing is the load-bearing decision; every later move presumes it. The migration is mechanical (the engine work has already been done — Genome models, registry, ingest log all exist). One PR. Tests should stay green. Once it ships, Milestone 2 (the visible "shared swarm Drive" change) becomes a 1-day diff because the object store underneath no longer cares which sub-agent wrote which Genome.

The diff to start tomorrow:
1. Add `agentdrive.drive.content_address` module — canonical JSON, sha256 hashing, sharded path.
2. Update `Genome.save()` to write to `objects/<prefix>/<hash>.json`, fall back to legacy layout on read.
3. Add `manifest.supersedes: list[str]` field.
4. Migration script: `agentdrive migrate v1-to-v2` walks existing Drives, rewrites layouts, preserves provenance.
5. Tests for: dedup (two identical Genomes produce one object), supersedes chains, migration idempotency.

That's the first concrete commit on the v2 path.
