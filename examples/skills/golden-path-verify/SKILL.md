---
name: golden-path-verify
category: core
role: shared
tags: [golden-path, verify, onboarding]
when_to_call: check install MCP learnings query loop before or after first run
description: Check golden path install → mcp → learnings → query without mutating state.
agentdrive_operation: golden_path_verify
---

# Golden path verify

Runs the doctor operation as a quick health check step from the golden path.

For the full walkthrough use `/golden-path run` or `agentdrive golden-path run`.