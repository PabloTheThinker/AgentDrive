---
name: sql-explain
description: >
  Explain a SQL query in plain English — intent, tables, indexes, join strategy, cost class, and
  risks (full scan, implicit cast, N+1).
category: agentdrives
role: pawn
tags: [sql, database, explain, query]
when_to_call: user pastes SQL and wants execution analysis without being a DBA
harness: agentdrive
---

# SQL explain

For each query report: **intent** (one sentence), **tables/indexes**, **join strategy**, **cost class** (low/medium/high), **risks** (full scan, implicit cast, N+1).
