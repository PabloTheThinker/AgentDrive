---
name: pool-query
description: >
  Semantic search over the AgentDrive pool — find genomes and DNA relevant to a task. How pawns pull knowledge from the hive before acting.
agentdrive_operation: pool_query
argument: task
category: core
role: shared
tags: [pool, dna, query, hive, genomes]
when_to_call: search the pool, find matching genomes, or orient before implementation
---

# Pool query

Runs `agentdrive drive query` — how pawns **pull DNA from the hive** before acting.

**Usage:** `/skill pool-query dedup identical agent outputs`
