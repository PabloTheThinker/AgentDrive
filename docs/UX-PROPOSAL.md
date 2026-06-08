# Agent Drive UX Proposal — what to learn from the reference CLI, what to build

**Status:** partially shipped (2026-06-07). See commits `acaa451` and follow-ups.
**Premise:** the reference CLI feels smooth. Agent Drive is closing the gap via Python+Rich patterns (no Ink rewrite). Below: 5 patterns ordered by user-impact ÷ build-cost, plus implementation status.

---

## Shipped vs remaining (2026-06-07)

| Pattern | Status | Where |
|---------|--------|-------|
| **1 — Typed event bus** | Shipped (v1) | `events.py` + `session_events.py`; `TranscriptLane` bus-driven ribbons; per-session `events.jsonl`; `agentdrive session events\|replay` |
| **2 — Keep typing** | Shipped | `chat_loop.py` + `ChatView` custom `PromptSession`; queue, slash bypass, double-Enter |
| **3 — Pool activity** | Shipped | `TranscriptLane` ribbons + `PoolActivityLane` thin row in streaming `Live` |
| **4 — Sub-agent tree** | Shipped | `SwarmActivityLane` in chat; `ChatTurnTelemetry` per turn; Grok spawn emits |
| **5 — CLI = slash** | Shipped | `genomes_api`, `skills` registry; `genomes search`, `/genome-search`, `/skill`, `agentdrive skills run`; golden-path ops + REPL |

**Still open:** full MessageDelta-driven chat body (streaming row still agent callback); rich TUI event replay panel (CLI + `/session` slash shipped).

---

## The diagnosis (original — largely addressed)

Agent Drive already had the bones. The gaps below drove this proposal; most are now mitigated:

- ~~**The agent runs, the input blocks.**~~ → `ChatLoop` async composer + turn queue
- ~~**Pool activity is invisible during chat.**~~ → ribbons + `PoolActivityLane` during streaming
- ~~**Sub-agents are lanes, not a live tree.**~~ → `SwarmActivityLane` + turn telemetry
- **Render calls are imperative.** → bus exists; chat still hand-wires subscribers (Pattern 1 remainder)
- **Slash commands and skills duplicate code paths.** → golden path + REPL unified; genomes TBD

---

## Pattern 1 — Typed event stream (the load-bearing change)

**What the reference CLI does.** The backend emits ~20 typed events (`message.start`, `message.delta`, `message.complete`, `thinking.delta`, `tool.start`, `tool.progress`, `tool.complete`, `status.update`, `approval.request`, `clarify.request`, `background.complete`, ...). The UI is pure: `event → state mutation → re-render`.

**Why it matters for Agent Drive.** This is the multiplier under every other pattern below. Once `pool.add`, `genome.match`, `subagent.spawn`, and `dna.inject` are events on the same bus as `message.delta`, every UI affordance becomes "render this state" instead of "wire a call from this codepath." It also makes the gateway swappable: today an in-process queue, tomorrow JSON-RPC over stdio (which is what unlocks IDE adapters later).

**What we build.** A `agentdrive.events` module: a typed `Event` dataclass hierarchy, a single `EventBus` with sync subscribers, and an `EventRecorder` that writes the full stream to `~/.agentdrive/sessions/<id>/events.jsonl` for replay/debug. Chat, pool, harness, and board all emit; the TUI subscribes.

**Cost.** ~1 day. The hard part is grandfathering existing imperative `console.print` calls in chat.py — they need to become `emit(MessageDelta(...))` and a renderer consumes them. Once the bus exists, Patterns 2–4 plug in.

**Recreation difficulty in Rich.** Trivial. Python's plain queues + threads are enough. No async required for v1.

---

## Pattern 2 — Keep typing while the agent works

**What the reference CLI does.** Plain text typed during a turn is **queued** and auto-drained after the current turn completes. Slash commands and `!shell` escapes **bypass the queue** and execute even mid-turn. `Enter Enter` interrupts the current turn cleanly.

**Why it matters for Agent Drive.** This is the single highest-perceived-fluency win in the whole proposal. Right now Agent Drive's UI is a polite turn-taking system — agent's turn, your turn, agent's turn. the reference CLI feels like the agent is a *colleague at a shared keyboard* because you can keep typing while it works. The cost of not having this is invisible until you use the reference CLI for an hour and switch back.

**What we build.** Refactor the chat loop from `prompt().then(run_turn)` to two cooperating threads: one runs `prompt_session.prompt_async()` in a loop, one runs turns from a `turn_queue`. The composer is always live. Plain text → queue. `/cmd` → immediate dispatch on the slash router. `!cmd` → immediate shell. Double-Enter on an empty buffer → set a cancel flag the turn worker polls.

**Cost.** ~1.5 days. The tricky bit is interaction between `prompt_toolkit`'s event loop and the `Live` streaming region. the reference CLI proves this is solvable in their stack; Agent Drive's is closer to ours than to theirs.

**Depends on Pattern 1** (need event bus to coordinate cleanly).

---

## Pattern 3 — Live DNA pool activity ribbon

**What the reference CLI does, applied to Agent Drive's actual differentiator.** the reference CLI's memory edits appear inline as small `▸ memory: added "..."` ribbons in the transcript when the agent writes to `MEMORY.md`. The user *sees* learning happen.

**What we build for Agent Drive.** A persistent thin status line *below* the streaming row, *above* the input, that pulses on every pool event:

```
─ pool ──  ▸ matched 3 genomes (0.87 0.72 0.61)  ·  ▸ recorded outcome ✓  ─
```

Plus inline transcript ribbons when something *substantive* happens (new genome ingested, score crossed threshold, sub-agent forked a pool). Quiet by default — never flashes for routine deltas, always flashes for meaningful learning. The user feels the pool growing.

**This is the visual proof of Agent Drive's value prop.** Without it, "the pool grows with use" is a claim. With it, you can see it.

**Cost.** ~0.5 day on top of Pattern 1 (just another subscriber on the bus).

---

## Pattern 4 — Live sub-agent tree (the swarm view)

**What the reference CLI does.** While a multi-agent task runs, a Unicode tree (`├─ └─`) draws live in the activity lane:

```
▾ payments-review-2026-05-23  $0.42 · 14.7s
  ├─ ingest-1     ✓ done       8,420 tok · $0.18
  ├─ trace-2     ⠴ running     bash(...)   3,201 tok · $0.09  ▍
  ├─ scorer-1    ⠴ running     pool.query  1,840 tok · $0.05  ▍
  └─ author-1    ⏸ queued
```

Each node shows: status spinner, current tool, elapsed, tokens, cost, optional "hotness" sparkline.

**Why it matters for Agent Drive.** Agent Drive's *whole pitch* is "every sub-agent gets its own pool." Today you can't see that happening — you see the result on the Mission Board after the fact. This view makes parallelism legible and converts an abstract isolation claim into a felt experience.

**What we build.** A `LiveSubagentTree` renderer driven by `subagent.spawn` / `subagent.tool` / `subagent.tokens` / `subagent.done` events. Pin it above the status line in the activity lane during multi-agent turns. Auto-collapse when the swarm finishes.

**Cost.** ~1 day. Data model is the actual work (parent_id, status, current_tool, tokens, cost, last_progress_ts). Rendering is `Live` + `rich.tree.Tree` + `Spinner`. Mission Board stays as the post-hoc retrospective view; this is the in-flight view.

**Depends on Patterns 1 + 2.**

---

## Pattern 5 — One code path for skills (CLI = slash)

**What the reference CLI does.** A skill is a `SKILL.md` with YAML frontmatter. `/<skill-name>` and `<cli> skills run <name>` route through the *same* `do_skill_run()` function. Tab-completion on the input surfaces them. The system prompt advertises them so the model suggests them in chat.

**Why it matters for Agent Drive.** Same principle applies to Agent Drive's genomes. Today `agentdrive genomes list` and a chat `/genomes` (if added) would be two implementations. the reference CLI proves they should be one. This also opens the door to "the model suggests `/genome security-incident-postmortem` mid-conversation" — which is exactly the kind of deeper integration you want.

**What we build.** A `agentdrive.skills` registry that loads from `~/.agentdrive/skills/*/SKILL.md`. One `run_skill(name, args)` function. Two thin wrappers: argparse subcommand + slash handler. The chat system prompt gets a generated "available skills" block so the LLM can suggest them inline.

**Cost.** ~0.5 day. Mostly a refactor of existing code into a shared module.

**Bonus.** Compatible with the `agentskills.io` open standard that the reference CLI ships against — instant skill ecosystem.

---

## The one hard thing — composer + live row concurrency

**The problem.** `prompt_toolkit` runs its own asyncio loop. Rich's `Live` runs its own refresh thread. Naively combined, you get input flicker or a frozen composer. the reference CLI side-steps this entirely because Ink is a React tree where input and live regions are sibling components in the same render loop.

**The fix in Rich.** Run `prompt_toolkit` in `prompt_async` mode inside a single asyncio event loop, drive the `Live` region from the same loop (or a coordinated thread that holds the screen lock), and use `prompt_toolkit`'s "patch_stdout" context manager so background prints (from event-bus subscribers) interleave cleanly above the input line.

**Risk.** This is the one place we might have to do real engineering work, not pattern-application. Mitigation: prototype Pattern 2 first as a spike — if `patch_stdout` + `Live` cooperate cleanly for our case, the rest is downstream. If not, we either build a custom screen manager or revisit whether Textual (Rich's full-app cousin) is worth the migration. **Recommend doing the spike before committing to the full plan.**

---

## Recommended build order (updated)

1. ~~**Spike**~~ — validated (`chat_loop.py` + `patch_stdout`)
2. ~~**Pattern 2**~~ — shipped
3. ~~**Pattern 3**~~ — shipped (ribbons + `pool_lane.py`)
4. ~~**Pattern 4**~~ — shipped (`swarm_lane.py`, `turn_telemetry.py`)
5. ~~**Pattern 1 completion**~~ — `session_events.py`, `TranscriptLane`, `session events|replay` CLI
6. ~~**Pattern 5 genomes**~~ — `genomes search`, `/genome-search`, `test_genomes_api.py`
7. ~~**Skills registry**~~ — `skills/registry.py`, `agentdrive skills list|show|run`, `/skills` `/skill`
8. **Streaming row on bus** — migrate `_stream_assistant_reply` to `MessageDelta` subscriber (optional polish)
9. ~~**Session replay in TUI**~~ — `/session events|replay` + `agentdrive session replay`
10. ~~**Grok spawn SubagentDone**~~ — wrapper emits done when spawn returns

---

## What we explicitly DON'T copy from the reference CLI

- **Ink/React stack.** Rewriting Agent Drive in TypeScript is not on the table for this round. The patterns translate; the stack doesn't need to.
- **JSON-RPC sidecar architecture.** Worth it long-term for IDE adapters; out of scope for the chat fluency work. The event bus is the in-process precursor.
- **the reference CLI's slash command vocabulary.** Borrow the *structure* (one function, two wrappers, model-aware), not the *names*. Agent Drive's commands belong to Agent Drive.
- **the reference CLI's specific memory format.** Agent Drive's DNA pool is structurally different from the reference CLI's `MEMORY.md`. We borrow the *visibility principle* (plaintext, browseable, editable), not the file layout.

---

## Open questions for the project maintainer

1. **Spike first, or full commit?** I lean spike — the composer/Live concurrency is the only real unknown, and a half-day prototype answers it cheaply.
2. **In-flight tree placement.** Above or below the streaming row? the reference CLI puts it in an activity lane; Agent Drive could put it inline in the transcript or pin it above the status rule. My instinct: pin above the status rule so it scrolls off after the swarm finishes.
3. **Are we OK breaking session JSONL format to add event-stream replay?** Pattern 1 adds an `events.jsonl` next to existing session storage. No migration needed if we treat the old format as authoritative for resume.
4. **Anything to *de-scope* before I start?** This is ~5 days; if you want a faster path to "feels different," Patterns 1+2+3 alone (~3 days) get most of the perceived improvement and Pattern 4 can ship later.
