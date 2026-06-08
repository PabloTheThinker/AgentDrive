"""
Live sub-agent tree lane for chat (UX Pattern 4).

Subscribes to subagent events on the default bus and renders a collapsible
Rich tree during active swarms while the assistant streams a reply.
"""

from __future__ import annotations

import threading
from typing import Any

from rich.console import Group, RenderableType

from agentdrive.events import (
    SubagentDone,
    SubagentSpawn,
    SubagentTokens,
    SubagentTool,
    subscribe,
    unsubscribe,
)
from agentdrive.tui.chrome import Palette
from agentdrive.tui.subagent_tree import SubagentTree


class SwarmActivityLane:
    """Thread-safe sub-agent tree driven by the event bus."""

    def __init__(
        self,
        *,
        root_id: str = "orchestrator",
        root_label: str = "agentdrive orchestrator",
        palette: Palette | None = None,
    ) -> None:
        self.palette = palette or Palette(None)
        self._root_id = root_id
        self._root_label = root_label
        self._tree = SubagentTree(root_id=root_id, root_label=root_label)
        self._lock = threading.Lock()
        self._tokens: list[Any] = []
        self._active = False

    def attach(self) -> None:
        """Subscribe to subagent events until :meth:`detach`."""
        if self._tokens:
            return

        def _apply(ev: Any) -> None:
            with self._lock:
                self._tree.apply(ev)
                if isinstance(ev, SubagentSpawn):
                    self._active = True
                if self._tree.is_done() and self._child_count() > 0:
                    self._active = False

        for event_type in (SubagentSpawn, SubagentTool, SubagentTokens, SubagentDone):
            self._tokens.append(subscribe(_apply, [event_type]))

    def detach(self) -> None:
        for tok in self._tokens:
            try:
                unsubscribe(tok)
            except Exception:
                pass
        self._tokens.clear()

    def _child_count(self) -> int:
        return max(0, len(self._tree.nodes()) - 1)

    def has_swarm_activity(self) -> bool:
        """True when at least one sub-agent exists and swarm is in flight."""
        with self._lock:
            return self._is_active_locked()

    def _is_active_locked(self) -> bool:
        """Swarm in flight — caller must hold ``_lock``."""
        return self._child_count() > 0 and (
            self._active or not self._tree.is_done()
        )

    def renderable(self) -> RenderableType | None:
        """Rich renderable for the activity lane, or None when collapsed."""
        with self._lock:
            if self._child_count() == 0:
                return None
            if not self._is_active_locked() and self._tree.is_done():
                return None
            return Group(self._tree.render(self.palette))

    def summary_line(self) -> str | None:
        """One-line post-swarm summary when collapsed."""
        with self._lock:
            children = [
                n for n in self._tree.nodes() if n.subagent_id != self._root_id
            ]
            if not children:
                return None
            done = sum(1 for n in children if n.status == "done")
            failed = sum(1 for n in children if n.status == "failed")
            total = len(children)
            p = self.palette
            if failed:
                return (
                    f"[{p.warn}]swarm · {done}/{total} ok · "
                    f"[{p.error}]{failed} failed[/][/]"
                )
            return f"[{p.ok}]swarm · {done}/{total} sub-agents complete[/]"

    def reset(self) -> None:
        """Clear tree state (e.g. between turns or sessions)."""
        with self._lock:
            self._tree = SubagentTree(
                root_id=self._root_id,
                root_label=self._root_label,
            )
            self._active = False