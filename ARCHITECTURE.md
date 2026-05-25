# Savant Architecture

## Overview

Savant is structured around three primary concerns:

1. **Orchestration** — Selecting, composing, and dispatching work using structured, genome-aware frameworks.
2. **Genome Representation & Registry** — First-class, versioned, evaluable packages of agent capability (the "DNA" of the system).
3. **Evolutionary Improvement** — Mechanisms for extracting value from runs, proposing improvements, merging, and selection.

These concerns are deliberately separated to keep the system maintainable and to allow different parts of the ecosystem to evolve at different rates.

## High-Level Components

- **Savant Core (Orchestrator)**: The typed framework dispatcher and mission engine. It is now genome-native — capable of reasoning about available Genomes when planning work, dispatching steps to appropriate workers, producing validated artifacts, and emitting rich telemetry that feeds the evolutionary layer.
- **Genome Registry**: Local and (future) remote stores of versioned Genomes. Supports discovery, forking, and provenance tracking.
- **DNA Scanners & Extractors**: Components that analyze instrumented agent runs (from external workers or Savant workers) and produce candidate Genomes.
- **Evolutionary Engine**: The improvement system — review, mutation proposal, safe merging, and performance-based selection.
- **Worker Agents**: Any capable execution environment (rich external agents, custom Savant workers, other ACP/MCP-compatible agents). Workers both consume and contribute Genomes.

## Genome Model

See `GENOME-SPEC.md` for the detailed specification. At a high level, a Genome contains:

- A manifest with identity, versioning, provenance, and applicability metadata
- A core typed framework (steps, inputs, output schema)
- Reasoning patterns and heuristics
- Tool compositions and strategies
- Evaluation data
- Full lineage

## Terminal Experience

A major focus of the current development phase is a high-quality, professional terminal interface. We are drawing from:

- Prior professional TUI and CLI implementations
- Mature terminal experiences (prompt_toolkit usage, skinning, live callbacks, spinners, reasoning display, tool progress, etc.)

The goal is a Savant TUI/CLI that feels as capable and pleasant as the best individual agents while exposing the unique power of the genome and evolutionary layers.

## Design Constraints

- Clear separation between the orchestrator and evolutionary concerns
- Strong typing and schema validation at framework and genome boundaries
- Support for both human operators and autonomous agents as users of the system
- Reproducibility and auditability as non-negotiable properties

This architecture is intended to be durable enough to support many years of incremental improvement while remaining simple enough to reason about at each layer.