# Savant Swarm Pools — DNA for Sub-Agents

> Part of the Savant engine — the open-source substrate behind AgentDrive. See [README](../README.md).

> **Note**: This document is superseded by the professional documentation suite:
> - `docs/POOL.md` — Full guide to the Savant Pool
> - `docs/SWARM.md` — Per-sub-agent pools, DNA growth, swarm dynamics
> - `docs/INTEGRATION.md` — Connecting Grok, Claude, Codex, etc.
> - `docs/SETTINGS.md` — Complete user-controllable settings reference
>
> Please refer to the new docs for the authoritative, up-to-date information.

---

When any AI (Grok, Claude Code, Codex, custom model, etc.) deploys sub-agents — exactly like the Grok build system does with `spawn_subagent` — each sub-agent receives its own isolated **Savant Pool**.

## Why Swarm Pools?

- **DNA = Memory + Patterns**: Every sub-agent's experience (successful frameworks, reasoning traces, tool compositions, outcomes) becomes portable, versioned, forkable DNA — the inherited-trait metaphor borrowed from biology, not from any franchise.
- The parent agent keeps the "global" pool.
- Each child gets a private, persistent pool that starts **empty** and fills only with *its own* work.
- This prevents contamination while still allowing selective sharing (user-controlled policies).
- The entire swarm's collective intelligence compounds because improvements in one sub-pool can be proposed upward or shared laterally under user rules.

This is the "Exo Labs for agent experience" — instead of connecting hardware, we connect lived agent experience across the swarm so they all grow faster together.

## User Control (Non-Negotiable)

Every Savant installation belongs to the user. The pool starts empty. The user (or any AI instructed by the user) can change:

- `isolation_level`: none | swarm | subagent (default: subagent)
- `auto_ingest_on_success`
- `sharing_policy`
- `retention`, quality thresholds, etc.

Settings live in `~/.savant/config.yaml` and can be overridden per-swarm or per-run.

## How Models Connect

Savant provides clean adapters (MCP server, stdio, HTTP) so:

- Grok build system / Claude Code / Codex / any model can be told: "use SavantPool for your sub-agents".
- Each spawned sub-agent gets `SAVANT_SWARM_ID` + `SAVANT_SUBAGENT_ID` environment or context, automatically scoping its pool.

See `adapters/` and `docs/INTEGRATION.md` (coming soon).

The result: every time you (or an AI) spawn a swarm of agents, the whole swarm gets a living, private, user-owned memory system that lets the sub-agents learn, adapt, and train themselves — exactly like the parent does.

This is the foundation for true multi-agent, self-improving systems that respect user sovereignty.
