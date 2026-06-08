---
name: learnings-log
description: Record one operational learning (key + insight) into the shared hive so future sessions and pawns inherit the note.
agentdrive_operation: learnings_log
argument: input
category: core
role: shared
tags: [learnings, memory, hive, record]
when_to_call: durable decision, runbook note, or pawn handoff worth remembering
---

# Learnings log

Writes to the AgentDrive learnings layer so **all pawns and future sessions** inherit the note.

**Usage:** `/skill learnings-log first-run Golden path completed on Parallax`
