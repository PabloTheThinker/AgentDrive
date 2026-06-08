---
name: swarm-orchestrator
description: >
  Hermes kanban-orchestrator adapted for AgentDrive — decompose quests, dispatch pawns, collect inheritance. Anti-rule: do not implement pawn work yourself.
category: backup
role: arisen
source: hermes-adapted
tags: [swarm, orchestrator, kanban, hermes, decompose]
when_to_call: multi-step project needs decomposition and pawn dispatch
related_skills: ['swarm-worker', 'arisen-orchestrator']
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
