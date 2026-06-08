---
name: swarm-worker
description: >
  Hermes kanban-worker adapted for pawns — structured handoffs, retry discipline, scope limits, and review-required blocking patterns.
category: backup
role: pawn
source: hermes-adapted
tags: [swarm, worker, kanban, hermes, handoff]
when_to_call: dispatched worker pawn on a scoped implementation or research task
related_skills: ['pawn-worker', 'hive-inheritance']
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
