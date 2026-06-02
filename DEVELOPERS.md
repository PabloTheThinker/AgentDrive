# DEVELOPERS — One-Command Bring-Up

This is the contributor's quick-start. For high-level orientation read [`VISION.md`](VISION.md), then [`ARCHITECTURE.md`](ARCHITECTURE.md). For the project's public framing read [`README.md`](README.md).

## Prerequisites

- Python 3.11+
- `git`
- (Optional) Docker + Docker Compose v2 — only needed for the federated peer demo

## Editable install

```bash
git clone https://github.com/PabloTheThinker/agentdrive.git
cd agentdrive
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

This installs the `agentdrive` CLI, the `agentdrive` engine package, the test deps (`pytest`, `pytest-asyncio`), and the lint/format tools (`ruff`, `mypy`).

## One-command demo — local Drive + 2 sub-agents + simulated peer

```bash
make dev
```

`make dev` does five things:

1. Wipes `~/.agentdrive-dev/` so the demo is reproducible (your real `~/.agentdrive/` is untouched).
2. Starts the FastAPI daemon on `http://127.0.0.1:8421` with `AGENTDRIVE_HOME=~/.agentdrive-dev`.
3. Spawns a parent Drive plus two sub-agent Drives via `examples/03_swarm.py`, ingesting seed genomes from `genomes/examples/`.
4. Boots a second daemon on `:8422` posing as a remote peer, mints a peer cap, and registers each side in the other's `peers.yaml`.
5. Tails both audit logs side-by-side so you can watch cap verifications + quarantine decisions in real time.

Hit `Ctrl-C` to stop. State persists in `~/.agentdrive-dev/` for inspection; rerun `make dev` to reset.

The same flow as raw commands lives in [`scripts/dev-bringup.sh`](scripts/dev-bringup.sh).

## Running the test suite

```bash
pytest                              # full suite
pytest --cov=src/agentdrive         # with coverage
pytest tests/test_cap_uri.py -v     # one file
pytest -k quarantine                # by name match
```

CI runs `pytest` + `ruff check .` + `ruff format --check .` on every PR. `mypy src/agentdrive` runs as an informational check (failures don't block merge yet).

## Project layout

```
src/agentdrive/
├── cap/              # capability URI grammar + CapStore + verification path
├── drive/            # Drive primitive (the local pool + content store)
├── harness/          # runtime harness that wraps agent calls
├── adapters/         # model + framework adapters (Claude, Codex, Grok, MCP)
├── reasoning/        # reasoning primitives + scoring
├── scanners/         # post-run signal extraction
├── quarantine/       # foreign-DNA sandbox
├── peers/            # peer registry + federation transport
├── inheritance/      # inheritance manifest assembly
├── confidence/       # confidence ratings + decay
├── reconciliation/   # reconciliation runner (the healing loop)
└── web/              # FastAPI daemon + Jinja templates
docs/                 # user + technical docs
examples/             # runnable AgentDrive API examples
genomes/examples/     # seed genomes shipped with the repo
scripts/              # install.sh, release.sh, dev-bringup.sh
docker/               # docker-compose self-host artifact
```

## Conventions

- **Public API lives at the package root.** `from agentdrive import Harness, AgentDrive, DriveQuery, ...` — never reach into submodules from user-facing examples.
- **All mutating web routes go through `require_cap()`.** The single verification path is `CapStore.verify_request()` in `src/agentdrive/cap/store.py`. Auth-system lifecycle routes use `require_admin` and are documented in [`SECURITY-HARDENING.md`](SECURITY-HARDENING.md).
- **Genome schema is versioned.** Bumps to the genome shape require a schema-version increment and a migration in `src/agentdrive/drive/migrations/`.
- **No cloud telemetry. Ever.** AgentDrive is local-first by contract. PRs that introduce phone-home behavior will be closed.

## Where to file what

| Kind of work          | Where it goes |
|-----------------------|---------------|
| Bug report            | [Issues](https://github.com/PabloTheThinker/agentdrive/issues) — use the bug template |
| Feature proposal      | [Discussions → Ideas](https://github.com/PabloTheThinker/agentdrive/discussions/categories/ideas) first, then PR |
| Security report       | GitHub Security (private) or see [`SECURITY.md`](SECURITY.md) |
| Docs typo / small fix | Direct PR is fine |

## Releasing

Maintainers only. See [`scripts/release.sh`](scripts/release.sh) and the tag-driven workflow in [`.github/workflows/release.yml`](.github/workflows/release.yml).
