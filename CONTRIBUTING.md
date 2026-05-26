# Contributing to AgentDrive

Thank you for your interest in contributing to AgentDrive — RAID for AI agents, powered by the open-source Agent Drive engine.

We hold ourselves to a high engineering standard: clear contracts, calm interfaces, and clean open-source practices.

## Code of Conduct

This project adopts the [Contributor Covenant](CODE_OF_CONDUCT.md). Be respectful, constructive, and focused on building the best possible foundation for agent memory and collective intelligence.

## Feature work — propose first

**Feature PRs are gated behind a GitHub Discussion.** Before opening a PR that adds, changes, or removes user-facing behavior, open a thread under [Discussions → Ideas](https://github.com/PabloTheThinker/agentdrive/discussions/categories/ideas) describing:

- The problem you're solving
- The proposed shape of the solution
- Alternatives considered
- Impact on the genome schema, capability URI grammar, or federation contract (if any)

This keeps the RFC surface lightweight while protecting the engine from drive-by architectural changes. Bug fixes, docs, tests, and small refactors do **not** need a Discussion — go straight to a PR.

## Getting started (development)

### Fork & clone

```bash
git clone https://github.com/YOUR_USERNAME/agentdrive.git
cd agentdrive
```

### Set up development environment

```bash
python -m pip install -e ".[dev]"
```

For a one-command bring-up of a local Drive + 2 sub-agents + simulated peer, see [`DEVELOPERS.md`](DEVELOPERS.md).

### Run the daemon

```bash
agentdrive web        # FastAPI daemon on http://127.0.0.1:8421
agentdrive            # TUI
```

### Run tests

```bash
pytest
pytest --cov=src/agentdrive
```

### Code style

- `ruff check .` and `ruff format .` before committing — CI enforces both.
- Type hints are expected on public functions; `mypy` runs as an informational check.
- Keep the TUI and web experience delightful and professional.

## Project structure

- `src/agentdrive/` — main package (src layout); contains `drive/`, `harness/`, `adapters/`, `reasoning/`, `scanners/`, `quarantine/`, `peers/`, `inheritance/`, `confidence/`, `reconciliation/`, `cap/`, `web/`
- `scripts/` — `install.sh`, `install.ps1`, release helpers
- `genomes/examples/` — seeded reference genomes
- `tests/` — pytest suite
- `docs/` — user and technical documentation
- `examples/` — runnable AgentDrive API examples (`01_hello_drive.py`, `02_dedup.py`, `03_swarm.py`)
- `site/` — landing site (static)

## Pull request process

1. Create a focused branch from `main`.
2. Make your changes + add or update tests.
3. Run `pytest` and `ruff check .` locally.
4. Update documentation if behavior changes (including `CHANGELOG.md` if user-visible).
5. Open a PR using the template (Problem / Solution / Test plan).

We review for:

- User sovereignty and safety (the local-first, privacy-absolute posture)
- Capability enforcement passes through the single verification path (`CapStore.verify_request`)
- Code clarity and maintainability
- Consistency with the existing professional tone
- Performance and correctness of the Drive + Harness + federation system

## Reporting issues

Use [GitHub Issues](https://github.com/PabloTheThinker/agentdrive/issues). The bug-report template asks for:

- OS + Python version
- AgentDrive version (`agentdrive --version`)
- Swarm topology (parent + sub-agent count, peers configured, federation state)
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs (`~/.agentdrive/audit.log` and daemon stderr are usually enough)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for helping make agent memory trustworthy, private, and evolutionary.
