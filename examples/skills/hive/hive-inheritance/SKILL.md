---
name: hive-inheritance
description: >
  Package pawn outcomes for parent ingest — summary, genomes used, new patterns, learnings key, and self-score for the shared pool.
category: hive
role: shared
source: agentdrive-hive
tags: [hive, inheritance, pool, swarm, pawn, ingest]
when_to_call: pawn completing a task and returning knowledge to the Arisen or pool
---

# Hive inheritance

When a pawn completes, the hive absorbs **outcomes** — not raw chat logs.

## What to return

| Field | Content |
|-------|---------|
| `outcome_summary` | One sentence, user-impact framed |
| `genomes_used` | DNA ids consulted |
| `new_patterns` | Reusable rules worth seeding as genomes |
| `learnings_key` | Short key for `learnings-log` |
| `score` | Self-rated 0–1 usefulness to future pawns |

## Pool etiquette

- Prefer **ingest** over repeating the same insight in every pawn session.
- Reject (do not ingest) one-off debugging noise.
- Quarantine anything from untrusted peers until reviewed.

Emits `InheritanceReceived` / `InheritanceAbsorbed` on the bus when wired through harness.
