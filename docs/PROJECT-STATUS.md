# AgentDrive / Agent Drive — Project Status

**Date:** 2026-05-25
**Audit scope:** docs, public naming, site truth, and local quality-gate wording.
**Source code logic:** untouched in this pass.

---

## 1. Product / engine split

AgentDrive is the public product name. Agent Drive remains acceptable where it is
describing the internal engine, older design notes, or Python object names that
still exist in historical examples. Public copy should not pitch "Agent Drive" as the
product unless the page is explicitly about engine internals.

Current public-facing state:

- `README.md` leads with AgentDrive and describes Agent Drive only as an internal
  engine concern where relevant.
- `site/index.html` is AgentDrive-facing and should avoid overstating unbuilt
  surfaces.
- `agentdrive` is the product CLI entrypoint in `pyproject.toml`; older `agentdrive`
  command references in docs should be treated as legacy/internal unless
  confirmed still intentional.
- `docs/POOL.md`, `docs/POOL-EVOLUTION.md`, and `docs/INTEGRATION.md` may keep
  Agent Drive terminology where they explain the engine pool model, but product
  framing should point back to AgentDrive.

## 2. Current verification

Fresh local checks from this docs pass:

| Command | Status | Notes |
|---|---|---|
| `pytest -q` | pass | Current count intentionally not hardcoded; use live pytest output as source of truth. |
| `pytest -q --disable-warnings` | pass | Confirms the suite passes without relying on warning output. |
| `ruff check src tests` | pass | `All checks passed!` |
| `mypy --version` | not installed | Mypy is configured as informational in CI, but was not locally available in this checkout. |

Known warning class from test output: repeated `datetime.utcnow()` deprecation
warnings from `src/agentdrive/genome/models.py`. This pass did not touch source
code.

## 3. What works today

- AgentDrive package metadata, CLI alias, examples, and site exist.
- CI exists for pytest and ruff, with CodeQL still present.
- The core test suite passes locally.
- `agentdrive web` is the current FastAPI + HTMX direction and binds to
  `http://127.0.0.1:8421` by default.
- The older `:8420` snapshot UI is now treated as legacy/snapshot-specific until
  its controls are absorbed into the FastAPI app.

## 4. Remaining gaps

- **FastAPI web Phase 2+.** The app has auth, setup/login, dashboard shell, and
  admin user approval, but Drive/Swarms/DNA/Snapshots/Capabilities/Peers need
  real pages and backed behavior.
- **Capability enforcement audit.** The README's capability claim should be
  backed by a pass over every user-facing path, especially new web routes and
  legacy snapshot controls.
- **Package hygiene.** Confirm stale rename artifacts are not tracked and keep
  generated package metadata ignored.
- **Naming cleanup.** Older docs still contain Agent Drive-first language. Keep
  Agent Drive where it means the engine; reduce it where it reads like public product
  branding.
- **Docker/self-host demo.** Still absent unless added in another branch.
- **PyPI/release.** Do not claim `pip install agentdrive` works from PyPI until
  a real release exists.
- **`CODE_OF_CONDUCT.md` / `DEVELOPERS.md`.** Still useful for OSS polish if
  absent in the current branch.

## 5. Recommended next fixes

1. Build the `agentdrive web` Phase 2 dashboard pages and route snapshot control
   through the new FastAPI surface.
2. Audit capability checks across CLI, web, adapters, and snapshot paths.
3. Continue link-preserving naming cleanup in older Pool/Agent Drive docs.
4. Add Docker/self-host and PyPI release paths only when they are real.
