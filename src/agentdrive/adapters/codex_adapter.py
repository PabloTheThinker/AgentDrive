"""
Codex / OpenAI Agent Agent Drive Adapter — Skeleton & Integration Guide.

Codex (and the broader OpenAI agent / "o1" / custom agent frameworks) usually
expose agent creation via:

- The Assistants API + tool calling
- Custom "agent" or "swarm" libraries the user writes
- Function calling loops where the model decides to "spawn worker"

Because there is no universal `spawn_subagent` in the public OpenAI surface,
integration is typically done at the *orchestrator* level the user (or the
model) maintains.

User instruction for a Codex-powered session:

    "Whenever you create helper agents, sub-solvers, or parallel workers for
     this task, give them access to the AgentDrive using the Codex adapter:

     from agentdrive.adapters.codex_adapter import CodexAgent DriveAdapter
     adapter = CodexAgent DriveAdapter()
     adapter.activate(swarm_id='codex-experiment-042')

     Then every worker you instantiate should receive a scoped pool via
     get_scoped_pool() or by passing the adapter's context."

The skeleton below provides:
- A uniform adapter the model can call
- Helpers to inject Agent Drive DNA into tool definitions / system prompts
- A ready-made wrapper for common "create_agent" patterns
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from agentdrive.adapters.base import (
    AgentDrive,
    Agent DriveAdapterBase,
    Agent DriveContext,
)

logger = logging.getLogger(__name__)


class CodexAgent DriveAdapter(Agent DriveAdapterBase):
    """Adapter for Codex-style / OpenAI agent runtimes.

    Typical usage pattern inside a Codex loop:

        adapter = CodexAgent DriveAdapter()
        adapter.activate(swarm_id="my-codex-swarm")

        def my_create_worker(prompt, **kwargs):
            ctx = adapter.get_context_for_child()
            # pass ctx into the worker's system prompt or env
            worker = real_create_worker(prompt + adapter.dna_injection_prompt(), env=ctx.as_env(), ...)
            return worker
    """

    def __init__(self, swarm_id: str | None = None, **kwargs: Any):
        super().__init__(name="codex", default_swarm_id=swarm_id, **kwargs)
        self._last_context: Agent DriveContext | None = None

    def get_name(self) -> str:
        return "codex"

    def activate(self, swarm_id: str | None = None, **options: Any) -> None:
        super().activate(swarm_id=swarm_id, **options)
        logger.info("CodexAgent DriveAdapter activated for OpenAI/Codex-style agents.")

    def get_context_for_child(self, subagent_id: str | None = None) -> Agent DriveContext:
        """Return a Agent DriveContext dict that can be serialized into a child worker."""
        swarm, _ = self.detect_context().swarm_id, None
        if not swarm:
            swarm = self._default_swarm or "codex-default"
        sub = subagent_id or f"codex-worker-{id(self) % 10000:04d}"
        ctx = Agent DriveContext(
            swarm_id=swarm,
            subagent_id=sub,
            parent_agent_id=os.environ.get("AGENTDRIVE_SUBAGENT_ID"),
        )
        self._last_context = ctx
        return ctx

    def dna_injection_prompt(self, task: str = "") -> str:
        """Return a ready-to-append system-prompt fragment that tells the agent
        about available Agent Drive DNA and how to use the Drive.
        """
        pool = self.get_scoped_pool()
        # Pull a couple of examples so the prompt itself is grounded
        try:
            dna = pool.get_relevant_dna(task or "general agent task", top_k=2)
            summary = "\n".join(
                f"- {d.get('genome_id')}: {d.get('why_relevant', '')[:120]}" for d in dna
            )
        except Exception:
            summary = "(AgentDrive is active — call get_scoped_pool() at runtime for live DNA)"

        return f"""

You have access to a AgentDrive of evolved agent DNA (frameworks + reasoning patterns).
Before tackling complex tasks, call (in your Python environment):

    from agentdrive.adapters import get_scoped_pool
    pool = get_scoped_pool()
    dna = pool.get_dna_for_task("...")

Relevant DNA already known for similar work:
{summary}

After successful work, record outcomes so the Drive (and future agents) improve.
""".strip()

    # Example wrapper the Codex user/model can apply around their agent factory
    def wrap_agent_factory(self, original_factory: Callable) -> Callable:
        """Decorator / wrapper for any `create_agent(...)` or `spawn(...)` the model uses."""

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            ctx = self.get_context_for_child()
            # Common patterns: pass as "extra_context", "env", or "system_prompt_suffix"
            if "env" in kwargs:
                kwargs["env"] = {**kwargs.get("env", {}), **ctx.as_env()}
            else:
                kwargs.setdefault("extra_context", {}).update(ctx.as_env())

            # Also inject a hint into any prompt
            if "prompt" in kwargs and isinstance(kwargs["prompt"], str):
                kwargs["prompt"] = (
                    kwargs["prompt"] + "\n" + self.dna_injection_prompt(kwargs["prompt"][:200])
                )

            agent = original_factory(*args, **kwargs)
            # If the returned agent object supports .run or similar, we could wrap further
            return agent

        return wrapped

    def get_pool(self, swarm_id: str | None = None, subagent_id: str | None = None) -> AgentDrive:
        return super().get_pool(swarm_id, subagent_id)


# Make import nice
CodexAgent DriveAdapter = CodexAgent DriveAdapter  # explicit

__all__ = ["CodexAgent DriveAdapter"]
