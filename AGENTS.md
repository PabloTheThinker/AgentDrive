# AGENTS.md — Notes for AI contributors

AgentDrive is built *by* humans and *with* AI agents. This file orients an AI contributor — Claude, Codex, Cursor, an in-house copilot — to the project's conventions so changes land cleanly the first time.

If you're a human contributor, [`CONTRIBUTING.md`](CONTRIBUTING.md) + [`DEVELOPERS.md`](DEVELOPERS.md) are your starting points instead.

## What this project is

- **Product:** AgentDrive — "RAID for AI agents." A local-first system that decomposes successful agent runs into typed, versioned **genomes** so agent capability survives the death of any individual process.
- **Engine:** Agent Drive. Open-source, MIT-licensed Python framework. Imported as `agentdrive` at the top of the public API; the internal modules retain `agentdrive` naming in a few legacy spots.
- **Posture:** Local-first. Privacy-absolute. No cloud control plane, no telemetry, no shared cache. Federation is opt-in, pull-only, and routes every foreign genome through quarantine.

Read [`VISION.md`](VISION.md) for the full framing before making non-trivial changes.

## Layout you need to know

| Path                                | What lives here |
|-------------------------------------|-----------------|
| `src/agentdrive/cap/`               | Capability URI grammar, `CapStore`, signing, verification |
| `src/agentdrive/drive/`             | The Drive primitive — content store + genome registry |
| `src/agentdrive/web/`               | FastAPI daemon + Jinja templates |
| `src/agentdrive/quarantine/`        | Foreign-DNA sandbox + promotion gate |
| `src/agentdrive/peers/`             | Peer registry + federation transport |
| `src/agentdrive/reconciliation/`    | The healing loop |
| `docs/`                             | User + technical docs |
| `examples/`                         | Runnable AgentDrive API examples |
| `tests/`                            | Pytest suite |

The public API is re-exported at `src/agentdrive/__init__.py`. Don't reach into submodules from examples or external docs.

## Hard rules

1. **Every mutating web route MUST verify through `CapStore.verify_request()`.** The single dependency factory is `require_cap()` in `src/agentdrive/web/authz.py`. Auth-system lifecycle routes (signup/setup/logout/user-approve) are the documented exception in [`SECURITY-HARDENING.md`](SECURITY-HARDENING.md).
2. **No cloud telemetry. No phone-home. Ever.** PRs that add network calls outside the federation protocol will be closed.
3. **Genome schema changes require a schema-version bump + a migration** in `src/agentdrive/drive/migrations/`. Do not silently change the shape of stored genomes.
4. **Trust boundaries are explicit.** Anything entering the live pool from outside the local Drive — peer genomes, imported snapshots, third-party adapters — passes through `quarantine.submit` and the evaluator gate. `trust_level` adjusts the quorum, it does not bypass the gate.
5. **`trash` > `rm`.** When cleaning up, prefer recoverable operations.

## Conventions

- **Public API:** `from agentdrive import Harness, AgentDrive, DriveQuery, DriveSettings, Genome, GenomeRegistry, Quarantine, DNADrive, LineageImmuneSystem, LineageDNAEvolver, GrantStore, ReconciliationRunner, ...`. Add to the package root (see the big `__all__` block in `src/agentdrive/__init__.py`), not to a submodule, when introducing a new top-level concept.
- **Type hints** are expected on public functions. `mypy src/agentdrive` runs as an informational check.
- **Ruff** owns lint + format. `ruff check .` and `ruff format --check .` must pass.
- **Tests live in `tests/`** mirroring the source tree. New mutating routes need an authz test that proves both the allow and deny paths.
- **Docs filenames** in `docs/` are preserved for link stability — content can be refactored, filenames stay.

## Common tasks

### Adding a new mutating web route

1. Add the handler to `src/agentdrive/web/app.py`.
2. Use `Depends(require_cap(scheme, action, resource_kind=..., resource_id=...))` — never roll your own auth.
3. Append to the audit log via the existing middleware; do not write directly to `audit.log`.
4. Add a test in `tests/web/` proving an unauthorized request returns 401/403 and an authorized request succeeds.

### Adding a new genome field

1. Bump the schema version in `src/agentdrive/drive/genome.py`.
2. Write a migration under `src/agentdrive/drive/migrations/` keyed by the new version.
3. Update `GENOME-SPEC.md` and add an example to `genomes/examples/`.
4. Run `pytest tests/drive/test_migrations.py` to confirm existing genomes still load.

### Adding a peer-federation message type

1. Update the message schema in `src/agentdrive/peers/messages.py`.
2. Route receive-side handling through `quarantine.submit` — never bypass.
3. Add an adversarial test under `tests/peers/` that confirms a malformed payload is quarantined and the audit log records the rejection.

## Things to avoid

- **Don't introduce a new auth path.** Cap + admin role are the only two. If you think you need a third, open a Discussion first.
- **Don't add background network calls.** No periodic check-ins, no version-update pings, no analytics — even anonymous.
- **Don't add a new top-level config file.** Settings live in `~/.agentdrive/config.yaml`. Extend the existing schema.
- **Don't paste large blocks of agent-generated code without reading them.** Genome schema, cap grammar, and federation transport are load-bearing; a plausible-looking diff that breaks an invariant is worse than no diff at all.

## Before you open a PR

- `ruff check . && ruff format --check . && pytest` all pass.
- The PR template (Problem / Solution / Test plan) is filled in.
- If the change is user-visible, `CHANGELOG.md` has an entry under `## Unreleased`.
- For feature work: a GitHub Discussion exists and is linked in the PR description.

Welcome aboard. Build carefully — every successful PR makes the pool more useful to the next operator who installs AgentDrive.
