---
name: doctor
description: "Health check — install, MCP, pool, and config sanity."
agentdrive_operation: doctor
category: core
role: shared
tags: [doctor, health, onboarding]
when_to_call: something feels broken or before a golden-path run
---

# Doctor

Runs `agentdrive doctor` — first diagnostic any pawn or Arisen should run when stuck.

**Usage:** `/skill doctor`