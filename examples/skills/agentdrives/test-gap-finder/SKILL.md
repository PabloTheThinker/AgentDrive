---
name: test-gap-finder
description: "List test cases NOT covered, ranked by risk — better than write more tests blindly."
category: agentdrives
role: pawn
tags: [testing, pytest, quality]
when_to_call: user asks if tests are sufficient or what's missing
---

# Test gap finder

Read function + existing tests. Output ranked gaps: **case**, **risk** (high/med/low), **why not covered**. Do not write tests unless asked — find gaps first.