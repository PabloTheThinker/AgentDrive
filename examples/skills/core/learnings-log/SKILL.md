---
name: learnings-log
description: "Record operational memory — one key + insight for future sessions."
agentdrive_operation: learnings_log
argument: input
category: core
role: shared
tags: [learnings, memory, hive]
when_to_call: user wants to persist an insight, decision, or runbook note
---

# Learnings log

Writes to the AgentDrive learnings layer so **all pawns and future sessions** inherit the note.

**Usage:** `/skill learnings-log first-run Golden path completed on Parallax`