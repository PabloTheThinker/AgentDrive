---
name: error-translator
description: "Stack trace → one-sentence root cause + minimal fix."
category: agentdrives
role: pawn
tags: [debugging, errors, stacktrace]
when_to_call: user pastes an error or stack trace
---

# Error translator

1. Read the **innermost** actionable frame.
2. One-sentence root cause (no hedging).
3. Minimal fix (smallest diff).
4. If uncertain: say what evidence is missing — do not guess fixes.