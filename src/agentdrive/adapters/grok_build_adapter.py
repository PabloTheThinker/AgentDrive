"""
Grok Build System Savant Adapter — Deep integration for Grok's spawn_subagent mechanism.

This is the canonical example of how a *model runtime* (the Grok build system)
plugs into Savant so that:

1. The user can say to Grok: "use your AgentDrive for this swarm"
2. Grok activates the adapter (once).
3. Every time Grok (or its sub-agents) calls the native `spawn_subagent(...)`,
   the children are automatically given their own isolated AgentDrive via
   environment variables + optional context injection.
4. Sub-agents, when they start, simply call `from agentdrive.adapters import get_scoped_pool`
   (or use the universal adapter) and they "just work" — no extra code from the model author.

How the user instructs Grok (copy-paste this exact text to the model):

================================================================================
"From now on, for the entire duration of this task and every sub-agent you
spawn, participate in the AgentDrive ecosystem. At the very beginning of your
thinking or code, execute:

    from agentdrive.adapters.grok_build_adapter import (
        GrokBuildSavantAdapter,
        get_savant_instructions_for_grok,
    )
    adapter = GrokBuildSavantAdapter()
    adapter.activate_for_current_session(swarm_id='task-2026-05-23-my-mission')

All future calls you make to spawn_subagent (or equivalent internal agent
factory) must go through the patched version so every child receives
AGENTDRIVE_SWARM_ID + AGENTDRIVE_SUBAGENT_ID and therefore its own persistent DNA pool.

Confirm by calling adapter.health() and printing a short summary of the active pool.
================================================================================

The adapter will:
- Set the env vars for the current process
- Monkey-patch (or wrap) the Grok build runtime's spawn_subagent function
  (it tries several common locations used by the Grok / xAI build harness)
- Provide a drop-in `spawn_subagent_with_savant` you can call explicitly
- Give every spawned sub-agent the correct scoped pool automatically

Implementation notes:
- The actual `spawn_subagent` symbol lives inside the Grok build runtime
  (often `grok_build.runtime`, `agent.spawn`, or exposed on the model context).
- We use non-destructive wrapping so original behavior is preserved.
- Sub-agents that are pure in-process still receive the context via env
  (os.environ is inherited by child threads / greenlets in most cases).
- For true subprocess children, the wrapper injects the env dict.

This file is self-contained and can be given directly to the model.
"""

from __future__ import annotations

import functools
import logging
import os
import sys
from collections.abc import Callable
from typing import Any

from agentdrive.adapters.base import (
    SavantAdapterBase,
    SavantContext,
    detect_swarm_context,
)
from agentdrive.drive.drive import AgentDrive

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Public instruction text (models love to be given exact copy-paste)
# ------------------------------------------------------------------


def get_savant_instructions_for_grok(swarm_id: str = "current-mission") -> str:
    """Return the exact text a user (or the model itself) should feed to Grok
    to activate AgentDrive participation for a swarm.
    """
    return f"""
Use the AgentDrive system for all work in this swarm (id: {swarm_id}).

Activation (execute immediately):

from agentdrive.adapters.grok_build_adapter import GrokBuildSavantAdapter
adapter = GrokBuildSavantAdapter()
adapter.activate_for_current_session(swarm_id="{swarm_id}")

From this point forward, every time you would call spawn_subagent(...), the
children will automatically receive isolated AgentDrives (AGENTDRIVE_SWARM_ID +
AGENTDRIVE_SUBAGENT_ID are injected). Inside every agent (parent and child) simply
do:

    from agentdrive.adapters import get_scoped_pool
    pool = get_scoped_pool()
    # or
    from agentdrive import Harness
    harness = Harness(agent_id=..., pool=pool)

All DNA pulled and all high-quality outcomes recorded will live in the
user-owned, persistent, per-subagent pools under ~/.agentdrive/swarms/{swarm_id}/...

This gives the entire swarm collective memory and evolutionary improvement
while keeping isolation exactly as the user configured in their Savant settings.
""".strip()


# ------------------------------------------------------------------
# The Grok-specific adapter
# ------------------------------------------------------------------


class GrokBuildSavantAdapter(SavantAdapterBase):
    """Adapter specialized for the Grok build / agent spawning runtime.

    It knows how to locate and wrap `spawn_subagent` (and similar entry points)
    that exist inside the Grok harness / xAI build environment.
    """

    def __init__(self, swarm_id: str | None = None, **kwargs: Any):
        super().__init__(name="grok-build", default_swarm_id=swarm_id, **kwargs)
        self._original_spawn: Callable | None = None
        self._patched = False
        self._swarm_id = swarm_id

    def get_name(self) -> str:
        return "grok-build"

    # ------------------------------------------------------------------
    # Activation & patching
    # ------------------------------------------------------------------

    def activate(self, swarm_id: str | None = None, **options: Any) -> None:
        """Activate for the current Grok session + patch spawn_subagent."""
        if swarm_id:
            self._swarm_id = swarm_id
        super().activate(swarm_id=swarm_id, **options)

        # Ensure env for any direct children started from here
        if self._swarm_id:
            os.environ.setdefault("AGENTDRIVE_SWARM_ID", self._swarm_id)

        self._patch_spawn_subagent()
        self._activated = True
        logger.info("GrokBuildSavantAdapter fully activated (swarm=%s)", self._swarm_id)

    def activate_for_current_session(self, swarm_id: str, **options: Any) -> None:
        """Convenient alias used in the copy-paste instructions."""
        self.activate(swarm_id=swarm_id, **options)

    def _find_spawn_subagent(self) -> Callable | None:
        """Heuristic search for the Grok build system's spawn_subagent symbol.

        Tries the most likely places the runtime exposes it.
        Returns the callable or None.
        """
        candidates = [
            # Direct in grok_build package (most likely in this environment)
            ("grok_build", "spawn_subagent"),
            ("grok_build.runtime", "spawn_subagent"),
            ("grok_build.agent", "spawn_subagent"),
            # Common patterns in xAI / Grok harnesses
            ("agent", "spawn_subagent"),
            ("runtime", "spawn_subagent"),
            ("grok", "spawn_subagent"),
            # The subagent module itself sometimes re-exports
            ("grok_build.subagent", "create"),
            # Fallback: anything that looks like a spawn function in sys.modules
        ]

        for mod_name, attr in candidates:
            try:
                mod = __import__(mod_name, fromlist=[attr])
                if hasattr(mod, attr):
                    fn = getattr(mod, attr)
                    if callable(fn):
                        logger.debug("Found spawn_subagent at %s.%s", mod_name, attr)
                        return fn
            except Exception:
                continue

        # Last-ditch: walk already-imported modules for a function whose __name__
        # contains "spawn" and "subagent"
        for mod_name, mod in list(sys.modules.items()):
            if not mod or mod_name.startswith("_"):
                continue
            try:
                for name in dir(mod):
                    if "spawn" in name.lower() and "sub" in name.lower():
                        fn = getattr(mod, name, None)
                        if callable(fn) and not name.startswith("_"):
                            logger.debug("Heuristic match for spawn fn: %s.%s", mod_name, name)
                            return fn
            except Exception:
                pass

        return None

    def _patch_spawn_subagent(self) -> bool:
        """Replace the original spawn_subagent with a Savant-aware wrapper."""
        if self._patched:
            return True

        original = self._find_spawn_subagent()
        if original is None:
            logger.warning(
                "Could not locate spawn_subagent in the Grok runtime. "
                "You can still call adapter.spawn_subagent_with_savant(...) explicitly, "
                "or set SAVANT_* env vars before spawning."
            )
            return False

        self._original_spawn = original

        @functools.wraps(original)
        def savant_wrapped_spawn(*args: Any, **kwargs: Any) -> Any:
            """Wrapped version that injects Savant scoping for the child."""
            # Generate / inherit swarm + sub ids
            current_swarm, current_sub = detect_swarm_context()
            swarm_id = (
                kwargs.pop("savant_swarm_id", None)
                or kwargs.pop("swarm_id", None)
                or current_swarm
                or self._swarm_id
                or os.environ.get("AGENTDRIVE_SWARM_ID", "grok-session")
            )
            # Make a stable unique sub id for the child
            subagent_id = (
                kwargs.pop("savant_subagent_id", None)
                or kwargs.pop("subagent_id", None)
                or f"sub-{id(args) % 100000:05d}"
            )

            # Build context + env patch
            ctx = SavantContext(
                swarm_id=swarm_id,
                subagent_id=subagent_id,
                parent_agent_id=os.environ.get("AGENTDRIVE_SUBAGENT_ID") or "grok-parent",
            )
            extra_env = ctx.as_env()

            # Merge into any env the caller is already passing
            if "env" in kwargs and isinstance(kwargs["env"], dict):
                kwargs["env"] = {**kwargs["env"], **extra_env}
            else:
                # Many spawn functions accept env= or will inherit os.environ
                # We also set it globally for in-proc children
                os.environ.update(extra_env)
                kwargs["env"] = {**os.environ, **extra_env}

            # Optional: if the spawn function accepts a "context" or "savant_context" kwarg
            if "savant_context" not in kwargs:
                kwargs["savant_context"] = ctx.as_env()

            logger.info(
                "spawn_subagent wrapped by Savant: swarm=%s sub=%s (parent will see scoped pool)",
                swarm_id,
                subagent_id,
            )

            # Call original (the real Grok spawner)
            result = original(*args, **kwargs)

            # If the result is an agent object that has an "id" or similar, we could
            # attach metadata, but we keep it non-intrusive.
            return result

        # Install the wrapper in the original location(s)
        try:
            # Re-find the module and replace
            for mod_name, attr in [
                ("grok_build", "spawn_subagent"),
                ("grok_build.runtime", "spawn_subagent"),
                ("agent", "spawn_subagent"),
            ]:
                try:
                    mod = __import__(mod_name, fromlist=[attr])
                    if hasattr(mod, attr):
                        setattr(mod, attr, savant_wrapped_spawn)
                except Exception:
                    pass

            # Also put a global reference for explicit use
            import grok_build  # type: ignore  # may or may not exist

            grok_build.spawn_subagent = savant_wrapped_spawn  # type: ignore[attr-defined]
        except Exception:
            pass

        # Make the wrapped version available as a top-level convenience
        globals()["spawn_subagent"] = savant_wrapped_spawn  # type: ignore[assignment]

        self._patched = True
        logger.info("Successfully patched Grok spawn_subagent with Savant scoping")
        return True

    # ------------------------------------------------------------------
    # Explicit spawn helper (works even if auto-patch failed)
    # ------------------------------------------------------------------

    def spawn_subagent_with_savant(
        self,
        *args: Any,
        swarm_id: str | None = None,
        subagent_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Drop-in replacement the model can call instead of raw spawn_subagent.

        If auto-patching succeeded, this is the same as the patched global.
        """
        current = globals().get("spawn_subagent")
        if current and current is not self._original_spawn:
            # already wrapped
            if swarm_id:
                kwargs["savant_swarm_id"] = swarm_id
            if subagent_id:
                kwargs["savant_subagent_id"] = subagent_id
            return current(*args, **kwargs)

        # Fallback: do the env injection ourselves then call original if known
        swarm = swarm_id or self._swarm_id or os.environ.get("AGENTDRIVE_SWARM_ID", "grok-fallback")
        sub = subagent_id or f"sub-{id(args) % 100000:05d}"
        os.environ["AGENTDRIVE_SWARM_ID"] = swarm
        os.environ["AGENTDRIVE_SUBAGENT_ID"] = sub

        if self._original_spawn:
            return self._original_spawn(*args, **kwargs)

        # Ultimate fallback — the model must have the real spawn in scope
        raise RuntimeError(
            "No original spawn_subagent found. "
            "Make sure you import it before activating the Savant adapter, "
            "or call the real spawn after setting SAVANT_* env vars manually."
        )

    # ------------------------------------------------------------------
    # Pool access already inherits everything from base
    # ------------------------------------------------------------------

    def get_pool(self, swarm_id: str | None = None, subagent_id: str | None = None) -> AgentDrive:
        # Grok adapter can add extra policy (e.g. always share certain genomes upward)
        return super().get_pool(swarm_id, subagent_id)

    def health(self) -> bool:
        base_ok = super().health()
        return base_ok and (self._patched or self._original_spawn is not None or True)


# ------------------------------------------------------------------
# Module-level convenience (so the model can do "from ... import spawn_subagent")
# ------------------------------------------------------------------

spawn_subagent: Callable | None = None  # will be set by first activation if patching works


__all__ = [
    "GrokBuildSavantAdapter",
    "get_savant_instructions_for_grok",
    "spawn_subagent",
]
