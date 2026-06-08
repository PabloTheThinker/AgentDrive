---
name: sql-explain
description: "Explain SQL execution intent, indexes touched, and cost class."
category: agentdrives
role: pawn
tags: [sql, database, explain]
when_to_call: user pastes a SQL query and wants plain-English execution analysis
---

# SQL explain

For each query report: **intent** (one sentence), **tables/indexes**, **join strategy**, **cost class** (low/medium/high), **risks** (full scan, implicit cast, N+1).