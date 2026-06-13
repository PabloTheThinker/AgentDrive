# AGENTS.md — For AI Contributors & Models Working on AgentDrive

This file is for models (Claude, Grok, Cursor, local agents, etc.) that are actively modifying or deeply using the AgentDrive codebase.

## Core Principle

**Never guess the current surface.**
Always start by calling the live `agentdrive_mcp_catalog(format="full")` (or the Python equivalent when working directly in the source).

The catalog + the `docs/ai-models/rules-and-patterns.md` page are the authoritative "rules for the AI".

## When Working in a Clone (the common case)

1. Be in the repo root.
2. Use the project's venv or your own after `pip install -e ".[mcp]"` (or the install.sh).
3. The MCP server, inhabitant source reader, and config helpers will all prefer the local tree.
4. When the human (or another agent) asks for client config, call `agentdrive_get_mcp_config_snippet(client=...)` from inside an MCP session or use the equivalent Python helper. This generates the correct dev block for the current clone.

## Documentation Style (OpenClaw + Hermes influence)

- We are moving toward a Mintlify-style structured docs site under `docs/` (`docs.json` + hierarchical folders + focused pages).
- The heart of the "instruction manual" for models lives in `docs/ai-models/`.
- Pages should be small, scannable, and actionable.
- Heavy use of "when to use", explicit patterns, tables, and "first action" callouts.
- SKILL-like or recipe-style sections are welcome when they help models (or humans directing models) execute reliably.

## Key Documents Models Should Read

- `docs/ai-models/rules-and-patterns.md` (the main operating manual)
- `docs/ai-models/local-models.md` and `docs/ai-models/quickstart.md`
- `docs/mcp/overview.md` and `docs/mcp/for-claude-cursor-codex.md`
- `docs/concepts/overview.md` (especially the sacred 6-step loop)
- Existing deep docs: `AD_GRID_JOIN.md`, `GOLDEN_PATH.md`, `MCP.md` (being migrated into the new structure)

## Code Changes by Models

- Prefer small, high-certainty changes with clear rationale recorded via the graph/inhabitants tools when possible.
- For source changes inside the clone, use the `inhabitant_*` code agency tools (`read_source`, `propose_code_change`, `apply_change`) with proper `program_id` + constitution refs.
- Always leave good traces (`experience_graph_record_reasoning`).

## Testing & Verification

- Run `agentdrive doctor --verbose` and `agentdrive mcp doctor` before claiming something is fixed.
- For model-facing changes, verify that `agentdrive_mcp_catalog()` reflects the improvement and that the new behavior is documented in the `ai-models/` section.

## Philosophy

We are building a system in which models (especially local ones) can live long-term, improve the user's substrate, and be governed.

Every trace you leave, every clear rationale, every recorded decision makes the next cycle (for you or for another agent) stronger.

Do the work in public inside the graph.

---

When in doubt: call the catalog, pull context, record your reasoning, follow the loop.