---
name: doctor
description: >
  Run AgentDrive health checks — install, config, MCP bridge, pool, and environment sanity. First
  diagnostic when something feels broken.
agentdrive_operation: doctor
category: core
role: shared
tags: [doctor, health, diagnose, onboarding]
when_to_call: errors, broken MCP, empty pool, or before golden-path run
harness: agentdrive
---

# Doctor

Runs `agentdrive doctor` — first diagnostic any pawn or Arisen should run when stuck.

**Usage:** `/skill doctor`
