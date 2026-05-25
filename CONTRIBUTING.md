# Contributing to Savant

Thank you for your interest in contributing to Savant — the user-sovereign living DNA system for AI agent swarms.

We hold ourselves to a high engineering standard: clear contracts, calm interfaces, and clean open-source practices.

## Code of Conduct

Be respectful, constructive, and focused on building the best possible foundation for agent memory and collective intelligence.

## Getting Started (Development)

### 1. Fork & Clone

```bash
git clone https://github.com/YOUR_USERNAME/agentdrive.git
cd agentdrive
```

### 2. Set up Development Environment

We strongly recommend using the installer in dev mode:

```bash
curl -fsSL https://vektraindustries.com/agentdrive/install | bash -s -- --dev
```

Or manually:

```bash
python -m pip install -e ".[dev]"
```

### 3. Run the TUI during development

```bash
savant
# or
python -m savant.tui.app
```

### 4. Run Tests

```bash
pytest
# or with coverage
pytest --cov=src/savant
```

### 5. Code Style

- Run `ruff check .` and `ruff format .` before committing.
- Type hints are expected on public functions.
- Keep the TUI experience delightful and professional.

## Project Structure

- `src/savant/` — Main package (src layout)
- `scripts/` — `install.sh`, `install.ps1`, future automation
- `genomes/examples/` — Seeded high-quality genomes
- `tests/` — Pytest suite
- `docs/` — User and technical documentation

## Pull Request Process

1. Create a focused branch from `main`.
2. Make your changes + add/update tests.
3. Run the full test suite and linters.
4. Update documentation if behavior changes.
5. Open a clear PR with:
   - What problem it solves
   - How it was tested
   - Any breaking changes

We review for:
- User sovereignty and safety
- Code clarity and maintainability
- Consistency with the existing professional tone
- Performance and correctness of the Pool + Harness system

## Reporting Issues

Use the GitHub Issues tab. Please include:
- Your OS + Python version
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs (`savant doctor` output is helpful)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for helping make agent memory trustworthy, private, and evolutionary.