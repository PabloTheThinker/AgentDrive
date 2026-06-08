"""
Bus-driven assistant message body for chat streaming (UX Pattern 1).

Subscribes to MessageDelta for the active session and accumulates text
thread-safely. The chat Live region reads this lane instead of an
on_chunk callback accumulator.
"""

from __future__ import annotations

import threading
from typing import Any

from agentdrive.events import MessageComplete, MessageDelta, subscribe, unsubscribe


class MessageStreamLane:
    """Thread-safe streaming text driven by MessageDelta on the event bus."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._parts: list[str] = []
        self._session_id: str | None = None
        self._tokens: list[Any] = []

    def set_session_id(self, session_id: str | None) -> None:
        with self._lock:
            self._session_id = session_id

    def reset(self) -> None:
        with self._lock:
            self._parts.clear()

    def text(self) -> str:
        with self._lock:
            return "".join(self._parts)

    def _matches(self, session_id: str | None) -> bool:
        with self._lock:
            target = self._session_id
        if target is None:
            return True
        return session_id is None or session_id == target

    def attach(self) -> None:
        if self._tokens:
            return

        def _on_delta(ev: MessageDelta) -> None:
            if not self._matches(ev.session_id):
                return
            if not ev.text:
                return
            with self._lock:
                self._parts.append(ev.text)

        def _on_complete(ev: MessageComplete) -> None:
            # Deltas already carry the full stream; complete is for recorders.
            if not self._matches(ev.session_id):
                return

        for handler, types in (
            (_on_delta, [MessageDelta]),
            (_on_complete, [MessageComplete]),
        ):
            self._tokens.append(subscribe(handler, types))

    def detach(self) -> None:
        for tok in self._tokens:
            try:
                unsubscribe(tok)
            except Exception:
                pass
        self._tokens.clear()