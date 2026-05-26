"""
Agent DriveAgent — the framework as the agent's body.

Composes:
- Agent DriveLLM       (the model = the agent's voice)
- Harness   (the Drive = the agent's lived experience / memory)
- AgentSession    (the conversation persistence)

The system prompt is built from:
- Agent Drive identity blurb
- DNA pulled from the Drive for the current turn
- Reasoning patterns surfaced by the top genomes

Each turn streams chunks via a caller-supplied callback so the TUI can
render incrementally. After every assistant turn the harness records
an outcome — every chat grows the Drive.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from agentdrive.agent.session import AgentSession, Turn
from agentdrive.events import (
    MessageComplete,
    MessageDelta,
    PoolMatch,
    emit,
)
from agentdrive.harness.harness import Harness
from agentdrive.providers.base import load_config_provider
from agentdrive.providers.llm import Agent DriveLLM

logger = logging.getLogger(__name__)


AGENTDRIVE_IDENTITY = (
    "You are Agent Drive — an AI agent whose body is the AgentDrive. "
    "Your knowledge comes from a living pool of DNA (Genomes): structured frameworks, "
    "reasoning patterns, and tool compositions accumulated from real agent work. "
    "Each turn, the most relevant DNA for the user's task is loaded into your context. "
    "Speak with clarity and warmth. Reference specific Genomes when they shape your answer. "
    "When the user asks about capabilities, frameworks, or past work, ground your reply in the Drive. "
    "When the Drive is sparse or empty, say so honestly and offer a way to seed it."
)


@dataclass
class TurnResult:
    """Outcome of a single user→assistant turn."""

    text: str
    pulled_genomes: list[dict[str, Any]]
    duration_s: float
    error: str | None = None


class Agent DriveAgent:
    """
    Conversational agent backed by the AgentDrive.

    Usage:
        agent = Agent DriveAgent(agent_id="my-agent")
        for chunk in agent.send("Hello"):
            print(chunk, end="")
    """

    def __init__(
        self,
        agent_id: str = "agentdrive-agent",
        session: AgentSession | None = None,
        swarm_id: str | None = None,
        subagent_id: str | None = None,
        identity: str | None = None,
        temperature: float = 0.6,
        max_tokens: int = 4096,
        history_turns: int = 20,
        pool_top_k: int = 5,
    ):
        self.agent_id = agent_id
        self.identity = identity or AGENTDRIVE_IDENTITY
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.history_turns = history_turns
        self.pool_top_k = pool_top_k
        self.steer: str | None = None

        self.harness = Harness(
            agent_id=agent_id,
            swarm_id=swarm_id,
            subagent_id=subagent_id,
        )
        self.session = session or AgentSession(agent_id=agent_id)
        self._llm: Agent DriveLLM | None = None
        self._last_pulled: list[dict[str, Any]] = []

    # ─────────────────────────────────────────────────────────────────
    # Provider / model
    # ─────────────────────────────────────────────────────────────────

    @property
    def llm(self) -> Agent DriveLLM | None:
        if self._llm is None:
            cfg = load_config_provider()
            if cfg and cfg[0]:
                try:
                    self._llm = Agent DriveLLM()
                except Exception:
                    self._llm = None
        return self._llm

    @property
    def has_model(self) -> bool:
        return self.llm is not None

    def reset_model(self) -> None:
        """Force re-resolution of the provider/model from config."""
        self._llm = None

    def model_label(self) -> str:
        llm = self.llm
        if not llm or not llm.provider:
            return "no model"
        try:
            short = (llm.model or llm.provider.default_model).split("/")[-1]
        except Exception:
            short = "?"
        return f"{llm.provider.display_name} · {short}"

    # ─────────────────────────────────────────────────────────────────
    # System prompt composition (framework = body)
    # ─────────────────────────────────────────────────────────────────

    def build_system_prompt(self, user_message: str) -> str:
        """Compose system prompt = identity + freshly-pulled DNA + reasoning patterns."""
        parts = [self.identity]

        if self.steer:
            parts.append(f"\nUser-set goal for this conversation:\n  {self.steer}")

        try:
            self._last_pulled = self.harness.pull_relevant_dna(
                task=user_message,
                top_k=self.pool_top_k,
            )
        except Exception:
            self._last_pulled = []

        # Emit PoolMatch so subscribers can render the Drive activity ribbon.
        try:
            genomes = [str(d.get("genome_id", "")) for d in self._last_pulled]
            scores = [
                float(d.get("relevance_score") or d.get("score") or 0.0) for d in self._last_pulled
            ]
            emit(
                PoolMatch(
                    genomes=genomes,
                    scores=scores,
                    session_id=getattr(self.session, "session_id", None),
                    swarm_id=getattr(self.harness, "swarm_id", None),
                    subagent_id=getattr(self.harness, "subagent_id", None),
                )
            )
        except Exception:
            logger.debug("Failed to emit PoolMatch", exc_info=True)

        if self._last_pulled:
            lines = ["\nRelevant DNA from your AgentDrive (most relevant first):"]
            for d in self._last_pulled[: self.pool_top_k]:
                gid = d.get("genome_id", "unknown")
                score = d.get("relevance_score") or d.get("score") or 0.0
                why = (d.get("why_relevant") or "")[:140].replace("\n", " ")
                lines.append(f"  - {gid} (relevance ~{score:.2f}): {why}")
                reasons = d.get("top_reasoning") or []
                if reasons:
                    lines.append(f"      patterns: {', '.join(reasons[:4])}")
            parts.append("\n".join(lines))
        else:
            parts.append(
                "\nYour pool currently has no DNA relevant to this turn. "
                "Answer from first principles and suggest a Genome the user might want to seed."
            )

        return "\n".join(parts)

    # ─────────────────────────────────────────────────────────────────
    # The turn loop
    # ─────────────────────────────────────────────────────────────────

    def send(
        self,
        message: str,
        on_chunk: Callable[[str], None] | None = None,
    ) -> TurnResult:
        """
        Send a user message, stream the assistant reply.

        If `on_chunk` is provided, each text chunk is passed to it as soon
        as it arrives (for live TUI rendering). The full text is returned
        in the TurnResult.
        """
        start = time.monotonic()

        # 1. Record the user turn immediately
        self.session.append(Turn(role="user", content=message))

        llm = self.llm
        if llm is None:
            text = (
                "No AI provider is configured. Use `agentdrive provider set <name>` "
                "in your terminal — then come back and we can talk properly."
            )
            self.session.append(Turn(role="assistant", content=text))
            try:
                emit(
                    MessageDelta(
                        text=text,
                        session_id=getattr(self.session, "session_id", None),
                    )
                )
            except Exception:
                logger.debug("Failed to emit MessageDelta (no_model)", exc_info=True)
            if on_chunk:
                on_chunk(text)
            try:
                emit(
                    MessageComplete(
                        text=text,
                        tokens=0,
                        cost_usd=0.0,
                        session_id=getattr(self.session, "session_id", None),
                    )
                )
            except Exception:
                logger.debug("Failed to emit MessageComplete (no_model)", exc_info=True)
            return TurnResult(text=text, pulled_genomes=[], duration_s=0.0, error="no_model")

        # 2. Build system prompt (pulls DNA as side effect)
        system = self.build_system_prompt(message)
        history = self.session.history_for_llm(max_turns=self.history_turns)

        # The current user message is now the last element of history;
        # Agent DriveLLM.stream() expects history to NOT include the current prompt.
        history_for_llm = history[:-1] if history and history[-1]["role"] == "user" else history

        # 3. Stream
        accumulated_parts: list[str] = []
        error: str | None = None
        try:
            for chunk in llm.stream(
                prompt=message,
                system=system,
                history=history_for_llm,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            ):
                accumulated_parts.append(chunk)
                # Emit MessageDelta BEFORE the user-supplied callback so
                # bus subscribers see chunks in order with the UI.
                try:
                    emit(
                        MessageDelta(
                            text=chunk,
                            session_id=getattr(self.session, "session_id", None),
                            swarm_id=getattr(self.harness, "swarm_id", None),
                            subagent_id=getattr(self.harness, "subagent_id", None),
                        )
                    )
                except Exception:
                    logger.debug("Failed to emit MessageDelta", exc_info=True)
                if on_chunk:
                    on_chunk(chunk)
        except Exception as exc:
            error = str(exc)
            err_chunk = f"\n\n[stream error: {error}]"
            accumulated_parts.append(err_chunk)
            if on_chunk:
                on_chunk(err_chunk)

        text = "".join(accumulated_parts)
        duration = time.monotonic() - start

        # 4. Persist assistant turn
        self.session.append(
            Turn(
                role="assistant",
                content=text,
                metadata={
                    "model": self.model_label(),
                    "duration_s": round(duration, 3),
                    "pulled_genomes": [g.get("genome_id") for g in self._last_pulled],
                    "error": error,
                },
            )
        )

        # 5. Record outcome → pool grows
        try:
            self.harness.record_outcome(
                {
                    "status": "success" if not error else "error",
                    "quality": 0.65 if not error else 0.0,
                    "agent_id": self.agent_id,
                    "task": message[:200],
                    "used_genomes": self.harness.get_pulled_genomes(),
                    "response_length": len(text),
                }
            )
        except Exception:
            pass

        # Emit MessageComplete before returning so subscribers can finalize
        # the streaming row. Tokens/cost are not reported by Agent DriveLLM today;
        # pass 0/0.0 rather than skipping the event.
        try:
            emit(
                MessageComplete(
                    text=text,
                    tokens=0,
                    cost_usd=0.0,
                    session_id=getattr(self.session, "session_id", None),
                    swarm_id=getattr(self.harness, "swarm_id", None),
                    subagent_id=getattr(self.harness, "subagent_id", None),
                )
            )
        except Exception:
            logger.debug("Failed to emit MessageComplete", exc_info=True)

        return TurnResult(
            text=text,
            pulled_genomes=self._last_pulled,
            duration_s=duration,
            error=error,
        )

    # ─────────────────────────────────────────────────────────────────
    # Session controls
    # ─────────────────────────────────────────────────────────────────

    def new_session(self) -> None:
        self.session.clear()

    def resume(self, session_id: str) -> None:
        self.session = AgentSession.load(self.agent_id, session_id)

    def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        return AgentSession.list_sessions(self.agent_id, limit=limit)

    def set_steer(self, goal: str | None) -> None:
        self.steer = goal.strip() if goal and goal.strip() else None
