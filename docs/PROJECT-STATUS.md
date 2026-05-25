# AgentDrive / Savant — Project Status

**Date:** 2026-05-24
**Audit scope:** docs, naming, surface polish, fresh-user verification.
**Source code logic:** untouched.

---

## 1. Product / engine split

The AgentDrive (product) ↔ Savant (engine) relationship is now consistent
across every user-facing surface that frames the project. `README.md`
opens with the "Powered by Savant — productized as AgentDrive" banner;
`VISION.md` carries the RAID analogy and pins the relationship in
marketing copy; `docs/RECOVERY.md` is explicitly the AgentDrive healing
loop, written against modules in `src/savant/`. Engine-internal docs
(`SWARM.md`, `POOL.md`, `INTEGRATION.md`, `SETTINGS.md`,
`SWARM_POOLS.md`) now each carry a one-line header pointing back at
the AgentDrive product framing in `README.md` — they remain
engine-voiced (they describe `Harness`, `SavantPool`, swarms,
config), which is correct: those are engine surfaces. The CLI banner
(`Savant Framework — living memory for AI agents`) and `pyproject`
description both stay engine-voiced; `pyproject` description has been
updated to call out the AgentDrive product line so PyPI metadata is
coherent with the README.

`MISSION_PLAN.md` is **stale** — it predates AgentDrive and frames
Savant as 100%-branded-Savant. Flagged below; not edited.

## 2. Cross-project audit

Grep across the repo for references to defunct or unrelated projects
that don't belong in a public OSS surface (specific names redacted
from the repo — see internal notes on the build server).

| File | Line | Issue | Classification |
|---|---|---|---|
| `docs/POOL-EVOLUTION.md` | 38, 102, 121 | mentions of a defunct external framework as integration example | **strip** — drop the example or replace with a generic "trusted peer" reference |

**Counts:** legit = 0 · strip = 3 (all in one file, same defunct
external project) · rename = 0. The bleed is contained to a single
doc that was written before that project was archived.

**Also flagged** (outside the requested keyword set, but the hard
constraint says "no DD/franchise references"): `docs/POOL-EVOLUTION.md`
§1 and §2 cite Dragon's Dogma 1/2 mechanics by name (DD1, DD2,
Dragonsplague, Rift Crystal, etc.) as research provenance. The doc's
own header acknowledges this is source vocabulary; per constraint it
should be neutralized to generic "borrow-and-return systems" framing.
Not edited — flagged for Pablo's call.

## 3. Verification matrix

Fresh `SAVANT_HOME=/tmp/agentdrive-verify-$$`.

| # | Command | Status | Evidence |
|---|---|---|---|
| 1 | `savant --version` | ✓ clean | `Savant 0.1.0` |
| 2 | `savant doctor` | ✓ clean | Config, Registry, Pool, Worker, Deps all ✓; AI provider intentionally unconfigured |
| 3 | `savant pool status` | ✓ clean | empty pool, paths resolved under `$SAVANT_HOME` |
| 4 | `savant pool stats` | ✓ clean | `No ingest events yet` — expected on empty home |
| 5 | `savant genomes list` | ✓ clean | empty, suggests `savant scan <dir>` |
| 6 | `savant peers list` | ✓ clean | `No peers registered` |
| 7 | `savant quarantine list` | ✓ clean | `No quarantine entries` |
| 8 | `savant reconcile run` | ✓ clean | full reconcile in 15 ms, 0/0/0 deltas |
| 9 | `timeout 20 savant demo-swarm` | ⚠ warning | completes in 9.3 s, **but one of four sub-agents (`scorer-1`) deterministically fails** in the demo. Output never explains it's expected. New user reads ✗ scorer-1 and thinks the demo is broken |
| 10 | `python3 -m pytest tests/ -q` | ✓ clean | **96 passed**, 494 warnings (all `datetime.utcnow()` deprecation noise in `genome/models.py`) |
| 11 | `scripts/test_healing_loop.py` | ✓ clean | `✓ healing loop completed end-to-end` |
| 12 | `scripts/test_federation.py` | ✓ clean | `✓ federation flow completed in 0.2s · QUARANTINE GATE HELD` |
| 13 | `scripts/test_failure_modes.py` | ✓ clean | `15/15 probes passed · no failures surfaced` |

**Summary:** 12 ✓ · 1 ⚠ · 0 ✗.

## 4. What works today (fresh user)

1. **Install & sanity check** — `pip install -e .` then `savant doctor` greens out in 2 s.
2. **Healing loop end-to-end** — `python3 scripts/test_healing_loop.py` rebuilds a dead sub-agent from `≥3-star` genomes, recording quarantine on failure.
3. **Federation with quarantine gate** — `python3 scripts/test_federation.py` proves no `trust_level=trusted` peer can bypass the quarantine validator.
4. **Failure-mode coverage** — `python3 scripts/test_failure_modes.py` runs 15 adversarial probes (corruption, prompt sanity, empty pool, bus subscriber explosions) and all hold.
5. **Background reconciliation** — `savant reconcile run` walks every configured pool and emits a delta report in <20 ms on empty state.
6. **Empty-state CLI** — `pool status`, `pool stats`, `genomes list`, `peers list`, `quarantine list` all give crisp output with no crashes.
7. **TUI demo orchestration** — `savant demo-swarm` renders a live swarm tree (one expected ✗ — see gap #1).
8. **Full test suite** — `pytest tests/ -q` → 96 passed.

## 5. Known gaps for a fresh user

- **`demo-swarm` looks broken on first run.** `scorer-1` always fails (`✗`). Either rename it to `scorer-1 (intentional-failure demo)` or print a footer line that explains the ✗ is illustrative.
- **`MISSION_PLAN.md` is pre-AgentDrive.** Still says *"100% Savant-branded (no external-brand pollution in core identity)"* and lists the original swarm work packages. Either delete, archive under `docs/archive/`, or rewrite as the AgentDrive roadmap.
- **`pyproject.toml` author email** — set to `pablo@vektraindustries.com` (the maintained address). Confirmed in the security audit pass.
- **`README.md` build badge** points at `actions` with `build-passing` hardcoded. Not wired to a real workflow result — cosmetic dishonesty if CI ever turns red.
- **No `agentdrive` CLI entrypoint.** The product is called AgentDrive in every doc, but the binary is `savant`. A thin `agentdrive` alias entrypoint in `pyproject.toml` (one line, points at the same `savant.cli:main`) would let `agentdrive doctor` work and reinforce the product framing.
- **`docs/POOL-EVOLUTION.md` contained 3 references to a defunct external project + a franchise-research preamble** — design doc is otherwise good, but the surface vocabulary contradicted the hard constraints; sanitized in the security pass.
- **`datetime.utcnow()` deprecation warnings** — 494 of them from `src/savant/genome/models.py`. Source bug, not fixed per instructions; flagged.

## 6. Recommended next 3 fixes (impact / effort)

1. **Add `agentdrive` CLI alias.** One line in `pyproject.toml`'s `[project.scripts]`: `agentdrive = "savant.cli:main"`. Lets `agentdrive doctor`, `agentdrive demo-swarm` work. Reinforces product framing in the terminal — the single largest "is this real" signal a fresh user gets. **Effort: 1 min. Impact: high.**
2. **Fix `demo-swarm` so it doesn't look broken.** Either flip `scorer-1` to succeed, or add a one-line `[dim]✗ scorer-1 is intentional — demonstrates failure tracking[/]` footer in the demo's exit print. Right now the first thing a new user sees after install is a red ✗. **Effort: 5 min. Impact: high.**
3. **Neutralize residual cross-project references in `docs/POOL-EVOLUTION.md`.** Replace any external-project name with "trusted peers" and rewrite §1–§2 in generic "borrow-and-return systems" voice, dropping franchise vocabulary. Removes the cross-project bleed and satisfies the no-franchise constraint in one pass. **Effort: 15 min. Impact: medium (only one file, but it's the file most likely to surface in search).**
