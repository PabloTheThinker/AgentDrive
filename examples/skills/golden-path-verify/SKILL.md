---
name: golden-path-verify
description: >
  Verify the seven-step first-run loop (install, doctor, MCP, think, learnings, query) without
  mutating state. Reports which steps pass or fail.
agentdrive_operation: golden_path_verify
category: core
role: shared
tags: [golden-path, verify, onboarding, health]
when_to_call: before or after first run, CI smoke, or when onboarding health is uncertain
---

# Golden path verify

Runs the doctor operation as a quick health check step from the golden path.

For the full walkthrough use `/golden-path run` or `agentdrive golden-path run`.
