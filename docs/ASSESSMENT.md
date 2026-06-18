# AgentDrive Assessment — What We Have and What Could Be Next

**Date:** 2026-06-18 (updated)  
**Scope:** Golden path, terminal UX (Patterns 1–5), CLI/MCP surface, session observability, skills registry, multiverse cognition, auto-learning, codebase mirrors, platform depth (Phases C–F).

---

## Executive summary

AgentDrive crossed a meaningful product threshold: **a new operator can install, wire MCP, run the memory loop, and use a terminal that feels alive while the agent works.** The UX-PROPOSAL’s five patterns are all shipped at v1. The codebase is in strong shape — **655+ tests collected, full suite green** — with multiverse, auto-learning, and codebase-mirror coverage added since the June 8 snapshot.

What you have now is not a demo shell. It is a **local-first agent memory platform** with a coherent operator surface (CLI + TUI + MCP), observable sessions, and a credible first-run story. The main gap is no longer “does the terminal feel broken?” but “which surface do we deepen next — terminal v2, web, or external adapters?”

---

## What we built (by layer)

### 1. Golden path — the product story is real

| Piece | What it does |
|-------|----------------|
| `docs/GOLDEN_PATH.md` | Canonical 7-step path: install → doctor → MCP → think → learnings → query |
| `golden_path.py` | `steps`, `verify`, `run` (with `--dry-run` for CI) |
| TUI gate | `/golden-path`, welcome panel, `config.golden_path.completed` |
| Parallax | 7/7 verify after learnings; live think with Ollama |

**Assessment:** This is the strongest product asset. It turns “local agent memory” from architecture into a repeatable loop.

### 2. CLI surface — discoverable, unified, scriptable

| Piece | What it does |
|-------|----------------|
| `cli_catalog.py` | 70+ categorized commands |
| `cli_surface.py` | Shared handlers for think, learnings, harness, session, skills, golden-path |
| `cli_repl.py` | `agentdrive repl` — same argparse handlers as subcommands |
| `--cli` / `AGENTDRIVE_NO_TUI` | Skip default TUI for headless operators |

**Assessment:** Pattern 5 (“CLI = slash”) is largely achieved. The REPL is the right long-term operator shell.

### 3. Terminal UX — all five patterns shipped (v1)

| Pattern | Status | Key modules |
|---------|--------|-------------|
| **1 — Typed event bus** | Shipped | `events.py`, `session_events.py`, `TranscriptLane`, `MessageStreamLane` |
| **2 — Keep typing** | Shipped | `chat_loop.py`, double-Enter interrupt, slash bypass |
| **3 — Drive activity** | Shipped | `PoolActivityLane` (Drive DNA ribbons), transcript ribbons |
| **4 — Sub-agent tree** | Shipped | `SwarmActivityLane`, `turn_telemetry.py`, Grok `SubagentSpawn`/`SubagentDone` |
| **5 — CLI = slash** | Shipped | `genomes_api`, `skills/`, golden-path ops + REPL |

Latest polish (`8b28deb`): MessageDelta streaming via `MessageStreamLane`; session replay panel + type filters; `skills init`.

### 4. Session observability

Every chat session writes `~/.agentdrive/agents/<agent>/sessions/<id>/events.jsonl`. CLI and `/session` expose events, replay, panel, and filters.

### 5. Skills — registry + scaffolding

`skills/registry.py` discovers bundled + user skills; `run_skill()` is shared by CLI and `/skill`. `skills init` scaffolds new skills. See `docs/SKILLS-LIBRARY.md` for the expanded library and hive/pawn model.

### 6. Platform depth (Phases C–F)

25-op registry + MCP bridge, dream cycle, Experience Graph tests, Fabric compose, sprint STOP gates, RRF retrieval (opt-in), eval replay, MCP hardening for any-model onboarding.

---

## Strengths

1. Coherent operator story — golden path + TUI gate + MCP + verify
2. Event-bus architecture — lanes compose; session recording is automatic
3. Test discipline — 655+ tests, per-lane + multiverse + auto-learning + memory bank suites
4. Unified dispatch — CLI, REPL, slash, skills share handlers
5. Low TODO debt — ~3 TODOs across ~22k LOC

---

## Gaps and technical debt

| Area | Gap |
|------|-----|
| Terminal v2 | Thinking/tool lanes; approval/clarify events; richer swarm tree (tokens/cost) |
| Skills | Thick library + auto-compose tuning; promotion path to Genomes |
| Web | Phase 2+ dashboard (Drive/Swarms/DNA pages thin) |
| Distribution | No PyPI/Docker release path yet |
| Architecture | In-process bus only; JSON-RPC sidecar not started |
| Docs | `PROJECT-STATUS.md` stale; consolidation adds `CAPABILITY_FUNNEL.md` + `ARCHITECTURE.md` |
| Naming | Pool → Drive drift in code (`pool/` module) — docs reframed, code rename incremental |

---

## What could be next (prioritized)

### Tier A — Highest leverage (1–2 weeks)

1. **Skills ecosystem** — bundled library, system-prompt catalog, pawn role injection for swarm spawns
2. **Thinking + tool lanes** — `ThinkingLane`, `ToolProgressLane` on the event bus
3. **Declarative chat renderer** — single `ChatRenderer` state object fed by lanes
4. **Golden path retention** — periodic verify nudges, MCP drift detection

### Tier B — Product expansion (2–4 weeks)

5. **Web dashboard Phase 2** — reuse `session_events` + pool stats in HTMX
6. **Event bus externalization** — JSONL tail → stdio JSON-RPC for IDE adapters
7. **Release hygiene** — PyPI, versioned install, Docker smoke

### Tier C — Platform depth

8. Swarm tree v2 (per-node cost/tokens)  
9. Federation operator tools (quarantine review)  
10. Capability enforcement audit  
11. AD-Grid / Mission Control (if swarm orchestration is the active bet)

---

## Recommended next move

| Goal | Sequence |
|------|----------|
| Production-ready for new operators | Skills library → thinking/tool lanes → golden-path retention → web session panel |
| IDE / any-model distribution | MCP polish → bus stdio spike → PyPI |
| Swarm differentiation | Pawn spawn profiles → swarm tree v2 → federation UX |

---

## Bottom line

**What you have:** A credible local-first agent memory product with a tested golden path, fluent Rich terminal (UX patterns v1), unified CLI/REPL/slash, MCP onboarding, session replay, and a growing skills library with hive/pawn roles for swarm agents.

**What you don’t have yet:** Thinking/tool visibility during turns, a full web product surface, external event transport for IDEs, or a public install path.

**Verdict:** Terminal UX v1 is complete. The project is ready to choose its next bet — deepen terminal, widen distribution, or expand web — all on the same event bus and session recording foundation.