# Agent Drive Genome Specification v0.1

This document defines the **Agent Genome** (or "DNA") format — the portable, versioned, evolvable unit of specialized capability in the Agent Drive ecosystem.

## Goals of the Format

- **Structured enough** to be composable, auditable, and machine-processable.
- **Rich enough** to capture not just "what to do" but "why it works" and "how well it works".
- **Evolvable** — supports forking, merging, and mutation with clear provenance.
- **Portable** across different agent implementations (with adapters).

## High-Level Structure

A Genome is a directory (or archive) containing:

```
genome/
├── manifest.yaml          # Identity, version, lineage, applicability
├── framework.yaml         # The core typed playbook
├── reasoning/             # High-signal patterns (causality, analogies, contradictions, etc.)
│   ├── patterns.jsonl
│   └── traces/
├── tools/                 # Proven tool compositions and guardrails
│   └── compositions.yaml
├── evaluations/           # Performance data on reference tasks
│   └── reference-evals.json
├── artifacts/             # Example successful outputs
├── provenance/            # Full history of creation and improvements
│   └── lineage.json
└── schema/                # Validation schemas
```

## manifest.yaml (Core Identity)

```yaml
genome:
  id: security-incident-postmortem-v2
  version: 2.3.1
  content_hash: sha256:...
  created: 2026-05-10
  last_improved: 2026-05-23

  authors:
    - type: human
      name: "Pablo Navarro"
    - type: agent
      id: "rich-node-042"
      run: "eng-2026-05-18-postmortem-17"

  applicability:
    domains: [security, devops, reliability]
    problem_signatures:
      - "production incident with unclear root cause"
      - "need for blameless + technically deep writeup"

  dependencies:
    genomes: []                    # other genomes this one builds on
    agent_capabilities: [tool_use, long_reasoning, file_analysis]

  evaluation_score:
    reference_tasks: 0.87
    human_preference: 0.92
    cost_efficiency: 0.78
```

## framework.yaml (The Structured Playbook)

This is the core typed `framework.yaml` specification.

It defines deterministic, schema-validated steps.

See the seeded examples under genomes/examples/ for reference shapes.

Key addition in Agent Drive: steps can declare which **genome sub-components** they activate.

## Reasoning Patterns (The "Why" Layer)

This is where we go beyond static playbooks and capture *how* good agents think.

Examples of what lives here:

- Causal chain templates that worked well
- Productive analogy mappings for the domain
- Contradiction detection heuristics
- Useful ways to structure a postmortem timeline
- Common failure modes and how to surface them early

These are stored in a machine-readable + human-readable form so both the Evolutionary Engine and other agents can use them.

## Tool Compositions

Not just "this tool exists", but **proven sequences and parallel patterns** that delivered value, including:

- Orderings that reduce context pollution
- Parallelization strategies that are safe
- Guardrail combinations that caught bad outputs early

## Evaluations & Calibration

Every serious genome should carry data about how well it performs.

This creates selection pressure and lets the system know when a genome is degrading or improving.

## Provenance & Lineage

Critical for trust and evolution.

`lineage.json` records:

- Parent genomes (when this was forked or merged)
- Improvement events (with links to the review run that proposed the change)
- Validation runs that confirmed the improvement

This gives us a true evolutionary tree instead of a bag of unrelated skills.

## Versioning Strategy

- **Semantic versioning** for the genome contract.
- **Content-addressed hashes** for exact reproducibility.
- **Forking model** similar to Git: you can fork a genome, improve it, and later propose merges or let the registry surface the best descendants.

## Compatibility & Adapters

Not every agent will natively understand the full genome format.

Agent Drive will provide:

- **Export adapters** → turn relevant parts of a genome into external skills, custom prompts, etc.
- **Import scanners** → pull useful patterns out of existing agent runs and package them as genomes.

## Evolution Operations (Supported in v0.1+)

Planned primitive operations on genomes:

- `scan(run)` → produce candidate genome
- `fork(genome)` → create a new versioned descendant
- `merge(genome_a, genome_b)` → safe recombination (with conflict resolution)
- `mutate(genome, proposal)` → apply an improvement
- `evaluate(genome, reference_suite)` → score it
- `select(best_n, criteria)` → evolutionary selection

## Next Steps for This Spec

This v0.1 is intentionally a starting point. As we implement the scanner and evolutionary engine, the exact shapes of `reasoning/`, `tools/`, and evaluation data will be refined based on what actually proves valuable to extract and transfer.

The invariant we will protect: **Genomes must be more than prompts or skills — they must be rich, structured, improvable packages of capability that compound across the ecosystem.**

---

This spec will live in the repo and evolve with the code. Contributions to the format are very welcome.