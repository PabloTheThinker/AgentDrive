---
name: swarm-orchestrator
description: "Orchestrator playbook — route work through pawns; do not do pawn work yourself."
category: backup
role: arisen
source: hermes-adapted
tags: [swarm, kanban, orchestrator, hermes]
related_skills: [swarm-worker, arisen-orchestrator]
when_to_call: multi-step project needs decomposition and pawn dispatch
---

# Swarm orchestrator (Hermes kanban-orchestrator → AgentDrive)

Adapted from Hermes `kanban-orchestrator` for AgentDrive hive.

## Anti-temptation rules

- **Do not implement** — spawn `pawn-worker` or `pawn-specialist`.
- **Do not recurse yourself** — one orchestration layer.
- **Decompose** into pawn-sized quests with clear done criteria.

## Lifecycle

1. Orient — `pool-query` + `think` for context
2. Plan — numbered pawn tasks
3. Dispatch — spawn with skills list
4. Collect — `hive-inheritance` from each pawn
5. Synthesize — learnings-log + user summary

Block only on human decisions — use specific questions.