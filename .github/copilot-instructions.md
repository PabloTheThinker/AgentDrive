# GitHub Copilot Instructions for AgentDrive

You are contributing to **AgentDrive** — a local-first, privacy-absolute system that gives AI agents the resilience of RAID by decomposing successful runs into typed, versioned genomes.

Read [`AGENTS.md`](../AGENTS.md) for the full AI-contributor brief. The summary below is what you need before editing a file.

## Conventions

- Python 3.11+, `src/agentdrive/` layout.
- Public API at the package root: `from agentdrive import ...`. Don't import from submodules in examples or docs.
- Type hints on all public functions.
- Ruff for lint + format. Run `ruff check .` and `ruff format --check .` before suggesting a commit.

## Hard rules

1. **Every mutating web route uses `Depends(require_cap(scheme, action, ...))`.** The single verification path is `CapStore.verify_request()` in `src/agentdrive/cap/store.py`. Do not invent a parallel auth path.
2. **No cloud calls.** No telemetry, no analytics, no version pings.
3. **Foreign data is quarantined.** Anything from a peer routes through `quarantine.submit` before the live pool.
4. **Schema bumps require a migration** in `src/agentdrive/drive/migrations/`.
5. **`trash` over `rm`** when removing files.

## Tests

New mutating routes need an authz test that proves both the allow and deny paths. New genome-shape changes need a migration test. Federation message-type changes need an adversarial test confirming malformed payloads quarantine cleanly.

## What good looks like

A good Copilot suggestion in this repo:

- Uses the existing dependency factories (`require_cap`, `require_admin`) instead of inlining auth.
- Routes errors through the existing exception types in `src/agentdrive/exceptions.py`.
- Adds a test next to the change.
- Does not introduce a new top-level config file or environment variable without precedent.
- Does not paste a "TODO: handle errors" — handle them at the boundary or let them propagate to the FastAPI exception handler.

## What to flag back to the human

If a suggested change would:

- Cross a trust boundary (write to the live pool from outside the local Drive)
- Add a network call to a host the user did not configure
- Modify the cap URI grammar or genome schema
- Touch `src/agentdrive/cap/` or `src/agentdrive/quarantine/` substantively

…stop and surface the implication explicitly before writing the diff.
