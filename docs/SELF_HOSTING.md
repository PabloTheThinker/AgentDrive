# Self-Hosting AgentDrive

AgentDrive is designed for sovereign, local-first operation. No cloud control plane, no telemetry, no shared caches. Everything lives under `~/.agentdrive/`.

## Quick Start (Linux/macOS)

```bash
# 1. Install (user scope recommended)
curl -fsSL https://raw.githubusercontent.com/PabloTheThinker/AgentDrive/main/scripts/install.sh | bash

# or via pip
python3 -m pip install --user git+https://github.com/PabloTheThinker/AgentDrive.git

# 2. Verify
agentdrive doctor
```

The installer creates `~/.agentdrive/config.yaml`, `genomes/`, `trust/`, and the web/TUI entry points.

## Instance Identity

Set a friendly name for *your* deployment:

```bash
export AGENTDRIVE_INSTANCE_NAME="My Research Drive"
# or
export AGENTDRIVE_INSTANCE_NAME="Team Orion Core"
```

The framework itself remains called **AgentDrive**.  
Only your runtime gets the personal name you choose. This is the recommended pattern for self-hosted / team deployments.

## Production Recommendations

- Run under a dedicated user with minimal privileges.
- Keep `~/.agentdrive/.env`, key databases (`auth.db`, `caps.db`, `grants.db`), and trust key material (`trust/self.json`, `trust/pending.pem`) at `chmod 600`.
- Use the built-in `agentdrive doctor` regularly — it now surfaces instance name + lightweight security posture.
- For long-running services, use the context manager for clean shutdown:

```python
from agentdrive import AgentDrive
with AgentDrive(name="prod-substrate") as d:
    # long running work
    ...
# explicit close() also available for non-context usage
```

## Docker / Compose (optional)

See `docker/` for a minimal compose that mounts your `~/.agentdrive` and exposes the web UI on a chosen port. All data remains on your host volume.

## Federation (opt-in, pull-only)

Peers are discovered via explicit registry entries under `peers/`. All inbound genomes are quarantined and must pass the evaluator gate before promotion. No automatic push, no shared cache.

## Backup & Recovery

- The entire state is the `~/.agentdrive/` tree (genomes are content-addressed JSON + sidecars).
- `agentdrive snapshot` / `restore` (or manual tar of the tree) gives point-in-time recovery.
- Reconciliation + HealingFactor + experience layer v3 daily consolidation provide the live self-healing substrate.

## Security Posture

Run `agentdrive doctor --security` (or the TUI security panel) for:

- grants.db / caps.db / auth.db permission hygiene (600)
- trust material age / rotation signals
- reconciliation health depth
- active quarantine count + recent releases
- revoked grant hygiene
- schema evolution security proposals

All checks are local and actionable. No phone-home.

## TUI & Web UI

- `agentdrive tui` — full terminal dashboard, chat, genome browser, reconciliation view
- `agentdrive web` — local FastAPI + Jinja UI (default http://127.0.0.1:8080)
- Both surface the same Drive + experience layer + HealingFactor state.

## First-Run Ownership

Onboarding (web or TUI) prompts for instance name + first agent identity. This is stored in config and used for headers, doctor output, and default experience genome metadata. No cloud account required.

## Upgrades

`agentdrive self-update` (when enabled) or re-running the install script pulls the latest from the canonical repo while preserving your local genomes, state, and config. Always review CHANGELOG.md.

## Philosophy

AgentDrive exists so that successful agent work survives the death of any individual process, machine, or swarm. Genomes are the DNA. The Drive is the body. You are the Conductor.
