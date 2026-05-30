# Dependency Updates Framework

**Goal**: Make absorbing Dependabot (and manual) dependency bumps a predictable, low-drama, auditable process that improves the project rather than creating technical debt.

This framework treats dependency updates as first-class changes that go through the same rigor as any other improvement (review, testing under real conditions, quarantine of risky changes, promotion only when healthy).

## Core Principles

1. **Never merge a dep bump blindly**. The unit tests on the PR branch are necessary but not sufficient.
2. **Reproduce under the new versions** using an isolated environment before declaring "compatible".
3. **Run the deep canaries** (healing, federation, failure modes) — these catch real behavioral changes that unit tests miss.
4. **Document the delta**. Every non-trivial bump must produce a short "compatibility note".
5. **Use the project's own mechanisms**. Promotion proposals, quarantine for risky external changes, genomes for the update playbook itself.
6. **Evolve the framework**. The process is versioned and can itself be improved via the dreaming/promotion loop.

## Standard Process (for any future bump)

### 1. Triage (on Dependabot PR or manual proposal)
- Identify scope: patch vs minor vs major group bump.
- Check Dependabot PR description for breaking changes / deprecations.
- Note affected areas (web, async clients, crypto, testing, etc.).

### 2. Reproduce & Validate (mandatory)
- Checkout the Dependabot branch (or create one with the proposed pins).
- Create isolated venv: `python -m venv /tmp/deps-verify && pip install -e ".[test]"` (resolves to the new bounds).
- Run:
  - `ruff check src/ tests/ && ruff format --check`
  - `pytest -q`
  - The three deep canaries: `scripts/test_*.py`
- Capture any new warnings, deprecations, or failures.

### 3. Fix & Improve (if needed)
- Address hard failures and high-severity deprecations.
- Improve test coverage for the changed libraries if gaps are revealed.
- Update any "tested with" notes.

### 4. Compatibility Note
Create or update a short section in this document (or a per-bump note) covering:
- Libraries changed + versions
- Behavioral deltas observed
- Workarounds or code changes required
- Remaining known deprecations / future work

### 5. Promotion Decision
- Low-risk (patch, action bumps, no test impact): update branch + merge after clean CI.
- Medium-risk (minor version of core libs): require the full reproduction above + sign-off.
- High-risk (major or group bumps with many changes): treat as a formal proposal. Use quarantine if the change touches external interfaces or persistence.

### 6. Post-Merge
- Run the full canary suite on main.
- Update any lockfiles or "known good" combinations if we adopt them.
- Feed learnings back into this framework (or a dedicated "dependency-update" genome).

## Tooling Support

### Doctor Command
`agentdrive doctor --deps` (or `agentdrive deps check`) should:
- Report current installed versions vs declared bounds.
- Flag known problematic combinations.
- Suggest next safe upgrade windows.

### CI
- Dependabot PRs automatically run the full matrix.
- Optional periodic "latest compatible" job (tests against upper bounds or latest satisfying the current pins).

### Genomes
The recommended process above can itself be encoded as a reusable genome (`dependency-update-process`).

When a significant bump arrives, the system can propose using (or evolving) that genome for the update campaign.

## Current Known State (as of latest group bump)

**Successfully absorbed (2026-05)**:
- httpx 0.28.1
- fastapi 0.136.3 + starlette
- uvicorn 0.48
- cryptography 48
- pytest-asyncio 1.4

**Observed**:
- StarletteDeprecationWarning on `httpx` + `starlette.testclient` (library-level; tracked for when `httpx2` stabilizes).
- No behavioral breakage in core drive, quarantine, healing, federation, or failure-mode paths.

**Framework Version**: 1.0 (initial)

See also:
- `pyproject.toml` for current declared bounds
- CI workflow for test matrix
- The three deep canary scripts as the compatibility gate
