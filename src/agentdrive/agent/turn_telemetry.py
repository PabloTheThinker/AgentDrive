"""Subagent bus telemetry for in-process chat turns.

Emits ``SubagentSpawn`` / ``SubagentTool`` / ``SubagentTokens`` /
``SubagentDone`` on the default event bus so the TUI swarm tree is
visible during ordinary chat — not only ``demo-swarm`` or external
orchestrators.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from agentdrive.events import (
    SubagentDone,
    SubagentSpawn,
    SubagentTokens,
    SubagentTool,
    emit,
)

logger = logging.getLogger(__name__)

ORCHESTRATOR_ID = "orchestrator"
ORCHESTRATOR_LABEL = "agentdrive orchestrator"


class ChatTurnTelemetry:
    """Lifecycle events for one ``AgentDriveAgent.send()`` turn."""

    __slots__ = ("_turn_id", "_session_id", "_swarm_id", "_subagent_id", "_start", "_token_est")

    def __init__(
        self,
        *,
        session_id: str | None,
        swarm_id: str | None = None,
        subagent_id: str | None = None,
    ) -> None:
        sid = (session_id or "local")[-8:]
        self._turn_id = f"chat-{sid}"
        self._session_id = session_id
        self._swarm_id = swarm_id
        self._subagent_id = subagent_id
        self._start = 0.0
        self._token_est = 0

    def begin(self) -> None:
        self._start = time.monotonic()
        try:
            emit(
                SubagentSpawn(
                    subagent_id=self._turn_id,
                    parent_id=ORCHESTRATOR_ID,
                    label="chat turn",
                    session_id=self._session_id,
                    swarm_id=self._swarm_id,
                )
            )
        except Exception:
            logger.debug("ChatTurnTelemetry.begin failed", exc_info=True)

    def tool(self, name: str) -> None:
        try:
            emit(
                SubagentTool(
                    subagent_id=self._turn_id,
                    tool=name,
                    session_id=self._session_id,
                    swarm_id=self._swarm_id,
                )
            )
        except Exception:
            logger.debug("ChatTurnTelemetry.tool failed", exc_info=True)

    def add_chunk(self, chunk: str) -> None:
        if not chunk:
            return
        self._token_est += max(1, len(chunk) // _CHARS_PER_TOKEN)

    def finish(self, *, ok: bool, error: str | None = None) -> None:
        duration = time.monotonic() - self._start
        if self._token_est > 0:
            try:
                emit(
                    SubagentTokens(
                        subagent_id=self._turn_id,
                        tokens=self._token_est,
                        cost_usd=0.0,
                        session_id=self._session_id,
                        swarm_id=self._swarm_id,
                    )
                )
            except Exception:
                logger.debug("ChatTurnTelemetry.tokens failed", exc_info=True)
        try:
            emit(
                SubagentDone(
                    subagent_id=self._turn_id,
                    ok=ok and error is None,
                    duration_s=duration,
                    session_id=self._session_id,
                    swarm_id=self._swarm_id,
                )
            )
        except Exception:
            logger.debug("ChatTurnTelemetry.finish failed", exc_info=True)


_CHARS_PER_TOKEN = 4


def emit_external_subagent_spawn(
    *,
    subagent_id: str,
    parent_id: str | None,
    label: str,
    session_id: str | None = None,
    swarm_id: str | None = None,
) -> None:
    """Emit when an external runtime (e.g. Grok ``spawn_subagent``) starts a child."""
    try:
        emit(
            SubagentSpawn(
                subagent_id=subagent_id,
                parent_id=parent_id or ORCHESTRATOR_ID,
                label=label or subagent_id,
                session_id=session_id,
                swarm_id=swarm_id,
            )
        )
    except Exception:
        logger.debug("emit_external_subagent_spawn failed", exc_info=True)


def spawn_label_from_kwargs(kwargs: dict[str, Any], args: tuple[Any, ...], fallback: str) -> str:
    """Best-effort human label for a spawned sub-agent."""
    for key in ("description", "name", "task", "prompt", "goal"):
        val = kwargs.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()[:48]
    if args and isinstance(args[0], str) and args[0].strip():
        return args[0].strip()[:48]
    return fallback