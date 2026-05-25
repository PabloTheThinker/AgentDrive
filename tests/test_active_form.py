"""Tests for the active-genome header (top-matched genome per turn).

Verifies state management of ``ChatView._active_form`` — the top-matched
genome for the current turn. Rendering is intentionally NOT tested
(Rich output is hard to assert against); we cover behavior instead:

  - PoolMatch with N genomes sets ``_active_form`` to (top_id, top_score).
  - Calling ``_sync_turn`` resets ``_active_form`` to None at the top so
    stale forms from prior turns can't leak into the next response.
  - Empty PoolMatch leaves ``_active_form`` as None and does not crash.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from rich.console import Console

from agentdrive.events import PoolMatch, default_bus, emit, subscribe, unsubscribe
from agentdrive.tui.chat import ChatView


class _FakeTUI:
    """Minimal stand-in for the real TUI passed into ChatView.

    ChatView's constructor reads ``tui.console`` and ``tui.skin``; nothing
    else is touched in the code paths exercised here.
    """

    def __init__(self) -> None:
        # Discard all output. Rich's Console handles a closed/null file.
        self.console = Console(file=open("/dev/null", "w"), force_terminal=False)
        self.skin = None
        self.running = True


@pytest.fixture
def clean_bus() -> Iterator[None]:
    """Snapshot + restore default_bus subscribers around each test."""
    with default_bus._lock:  # type: ignore[attr-defined]
        saved = list(default_bus._subs)  # type: ignore[attr-defined]
        default_bus._subs.clear()  # type: ignore[attr-defined]
    try:
        yield
    finally:
        with default_bus._lock:  # type: ignore[attr-defined]
            default_bus._subs = saved  # type: ignore[attr-defined]


@pytest.fixture
def chat_view() -> ChatView:
    return ChatView(_FakeTUI(), agent_id="active-form-test")


def test_active_form_set_on_pool_match(chat_view: ChatView, clean_bus: None) -> None:
    """A PoolMatch with multiple genomes should set ``_active_form`` to
    the top (id, score) pair."""
    # Wire the same handler that enter() wires, so emit() reaches it.
    token = subscribe(chat_view._on_pool_match, [PoolMatch])
    try:
        emit(
            PoolMatch(
                genomes=["security-incident-postmortem", "bug-triage", "release-notes"],
                scores=[0.87, 0.72, 0.61],
            )
        )
    finally:
        unsubscribe(token)

    assert chat_view._active_form == ("security-incident-postmortem", 0.87)


def test_active_form_cleared_before_each_turn(chat_view: ChatView) -> None:
    """``_sync_turn`` must zero out ``_active_form`` at the top of the
    function so a prior turn's match cannot leak into the next response."""
    # Seed a stale form as if the previous turn matched something.
    chat_view._active_form = ("stale-genome", 0.99)

    # No-op the downstream handler — we are testing _sync_turn's prelude.
    calls: list[str] = []
    chat_view._handle_user_message = lambda msg: calls.append(msg)  # type: ignore[assignment]

    # InterruptSignal is duck-typed; _sync_turn only stashes it.
    chat_view._sync_turn("ping", sig=object())

    assert chat_view._active_form is None
    assert calls == ["ping"], "downstream handler should still receive the message"


def test_active_form_handles_empty_match(chat_view: ChatView, clean_bus: None) -> None:
    """A PoolMatch with empty genome/score lists should not crash and
    should leave ``_active_form`` as None (pure-model turn)."""
    # Pre-seed with a stale value so we can confirm it is reset to None.
    chat_view._active_form = ("stale", 0.5)

    token = subscribe(chat_view._on_pool_match, [PoolMatch])
    try:
        emit(PoolMatch(genomes=[], scores=[]))
    finally:
        unsubscribe(token)

    assert chat_view._active_form is None
