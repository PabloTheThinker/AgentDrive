"""Tests for the standalone ``agentdrive.chat_loop`` module.

Tests drive the loop via a small ``_FakeComposer`` harness that replaces
``ChatLoop._get_input``. The harness lets each test script a sequence of
inputs (``str`` lines, ``INTERRUPT`` sentinels, or ``EOF``) with optional
per-step delays so we can observe behaviour while a turn is in flight.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest
from rich.console import Console

from agentdrive.chat_loop import EOF, INTERRUPT, ChatLoop, InterruptSignal

# ---------------------------------------------------------------------------
# Fake composer harness
# ---------------------------------------------------------------------------


class _FakeComposer:
    """Scripted replacement for ``ChatLoop._get_input``.

    Each step is ``(delay_seconds, value)``. ``value`` may be a ``str`` line,
    the ``INTERRUPT`` sentinel, or ``EOF``. The composer waits ``delay``
    before returning the value, mimicking the user pausing between keystrokes.
    After the script is exhausted, returns ``EOF``.
    """

    def __init__(self, steps: list[tuple[float, Any]]) -> None:
        self._steps = list(steps)
        self._idx = 0
        self.consumed: list[Any] = []

    async def __call__(self) -> Any:
        if self._idx >= len(self._steps):
            return EOF
        delay, value = self._steps[self._idx]
        self._idx += 1
        if delay > 0:
            await asyncio.sleep(delay)
        self.consumed.append(value)
        return value


def _make_loop(steps: list[tuple[float, Any]]) -> tuple[ChatLoop, _FakeComposer]:
    console = Console(force_terminal=False, file=open("/dev/null", "w"))
    loop = ChatLoop(console)
    composer = _FakeComposer(steps)
    loop._get_input = composer  # type: ignore[method-assign]
    return loop, composer


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plain_text_queues_during_turn() -> None:
    processed: list[str] = []

    async def runner(msg: str, sig: InterruptSignal) -> None:
        await asyncio.sleep(0.5)
        processed.append(msg)

    # First message at t=0 starts a 0.5s turn. Two more at t=0.1, t=0.2
    # must queue and run after.
    loop, _ = _make_loop(
        [
            (0.0, "first"),
            (0.1, "second"),
            (0.1, "third"),
            (1.5, EOF),  # give worker time to drain
        ]
    )
    loop.register_turn_runner(runner)
    await asyncio.wait_for(loop.run(), timeout=5.0)

    assert processed == ["first", "second", "third"]


@pytest.mark.asyncio
async def test_slash_bypasses_queue() -> None:
    turn_started = asyncio.Event()
    turn_done = asyncio.Event()
    slash_calls: list[tuple[str, bool]] = []  # (line, turn_was_in_flight)

    async def runner(msg: str, sig: InterruptSignal) -> None:
        turn_started.set()
        await asyncio.sleep(0.5)
        turn_done.set()

    async def slash(line: str) -> str | None:
        slash_calls.append((line, turn_started.is_set() and not turn_done.is_set()))
        return None

    loop, _ = _make_loop(
        [
            (0.0, "plain"),
            (0.1, "/now"),
            (1.0, EOF),
        ]
    )
    loop.register_turn_runner(runner)
    loop.register_slash_handler(slash)
    await asyncio.wait_for(loop.run(), timeout=5.0)

    assert len(slash_calls) == 1
    assert slash_calls[0][0] == "/now"
    assert slash_calls[0][1] is True, "slash handler should run while turn is in flight"
    assert loop.queue_depth() == 0


@pytest.mark.asyncio
async def test_double_enter_sets_interrupt_signal() -> None:
    interrupted = asyncio.Event()
    exited_cleanly = asyncio.Event()

    async def runner(msg: str, sig: InterruptSignal) -> None:
        # poll cooperatively
        for _ in range(200):
            if sig.is_set():
                interrupted.set()
                exited_cleanly.set()
                return
            await asyncio.sleep(0.02)

    loop, _ = _make_loop(
        [
            (0.0, "start a long turn"),
            (0.2, INTERRUPT),  # tests inject INTERRUPT directly
            (0.5, EOF),
        ]
    )
    loop.register_turn_runner(runner)
    await asyncio.wait_for(loop.run(), timeout=5.0)

    assert interrupted.is_set(), "turn runner should observe interrupt signal"
    assert exited_cleanly.is_set(), "turn runner should exit cooperatively"


@pytest.mark.asyncio
async def test_slash_exit_ends_loop() -> None:
    ran = asyncio.Event()

    async def slash(line: str) -> str | None:
        ran.set()
        return "EXIT"

    # Add an extra input after /exit; it should never be consumed because
    # the loop must return immediately on EXIT.
    loop, composer = _make_loop(
        [
            (0.0, "/exit"),
            (0.0, "should-not-process"),
        ]
    )
    loop.register_slash_handler(slash)
    await asyncio.wait_for(loop.run(), timeout=5.0)

    assert ran.is_set()
    assert composer.consumed == ["/exit"], "loop must terminate before consuming next input"


@pytest.mark.asyncio
async def test_handler_exception_does_not_crash_loop(caplog) -> None:
    processed: list[str] = []
    call_count = {"n": 0}

    async def runner(msg: str, sig: InterruptSignal) -> None:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("boom")
        processed.append(msg)

    loop, _ = _make_loop(
        [
            (0.0, "first-will-crash"),
            (0.2, "second-should-still-run"),
            (0.5, EOF),
        ]
    )
    loop.register_turn_runner(runner)
    with caplog.at_level(logging.ERROR, logger="agentdrive.chat_loop"):
        await asyncio.wait_for(loop.run(), timeout=5.0)

    assert processed == ["second-should-still-run"]
    assert any("turn runner raised" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_enqueue_from_slash_handler_avoids_recursion() -> None:
    """A slash handler that calls loop.enqueue() should schedule a turn on
    the worker rather than running it inline (the /retry recursion bug).
    """
    processed: list[str] = []

    async def runner(msg: str, sig: InterruptSignal) -> None:
        processed.append(msg)

    captured_loop: list[ChatLoop] = []

    async def slash(line: str) -> str | None:
        # Simulate /retry: enqueue a message rather than recursing into the runner.
        captured_loop[0].enqueue("retried-message")
        return None

    loop, _ = _make_loop(
        [
            (0.0, "/retry"),
            (0.3, EOF),
        ]
    )
    captured_loop.append(loop)
    loop.register_turn_runner(runner)
    loop.register_slash_handler(slash)
    await asyncio.wait_for(loop.run(), timeout=5.0)

    assert processed == ["retried-message"]


@pytest.mark.asyncio
async def test_sync_turn_runner_adapter() -> None:
    """register_sync_turn_runner should wrap a blocking callable via to_thread."""
    processed: list[str] = []

    def sync_runner(msg: str, sig: InterruptSignal) -> None:
        # Sync function — would block the event loop without to_thread.
        import time as _t

        _t.sleep(0.05)
        processed.append(msg)

    loop, _ = _make_loop(
        [
            (0.0, "one"),
            (0.0, "two"),
            (0.5, EOF),
        ]
    )
    loop.register_sync_turn_runner(sync_runner)
    await asyncio.wait_for(loop.run(), timeout=5.0)

    assert processed == ["one", "two"]


@pytest.mark.asyncio
async def test_request_exit_terminates_loop_from_turn_runner() -> None:
    processed: list[str] = []

    captured_loop: list[ChatLoop] = []

    async def runner(msg: str, sig: InterruptSignal) -> None:
        if msg == "bye":
            captured_loop[0].request_exit()
            return
        processed.append(msg)

    loop, _ = _make_loop(
        [
            (0.0, "hello"),
            (0.1, "bye"),
            (0.1, "should-not-process"),
        ]
    )
    captured_loop.append(loop)
    loop.register_turn_runner(runner)
    await asyncio.wait_for(loop.run(), timeout=5.0)

    assert processed == ["hello"]


@pytest.mark.asyncio
async def test_request_exit_does_not_interrupt_sync_turn() -> None:
    """request_exit() should set the stop signal but a sync turn already in
    flight must finish cleanly. The loop can't safely cancel a thread, so
    the contract is voluntary polling — sync runners that ignore the signal
    still complete.
    """
    import time as _t

    finished: list[str] = []
    captured_loop: list[ChatLoop] = []

    def sync_runner(msg: str, sig: InterruptSignal) -> None:
        # Trigger exit mid-turn from inside the sync runner; the runner
        # itself ignores `sig` (legacy behavior). It must still complete.
        captured_loop[0].request_exit()
        _t.sleep(0.05)
        # Signal is observable but the runner chose not to act on it.
        assert sig.is_set() or captured_loop[0]._stop.is_set()
        finished.append(msg)

    loop, _ = _make_loop([(0.0, "do-work"), (0.5, EOF)])
    captured_loop.append(loop)
    loop.register_sync_turn_runner(sync_runner)
    await asyncio.wait_for(loop.run(), timeout=5.0)

    assert finished == ["do-work"], "sync turn must complete even after request_exit"


@pytest.mark.asyncio
async def test_queue_depth_reports_correctly() -> None:
    probe_depth: list[int] = []
    runner_done = asyncio.Event()

    async def runner(msg: str, sig: InterruptSignal) -> None:
        if msg == "long":
            await asyncio.sleep(0.5)
        await asyncio.sleep(0.01)
        if msg == "last":
            runner_done.set()

    loop, _ = _make_loop(
        [
            (0.0, "long"),
            (0.05, "q1"),
            (0.05, "q2"),
            (0.05, "last"),
            (2.0, EOF),
        ]
    )
    loop.register_turn_runner(runner)

    # Probe queue_depth after the 3 followups have landed but before the
    # long turn finishes (t=0.5).
    async def probe() -> None:
        await asyncio.sleep(0.3)
        probe_depth.append(loop.queue_depth())

    probe_task = asyncio.create_task(probe())
    await asyncio.wait_for(loop.run(), timeout=8.0)
    await probe_task

    assert probe_depth == [3], f"expected [3] queued at probe time, got {probe_depth}"
    assert loop.queue_depth() == 0
    assert runner_done.is_set()
