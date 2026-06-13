---
title: "Golden Path"
description: "The canonical 10-minute first-run that proves the entire system is working for both humans and AI models."
---

# Golden Path

The Golden Path is the shortest sequence that demonstrates a healthy, useful AgentDrive installation for both human operators and the AI models that will use it.

Do this once after install or after cloning. It seeds the drive, proves MCP, proves synthesis + recording, and leaves you with a working substrate.

## The Sequence

1. `agentdrive doctor`
   Verifies home, config, registry, pool, workers, MCP bridge.

2. `agentdrive mcp install && agentdrive mcp doctor`
   Installs the MCP extra (editable if in a clone) and writes client configs. Verifies the bridge reports tools.

3. `agentdrive golden-path run` (or step through manually)
   - Seeds experience layer if needed.
   - Runs a `think`.
   - Logs a learning.
   - Performs a drive query.

4. Connect at least one model via MCP and have it call `agentdrive_mcp_catalog()`.

5. (Optional but recommended for models) Launch the Grid + Tower:
   ```bash
   agentdrive grid run --swarm-id stabilization-wave-20260531 --with-tower
   ```
   Visit the Tower to see the system is alive.

## What Success Looks Like

- `doctor` is all green (or only "AI provider not configured" if you haven't set one yet).
- MCP doctor reports ~39–41 tools registered and the launcher resolved correctly.
- A `think` returns cited synthesis with mandatory gaps.
- Learnings are logged and queryable.
- Your connected model (Claude, local LLM, etc.) can see the catalog and pull a context pack.

## For AI Models Reading This

If a human has just run the Golden Path and connected you:

- Call `agentdrive_mcp_catalog()` now.
- Pull a `experience_graph_get_context_pack`.
- Record something (even a small structural observation) with `experience_graph_record_reasoning`.
- This proves the loop works for you.

The stabilization-wave drive is deliberately rich with real traces from the system's own development. Study it.

## After the Golden Path

- Read the full **[Rules for AI Models](/ai-models/rules-and-patterns)**.
- Explore concepts.
- Start real work (or let an autonomous agent start real work).
- Come back to `doctor` and `mcp doctor` whenever something feels off.

The Golden Path is not the destination. It is the proof that the substrate is alive and that you (the model) can think inside it.