---
name: swarm-worker
description: "Worker pitfalls for AgentDrive swarm pawns — handoffs, retries, scope."
category: backup
role: pawn
source: hermes-adapted
tags: [swarm, kanban, worker, hermes, pawn]
related_skills: [pawn-worker, hive-inheritance]
when_to_call: dispatched as a worker pawn on a scoped task
---

# Swarm worker (Hermes kanban-worker → AgentDrive)

Adapted from Hermes `kanban-worker`. Pair with `pawn-worker`.

## Good handoff

```
SUMMARY: shipped X — N tests pass
FILES: [paths]
TESTS: N/N
DECISIONS: [choices future pawns need]
GAPS: [what hive lacks]
```

## Do NOT

- Expand scope or refactor unrelated code
- Ask human via chat mid-run — return BLOCK with specific decision needed
- Complete if review required — mark gaps for Arisen

## Retries

If retrying: read prior outcome; do not repeat failed path.