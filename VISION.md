# Vision — Agent Drive and AgentDrive

## Premise

Agents fail. They crash, hang, miss deadlines, drift from the signature of the work they were dispatched to do, and return outputs that look right and are wrong. Today's stacks treat each failure as a one-off: the operator restarts the run, swaps a prompt, escalates to a human, or accepts the loss. Nothing in the system remembers what a healthy version of the capability looked like, and nothing rebuilds it from the parts that are still intact. Capability lives inside a single live process; when the process dies, the capability dies with it. At fleet scale this is the dominant failure mode and it has no first-class solution.

## The RAID parallel

RAID survived a generation of unreliable drives by refusing to keep capability in one place. Mirrored blocks and parity stripes meant the array could lose a drive without losing the data — the surviving members carried enough information to rebuild the failed one. AgentDrive applies the same discipline to agent capability. Every successful run is decomposed into typed, versioned **Genomes** that mirror the reasoning, tool composition, and evaluation criteria that made the run work. When an agent dies, the surviving genomes in the pool — graded by confidence, ranked by encounter history — carry enough information to rebuild it. Mirroring genomes is to AgentDrive what mirroring blocks is to RAID.

## What Agent Drive is. What AgentDrive is.

**Agent Drive** is the engine: a Python framework that defines the genome schema, runs the DNA pool, scores confidence, ferries inheritance manifests across swarms, quarantines foreign DNA, registers trusted peers, and runs the reconciliation loop. It is open-source, MIT-licensed, and stays as it is. **AgentDrive** is the product layered on top — "RAID for AI agents" packaged for operators who need agents that survive production. The relationship in marketing copy: *AgentDrive — powered by Agent Drive.* Engine is the substrate; product is the experience.

## The healing loop

An agent dies — crash, hang, missed deadline, validation failure, signature drift. The `ReconciliationRunner` detects the missing or stalled sub-agent and surfaces it on the event bus. Recovery genomes are pulled via `pool.query`, filtered to the ≥3-star tier of `ConfidenceRating`. A repair swarm of three sub-agents is dispatched (`SubagentSpawn` × 3), each carrying one of the top-three matches. Their outputs are assembled into an `InheritanceManifest` and validated against the original genome's evaluation criteria. If a candidate passes, `ConfidenceUpdated` fires for the source genome and the repair genomes, and the work is reabsorbed into the pool. If every candidate fails, the original task is routed to `quarantine.submit` for operator review. Full sequence in [`docs/RECOVERY.md`](docs/RECOVERY.md).

## Local-first, privacy-absolute

The pool lives at `$AGENTDRIVE_HOME` on the operator's machine. The healing loop runs locally. Genomes, manifests, confidence sidecars, and the quarantine ledger never leave the host unless the operator opts in to a trusted peer in `peers.yaml`. Federation is pull-only and gated: every peer genome routes through `quarantine.submit` before it can touch the live pool, regardless of `trust_level`. No cloud control plane, no telemetry, no shared cache. Cross-instance learning is continuous, but it happens on the operator's terms — the federated-learning layer makes it safe without making it remote.

## What this unlocks

Operators run agents at production scale knowing failures auto-heal. Teams pool genomes across instances and watch capability compound across the deployment instead of evaporating with each crashed process. The cost of a single agent dying drops from "rerun the mission and hope" to "the pool rebuilt it before anyone noticed." Multiply across a fleet and the curve flips: every failure becomes a training signal, every peer's promoted genome becomes a hardening pass, and the system gets more reliable with use rather than less. That is the shift Agent Drive makes possible and AgentDrive makes operational.

---

See [`README.md`](README.md) for installation and quickstart, [`docs/RECOVERY.md`](docs/RECOVERY.md) for the healing-loop deep dive, and [`docs/POOL-EVOLUTION.md`](docs/POOL-EVOLUTION.md) for the federated-learning stack the healing loop runs on.
