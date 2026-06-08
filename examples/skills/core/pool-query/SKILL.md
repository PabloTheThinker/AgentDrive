---
name: pool-query
description: "Semantic drive query — find relevant genomes for a task."
agentdrive_operation: pool_query
argument: task
category: core
role: shared
tags: [pool, dna, query, hive]
when_to_call: user wants to search the AgentDrive pool or find matching DNA
---

# Pool query

Runs `agentdrive drive query` — how pawns **pull DNA from the hive** before acting.

**Usage:** `/skill pool-query dedup identical agent outputs`