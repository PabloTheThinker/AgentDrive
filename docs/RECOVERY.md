# Recovery — the AgentDrive healing loop

**Status:** reference doc. Describes behavior composed from modules
already shipped in the Agent Drive engine: `reconciliation`, `confidence`,
`inheritance`, `quarantine`, and the genome registry.

AgentDrive is RAID for AI agents. This doc is the deep dive on the
healing loop — how a dead agent is rebuilt from the surviving DNA in
the pool, step by step, mapped to the actual modules and events in the
codebase. See [`VISION.md`](../VISION.md) for framing and
[`README.md`](../README.md) for the engine + product split.

---

## 1. Failure modes — what counts as "agent death"

The healing loop fires on any of the following:

- **Crash.** The sub-agent process exits non-zero, segfaults, or is
  reaped by the OS. `SubagentDone` fires with `ok=False`.
- **Hung subprocess.** No `SubagentTokens` or `SubagentTool` event has
  arrived from the sub-agent within the configured deadline. The
  reconciliation pass notices the gap and treats the sub-agent as dead.
- **Missed deadline.** The sub-agent is still emitting, but the
  mission's overall budget — wall clock, token, or tool-call — was
  exceeded. The orchestrator marks the run failed.
- **Validation failure.** The sub-agent returned an output, but it did
  not satisfy the original genome's `evaluation_score` criteria.
- **Signature drift.** The output's structure or content no longer
  matches the genome's declared output contract. Common cause when a
  provider silently changes model behavior between calls.

All five terminate in the same place: a missing or failed sub-agent that
the operator's fleet was depending on.

## 2. The healing flow

Each step names the module and event that drive it.

### 2.1 Death detected → `ReconciliationRunner`

The background `ReconciliationRunner` (see
[`src/agentdrive/reconciliation.py`](../src/agentdrive/reconciliation.py)) runs
on its configured `interval_s` and on every `SubagentDone(ok=False)`.
When the run finishes, it emits `ReconciliationCompleted`. If anything
changed since the previous pass, it additionally emits
`ReconciliationDelta` with the new and updated genome ids. A dead
sub-agent shows up here as either a missing expected manifest or a
`SubagentDone(ok=False)` event that the runner consumes.

### 2.2 Recovery genomes pulled → `pool.query` + `ConfidenceRating`

The orchestrator calls `pool.query` against the task signature of the
dead work. The result set is filtered to genomes whose persisted
`ConfidenceRating.stars` is ≥ 3 (see
[`src/agentdrive/confidence.py`](../src/agentdrive/confidence.py)). Three stars
is the default eligibility floor for recovery work because it requires
both a real encounter history (≥ 25 encounters) and a real success rate
(≥ 75%) under the default `ConfidenceRule`. Operators can lower the
floor in `~/.agentdrive/settings.yaml` for non-critical fleets.

### 2.3 Repair swarm dispatched → three `SubagentSpawn` events

The top three matches are handed to three fresh sub-agents — one genome
per sub-agent. Each spawn fires a `SubagentSpawn` event carrying the
swarm id, sub-agent id, and the genome id being applied. The three run
in parallel under the same swarm scope so their pools live side by side
under `~/.agentdrive/swarms/<swarm_id>/<subagent_id>/`.

### 2.4 Outputs collected → `InheritanceManifest`

When each repair sub-agent finishes, it writes an `InheritanceManifest`
to `~/.agentdrive/inheritance/<swarm_id>/<subagent_id>.json` (see
[`src/agentdrive/inheritance.py`](../src/agentdrive/inheritance.py)). The
manifest enumerates: genomes pulled, genomes created (if the sub-agent
extracted any new DNA from its run), outcomes logged, and total
duration. `SubagentDone` fires; the inheritance hook automatically
loads the manifest.

### 2.5 Validation → scoring against the original genome's criteria

Each repair candidate's output is scored against the *original* genome's
`evaluation_score` contract. Candidates that fail validation are
flagged. Those that pass advance to approval.

### 2.6 Approval — `ConfidenceUpdated` or `quarantine.submit`

If any repair output passes validation:

- `ConfidenceUpdated` fires for the source genome (the one that died)
  and for each repair genome that contributed to a successful candidate.
  Stars are recomputed by `confidence.update` and the `confidence.json`
  sidecar is rewritten.
- The repair manifest is absorbed into the parent pool through
  `record_manifest` with `auto_absorb=True`, emitting `PoolIngest`
  events as each new genome lands.

If every candidate fails:

- The original task is wrapped and submitted via `quarantine.submit`
  with `source_peer="recovery:<task_id>"`. It lands in the quarantine
  ledger as `PENDING` for operator review and surfaces in
  `agentdrive quarantine list`. `QuarantineSubmitted` fires.

## 3. Genome-as-snapshot

The existing genome manifest plus its sidecar files act as the
equivalent of a RAID parity block:

| File                         | Role in recovery                             |
|------------------------------|----------------------------------------------|
| `manifest.json`              | Schema, version, framework, output contract  |
| `confidence.json`            | Trust signal — eligibility for recovery work |
| `ultimate.json` (if present) | Promotion marker — top-tier genomes          |
| Provenance + improvement log | Lineage and `score_delta` history            |

Together they carry enough information to rebuild lost capability
without needing the original process, the original prompt, or the
original tool state. A genome is, intentionally, a snapshot of *what
the work looked like when it worked*.

## 4. Cross-instance recovery

When the local pool does not contain a viable ≥3-star match, the
`PeerRegistry` (see [`src/agentdrive/peers.py`](../src/agentdrive/peers.py)) is
consulted. The registry walks each trusted peer through its matching
`PeerAdapter` and collects candidate genome directories. Every single
candidate routes through `quarantine.submit` — there is no fast path
for "trusted" peers. The quarantine validators (`SchemaValid`,
`SizeLimit`, `NoExecutables`, `PromptSanity`, `SignatureValid`) run
before any peer genome touches the live pool. Once a peer genome is
approved (`QuarantineApproved`), it joins the next reconciliation pass
and becomes eligible for recovery work on subsequent failures.

## 5. What survives across the healing

**Survives:**

- The session state on disk under `~/.agentdrive/sessions/<id>/`
- Any partial outputs the dead sub-agent flushed before death
- The full audit trail in `~/.agentdrive/quarantine/log.jsonl` and the
  reconciliation state at `$AGENTDRIVE_HOME/reconciliation.json`
- The inheritance manifest of every repair sub-agent
- `ConfidenceRating` sidecars on every involved genome — including the
  one that died, because its failure is a real signal

**Lost:**

- In-flight LLM context that had not yet been checkpointed back to
  disk. AgentDrive cannot reach into a dead model's residual
  conversation buffer.
- Tool-call results that were issued and never returned before the
  process died (the underlying tool may have side-effected; the
  response was lost).
- Any in-memory state the sub-agent held that was not represented as
  a genome, a manifest entry, or a pool outcome.

## 6. Limits — what this does NOT solve

- **Provider outages.** If the underlying model is down, AgentDrive
  cannot resurrect work that depends on inference. The healing loop
  expects functioning models.
- **Upstream data corruption.** If the input to the original task was
  bad, the genomes pulled to repair it will fail validation against
  the same bad input. AgentDrive heals capability, not inputs.
- **Loss of `$AGENTDRIVE_HOME`.** If the operator's pool directory itself
  is destroyed — disk failure, accidental `rm -rf`, encrypted
  ransomware on the host — the healing loop has nothing to heal from.
  This is the RAID-controller-fails analogy: redundancy at the genome
  level does not protect against destruction at the substrate level.
  Snapshot `$AGENTDRIVE_HOME` accordingly.
- **Adversarial peer genomes.** The quarantine validators catch
  schema, size, executable, and prompt-injection patterns. They do
  not catch a sufficiently subtle behavioral attack from a peer the
  operator marked `trusted`. Treat the trust store as security
  boundary, not a convenience.
- **Single-shot tasks with no encounter history.** Recovery works on
  genomes with at least a ≥3-star confidence rating. Brand-new work
  that has never been encountered before has no parity stripe to
  rebuild from. The first run is always the operator's risk.

---

See [`VISION.md`](../VISION.md) for the framing and
[`docs/POOL-EVOLUTION.md`](POOL-EVOLUTION.md) for the federated-learning
stack that the healing loop rides on top of.
