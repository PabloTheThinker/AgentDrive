"""Standalone async chat loop with queued turns + bypass slash/shell handlers.

Implements Pattern 2 from docs/UX-PROPOSAL.md ("keep typing while the agent
works"). The recipe is the one validated by /tmp/savant-spike/spike.py:

* single asyncio event loop
* ``prompt_toolkit.PromptSession.prompt_async`` for the composer
* ``patch_stdout(raw=True)`` so background prints don't corrupt the input line
* turn execution runs as an ``asyncio.Task`` consuming an ``asyncio.Queue``
* slash + shell handlers bypass the queue and run concurrently

This module is *mechanical only*. It owns no rendering decisions; all output
flows through the ``rich.console.Console`` the caller injects.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

try:  # pragma: no cover - optional dependency at import time
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.patch_stdout import patch_stdout
except Exception:  # pragma: no cover - tests use the fake composer
    PromptSession = None  # type: ignore[assignment]
    FileHistory = None  # type: ignore[assignment]
    KeyBindings = None  # type: ignore[assignment]
    patch_stdout = None  # type: ignore[assignment]

try:  # rich is a project dependency, but keep the import soft for typing
    from rich.console import Console
except Exception:  # pragma: no cover
    Console = object  # type: ignore[assignment,misc]


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Interrupt signal
# ---------------------------------------------------------------------------


class InterruptSignal:
    """Cooperative interrupt flag passed into a turn runner.

    Wraps :class:`asyncio.Event` deliberately — the turn runner should not
    need to import asyncio just to poll for an interrupt. The contract is
    explicit: ``is_set()`` to poll, ``set()`` from the loop on double-Enter,
    ``clear()`` between turns.
    """

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def set(self) -> None:
        self._event.set()

    def clear(self) -> None:
        self._event.clear()

    def is_set(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        """Async wait for the signal — handy for cooperative turns."""
        await self._event.wait()


# ---------------------------------------------------------------------------
# Sentinels
# ---------------------------------------------------------------------------


class _Interrupt:
    """Sentinel returned by ``_get_input`` to mean 'double-Enter fired'."""


class _EOF:
    """Sentinel returned by ``_get_input`` to mean 'composer hit EOF'."""


INTERRUPT = _Interrupt()
EOF = _EOF()


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------


TurnRunner = Callable[[str, InterruptSignal], Awaitable[None]]
SlashHandler = Callable[[str], Awaitable[str | None]]
ShellHandler = Callable[[str], Awaitable[None]]


# ---------------------------------------------------------------------------
# ChatLoop
# ---------------------------------------------------------------------------


class ChatLoop:
    """Cooperating composer + turn-queue loop.

    The loop coordinates input → handler dispatch and nothing else. All
    output is the caller's responsibility (use the ``console`` you handed in).
    """

    DOUBLE_ENTER_WINDOW_S: float = 0.6

    def __init__(
        self,
        console: Console,
        *,
        prompt_fn: Callable[[], str] = lambda: "you > ",
        history_file: Path | None = None,
        slash_prefix: str = "/",
        shell_prefix: str = "!",
        prompt_session: object | None = None,
        completer: object | None = None,
    ) -> None:
        self.console = console
        self._prompt_fn = prompt_fn
        self._history_file = history_file
        self._slash_prefix = slash_prefix
        self._shell_prefix = shell_prefix
        # Allow callers to inject an existing PromptSession (with their own
        # keybindings, history, multiline behavior) so we preserve the exact
        # composer UX they already shipped. If None, the loop builds one on
        # first input.
        self._session: object | None = prompt_session
        self._completer = completer

        self._turn_runner: TurnRunner | None = None
        self._slash_handler: SlashHandler | None = None
        self._shell_handler: ShellHandler | None = None

        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._interrupt = InterruptSignal()
        self._current_turn_task: asyncio.Task[None] | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

        # double-enter tracking
        self._last_empty_enter_ts: float = 0.0

    # -- registration ------------------------------------------------------

    def register_turn_runner(self, runner: TurnRunner) -> None:
        self._turn_runner = runner

    def register_sync_turn_runner(self, runner: Callable[[str, InterruptSignal], None]) -> None:
        """Convenience: adapt a sync turn runner via :func:`asyncio.to_thread`.

        Use this when the existing turn implementation is blocking (e.g.
        already uses its own worker thread + Rich ``Live``). The signal is
        still passed through so the runner can poll cooperatively if it
        chooses; legacy runners that ignore it remain interruptible only via
        the existing KeyboardInterrupt path.
        """

        async def _async_adapter(msg: str, sig: InterruptSignal) -> None:
            await asyncio.to_thread(runner, msg, sig)

        self._turn_runner = _async_adapter

    def register_slash_handler(self, handler: SlashHandler) -> None:
        self._slash_handler = handler

    def register_shell_handler(self, handler: ShellHandler) -> None:
        self._shell_handler = handler

    # -- introspection -----------------------------------------------------

    def queue_depth(self) -> int:
        """Number of queued plain-text messages waiting for the turn runner."""
        return self._queue.qsize()

    def enqueue(self, message: str) -> None:
        """Inject a plain-text message into the turn queue.

        Use from a slash handler (``/retry``, ``/replay``, etc.) that needs
        to schedule a turn without recursing into the turn runner from the
        composer thread — recursion would race the worker and spawn a
        second ``Live`` region. ``put_nowait`` is safe here because the
        queue is unbounded.
        """
        self._queue.put_nowait(message)

    def request_exit(self) -> None:
        """Ask the loop to terminate after the current dispatch completes.

        Equivalent to a slash handler returning ``"EXIT"``, but callable
        from anywhere — useful for the turn runner when it sees a reserved
        bare-word exit command (``exit``, ``quit``, etc.) that the slash
        handler will never see.
        """
        self._stop.set()
        try:
            self._queue.put_nowait("")
        except Exception:  # pragma: no cover - defensive
            pass

    # -- main loop ---------------------------------------------------------

    async def run(self) -> None:
        """Drive the loop until ``/exit``-style slash or EOF."""
        self._worker_task = asyncio.create_task(self._turn_worker(), name="chat-loop-worker")
        try:
            await self._input_loop()
        finally:
            self._stop.set()
            # Wake the worker if it's blocked on queue.get
            self._queue.put_nowait("")  # type: ignore[arg-type]
            if self._worker_task is not None:
                try:
                    await self._worker_task
                except Exception:  # pragma: no cover - defensive
                    logger.exception("chat-loop worker raised on shutdown")
            if self._current_turn_task is not None and not self._current_turn_task.done():
                self._interrupt.set()
                self._current_turn_task.cancel()
                try:
                    await self._current_turn_task
                except (asyncio.CancelledError, Exception):
                    pass

    async def _input_loop(self) -> None:
        while not self._stop.is_set():
            try:
                line = await self._get_input()
            except (EOFError, KeyboardInterrupt):
                return

            if line is EOF:
                return
            if line is INTERRUPT:
                self._handle_interrupt()
                continue
            assert isinstance(line, str)

            stripped = line.strip()
            if not stripped:
                # Empty submit while no turn is running — just ignore
                continue

            if stripped.startswith(self._slash_prefix):
                should_exit = await self._dispatch_slash(stripped)
                if should_exit:
                    return
                continue

            if stripped.startswith(self._shell_prefix):
                await self._dispatch_shell(stripped[len(self._shell_prefix) :].strip())
                continue

            # Plain text → queue
            await self._queue.put(line)

    # -- input acquisition (test seam) -------------------------------------

    async def _get_input(self):  # pragma: no cover - exercised via spike, not tests
        """Acquire one composer submission.

        Returns a ``str`` on a normal submit, ``EOF`` on Ctrl-D, or
        ``INTERRUPT`` if double-Enter fired on an empty buffer.

        TEST-ONLY SEAM: monkeypatch this method to inject scripted input.
        The public API does not change for testing.
        """
        if PromptSession is None:
            raise RuntimeError(
                "prompt_toolkit is required for the default _get_input; "
                "tests should monkeypatch ChatLoop._get_input."
            )

        if self._session is None:
            history = FileHistory(str(self._history_file)) if self._history_file else None
            kb = KeyBindings()

            @kb.add("enter")
            def _(event):  # type: ignore[no-untyped-def]
                buf = event.current_buffer
                text = buf.text
                if not text:
                    now = time.monotonic()
                    last = self._last_empty_enter_ts
                    self._last_empty_enter_ts = now
                    if (
                        self._current_turn_task is not None
                        and not self._current_turn_task.done()
                        and now - last <= self.DOUBLE_ENTER_WINDOW_S
                        and last > 0
                    ):
                        # Fire interrupt without submitting a prompt
                        self._interrupt.set()
                        self._last_empty_enter_ts = 0.0
                    # do NOT validate-and-handle; keep prompt open
                    return
                self._last_empty_enter_ts = 0.0
                buf.validate_and_handle()

            session_kwargs = {"history": history, "key_bindings": kb}
            if self._completer is not None:
                session_kwargs["completer"] = self._completer
            self._session = PromptSession(**session_kwargs)

        try:
            with patch_stdout(raw=True):  # type: ignore[misc]
                text = await self._session.prompt_async(self._prompt_fn())  # type: ignore[union-attr]
        except EOFError:
            return EOF
        # If the interrupt fired during this prompt, surface it
        if self._interrupt.is_set() and not text.strip():
            return INTERRUPT
        return text

    # -- dispatch ---------------------------------------------------------

    def _handle_interrupt(self) -> None:
        # The composer-side handler already set the signal; this is here
        # for input sources (tests) that surface INTERRUPT as a value.
        if self._current_turn_task is not None and not self._current_turn_task.done():
            self._interrupt.set()

    async def _dispatch_slash(self, line: str) -> bool:
        """Returns True if the loop should exit."""
        if self._slash_handler is None:
            logger.warning("slash command received but no handler registered: %r", line)
            return False
        try:
            reply = await self._slash_handler(line)
        except Exception:
            logger.exception("slash handler raised for input %r", line)
            return False
        if reply == "EXIT":
            return True
        return False

    async def _dispatch_shell(self, line: str) -> None:
        if self._shell_handler is None:
            logger.warning("shell command received but no handler registered: %r", line)
            return
        try:
            await self._shell_handler(line)
        except Exception:
            logger.exception("shell handler raised for input %r", line)

    # -- worker -----------------------------------------------------------

    async def _turn_worker(self) -> None:
        while not self._stop.is_set():
            msg = await self._queue.get()
            if self._stop.is_set():
                return
            if not msg:
                # empty sentinel (e.g. shutdown wake) — skip
                continue
            if self._turn_runner is None:
                logger.warning("turn received but no runner registered: %r", msg)
                continue
            self._interrupt.clear()
            self._current_turn_task = asyncio.create_task(
                self._turn_runner(msg, self._interrupt),
                name="chat-loop-turn",
            )
            try:
                await self._current_turn_task
            except asyncio.CancelledError:
                # Turn was cancelled (shutdown) — propagate cleanly
                raise
            except Exception:
                logger.exception("turn runner raised for message %r", msg)
            finally:
                self._current_turn_task = None


__all__ = [
    "ChatLoop",
    "InterruptSignal",
    "INTERRUPT",
    "EOF",
]
