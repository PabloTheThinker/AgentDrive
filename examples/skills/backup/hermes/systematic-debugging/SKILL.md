---
name: systematic-debugging
description: >
  Four-phase root-cause debugging — investigate, pattern-match, hypothesize, fix. No fixes before understanding WHY. Stop after three failed fixes and question architecture.
category: backup
role: shared
source: hermes-adapted
tags: [debugging, root-cause, hermes, troubleshooting]
when_to_call: bug, test failure, unexpected behavior, or production incident
---

# Systematic debugging (Hermes-adapted)

**Iron law:** NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST.

## Phases

1. **Root cause** — read errors, reproduce, check recent changes, trace data flow.
2. **Pattern** — find working examples in codebase; diff against broken.
3. **Hypothesis** — one theory, minimal test, verify.
4. **Implementation** — regression test first, single fix, full suite.

If 3+ fixes failed: stop — question architecture; discuss with Arisen.

Use with `pawn-worker` for headless swarm runs; use `grok-check-work` for verification pass.
