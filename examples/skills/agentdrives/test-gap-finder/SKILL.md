---
name: test-gap-finder
description: >
  Compare a function to its tests and list uncovered cases ranked by risk. Finds gaps first; does
  not write tests unless asked.
category: agentdrives
role: pawn
tags: [testing, pytest, coverage, quality, risk]
when_to_call: are tests sufficient, what's missing, or pre-refactor risk check
harness: agentdrive
---

# Test gap finder

Read function + existing tests. Output ranked gaps: **case**, **risk** (high/med/low), **why not covered**. Do not write tests unless asked — find gaps first.
