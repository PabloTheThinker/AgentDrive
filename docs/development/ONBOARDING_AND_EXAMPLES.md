# AgentDrive Onboarding & Examples Guide

> **Note for public repository**: This guide was refined during internal development. Any historical references to specific private identities or directories have been generalized. The authoritative end-user manual is `HELP.md`.

**The complete, copy-paste runnable tour of what AgentDrive actually is, what is working today, and exactly how everything fits together — for new users and advanced operators alike.**

This document turns the abstract architecture (see `CONCEPTS.md`, `HELP.md`, `ARCHITECTURE.md`) into concrete, safe, immediately executable experiences. Every example below is self-contained, heavily commented, and documents precisely which surfaces it exercises (Drive tiers, Quarantine + immune, DNADrive + grants + ancestry, Harness, LineageDNAEvolver, GrokPatternLineageBridge, etc.).

Run them in order. Read the headers first. They are the living specification of "what works today."

---

## Quick Verification (Start Here)

```bash
# After any install (pip or the curl | bash installer)
agentdrive doctor
agentdrive drive status
agentdrive genomes list
```

All examples write only under `~/.agentdrive/` (or isolated temps) and are safe to re-run. Use unique agent/swarm IDs in your own code.

---

## The Examples — Progressive Learning Path

| # | File | Focus | Key Surfaces Exercised | "What this proves is working" |
|---|------|-------|--------------------------|--------------------------------|
| 01 | `examples/01_hello_drive.py` | Core Personal Drive + Harness | AgentDrive / Harness, ingest, pull_relevant_dna, record_outcome, content store | Basic private memory loop for any agent. |
| 02 | `examples/02_dedup.py` | Content-addressed deduplication invariant | ContentStore, SHA-256 identity, global dedup across Drives | Identical genomes converge to one object everywhere on the machine. |
| 03 | `examples/03_swarm.py` | Shared Swarm Drives (stigmergy) | SwarmDriveManager, get_or_create_pool, sibling sub-agents sharing one Drive | Sub-agents on the same mission see each other's genomes with zero extra wiring. |
| 04 | `examples/04_quarantine_workflow.py` | **Mandatory safety gate** for all foreign DNA | Quarantine, QuarantineStatus, full submit→validate→approve/reject, LineageImmuneRule | No external genome ever touches a live pool without explicit operator + rule approval. Immune engine runs on every candidate. |
| 05 | `examples/05_lineage_dna_grants.py` | Full lineage-enhanced stack (native) | DNADrive + Ancestry (forward-only closure), LineageShareGrant + GrantStore + pull_via_grant, LineageImmuneSystem, LineageDNAEvolver (Research→Evaluate→Evolve, dry_run), Harness publish_to_dna / pull_inherited_dna | DNA inheritance, signed cousin sharing (always via quarantine in prod), adaptive immune memory, safe evolution cycles, Harness ergonomics. |
| 10 | `examples/10_lineage_integration_test.py` | Smoke of the advanced modules | LineageImmuneSystem.assess_genome, LineageDNAEvolver.run_full_cycle (dry_run) | Quick verification that the immune + evolver engines return correct ThreatLevel / fitness_delta / findings. |
| **11** | `examples/11_high_continuity_bridge_demo.py` | **High-Continuity Operator Bridge** (advanced) | GrokPatternLineageBridge, pattern export & publish, consume helpers, LineageDNAEvolver with external index, LineageImmuneSystem | Operators maintaining their own research indexes can publish custom patterns as inheritable DNA, consume collective DNA, and safely drive evolution cycles. |

**Run the full curated set (copy-paste):**

```bash
python3 examples/01_hello_drive.py
python3 examples/02_dedup.py
python3 examples/03_swarm.py
python3 examples/04_quarantine_workflow.py
python3 examples/05_lineage_dna_grants.py
python3 examples/10_lineage_integration_test.py
python3 examples/11_high_continuity_bridge_demo.py   # high-continuity operator bridge demo
```

After each, explore with `agentdrive` CLI / TUI / `agentdrive web` (http://127.0.0.1:8421).

---

## Beginner Path (Core Intuition)

Start with 01–03. These establish that AgentDrive is always present, deduplicated, and shared when you want it to be — without changing how you write your agent loops.

See `HELP.md` → "Practical How-To Workflows" and the Harness section in `docs/INTEGRATION.md`.

---

## Safety & Trust Path (Non-Negotiable)

**Run 04 before anything involving peers, grants, federation, or external patterns.**

Quarantine is not optional. Every genome arriving via `peers sync`, `LineageShareGrant`, adapters, or repair candidates is forced through it. The `LineageImmuneRule` (powered by `LineageImmuneSystem`) provides adaptive memory: it learns hostile prompt-injection signatures and gives lineage-based self-tolerance boosts.

After 04 you will understand why `agentdrive quarantine list` and the web approve/reject buttons exist.

---

## Lineage, Grants & Evolution Path (The Advanced Native Layer)

05 + 10 give you the complete picture of the **lineage-enhanced features** added for high-agency use:

- `DNADrive(agent_id)` — your long-term ancestral memory. Publish once; descendants (and you) pull forward-only via ancestry closure table.
- Signed `LineageShareGrant`s for controlled sideways (cousin) sharing. Results **must** still go through Quarantine.
- `LineageDNAEvolver` — structured Research (native ledger + patterns + ancestry + optional external brain) → multi-signal Evaluate (fitness + immune) → safe proposed mutations.
- Harness convenience methods that most agents should use.

All of this is 100% native — no external Lineage Engine required.

---

## High-Continuity Operator Bridge Quickstart (Advanced Path)

**This section is for operators who maintain their own research or pattern indexes and want to publish high-value work as first-class, inheritable DNA in AgentDrive.**

### Why This Exists

Advanced nodes maintain deep, long-horizon context and high-quality internal patterns. The bridge turns those patterns into first-class AgentDrive citizens:

- **PUBLISH**: `ilo_pattern_to_genome()` + `publish_ilo_genome()` (or `activate_as_ilo_conductor(..., publish_best=True)`) — your CognitivePatterns, narrative styles, and lineage heuristics become versioned, content-addressed, fitness-scored Genomes in your DNA Drive (and optionally current swarm).
- **CONSUME**: `consume_inherited_dna()`, `consume_swarm_dna()`, `consume_for_ilo_research()` — feed collective + ancestral DNA into the node's Research phase or context composer.
- **EVOLVE**: `LineageDNAEvolver(..., brain_path=bridge.brain_path).run_full_cycle(dry_run=True)` — use AgentDrive + your own brain as joint research sources, then publish improvements back.

The bridge is lightweight, has no external runtime dependencies, and is re-exported at the top level:

```python
from agentdrive import GrokPatternLineageBridge, LineageDNAEvolver, LineageImmuneSystem
# or
from agentdrive.adapters import GrokPatternLineageBridge, ilo_pattern_to_genome, publish_ilo_genome
```

### The One-Shot Activation Ritual

```python
from pathlib import Path
from agentdrive import GrokPatternLineageBridge

bridge = GrokPatternLineageBridge(
    brain_path=Path("~/.my-research/brain"),   # your own research index
    operator_id="my-high-continuity-node"      # stable identifier for your node
)

summary = bridge.activate_as_ilo_conductor(
    swarm_id="current-long-mission",
    publish_best=True,
    min_fitness_to_publish=0.75,
)
print(summary)
# → {"agent_id": "...", "published_count": N, "inherited_available": M, "status": "ilo-conductor-live-in-agentdrive", ...}
```

This pattern is designed for any long-running or high-continuity system that wants its internal work to become durable, shareable DNA.

### Full Runnable Demonstration

See and run:

```bash
python3 examples/11_high_continuity_bridge_demo.py
```

It exercises **everything** listed above with a simulated research directory (no pollution of your real data), a custom pattern, activate, publish, consume, safe evolver cycle, and the immune assessment engine.

The header of `11_high_continuity_bridge_demo.py` contains the authoritative "what it exercises" + safety rules.

### External Research Index Configuration

- The bridge accepts any directory you point it at as the external research source.
- Use a stable `operator_id` for your long-running node so its published DNA is properly attributed in ancestry.
- Always pass explicitly:

```python
bridge = GrokPatternLineageBridge(
    brain_path=Path.home() / ".agentdrive-ilo" / "brain"
)
```

The `export_high_fitness_patterns()` scanner walks a directory for files containing `fitness` or `score` fields (JSON, Markdown frontmatter, YAML, etc.). Point it at your own research index.

### Safe DNA Evolution Cycle

Never mutate live DNA without review:

```python
evolver = LineageDNAEvolver(my_genome, brain_path=bridge.brain_path)
result = evolver.run_full_cycle(
    focus_areas=["reasoning_depth", "provenance", "speech_clarity"],
    dry_run=True,                 # ← always start here
)
print(result.research_findings, result.fitness_delta, result.mutations_proposed)

if result.fitness_delta > 0.05 and not result.immune_flags:
    # Human or high-confidence gate review here
    improved = ... build new genome from result ...
    bridge.publish_ilo_genome(improved, agent_id=bridge.ilo_agent_id)
```

Self-published work goes straight to your DNA Drive. Foreign, consumed, or grant-derived DNA still routes through Quarantine + `LineageImmuneRule`.

### Interaction With the Rest of the System

- Published genomes are queryable via `DNADrive("ilo-...").pull_inherited(...)`, Harness, `agentdrive drive query`, TUI, web DNA views.
- They participate in reconciliation, snapshot manifests, and future healing loops.
- The immune engine (`LineageImmuneSystem`) that the bridge demo exercises is the **exact same** one registered as `LineageImmuneRule` in Quarantine (see 04 and `dna/lineage_immune.py`).

### Example Flow for a High-Continuity Operator

1. `activate_as_ilo_conductor(...)` at mission start.
2. During deep Research: `consume_for_ilo_research(...)` → feed into context.
3. After valuable work: export + publish best patterns.
4. Periodically: run evolver cycles (dry) on core genomes, review, publish mutations.
5. Sub-agents can inherit published DNA automatically via the Harness and swarm scoping.
6. Everything remains under the operator's `~/.agentdrive/` keys and capabilities.

This is the "new power user path" delivered by the recent GrokPatternLineageBridge + re-export work.

---

## After the Examples — How to Explore & Operate

- **CLI**: `agentdrive doctor`, `agentdrive drive query/status/ingest`, `agentdrive quarantine ...`, `agentdrive reconcile`, `agentdrive genomes`, `agentdrive web`.
- **TUI** (default `agentdrive`): live ribbons for quarantine, reconciliation, inheritance, DNA events.
- **Web**: `agentdrive web` → http://127.0.0.1:8421 (auth + approve/reject quarantine, capabilities, DNA views, peers).
- **Python REPL / your harness**:
  ```python
  from agentdrive import Harness, DNADrive, GrokPatternLineageBridge, LineageDNAEvolver, LineageImmuneSystem
  # ... the surfaces shown in the examples
  ```
- **Inspection**: `ls ~/.agentdrive/dna/<agent-id>/`, `~/.agentdrive/quarantine/log.jsonl`, `reconciliation.json`.

---

## What Is Actually Working Today (Grounded in the Examples)

(See also the authoritative "What Is Actually Working Today" in `HELP.md`.)

- All three Drive tiers + global content-addressed dedup.
- Capability URIs + single verification chokepoint (enforced on web + internal paths).
- Quarantine with full lifecycle + LineageImmuneRule (every foreign path).
- DNADrive + forward-only Ancestry closure table.
- Signed LineageShareGrant + pull_via_grant (with mandatory quarantine reminder).
- Harness pull/record + publish_to_dna / pull_inherited_dna.
- LineageDNAEvolver full cycles (native sources + pluggable brain_path).
- GrokPatternLineageBridge + export / publish / consume for operators with external research indexes.
- Reconciliation events powering live UIs.
- TUI, web (FastAPI + HTMX, auth, admin), CLI, doctor, and all examples.

The engine, safety model, and evolutionary surfaces are solid and exercised end-to-end.

---

## Further Reading (Curated)

- **Start here**: This file + `HELP.md` (the primary user reference) + `README.md`
- **Mental models**: `CONCEPTS.md`
- **Deep integration**: `docs/INTEGRATION.md` (advanced lineage section)
- **Specific domains**: `docs/AGENTDRIVE-V2-INHERITANCE.md`, `GENOME-SPEC.md`, `docs/SWARM.md`
- **Source of truth for the bridge**: `src/agentdrive/adapters/grok_build_adapter.py` (extensive comments)

**AgentDrive gives agents a living, sovereign, evolutionary substrate.**

Run the examples. Approve genomes through quarantine. Watch a swarm share DNA. The map is now actionable.

---

*Maintained as part of the AgentDrive improvement swarm. Contributions that improve clarity or add new runnable demonstrations are welcome.*