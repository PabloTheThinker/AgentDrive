# Chat Pattern 2 — Pre-Integration Audit

**Target:** `src/agentdrive/tui/chat.py` (1117 lines, single `ChatView` class)
**Scope:** Read-only audit. Map blocking-loop surface area so the integrator can
swap in a queue-driven async `ChatLoop` without regressing behavior.
**Reference:** `docs/UX-PROPOSAL.md` Pattern 2 (keep typing while agent works),
`src/agentdrive/events.py` (typed `EventBus` already exists — chat.py does **not**
import it yet).

---

## 1. The blocking input loop

- **Function:** `ChatView.enter()` — lines **170–222**
- **Blocking call:** `self._prompt_session.prompt(...)` at lines **191–194**
- **Loop frame:** `while True:` at line 189
- **Pseudocode (per iteration):**
  ```
  line = prompt_session.prompt(composer_prompt, completer)   # BLOCKS here
  if line in RESERVED_WORDS: exit
  if line.startswith("/"): _handle_command(line) -> may return "exit"/"back"
  else: _handle_user_message(line)                            # also BLOCKS
  ```
  The whole turn (network + streaming `Live`) runs *while the composer is dead*.
  No queue, no cancellation hook, no event bus subscription.

`PromptSession` is constructed once at **143–149** (multiline=True, custom
keybindings at 126–141 for Enter/Shift-Enter newline semantics). These
keybindings MUST be re-attached to `prompt_async()`.

---

## 2. The turn execution path

User text → printed assistant reply call chain:

| Step | Method | Lines |
|---|---|---|
| Loop dispatches plain text | `enter()` line 222 | 170–222 |
| Echo user bubble + guard no-model | `_handle_user_message()` | 385–400 |
| Render `You` header + body | `_render_user_bubble()` | 402–414 |
| Stream the reply (orchestrator) | `_stream_assistant_reply()` | 416–510 |
| Worker thread calls model | inline `worker()` → `self.agent.send(message, on_chunk=...)` | 440–449 |
| Per-chunk accumulator | inline `on_chunk()` (lock-guarded) | 436–438 |
| `Live` region (Rich) instantiated | `with Live(...)` block | 472–486 |
| Render frame builder | inline `render()` returns `Group(body, cursor_line)` | 451–469 |
| DNA tree post-render | `_render_dna_tree()` | 512–542 |
| Status rule footer | `_print_status_rule()` | 334–379 |

**Where streaming happens:** `Live` is created at line 472, fed by accumulator
text mutated by the worker thread; the *main* thread polls `done_event` every
~83 ms (line 480) and re-issues `live.update(render())`.

**Where the agent is called:** `self.agent.send(...)` line 442 — synchronous,
blocking, callback-based streaming via `on_chunk`. See
`src/agentdrive/agent/agent.py:165`.

**Where tool calls render:** **Not present.** No tool-call ribbon, no
`ToolStart/ToolProgress/ToolComplete` rendering in chat.py. Only DNA tree
(post-turn) at 512–542.

**Where the session saves:** **Not in chat.py.** Persistence is owned by
`Agent DriveAgent.send()` internally; chat.py never calls a save method. The only
read of session state is `self.agent.session.turns` (lines 330, 351, 650, 848).

---

## 3. Slash command dispatch

- **Switch:** `_handle_command()` lines **548–613** (long if/elif on `cmd`).
- **Delegated set:** `_DELEGATED_SLASH` set at lines 162–168; routed through
  `_delegate_to_tui()` (615–627) which calls `self.tui._dispatch(bare)`.
- **All handlers are synchronous.** No `async def` anywhere in the file.
- **Handlers with non-trivial I/O** (candidates to remain blocking / run off the
  composer thread even after refactor):
  - `_cmd_sessions` (683–718) — disk scan via `agent.list_sessions`
  - `_cmd_resume` (720–749) — disk read + session rehydrate
  - `_cmd_model` (751–807) — provider config read/write
  - `_cmd_provider` (809–838) — provider registry walk
  - `_cmd_pool` (918–945) — pool stats query
  - `_cmd_genomes` (963–1009) — registry list via `genomes_api`
  - `_cmd_genome` (1011–1103) — registry get
  - `_cmd_retry` (840–852) — **re-enters `_handle_user_message`** → triggers a
    full turn. Must route through the new queue, not call directly.
  - `_delegate_to_tui` (615–627) — arbitrary TUI dispatch; unknown blocking
    cost (board, doctor, scan, run, evolve, compose, setup …).

Pure UI handlers (safe inline on composer thread): `_cmd_help`, `_cmd_steer`,
`_cmd_indicator`, `_cmd_reasoning`, `_cmd_dna`, `_cmd_new` (modulo confirm).

---

## 4. Threading and `Live` regions

chat.py **already uses threads**:

- One `threading.Thread(target=worker, daemon=True)` per turn (line 448) runs
  `agent.send()`.
- Shared state guarded by `threading.Lock()` (432) and `threading.Event()`
  (433).
- `Live` is created **per turn**, inside `_stream_assistant_reply` (line 472),
  i.e. *inside* the prompt loop body — not at construction time. Good news:
  scope is bounded to the turn. Bad news: after the refactor, `Live` will be
  running on the turn-worker side while `prompt_async()` is concurrently
  driving the composer below it. They must coordinate via
  `prompt_toolkit.patch_stdout` (called out in UX-PROPOSAL §"hard thing",
  line 110).

`refresh_per_second=12` and `transient=False` (lines 475–476) — the streamed
region stays on screen after the turn, which is correct and must be preserved.

---

## 5. Session and persistence state (must survive refactor)

Instance state held on `ChatView` (constructor 110–149):

- `self.tui`, `self.console`, `self.skin`, `self.palette` — UI handles.
- `self.agent_id`, `self.agent` (`Agent DriveAgent`) — owns session + pool + LLM.
- `self.indicator_style` (default `"unicode"`) — mutated by `/indicator`.
- `self.show_reasoning_hints` (bool) — mutated by `/reasoning`.
- `self._last_user_message` (Optional[str]) — used by `/retry` (840–852);
  cleared on `/new` (674).
- `self._prompt_session` (PromptSession) — history file + keybindings; reused
  every iteration. The new loop must reuse the *same* session so FileHistory
  arrow-up works across turns.

Implicit state (lives on `self.agent`): `agent.session.turns`,
`agent.session.session_id`, `agent.steer`, `agent._last_pulled` (read by
`_cmd_dna` line 949), `agent.harness.pool`.

---

## 6. What MUST NOT regress (regression checklist)

1. **Multiline composer keybindings.** Enter submits; `\<Enter>`, Ctrl+Enter,
   Alt+Enter, Esc-Enter all insert a newline (126–141).
2. **History search.** Up-arrow walks `FileHistory` at
   `~/.agentdrive/.agentdrive_chat_history` (144).
3. **Streaming cursor animation.** Blinking `▍` at ~2.4 Hz interleaved with
   `Indicator.frame()` rotation (454, 461–467).
4. **`Live` finalization.** On completion the region re-renders as
   `Padding(Markdown(final_text), (0,0,0,2))`; on empty reply prints
   `[no response]` (483–486).
5. **KeyboardInterrupt mid-stream** → "Interrupted — partial reply saved."
   plus `t.join(timeout=2)` (487–491). Pattern 2 redefines Ctrl-C semantics;
   make sure double-Enter-cancel doesn't lose the partial-save behavior.
6. **Status rule after every action.** Every handler ends with
   `self._print_status_rule()`; the queued-turn worker must also emit it.
7. **`/help` panel layout** via `CHAT_HELP_SECTIONS` (66–104) — section-panel
   render at 640–646.
8. **`/retry` semantics** — pops trailing assistant + user turn, re-sends
   (848–852). After refactor, retry must go through the queue, not block.
9. **Model-not-configured guard** (389–398): warning + status rule, no turn.
10. **Welcome panel + status rule on entry** (171–172); also re-printed by
    `/chat` (596–598).
11. **Confirm modal on `/new`** when session has turns (652–671).
12. **Delegated slash exit codes.** `_handle_command` returns `"exit"` /
    `"back"` and `enter()` acts on them (210–219). Queue dispatch must
    preserve this return-value channel.

---

## 7. Integration insertion points

**Replace exactly one method:** `ChatView.enter()` (170–222). It becomes a
thin shim that constructs a `ChatLoop` and hands it the existing handlers.

**Leave as-is (become injected handlers):** everything else, especially
`_handle_user_message`, `_handle_command`, `_stream_assistant_reply`,
`_print_status_rule`, `_print_welcome`, `_composer_prompt`.

**Before (current 189–222 condensed):**
```python
while True:
    try:
        line = self._prompt_session.prompt(self._composer_prompt(), completer=completer).strip()
    except (KeyboardInterrupt, EOFError):
        self.tui.running = False; self._print_goodbye(); return
    if not line: continue
    if line.lower() in self._RESERVED_WORDS:
        self.tui.running = False; self._print_goodbye(); return
    if line.startswith("/"):
        action = self._handle_command(line)
        if action == "exit": self.tui.running = False; self._print_goodbye(); return
        if action == "back": self._print_goodbye(brief=True); return
        continue
    self._handle_user_message(line)
```

**After (sketch):**
```python
from agentdrive.chat_loop import ChatLoop, ExitSignal

loop = ChatLoop(
    prompt_session=self._prompt_session,
    completer=completer,
    composer_prompt=self._composer_prompt,
    on_turn=self._handle_user_message,          # plain text → queued
    on_command=self._handle_command,            # "/cmd" → immediate, returns "exit"/"back"/""
    reserved_words=self._RESERVED_WORDS,
    console=self.console,                       # so ChatLoop can patch_stdout
)
try:
    asyncio.run(loop.run())                     # composer + turn-worker cohabit
except ExitSignal as s:
    if s.kind == "exit":
        self.tui.running = False; self._print_goodbye()
    else:  # "back"
        self._print_goodbye(brief=True)
```

`ChatLoop` owns: (a) `prompt_async()` in a tight loop wrapped in
`patch_stdout()`; (b) a `turn_queue` drained by a worker coroutine that awaits
`on_turn` in a thread (`asyncio.to_thread`) since `_handle_user_message` is
sync and contains `Live`; (c) immediate dispatch of slash commands on the
composer side, with a lock so they don't overlap a running turn's `Live`.

---

## 8. Top 3 risks

1. **`Live` + `prompt_async` screen contention.**
   *Breaks:* composer flickers, eats lines, or freezes while `Live` is
   refreshing at 12 Hz.
   *Symptom:* typed characters disappear or the cursor jumps mid-stream.
   *Mitigation:* wrap the entire `prompt_async()` body in
   `prompt_toolkit.patch_stdout.patch_stdout(raw=True)` and run `Live` with
   `console=self.console` (already true) so both share the same screen lock.

2. **`/retry` and `_handle_user_message` recursion through the new queue.**
   *Breaks:* `_cmd_retry` (line 852) calls `_handle_user_message` directly; if
   the queue worker is the thing that calls handlers, a slash command running
   on the composer thread will trigger a turn off-queue and race the worker.
   *Symptom:* duplicate assistant bubbles, interleaved `Live` regions, or
   `agent.session.turns` mutated from two threads.
   *Mitigation:* `_cmd_retry` should `loop.enqueue(self._last_user_message)`
   instead of calling the handler — expose `enqueue` on the `ChatLoop` and
   inject it into the command router (or use a module-level
   `current_loop.enqueue()`).

3. **Delegated TUI dispatch (`_delegate_to_tui`, line 615) is opaque-blocking.**
   *Breaks:* `/board`, `/doctor`, `/scan`, `/run`, etc. enter `self.tui._dispatch`
   which may launch its own prompts, screens, or long-running operations that
   were never designed to coexist with a live composer below them.
   *Symptom:* nested prompts, double Ctrl-C handling, scrambled output when
   the delegated command tries to read stdin while `prompt_async` also owns
   it.
   *Mitigation:* treat delegated commands as "freeze composer" — `ChatLoop`
   exits `patch_stdout`, awaits the delegated call, then re-enters the
   composer. Document this as a known limitation; full integration of those
   surfaces is out of Pattern 2 scope.
