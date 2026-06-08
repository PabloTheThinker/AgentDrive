"""
Agent Drive Chat — premium streaming TUI for talking to your Agent Drive Agent.

The AgentDrive is the agent's body, the configured LLM is the voice,
the AgentDrive is the lived memory. Every turn grows the Drive.

Layout principles (mirrored across every Agent Drive surface via chrome.py):
- Messages render with a role glyph + label, no decorative boxes.
- Nested content uses tree stems (├─ └─ │).
- One blank line between turns. No internal padding.
- Persistent single-line status rule after every turn:
    ─ provider · model ─ session abc · N turns ─ pool N ─ ████░░░░░░ 45% ─
- Streaming render shows a blinking ▍ cursor (420ms duty cycle) inline
  with the rotating indicator while the model emits.
- System panels (welcome, /help, /sessions, /provider, /dna, /pool) are
  rounded-border panels with section headings + key-value rows.
- Destructive operations gated by a confirm modal.
- Slash commands flow naturally inside the chat — no mode-switching.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from rich.console import Group
from rich.live import Live
from rich.markdown import Markdown
from rich.markup import escape as rich_escape
from rich.padding import Padding
from rich.panel import Panel
from rich.text import Text

from agentdrive.agent import AgentDriveAgent, Indicator
from agentdrive.chat_loop import ChatLoop
from agentdrive.constants import get_agentdrive_home
from agentdrive.tui.chrome import (
    Glyphs,
    Palette,
    Section,
    Tree,
    TreeRow,
    confirm_prompt,
    context_bar,
    error_line,
    ok_line,
    section_panel,
    status_rule,
    warn_line,
)
from agentdrive.tui.loading import MicroSpinner
from agentdrive.tui.message_stream_lane import MessageStreamLane
from agentdrive.tui.pool_lane import PoolActivityLane
from agentdrive.tui.swarm_lane import SwarmActivityLane
from agentdrive.tui.transcript_lane import TranscriptLane

# Nominal context window assumed when the active model is unknown.
_NOMINAL_CONTEXT = 100_000
# Rough chars-per-token used to estimate context usage from session text.
_CHARS_PER_TOKEN = 4

CHAT_HELP_SECTIONS = [
    (
        "Conversation",
        [
            ("/help", "show this panel"),
            ("/clear  /new", "start a fresh session (confirm)"),
            ("/retry", "re-run the last user message"),
            ("(empty) Enter Enter", "interrupt the current turn (double-Enter)"),
            ("/steer <goal>", "set a persistent goal for the agent"),
            ("/unsteer", "clear the steering goal"),
        ],
    ),
    (
        "Sessions",
        [
            ("/sessions", "list recent sessions"),
            ("/resume <id>", "resume a prior session"),
        ],
    ),
    (
        "Agent body",
        [
            ("/model [id]", "show or switch the active model"),
            ("/provider", "show all known providers"),
            ("/dna", "show DNA pulled for the last turn"),
            ("/pool", "pool stats"),
        ],
    ),
    (
        "Golden path (memory loop)",
        [
            ("/golden-path verify", "check install → mcp → learnings → query"),
            ("/golden-path run", "run the first-run walkthrough"),
            ("/think <question>", "cited synthesis + gaps (no chat turn)"),
            ("/learnings list", "operational memory for this project"),
            ("/learnings log <key> <insight>", "record a learning"),
            ("/session events [id] [--type T]", "typed event stream (optional type filter)"),
            ("/session replay [id] [--type T]", "numbered timeline from events.jsonl"),
            ("/session panel [id]", "rich replay panel with type histogram"),
            ("/session filter <Type> [id]", "replay only events of one type"),
            ("/skills list", "discover SKILL.md capabilities"),
            ("/skills init <name>", "scaffold ~/.agentdrive/skills/<name>/SKILL.md"),
            ("/skill <name> [args]", "run a skill (same path as agentdrive skills run)"),
        ],
    ),
    (
        "Display",
        [
            ("/indicator <s>", "spinner: unicode | ascii | emoji | kaomoji"),
            ("/reasoning on|off", "toggle reasoning hints"),
        ],
    ),
    (
        "Top-level commands (delegate to TUI)",
        [
            ("/doctor", "animated health check"),
            ("/board", "AgentDrive Mission Board (kanban)"),
            ("/genomes", "browse the genome registry"),
            ("/genome-search <query>", "search genomes by task description"),
            ("/view <id>", "inspect a specific genome"),
            ("/run <id>", "execute a genome"),
            ("/scan <path>", "extract DNA from a run"),
            ("/evolve <id>", "propose a genome improvement"),
            ("/compose", "multi-genome mission composer"),
            ("/setup", "re-run the setup wizard"),
            ("/status", "registry + activity"),
        ],
    ),
    (
        "Exit",
        [
            ("/exit  /quit  exit", "close the TUI completely"),
            ("/back", "drop to the legacy command menu"),
        ],
    ),
]


class ChatView:
    """The polished Agent Drive chat experience."""

    def __init__(self, tui: Any, agent_id: str = "agentdrive-agent"):
        self.tui = tui
        self.console = tui.console
        self.skin = getattr(tui, "skin", None)
        self.palette = Palette(self.skin)
        self.agent_id = agent_id
        self.agent = AgentDriveAgent(agent_id=agent_id)
        self.indicator_style = "unicode"
        self.show_reasoning_hints = False
        self._last_user_message: str | None = None
        # Set by enter() while the async ChatLoop is running, cleared after.
        # /retry uses this to enqueue a replay onto the worker rather than
        # recursing into _handle_user_message from the composer thread.
        self._chat_loop: Any | None = None
        # Set by the turn runner for the duration of a turn; the streaming
        # render polls this to honor double-Enter interrupts.
        self._current_interrupt: Any | None = None
        # Double-Enter tracker for the existing PromptSession keybindings.
        self._last_empty_enter_ts: float = 0.0
        # Active genome: top-matched genome driving the current turn.
        # Cleared at the start of each turn by _sync_turn, set by the
        # PoolMatch handler. Tuple of (genome_id, top_score).
        self._active_form: tuple[str, float] | None = None
        # Pattern 4 — live sub-agent tree pinned above streaming body.
        self._swarm_lane = SwarmActivityLane(palette=self.palette)
        # Pattern 3 — thin pool status row below stream during turns.
        self._pool_lane = PoolActivityLane(palette=self.palette)
        # Pattern 1 — bus-driven assistant body text during streaming turns.
        self._message_lane = MessageStreamLane()
        # Pattern 1 — bus-driven transcript ribbons (pool/evolution/federation).
        self._transcript_lane = TranscriptLane(self.console, self.palette)

        history_file = get_agentdrive_home() / ".agentdrive_chat_history"

        # Multi-line composer: Enter submits, Shift+Enter / Ctrl+Enter / Alt+Enter
        # inserts a newline. Backslash-Enter also inserts a newline (works on
        # terminals where Shift+Enter is captured by the terminal app).
        kb = KeyBindings()

        @kb.add("enter")
        def _submit(event):
            buf = event.current_buffer
            # If the previous char is a backslash, replace it with a newline.
            if buf.text and buf.text[buf.cursor_position - 1 : buf.cursor_position] == "\\":
                buf.delete_before_cursor(1)
                buf.insert_text("\n")
                self._last_empty_enter_ts = 0.0
                return
            # Double-Enter on an empty buffer while a turn is in flight
            # cooperatively interrupts the running turn instead of submitting.
            if not buf.text:
                now = time.monotonic()
                last = self._last_empty_enter_ts
                self._last_empty_enter_ts = now
                loop = self._chat_loop
                if (
                    loop is not None
                    and last > 0
                    and (now - last) <= ChatLoop.DOUBLE_ENTER_WINDOW_S
                    and getattr(loop, "_current_turn_task", None) is not None
                    and not loop._current_turn_task.done()
                ):
                    loop._interrupt.set()
                    self._last_empty_enter_ts = 0.0
                # Either way, do NOT submit an empty buffer; keep prompt open.
                return
            self._last_empty_enter_ts = 0.0
            buf.validate_and_handle()

        @kb.add(Keys.ControlJ)  # Ctrl+Enter on many terminals
        @kb.add("escape", "enter")  # Alt+Enter
        def _newline(event):
            event.current_buffer.insert_text("\n")

        self._prompt_session: PromptSession = PromptSession(
            history=FileHistory(str(history_file)),
            enable_history_search=True,
            multiline=True,
            key_bindings=kb,
            prompt_continuation=lambda width, line_number, is_soft_wrap: " " * 2,
        )

    # ────────────────────────────────────────────────────────────────
    # Entry / main loop
    # ────────────────────────────────────────────────────────────────

    # Bare words that always behave as commands, never as chat messages.
    _RESERVED_WORDS = {"exit", "quit", "q", ":q", "bye"}

    # Slash commands that delegate to the legacy TUI dispatch (top-level commands).
    # Note: /genomes, /g, /genome (singular), /genome-search, /view, /v are
    # handled natively in this class via _cmd_genomes / _cmd_genome /
    # _cmd_genome_search — Pattern 5 (shared genomes_api logic, chat-native
    # rendering).
    _DELEGATED_SLASH = {
        "/status",
        "/s",
        "/scan",
        "/run",
        "/r",
        "/evolve",
        "/e",
        "/compose",
        "/c",
        "/doctor",
        "/dr",
        "/setup",
        "/configure",
        "/import",
        "/seed",
        "/board",
        "/missions",
        "/kanban",
        "/b",
    }

    def enter(self) -> None:
        import asyncio as _asyncio

        from agentdrive.chat_loop import ChatLoop, InterruptSignal

        self._print_welcome()
        from agentdrive.tui.experience import (
            render_golden_path_gate,
            should_show_golden_path_gate,
        )

        if should_show_golden_path_gate():
            render_golden_path_gate(self.console, palette=self.palette)
        self._print_status_rule()

        completer = WordCompleter(
            [
                # Chat-internal
                "/help",
                "/golden-path",
                "/golden",
                "/think",
                "/learnings",
                "/session",
                "/skills",
                "/skill",
                "/clear",
                "/new",
                "/sessions",
                "/resume",
                "/model",
                "/provider",
                "/retry",
                "/steer",
                "/unsteer",
                "/indicator",
                "/reasoning",
                "/pool",
                "/dna",
                "/genomes",
                "/g",
                "/genome",
                "/genome-search",
                "/view",
                "/v",
                "/back",
                "/quit",
                "/exit",
                # Delegated to TUI dispatch
                *sorted(self._DELEGATED_SLASH),
            ],
            ignore_case=True,
            sentence=True,
        )

        # Captured by handlers below so enter() can pick the right goodbye
        # path after the loop returns. "exit" closes the whole TUI; "back"
        # drops to the legacy menu (TUI keeps running).
        self._exit_action: str | None = None

        def _sync_turn(msg: str, sig: InterruptSignal) -> None:
            self._sync_turn(msg, sig)

        async def _slash(line: str) -> str | None:
            action = self._handle_command(line)
            if action == "exit":
                self._exit_action = "exit"
                return "EXIT"
            if action == "back":
                self._exit_action = "back"
                return "EXIT"
            return None

        # Reuse the existing PromptSession so multiline / shift-enter /
        # backslash-newline keybindings, FileHistory, and double-Enter
        # interrupt (empty buffer) all stay in force.
        self._swarm_lane.attach()
        self._pool_lane.attach()
        self._message_lane.attach()
        self._transcript_lane.attach()
        self._chat_loop = ChatLoop(
            self.console,
            prompt_fn=self._composer_prompt,
            prompt_session=self._prompt_session,
            completer=completer,
        )
        self._chat_loop.register_sync_turn_runner(_sync_turn)
        self._chat_loop.register_slash_handler(_slash)

        # Active Form header — PoolMatch stays on ChatView (not TranscriptLane).
        from agentdrive.events import PoolMatch, subscribe, unsubscribe

        _pool_match_token = subscribe(self._on_pool_match, [PoolMatch])

        # Pattern 1 — record the full typed event stream for this session.
        self.agent.attach_session_recorder()
        try:
            _asyncio.run(self._chat_loop.run())
        except KeyboardInterrupt:
            self._exit_action = self._exit_action or "exit"
        finally:
            self._chat_loop = None
            self.agent.detach_session_recorder()
            self._swarm_lane.detach()
            self._pool_lane.detach()
            self._message_lane.detach()
            self._transcript_lane.detach()
            try:
                unsubscribe(_pool_match_token)
            except Exception:
                pass

        if self._exit_action == "back":
            self._print_goodbye(brief=True)
            return

        # "exit" or unset (EOF / Ctrl-D) → close the whole TUI.
        self.tui.running = False
        self._print_goodbye()

    # ────────────────────────────────────────────────────────────────
    # Welcome panel (sectioned)
    # ────────────────────────────────────────────────────────────────

    def _print_welcome(self) -> None:
        p = self.palette

        # Logo + tagline
        logo = Text()
        logo.append(f"{Glyphs.DIAMOND} ", style=p.accent)
        logo.append("AGENTDRIVE", style=p.title + " bold")
        logo.append("  Agent", style=p.accent)

        tagline = Text(
            "body: framework · voice: model · memory: pool",
            style=p.muted + " italic",
        )

        sections: list[Any] = []

        # — Voice
        if self.agent.has_model:
            llm = self.agent.llm
            pname = llm.provider.display_name if llm and llm.provider else "—"
            model = llm.model if llm and llm.model else "—"
            voice_rows = [
                ("provider", f"[agentdrive.genome]{pname}[/]"),
                ("model", f"[agentdrive.framework]{model}[/]"),
                ("key", "[agentdrive.ok]✓ configured[/]"),
            ]
        else:
            voice_rows = [
                ("provider", "[agentdrive.warn]not set[/]"),
                ("model", "—"),
                ("key", "[agentdrive.warn]missing[/]"),
                ("setup", f"[{p.accent}]agentdrive provider set <name>[/]"),
            ]
        sections.append(Section("Voice", voice_rows, palette=p))

        # — Memory
        try:
            stats = self.agent.harness.pool.get_pool_stats()
            rs = stats.get("registry_stats", {})
            n = rs.get("count", 0)
            doms = ", ".join(rs.get("domains_covered", [])[:4]) or "—"
            ingests = stats.get("ingest_events", 0)
            avg = rs.get("avg_score", 0)
            memory_rows = [
                ("genomes", f"[agentdrive.genome]{n}[/]"),
                ("domains", doms),
                ("ingests", str(ingests)),
                ("avg score", f"{avg:.2f}"),
            ]
        except Exception:
            memory_rows = [("drive", "[agentdrive.warn]unavailable[/]")]
        sections.append(Section("Memory", memory_rows, palette=p))

        # — Session
        session_rows = [
            ("id", f"[agentdrive.genome]{self.agent.session.session_id}[/]"),
            ("agent", self.agent.agent_id),
        ]
        if self.agent.steer:
            session_rows.append(
                ("steering", f"[agentdrive.framework]{rich_escape(self.agent.steer)}[/]")
            )
        sections.append(Section("Session", session_rows, palette=p))

        # — Golden path
        try:
            from agentdrive.tui.experience import (
                golden_path_status_segment,
                is_golden_path_marked_complete,
            )

            gp_seg = golden_path_status_segment(p)
            gp_rows = [
                ("status", gp_seg),
                (
                    "next",
                    f"[{p.accent}]/golden-path run[/]"
                    if not is_golden_path_marked_complete()
                    else f"[{p.muted}]complete[/]",
                ),
            ]
            sections.append(Section("Golden path", gp_rows, palette=p))
        except Exception:
            pass

        inner_parts: list[Any] = [
            logo,
            tagline,
            Text(""),
            sections[0],
            Text(""),
            sections[1],
            Text(""),
            sections[2],
        ]
        if len(sections) > 3:
            inner_parts.extend([Text(""), sections[3]])
        inner_parts.extend(
            [
                Text(""),
                Text.from_markup(
                    f"[{p.muted}]Type to talk · [{p.accent}]/help[/{p.accent}] for commands · "
                    f"[{p.accent}]/golden-path run[/{p.accent}] first-run · "
                    f"[{p.accent}]/exit[/{p.accent}] to quit[/]"
                ),
            ]
        )
        inner = Group(*inner_parts)

        self.console.print()
        self.console.print(
            Panel(
                inner,
                border_style=p.border,
                padding=(1, 2),
            )
        )

        if not self.agent.has_model:
            self.console.print()
            self.console.print(
                warn_line(
                    f"No AI provider configured. Run [{p.accent}]agentdrive provider set <name>[/] in your shell.",
                    palette=p,
                )
            )

    # ────────────────────────────────────────────────────────────────
    # Composer / status rule
    # ────────────────────────────────────────────────────────────────

    def _composer_prompt(self) -> str:
        return f"\n{Glyphs.USER} "

    def _estimate_context_used(self) -> int:
        """Rough token-count estimate based on session text length."""
        total_chars = 0
        for t in self.agent.session.turns:
            total_chars += len(t.content)
        return total_chars // _CHARS_PER_TOKEN

    def _print_status_rule(self) -> None:
        p = self.palette

        # Model segment
        if self.agent.has_model:
            try:
                llm = self.agent.llm
                short = (llm.model or llm.provider.default_model).split("/")[-1]
                pname = llm.provider.name if llm and llm.provider else "?"
                model_seg = f"[{p.accent}]{pname}[/] [{p.muted}]·[/] {short}"
            except Exception:
                model_seg = "[agentdrive.warn]no model[/]"
        else:
            model_seg = "[agentdrive.warn]no model[/]"

        # Session segment
        sid_short = self.agent.session.session_id.split("-")[-1]
        n_turns = sum(1 for t in self.agent.session.turns if t.role == "user")
        session_seg = (
            f"session {sid_short} [{p.muted}]·[/] {n_turns} turn{'s' if n_turns != 1 else ''}"
        )

        # Pool segment
        pool_seg = ""
        try:
            stats = self.agent.harness.pool.get_pool_stats()
            n = stats.get("registry_stats", {}).get("count", 0)
            pool_seg = f"pool {n}"
        except Exception:
            pass

        # Context bar
        ctx_used = self._estimate_context_used()
        ctx_seg = context_bar(ctx_used, _NOMINAL_CONTEXT, p) if ctx_used > 0 else ""

        # Steer
        steer_seg = ""
        if self.agent.steer:
            steer_preview = self.agent.steer[:32] + ("…" if len(self.agent.steer) > 32 else "")
            steer_seg = f"[agentdrive.framework]steer:[/] {rich_escape(steer_preview)}"

        # Golden path segment
        gp_seg = ""
        try:
            from agentdrive.tui.experience import golden_path_status_segment

            gp_seg = golden_path_status_segment(p)
        except Exception:
            pass

        # Help hint
        help_seg = f"[{p.muted}]/help[/]"

        segments = [model_seg, session_seg, pool_seg, ctx_seg, steer_seg]
        if gp_seg:
            segments.append(gp_seg)
        segments.append(help_seg)

        self.console.print(status_rule(*segments, palette=p))

    # ────────────────────────────────────────────────────────────────
    # User → assistant turn rendering
    # ────────────────────────────────────────────────────────────────

    def _on_pool_match(self, ev: Any) -> None:
        """Active Form header: render a bold glowing line directly above
        where the assistant reply will stream so the user always knows
        which DNA is driving the response. Empty match case is rendered
        quieter but still honest. Also updates ``self._active_form``.
        """
        p = self.palette
        if not ev.genomes:
            self._active_form = None
            self.console.print("  [dim]◯ active genome · (no DNA matched · pure model)[/]")
            return
        top_genome = ev.genomes[0]
        top_score = ev.scores[0] if ev.scores else 0.0
        self._active_form = (top_genome, top_score)
        extra = len(ev.genomes) - 1
        extra_seg = f"  [dim]▸ +{extra} more[/]" if extra > 0 else ""
        self.console.print(
            f"  [bold {p.accent}]◉ active genome[/] [dim]·[/] "
            f"[{p.genome}]{top_genome}[/]  "
            f"[dim]▸ score {top_score:.2f}[/]"
            f"{extra_seg}"
        )

    def _sync_turn(self, msg: str, sig: Any) -> None:
        # Active Form: clear any stale top-genome from the previous
        # turn before this one's PoolMatch arrives. Stale forms must
        # not leak into the next response's header line.
        self._active_form = None
        stripped = msg.strip()
        if not stripped:
            return
        # Bare-word exit commands close the whole TUI; route through
        # request_exit so the loop terminates after this dispatch.
        if stripped.lower() in self._RESERVED_WORDS:
            self._exit_action = "exit"
            if self._chat_loop is not None:
                self._chat_loop.request_exit()
            return
        # Stash the signal so _stream_assistant_reply can poll it
        # cooperatively in its render loop.
        self._current_interrupt = sig
        try:
            self._handle_user_message(msg)
        finally:
            self._current_interrupt = None

    def _handle_user_message(self, message: str) -> None:
        self._last_user_message = message
        self._render_user_bubble(message)

        if not self.agent.has_model:
            self.console.print()
            self.console.print(
                warn_line(
                    "Can't reply — no provider configured. "
                    f"Run [{self.palette.accent}]agentdrive provider set <name>[/] in your shell.",
                    palette=self.palette,
                )
            )
            self.console.print()
            self._print_status_rule()
            return

        self._stream_assistant_reply(message)

    def _render_user_bubble(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M")
        p = self.palette

        header = Text()
        header.append(f"{Glyphs.USER} ", style=p.accent + " bold")
        header.append("You", style="bold")
        header.append(f"  {ts}", style=p.muted)

        self.console.print()
        self.console.print(header)
        for line in message.splitlines() or [message]:
            self.console.print(f"  {rich_escape(line)}")

    def _stream_assistant_reply(self, message: str) -> None:
        self._swarm_lane.reset()
        self._pool_lane.reset()
        ts = datetime.now().strftime("%H:%M")
        p = self.palette
        model_label = self.agent.model_label()

        header = Text()
        header.append(f"{Glyphs.ASSISTANT} ", style=p.title + " bold")
        header.append("Agent Drive", style="bold")
        header.append(f"  {ts}", style=p.muted)
        header.append(f"  ·  {model_label}", style=p.muted)

        self.console.print()
        self.console.print(header)

        indicator = Indicator(style=self.indicator_style)
        done_event = threading.Event()
        result_container: dict = {}

        self._message_lane.reset()
        self._message_lane.set_session_id(
            getattr(self.agent.session, "session_id", None)
        )

        def worker() -> None:
            try:
                result_container["result"] = self.agent.send(message)
            except Exception as exc:
                result_container["error"] = exc
            finally:
                done_event.set()

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        def render() -> Group:
            text = self._message_lane.text()
            cursor_visible = (int(time.monotonic() * 2.4) % 2) == 0

            parts: list[Any] = []
            swarm = self._swarm_lane.renderable()
            if swarm is not None:
                parts.append(Padding(swarm, (0, 0, 1, 0)))

            if text:
                body: Any = Padding(Markdown(text), (0, 0, 0, 2))
            else:
                body = Padding(Text("…", style=p.muted), (0, 0, 0, 2))
            parts.append(body)

            cursor_line = Text()
            cursor_line.append("  ")
            if cursor_visible:
                cursor_line.append(Glyphs.STREAM_CURSOR, style=p.accent)
            else:
                cursor_line.append(" ")
            cursor_line.append(f"   {indicator.frame()}", style="")
            parts.append(cursor_line)

            pool = self._pool_lane.renderable()
            if pool is not None:
                parts.append(Padding(pool, (0, 0, 0, 0)))

            return Group(*parts)

        interrupted_by_signal = False
        try:
            with Live(
                render(),
                console=self.console,
                refresh_per_second=12,
                transient=False,
            ) as live:
                while not done_event.is_set():
                    # Cooperative interrupt: double-Enter sets the signal.
                    if self._current_interrupt is not None and self._current_interrupt.is_set():
                        interrupted_by_signal = True
                        break
                    live.update(render())
                    time.sleep(1 / 12.0)
                if interrupted_by_signal:
                    # Freeze the partial reply in place and exit cleanly.
                    partial_text = self._message_lane.text()
                    if partial_text:
                        live.update(Padding(Markdown(partial_text), (0, 0, 0, 2)))
                else:
                    final_text = self._message_lane.text()
                    if final_text:
                        live.update(Padding(Markdown(final_text), (0, 0, 0, 2)))
                    else:
                        live.update(
                            Padding(Text("[no response]", style="agentdrive.warn"), (0, 0, 0, 2))
                        )
        except KeyboardInterrupt:
            done_event.set()
            self.console.print()
            self.console.print(warn_line("Interrupted — partial reply saved.", palette=p))
            t.join(timeout=2)

        if interrupted_by_signal:
            self.console.print()
            self.console.print(warn_line("Interrupted — partial reply saved.", palette=p))
            # Don't join indefinitely; let the worker keep finishing in the
            # background, but return promptly so the composer regains focus.
            t.join(timeout=2)
            summary = self._swarm_lane.summary_line()
            if summary:
                self.console.print(f"  {summary}")
            self.console.print()
            self._print_status_rule()
            return

        summary = self._swarm_lane.summary_line()
        if summary:
            self.console.print(f"  {summary}")

        result = result_container.get("result")
        if result and result.pulled_genomes:
            self._render_dna_tree(result.pulled_genomes, result.duration_s)
        elif result:
            self.console.print(
                f"\n[{p.muted}]  · {result.duration_s:.1f}s · 0 genomes consulted[/]"
            )
        else:
            err = result_container.get("error")
            if err:
                self.console.print()
                self.console.print(
                    error_line(
                        f"turn failed: {rich_escape(str(err))}",
                        palette=p,
                    )
                )

        self.console.print()
        self._print_status_rule()

    def _render_dna_tree(self, genomes: list[dict], duration_s: float) -> None:
        p = self.palette
        n = len(genomes)

        self.console.print()
        head = Text()
        head.append(f"  {Glyphs.EXPANDED} ", style=p.accent)
        head.append(f"DNA · {n} consulted", style=f"bold {p.accent}")
        head.append(f"  · {duration_s:.1f}s", style=p.muted)
        self.console.print(head)

        rows: list[TreeRow] = []
        for g in genomes:
            gid = g.get("genome_id", "?")
            score = g.get("relevance_score") or g.get("score") or 0.0
            why = (g.get("why_relevant") or "").strip().split("\n")[0][:60]
            reasons = g.get("top_reasoning") or []

            children = []
            if reasons:
                children.append(
                    TreeRow(
                        label=f"patterns: [italic]{', '.join(reasons[:3])}[/]",
                    )
                )

            label = f"[bold {p.genome}]{gid}[/]"
            secondary = f"{score:.2f}"
            if why:
                secondary += f"  {why}"
            rows.append(TreeRow(label=label, secondary=secondary, children=children))

        self.console.print(Padding(Tree(rows, palette=p, indent=4), (0, 0, 0, 0)))

    # ────────────────────────────────────────────────────────────────
    # Slash commands
    # ────────────────────────────────────────────────────────────────

    def _handle_command(self, line: str) -> str:
        """Run a slash command. Returns 'exit' to close TUI, 'back' to drop
        to legacy menu, '' to stay in chat."""
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("/quit", "/exit"):
            return "exit"
        if cmd == "/back":
            return "back"

        # ─── Chat-internal ───
        if cmd == "/help":
            self._cmd_help()
        elif cmd in ("/clear", "/new"):
            self._cmd_new()
        elif cmd == "/sessions":
            self._cmd_sessions()
        elif cmd == "/resume":
            self._cmd_resume(arg)
        elif cmd == "/model":
            self._cmd_model(arg)
        elif cmd == "/provider":
            self._cmd_provider()
        elif cmd == "/retry":
            self._cmd_retry()
        elif cmd == "/steer":
            self._cmd_steer(arg)
        elif cmd == "/unsteer":
            self.agent.set_steer(None)
            self.console.print()
            self.console.print(ok_line("Steering cleared.", palette=self.palette))
            self.console.print()
            self._print_status_rule()
        elif cmd == "/indicator":
            self._cmd_indicator(arg)
        elif cmd == "/reasoning":
            self._cmd_reasoning(arg)
        elif cmd == "/pool":
            self._cmd_pool()
        elif cmd == "/dna":
            self._cmd_dna()
        elif cmd in ("/genomes", "/g"):
            self._cmd_genomes(arg)
        elif cmd in ("/genome", "/view", "/v"):
            self._cmd_genome(arg)
        elif cmd == "/genome-search":
            self._cmd_genome_search(arg)
        elif cmd in (
            "/golden-path",
            "/golden",
            "/think",
            "/learnings",
            "/session",
            "/skills",
            "/skill",
        ):
            from agentdrive.tui.experience import handle_ops_slash

            self.console.print()
            handle_ops_slash(
                self.console,
                cmd,
                arg,
                palette=self.palette,
                agent_id=self.agent.agent_id,
                current_session_id=self.agent.session.session_id,
            )
            self.console.print()
            self._print_status_rule()
        elif cmd == "/chat":
            # Already in chat — re-show the welcome panel as a gentle reminder.
            self._print_welcome()
            self._print_status_rule()

        # ─── Delegated to TUI dispatch ───
        elif cmd in self._DELEGATED_SLASH:
            self._delegate_to_tui(line)

        else:
            self.console.print()
            self.console.print(
                warn_line(
                    f"Unknown command: {cmd}  — try [{self.palette.accent}]/help[/]",
                    palette=self.palette,
                )
            )
            self.console.print()
            self._print_status_rule()

        return ""

    def _delegate_to_tui(self, line: str) -> None:
        """Strip the leading slash and run the command through the TUI's dispatch."""
        bare = line[1:]  # "/genomes search foo" → "genomes search foo"
        self.console.print()
        try:
            self.tui._dispatch(bare)
        except Exception as e:
            self.console.print(
                error_line(
                    f"command failed: {rich_escape(str(e))}",
                    palette=self.palette,
                )
            )
        self.console.print()
        self._print_status_rule()

    # ────────────────────────────────────────────────────────────────
    # Command renderers
    # ────────────────────────────────────────────────────────────────

    def _cmd_help(self) -> None:
        p = self.palette

        section_groups: list[Any] = []
        for title, rows in CHAT_HELP_SECTIONS:
            section_groups.append(Section(title, rows, palette=p, key_width=18))

        self.console.print()
        self.console.print(
            section_panel(
                *section_groups,
                title="Agent Drive Chat · commands",
                palette=p,
            )
        )
        self._print_status_rule()

    def _cmd_new(self) -> None:
        p = self.palette
        n_turns = sum(1 for t in self.agent.session.turns if t.role == "user")
        if n_turns > 0:
            self.console.print()
            ok = confirm_prompt(
                self.console,
                title="Start a fresh session?",
                body=(
                    f"This will archive the current session "
                    f"([agentdrive.genome]{self.agent.session.session_id}[/], {n_turns} turn{'s' if n_turns != 1 else ''})"
                    " and start a new one.\n"
                    f"You can resume the archived session later with [{p.accent}]/resume <id>[/]."
                ),
                default_yes=False,
                palette=p,
                danger=False,
            )
            if not ok:
                self.console.print()
                self.console.print(
                    self.palette.muted + " canceled" if False else Text("  canceled", style=p.muted)
                )
                self.console.print()
                self._print_status_rule()
                return

        self.agent.new_session()
        self._last_user_message = None
        self.console.print()
        self.console.print(
            ok_line(
                f"New session. [agentdrive.genome]{self.agent.session.session_id}[/]",
                palette=p,
            )
        )
        self.console.print()
        self._print_status_rule()

    def _cmd_sessions(self) -> None:
        p = self.palette
        with MicroSpinner(self.console, "scanning sessions…", accent=p.accent):
            rows = self.agent.list_sessions(limit=15)

        if not rows:
            self.console.print()
            self.console.print(warn_line("No prior sessions for this agent.", palette=p))
            self.console.print()
            self._print_status_rule()
            return

        head = Text("Sessions  ", style=f"bold {p.accent}")
        head.append(f"({len(rows)})", style=p.muted)

        tree_rows: list[TreeRow] = []
        for r in rows:
            created = r.get("created", "")[:19].replace("T", " ")
            label = f"[bold {p.genome}]{r['session_id']}[/]"
            secondary = f"{r['turns']} turn{'s' if r['turns'] != 1 else ''}  {created}"
            tree_rows.append(TreeRow(label=label, secondary=secondary))

        hint = Text()
        hint.append("Resume with ", style=p.muted)
        hint.append("/resume <id>", style=f"bold {p.accent}")

        self.console.print()
        self.console.print(
            section_panel(
                Group(head, Text(""), Tree(tree_rows, palette=p)),
                Text(""),
                hint,
                palette=p,
            )
        )
        self._print_status_rule()

    def _cmd_resume(self, sid: str) -> None:
        p = self.palette
        if not sid:
            self.console.print()
            self.console.print(warn_line("Usage: /resume <session-id>", palette=p))
            self.console.print()
            self._print_status_rule()
            return
        try:
            with MicroSpinner(self.console, f"resuming {sid}…", accent=p.accent):
                self.agent.resume(sid)
        except FileNotFoundError:
            self.console.print()
            self.console.print(
                error_line(
                    f"No session matching [agentdrive.genome]{sid}[/]",
                    palette=p,
                    suggestion=f"run [{p.accent}]/sessions[/] to list available IDs",
                )
            )
            self.console.print()
            self._print_status_rule()
            return
        n = len(self.agent.session.turns)
        self.console.print()
        self.console.print(
            ok_line(
                f"Resumed [agentdrive.genome]{sid}[/]",
                palette=p,
                secondary=f"{n} turns loaded",
            )
        )
        self.console.print()
        self._print_status_rule()

    def _cmd_model(self, arg: str) -> None:
        from agentdrive.providers import get, load_config_provider, save_config_provider

        p = self.palette

        if arg:
            cfg = load_config_provider()
            if not (cfg and cfg[0]):
                self.console.print()
                self.console.print(
                    warn_line(
                        f"No provider configured. Run [{p.accent}]agentdrive provider set <name>[/] first.",
                        palette=p,
                    )
                )
                self.console.print()
                self._print_status_rule()
                return
            save_config_provider(cfg[0], arg)
            self.agent.reset_model()
            self.console.print()
            self.console.print(
                ok_line(
                    f"Model → [agentdrive.genome]{arg}[/]",
                    palette=p,
                )
            )
            self.console.print()
            self._print_status_rule()
            return

        cfg = load_config_provider()
        if not (cfg and cfg[0]):
            self.console.print()
            self.console.print(
                warn_line(
                    f"No provider configured. Run [{p.accent}]agentdrive provider set <name>[/] in your shell.",
                    palette=p,
                )
            )
            self.console.print()
            self._print_status_rule()
            return

        profile = get(cfg[0])
        pname = profile.display_name if profile else cfg[0]
        model = cfg[1] or (profile.default_model if profile else "?")
        key_ok = profile and profile.has_key()
        rows = [
            ("provider", f"[agentdrive.genome]{pname}[/]"),
            ("model", f"[agentdrive.framework]{model}[/]"),
            ("key", "[agentdrive.ok]✓[/]" if key_ok else "[agentdrive.warn]missing[/]"),
        ]
        hint = Text()
        hint.append("Switch with ", style=p.muted)
        hint.append("/model <model-id>", style=f"bold {p.accent}")

        self.console.print()
        self.console.print(
            section_panel(
                Section("Active model", rows, palette=p),
                hint,
                palette=p,
            )
        )
        self._print_status_rule()

    def _cmd_provider(self) -> None:
        from agentdrive.providers import list_all

        p = self.palette

        with MicroSpinner(self.console, "loading providers…", accent=p.accent):
            all_p = list(list_all())

        rows: list[TreeRow] = []
        for prov in all_p:
            key_mark = f"[bold {p.ok}]✓[/] " if prov.has_key() else f"[{p.muted}]·[/] "
            label = f"{key_mark}[bold]{prov.name}[/]"
            secondary = prov.default_model
            rows.append(TreeRow(label=label, secondary=secondary))

        head = Text("Providers", style=f"bold {p.accent}")
        hint = Text()
        hint.append("Configure in your shell: ", style=p.muted)
        hint.append("agentdrive provider set <name>", style=f"bold {p.accent}")

        self.console.print()
        self.console.print(
            section_panel(
                Group(head, Text(""), Tree(rows, palette=p)),
                Text(""),
                hint,
                palette=p,
            )
        )
        self._print_status_rule()

    def _cmd_retry(self) -> None:
        p = self.palette
        if not self._last_user_message:
            self.console.print()
            self.console.print(warn_line("Nothing to retry.", palette=p))
            self.console.print()
            self._print_status_rule()
            return
        while self.agent.session.turns and self.agent.session.turns[-1].role != "user":
            self.agent.session.turns.pop()
        if self.agent.session.turns and self.agent.session.turns[-1].role == "user":
            self.agent.session.turns.pop()
        # Enqueue rather than recurse: /retry runs on the composer thread,
        # and calling _handle_user_message inline would spawn a second
        # Live region racing the worker. The worker drains this when the
        # current turn (if any) finishes.
        if self._chat_loop is not None:
            self._chat_loop.enqueue(self._last_user_message)
        else:
            self._handle_user_message(self._last_user_message)

    def _cmd_steer(self, arg: str) -> None:
        p = self.palette
        if not arg:
            current = self.agent.steer or "[dim]none[/]"
            self.console.print()
            self.console.print(Text.from_markup(f"  [bold]Steering goal:[/] {current}"))
            self.console.print()
            self._print_status_rule()
            return
        self.agent.set_steer(arg)
        self.console.print()
        self.console.print(
            ok_line(
                f"Steering set: {rich_escape(arg)}",
                palette=p,
            )
        )
        self.console.print()
        self._print_status_rule()

    def _cmd_indicator(self, arg: str) -> None:
        p = self.palette
        styles = Indicator.styles()
        if not arg:
            self.console.print()
            self.console.print(
                Text.from_markup(
                    f"  [bold]Indicator:[/] [agentdrive.genome]{self.indicator_style}[/]  "
                    f"[dim]options: {', '.join(styles)}[/]"
                )
            )
            self.console.print()
            self._print_status_rule()
            return
        if arg not in styles:
            self.console.print()
            self.console.print(
                warn_line(
                    f"Unknown style '{arg}'. Options: {', '.join(styles)}",
                    palette=p,
                )
            )
            self.console.print()
            self._print_status_rule()
            return
        self.indicator_style = arg
        self.console.print()
        self.console.print(
            ok_line(
                f"Indicator → [agentdrive.genome]{arg}[/]",
                palette=p,
            )
        )
        self.console.print()
        self._print_status_rule()

    def _cmd_reasoning(self, arg: str) -> None:
        p = self.palette
        val = arg.lower()
        if val in ("on", "true", "1"):
            self.show_reasoning_hints = True
        elif val in ("off", "false", "0"):
            self.show_reasoning_hints = False
        state = "on" if self.show_reasoning_hints else "off"
        self.console.print()
        self.console.print(
            ok_line(
                f"Reasoning hints [agentdrive.genome]{state}[/]",
                palette=p,
            )
        )
        self.console.print()
        self._print_status_rule()

    def _cmd_pool(self) -> None:
        p = self.palette
        try:
            with MicroSpinner(self.console, "loading pool stats…", accent=p.accent):
                stats = self.agent.harness.pool.get_pool_stats()
        except Exception as e:
            self.console.print()
            self.console.print(error_line(f"Pool unavailable: {e}", palette=p))
            self.console.print()
            self._print_status_rule()
            return

        rs = stats.get("registry_stats", {})
        rows = [
            ("name", stats.get("name", "main")),
            ("genomes", f"[agentdrive.genome]{rs.get('count', 0)}[/]"),
            ("domains", ", ".join(rs.get("domains_covered", [])[:6]) or "—"),
            ("ingests", str(stats.get("ingest_events", 0))),
            ("avg score", f"{rs.get('avg_score', 0):.2f}"),
            ("steps", str(rs.get("total_steps", 0))),
        ]

        self.console.print()
        self.console.print(
            section_panel(
                Section("Pool", rows, palette=p),
                palette=p,
            )
        )
        self._print_status_rule()

    def _cmd_dna(self) -> None:
        p = self.palette
        dna = self.agent._last_pulled
        if not dna:
            self.console.print()
            self.console.print(warn_line("No DNA was pulled for the most recent turn.", palette=p))
            self.console.print()
            self._print_status_rule()
            return
        self.console.print()
        self._render_dna_tree(dna, 0.0)
        self.console.print()
        self._print_status_rule()

    # ─── Pattern 5: genome surface (shares agentdrive.genomes_api with CLI) ───

    def _cmd_genomes(self, arg: str = "") -> None:
        """Chat-native listing of registered genomes. Logic via genomes_api;
        rendering via chat chrome (matches the rest of this surface)."""
        from agentdrive import genomes_api

        p = self.palette
        try:
            with MicroSpinner(self.console, "loading genomes…", accent=p.accent):
                entries = genomes_api.list_genomes()
        except Exception as e:
            self.console.print()
            self.console.print(error_line(f"Registry error: {rich_escape(str(e))}", palette=p))
            self.console.print()
            self._print_status_rule()
            return

        if not entries:
            self.console.print()
            self.console.print(
                warn_line(
                    f"No genomes registered. Use [{p.accent}]/import[/] to seed the example.",
                    palette=p,
                )
            )
            self.console.print()
            self._print_status_rule()
            return

        rows: list[TreeRow] = []
        for idx, e in enumerate(entries, 1):
            gid_short = e.id
            dom = ", ".join(e.domains[:2]) or "—"
            badge = "[bold magenta]◆ PROMOTED[/] " if e.is_ultimate else ""
            ult_suffix = (
                f" [dim magenta]{e.ultimate_version}[/]"
                if (e.is_ultimate and e.ultimate_version)
                else ""
            )
            label = (
                f"[{p.muted}]{idx:>2}[/]  {badge}[bold {p.genome}]{gid_short}[/] "
                f"[dim]@{e.version}[/]{ult_suffix}"
            )
            secondary = (
                f"{dom}  [{p.muted}]·[/] {e.num_steps} step{'s' if e.num_steps != 1 else ''}  "
                f"[{p.muted}]·[/] score [{p.evolution}]{e.score:.2f}[/]"
            )
            rows.append(TreeRow(label=label, secondary=secondary))

        self.console.print()
        self.console.print(
            section_panel(
                Tree(rows, palette=p),
                title=f"Genomes  ({len(entries)})",
                palette=p,
            )
        )
        hint = Text()
        hint.append("Inspect with ", style=p.muted)
        hint.append("/genome <id>", style=f"bold {p.accent}")
        hint.append("  ·  search with ", style=p.muted)
        hint.append("/genome-search <query>", style=f"bold {p.accent}")
        self.console.print(hint)
        self._print_status_rule()

    def _cmd_genome_search(self, query: str = "") -> None:
        """Chat-native genome search. Logic via genomes_api.search_genomes."""
        from agentdrive import genomes_api

        p = self.palette
        query = (query or "").strip()
        if not query:
            self.console.print()
            self.console.print(
                warn_line(
                    f"Usage: [{p.accent}]/genome-search <query>[/]  "
                    f"— list all with [{p.accent}]/genomes[/]",
                    palette=p,
                )
            )
            self.console.print()
            self._print_status_rule()
            return

        try:
            with MicroSpinner(self.console, "searching genomes…", accent=p.accent):
                matches = genomes_api.search_genomes(query)
        except Exception as e:
            self.console.print()
            self.console.print(error_line(f"Search error: {rich_escape(str(e))}", palette=p))
            self.console.print()
            self._print_status_rule()
            return

        if not matches:
            self.console.print()
            self.console.print(
                warn_line(
                    f"No matching genomes for [{p.genome}]{rich_escape(query[:80])}[/]. "
                    "Try broadening the description.",
                    palette=p,
                )
            )
            self.console.print()
            self._print_status_rule()
            return

        rows: list[TreeRow] = []
        for idx, m in enumerate(matches, 1):
            dom = ", ".join(m.domains[:2]) or "—"
            label = (
                f"[{p.muted}]{idx:>2}[/]  [bold {p.genome}]{m.genome_id}[/] "
                f"[dim]@{m.version}[/]"
            )
            secondary = (
                f"{dom}  [{p.muted}]·[/] score [{p.evolution}]{m.score:.2f}[/]"
            )
            rows.append(TreeRow(label=label, secondary=secondary))

        self.console.print()
        self.console.print(
            section_panel(
                Tree(rows, palette=p),
                title=f"Genome Search  ({len(matches)})  ·  {query[:60]}",
                palette=p,
            )
        )
        hint = Text()
        hint.append("Inspect with ", style=p.muted)
        hint.append("/genome <id>", style=f"bold {p.accent}")
        self.console.print(hint)
        self._print_status_rule()

    def _cmd_genome(self, gid: str = "") -> None:
        """Chat-native single-genome inspector. Logic via genomes_api."""
        from agentdrive import genomes_api

        p = self.palette
        gid = (gid or "").strip()
        if not gid:
            self.console.print()
            self.console.print(
                warn_line(
                    f"Usage: [{p.accent}]/genome <id>[/]  — list with [{p.accent}]/genomes[/]",
                    palette=p,
                )
            )
            self.console.print()
            self._print_status_rule()
            return

        try:
            with MicroSpinner(self.console, "loading genome…", accent=p.accent):
                info = genomes_api.get_genome(gid)
        except Exception as e:
            self.console.print()
            self.console.print(error_line(f"Load error: {rich_escape(str(e))}", palette=p))
            self.console.print()
            self._print_status_rule()
            return

        if info is None:
            self.console.print()
            self.console.print(error_line(f"Genome not found: {rich_escape(gid)}", palette=p))
            self.console.print()
            self._print_status_rule()
            return

        authors = ", ".join(info.authors) or "—"
        domains = ", ".join(info.domains) or "—"
        score_str = f"[{p.evolution}]{info.score:.2f}[/]"
        manifest_rows = [
            ("id", f"[bold {p.genome}]{info.id}[/]  [dim]@{info.version}[/]"),
            ("created", info.created or "—"),
            ("last", info.last_improved or "—"),
            ("authors", authors),
            ("domains", domains),
            ("score", score_str),
        ]

        sections: list[Any] = [Section("Manifest", manifest_rows, palette=p, key_width=10)]

        if info.step_previews:
            preview = info.step_previews[:6]
            step_rows = [
                TreeRow(
                    label=f"[bold {p.evolution}]{s['name']}[/]",
                    secondary=(s.get("description") or "")[:60],
                )
                for s in preview
            ]
            if info.num_steps > len(preview):
                step_rows.append(
                    TreeRow(
                        label=f"[dim]+ {info.num_steps - len(preview)} more step"
                        f"{'s' if info.num_steps - len(preview) != 1 else ''}[/]"
                    )
                )
            fw_head = Text()
            fw_head.append("Framework", style=f"bold {p.accent}")
            fw_head.append(f"  {info.framework_id or 'n/a'}", style=p.muted)
            fw_head.append(
                f"  {info.num_steps} step{'s' if info.num_steps != 1 else ''}", style=p.muted
            )
            sections.append(Group(fw_head, Tree(step_rows, palette=p)))

        if info.reasoning_pattern_keys:
            keys = info.reasoning_pattern_keys
            preview = ", ".join(keys[:5])
            if len(keys) > 5:
                preview += f"  (+{len(keys) - 5} more)"
            sections.append(
                Section(
                    "Reasoning patterns",
                    [
                        ("count", str(len(keys))),
                        ("keys", preview),
                    ],
                    palette=p,
                    key_width=8,
                )
            )

        if info.tool_composition_keys:
            keys = info.tool_composition_keys
            preview = ", ".join(keys[:3])
            if len(keys) > 3:
                preview += f"  (+{len(keys) - 3} more)"
            sections.append(
                Section(
                    "Tool compositions",
                    [
                        ("count", str(len(keys))),
                        ("keys", preview),
                    ],
                    palette=p,
                    key_width=8,
                )
            )

        self.console.print()
        self.console.print(
            section_panel(
                *sections,
                title=f"Genome · {info.genome_id}",
                palette=p,
            )
        )
        self._print_status_rule()

    def _print_goodbye(self, brief: bool = False) -> None:
        p = self.palette
        self.console.print()
        if brief:
            self.console.print(
                Text.from_markup(
                    f"[{p.muted}]→ legacy command menu (type[/] [{p.accent}]chat[/] [{p.muted}]to return)[/]"
                )
            )
        else:
            self.console.print(
                Text.from_markup(
                    f"[{p.muted}]Session saved at[/] [{p.accent}]{self.agent.session.path}[/]"
                )
            )
        self.console.print()
