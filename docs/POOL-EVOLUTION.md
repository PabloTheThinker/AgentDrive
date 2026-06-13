# AgentDrive Pool Evolution — a continuous learning loop

**Status:** proposal for review. AgentDrive's federated learning
surface — what the internal pool engine does between turns and across
instances.

---

## 1. The mechanics this proposal builds on

Long-running multi-agent systems with companion AIs tend to converge on
four mechanics that, together, make capability transfer feel alive
rather than statistical. **Encounter-graded confidence:** a capability
earns trust by repeated success on the *same shape of problem*, not
raw use count — a genome that nailed twelve different incident
postmortems is more trustworthy than one used fifty times across mixed
domains. **Knowledge ferrying:** when an agent finishes work elsewhere,
the artifacts and lessons it gained travel back to its home pool as a
structured manifest rather than being absorbed wholesale. **Trust-gated
contagion control:** any capability arriving from a foreign pool can
carry pathological patterns (poisoned prompts, malformed manifests,
behavior that subverts the host) — federation only works if every
foreign byte passes a validation gate before going live. **Provenance
threading:** at the moment a capability is used, the operator can see
where it came from, who validated it, and what it has done before — the
audit trail is part of the runtime surface, not a separate log nobody
reads.

These four are domain-agnostic. They show up in game-AI companion
systems, in distributed package registries, in CDN edge caching, and in
biology's selection-pressure model. The proposal below applies them to
AgentDrive's pool engine specifically.

---

## 2. The four mechanics mapped to AgentDrive

| Mechanic | AgentDrive implementation |
|---|---|
| Encounter-graded confidence | Per-genome **encounter confidence** — score climbs only with repeat success on the same problem shape |
| Knowledge ferrying back to a home pool | **Inheritance manifests** — DNA learned in a foreign pool surfaces in the home pool on return |
| Trust-gated contagion control | **Trust-gated quarantine** on every foreign DNA before live use |
| Provenance threading at runtime | Pre-turn **provenance ribbon** naming the genome's lineage and prior wins |
| Cross-instance capability exchange | **Federated absorption** between trusted peer AgentDrive instances under explicit policy |
| Behavioral profile shaped by past use | (deferred — echo-chamber risk warrants holding until we have isolation primitives in place) |

---

## 3. Proposed AgentDrive evolutions

### 3.1 Encounter-graded confidence
Per-genome confidence climbs only on repeat success against the same
problem shape, not raw use count. Surfaces as a 0–3 marker in `/pool`.
**Build.** Extend `PoolOutcome` with a coarse `encounter_tag` (hash of
intent+domain) at harness entry. New `~/.agentdrive/pool/encounters.jsonl`.
Weight `get_relevant_dna` toward confidence-for-this-encounter over raw
average score.
**Impact:** high. **Risk:** tag collision — cap the vocabulary to a
stable derivation from genome domains.

### 3.2 Pool reconciliation routine
Every agent runs a periodic background pass that scans foreign pools
(sub-agents, federated peers) for entries added since last reconciliation
and ingests anything that clears trust + quality gates. The reframe in §4
becomes real here.
**Build.** New `agentdrive.pool.reconciler` module. Cron-style worker driven
by the event bus or `apscheduler`. New events `PoolReconcileStart`,
`PoolAbsorb`, `PoolReconcileDone`. Audit trail at
`~/.agentdrive/pool/reconcile.jsonl`.
**Impact:** high. **Risk:** runaway absorption — per-source quotas + an
audit ribbon in chat.

### 3.3 Trust-gated quarantine
Any DNA from a non-local pool runs through a sandboxed evaluator on a
small synthetic task set before being ranked for live use.
**Build.** Extend the existing `ultimate` promotion harness with
`quarantine_eval(genome)` — a frozen evaluator with no tool access. New
entry status: `quarantined | trusted | promoted`. New event
`PoolQuarantine`.
**Impact:** high (precondition for §3.2 + §3.6). **Risk:** evaluator
becomes a chokepoint — keep it cheap and async.

### 3.4 Provenance ribbon
When a genome is injected, the existing pool ribbon gains a one-line
lineage tag — `▸ applying incident-postmortem-12 · 4 prior wins · last
used 2d ago · learned from swarm:trace-2`. Makes "the pool is learning"
legible in real time.
**Build.** Enrich `PoolMatch` with a `lineage` field. Pure UI work on the
existing event bus. No new storage.
**Impact:** medium (perception win, cheap). **Risk:** noise — throttle to
one ribbon per turn.

### 3.5 Cross-agent inheritance manifest
When a sub-agent or peer pool hands control back, it ships a single
manifest of "new lessons since last sync" — scoped, signed,
quarantine-eligible. Replaces today's implicit swarm-pool merge with an
explicit, auditable hand-off.
**Build.** New `manifest.jsonl` per pool. `Harness` emits one on
context exit. Reconciler (§3.2) consumes them. New CLI:
`agentdrive drive inherit <swarm_id>`.
**Impact:** high. **Risk:** schema churn — version the manifest from day
one.

**Hermes-style skill ferrying.** The manifest also carries
`skills_created`: reusable playbooks distilled from the sub-agent's actual
successful work. Local sub-agent skills install into
`~/.agentdrive/skills/inherited/<swarm>/<subagent>/<skill>/SKILL.md`, making
them discoverable by the normal skills catalog and prompt matcher. Like
Hermes self-evolution candidates, inherited skills are constraint-gated before
installation: bounded name/description/body size, non-empty body, no overwrite
without force, and external peer skills rejected for review by default. They
must not bypass the same trust boundary as foreign DNA.

### 3.6 Federated peer registry
Opt-in directory of trusted peer AgentDrive instances (other operators, external
agent frameworks that speak the pool protocol) the reconciler may poll.
Pull-only. Zero cloud.
Configured in `~/.agentdrive/peers.yaml`.
**Build.** New `agentdrive.adapters.peers` module + a minimal HTTP manifest
endpoint, built on the `adapters/` skeleton in MISSION_PLAN.md.
**Impact:** medium today, transformative once peers exist. **Risk:**
trust model. Ship local-only first; gate federation behind a real
handshake.

---

## 4. The reframe of AgentDrive's purpose

Today AgentDrive's pool is a **library of capabilities**: an agent walks up at
prompt time, asks for genomes matching the task, and injects them into
its system prompt. The pool is a reactive lookup table.

The reframe: every agent runs a **pool reconciliation routine** in the
background, periodically scanning sub-agent pools, peer AgentDrive instances, and
external sources (partner installs, third-party agent frameworks
speaking the pool protocol) for new DNA produced since last
reconciliation. Anything clearing trust + quarantine
gates is absorbed, ranked, and made available next turn — without the
operator asking. The agent inherits continuously, the way a city absorbs
people who move into it.

This shifts the AgentDrive pool engine from "library of capabilities" to **a
living federated learning organism**: every agent session, every
sub-agent run, every peer's promoted genome flows through quarantine
and lands in the operator's Drive overnight. The pool stops being a tool and becomes
metabolism. The pitch shifts from "your agent has a DNA pool" to "your
fleet learns from every other fleet you trust."

---

## 5. Recommended build order

Ranked by impact ÷ effort.

| # | Proposal | Days | Rationale |
|---|---|---|---|
| 1 | §3.4 Provenance ribbon | 0.5 | Cheapest; makes the value prop visible immediately. Pure event-bus work. |
| 2 | §3.1 Encounter-graded confidence | 1.0 | Sharpens ranking; tiny extension of `PoolOutcome`. |
| 3 | §3.5 Inheritance manifest | 1.5 | Foundation for §3.2 and §3.6. Builds on existing swarm isolation. |
| 4 | §3.3 Trust-gated quarantine | 2.0 | Security precondition for any external ingestion. |
| 5 | §3.2 Reconciliation routine | 2.0 | The §4 reframe becomes real here. Depends on 3 + 4. |
| 6 | §3.6 Federated peer registry | 3.0+ | Highest ceiling, highest trust burden. Last. |

**MVP slice (≈5 dev-days):** §3.4 + §3.1 + §3.5 + §3.3. Demoable
end-to-end as "your sub-agents bring lessons home with an audit trail."

---

## 6. Open questions for the project maintainer

1. **Reconciliation cadence.** Background poll every N minutes, on every
   `subagent.done`, or operator-triggered only? Each has a different
   failure mode (drift vs. lag vs. friction).
2. **Federation MVP.** Ship §3.6 in the first cut, or keep the system
   local-only (sub-agents → parent only) until the trust model is real?
   Recommend local-only first; federation is the moat but the trust
   surface is brutal.
3. **Encounter-tag vocabulary.** Auto-derive from genome domains, or
   require authors to declare `encounter_class` in the manifest? Auto is
   faster; declared is auditable.
4. **Name for the reconciliation routine in user-facing copy.** "Pool
   reconciliation" is precise but cold. Alternatives: "pool sync",
   "ingest pass", "absorption cycle". Need a project name pick.
5. **Cut scope confirmation.** A behavioral-bias profile (operator-level
   ranking drift learned from accept/reject) is deferred above on
   echo-chamber risk. Confirm we hold, or want it scoped back in.
