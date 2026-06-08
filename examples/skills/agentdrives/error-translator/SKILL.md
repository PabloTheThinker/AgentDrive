---
name: error-translator
description: >
  Translate a stack trace to one-sentence root cause plus minimal fix. States missing evidence
  instead of guessing when uncertain.
category: agentdrives
role: pawn
tags: [debugging, errors, stacktrace, root-cause]
when_to_call: user pastes an error, exception, or failing test output
harness: agentdrive
---

# Error translator

1. Read the **innermost** actionable frame.
2. One-sentence root cause (no hedging).
3. Minimal fix (smallest diff).
4. If uncertain: say what evidence is missing — do not guess fixes.
