"""Live sub-agent tree (UX Pattern 4).

Data model + Rich renderer for a swarm of sub-agents emitting
``SubagentSpawn`` / ``SubagentTool`` / ``SubagentTokens`` / ``SubagentDone``
events on the Savant event bus.

This module is intentionally renderer-only. It does not subscribe to the
bus, does not own a ``rich.live.Live``, and never touches the chat surface.
Callers feed it events via :meth:`SubagentTree.apply` and render via
:meth:`SubagentTree.render` — both safe to call from any thread context as
long as the caller serializes access (the bus default dispatch is
synchronous, so a single subscriber callback satisfies this).

Visual convention is borrowed from ``board_view._mission_to_tree_row``:
palette-driven colors, ``Glyphs.RUNNING / CHECK / CROSS`` for status,
dim secondary text after the primary label.

Render format target (one node)::

    ├─ ⠴ ingest-1    bash(...)             8,420 tok · $0.18 · 12.7s

Spinner: ``rich.spinner.Spinner("dots", style=palette.accent)`` for
running nodes; static glyph for terminal nodes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from rich.console import Group
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
from rich.tree import Tree as RichTree

from agentdrive.events import (
    Event,
    SubagentDone,
    SubagentSpawn,
    SubagentTokens,
    SubagentTool,
)
from agentdrive.tui.chrome import Glyphs, Palette

# Terminal statuses — once a node reaches one of these, no further updates
# will change its glyph (tokens/cost can still accumulate from late events).
_TERMINAL = frozenset({"done", "failed"})

_QUEUED = "queued"
_RUNNING = "running"
_DONE = "done"
_FAILED = "failed"


@dataclass
class SubagentNode:
    """A single sub-agent in the live tree.

    Fields mirror the spec exactly. ``last_progress_ts`` uses
    ``time.monotonic()`` so callers can compare ages without worrying
    about wall-clock jumps.
    """

    subagent_id: str
    parent_id: str | None  # None for root
    label: str
    status: str  # "queued" | "running" | "done" | "failed"
    current_tool: str | None = None
    tokens: int = 0
    cost_usd: float = 0.0
    duration_s: float = 0.0
    last_progress_ts: float = field(default_factory=time.monotonic)

    @property
    def is_terminal(self) -> bool:
        return self.status in _TERMINAL


class SubagentTree:
    """Mutable tree of ``SubagentNode`` driven by event application."""

    def __init__(self, root_id: str, root_label: str) -> None:
        self._root_id = root_id
        root = SubagentNode(
            subagent_id=root_id,
            parent_id=None,
            label=root_label,
            status=_RUNNING,
        )
        self._nodes: dict[str, SubagentNode] = {root_id: root}
        # Parent -> insertion-ordered list of child ids.
        self._children: dict[str, list[str]] = {root_id: []}

    # ── public API ────────────────────────────────────────────────────

    @property
    def root_id(self) -> str:
        return self._root_id

    def get(self, subagent_id: str) -> SubagentNode | None:
        return self._nodes.get(subagent_id)

    def nodes(self) -> list[SubagentNode]:
        return list(self._nodes.values())

    def apply(self, event: Event) -> None:
        """Idempotently update the tree from a subagent event.

        Events that don't carry a ``subagent_id`` (or carry one that we've
        never seen, for non-Spawn events) are silently ignored — the tree
        only cares about its own swarm.
        """
        if isinstance(event, SubagentSpawn):
            self._apply_spawn(event)
            return

        sid = event.subagent_id
        if sid is None:
            return
        node = self._nodes.get(sid)
        if node is None:
            return

        if isinstance(event, SubagentTool):
            node.current_tool = event.tool or None
            if node.status == _QUEUED:
                node.status = _RUNNING
            node.last_progress_ts = time.monotonic()
            return

        if isinstance(event, SubagentTokens):
            node.tokens += int(event.tokens or 0)
            node.cost_usd += float(event.cost_usd or 0.0)
            if node.status == _QUEUED:
                node.status = _RUNNING
            node.last_progress_ts = time.monotonic()
            return

        if isinstance(event, SubagentDone):
            node.status = _DONE if event.ok else _FAILED
            node.duration_s = float(event.duration_s or node.duration_s)
            node.current_tool = None
            node.last_progress_ts = time.monotonic()
            return

    def is_done(self) -> bool:
        """True when every node is in a terminal status."""
        return all(n.is_terminal for n in self._nodes.values())

    def render(self, palette: Palette) -> RichTree:
        """Build a Rich ``Tree`` ready to print or hand to ``Live``."""
        root_node = self._nodes[self._root_id]
        root_renderable = self._render_node(root_node, palette, is_root=True)
        tree = RichTree(root_renderable, guide_style=palette.muted)
        self._attach_children(tree, self._root_id, palette)
        return tree

    # ── internals ─────────────────────────────────────────────────────

    def _apply_spawn(self, event: SubagentSpawn) -> None:
        sid = event.subagent_id
        if not sid:
            return
        if sid in self._nodes:
            # Idempotent: same spawn twice is a no-op. Don't reset status,
            # don't duplicate the child entry under the parent.
            return

        parent_id = event.parent_id or self._root_id
        if parent_id not in self._nodes:
            # Unknown parent — graft under root so we don't lose the node.
            parent_id = self._root_id

        node = SubagentNode(
            subagent_id=sid,
            parent_id=parent_id,
            label=event.label or sid,
            status=_QUEUED,
        )
        self._nodes[sid] = node
        self._children.setdefault(parent_id, []).append(sid)
        self._children.setdefault(sid, [])

    def _attach_children(self, rich_tree: RichTree, parent_id: str, palette: Palette) -> None:
        for child_id in self._children.get(parent_id, []):
            node = self._nodes[child_id]
            renderable = self._render_node(node, palette, is_root=False)
            branch = rich_tree.add(renderable)
            self._attach_children(branch, child_id, palette)

    @staticmethod
    def _status_glyph(node: SubagentNode, palette: Palette):
        """Return either a rich Spinner (running) or a styled Text glyph."""
        if node.status == _RUNNING:
            return Spinner("dots", style=palette.accent)
        if node.status == _DONE:
            return Text(Glyphs.CHECK, style=f"bold {palette.ok}")
        if node.status == _FAILED:
            return Text(Glyphs.CROSS, style=f"bold {palette.error}")
        # queued
        return Text("⏸", style=palette.muted)

    @classmethod
    def _render_node(cls, node: SubagentNode, palette: Palette, *, is_root: bool) -> Group:
        """Render one node as ``[glyph]  label   secondary    stats``.

        Built with a single-row ``rich.table.Table`` so the spinner cell
        re-animates inside ``Live`` while the static cells stay still.
        """
        # Label cell — bold primary + dim current tool/secondary.
        label_text = Text()
        label_text.append(node.label, style="bold")

        if node.current_tool and not node.is_terminal:
            label_text.append("  ")
            label_text.append(f"{node.current_tool}", style=palette.muted)

        # Stats cell (tokens · cost · duration) — only the parts we have.
        stats_parts: list[str] = []
        if node.tokens:
            stats_parts.append(f"{node.tokens:,} tok")
        if node.cost_usd:
            stats_parts.append(f"${node.cost_usd:.2f}")
        if node.duration_s:
            stats_parts.append(f"{node.duration_s:.1f}s")
        stats_text = Text(" · ".join(stats_parts), style=palette.muted)

        table = Table.grid(expand=False, padding=(0, 1))
        table.add_column(no_wrap=True)  # glyph / spinner
        table.add_column(no_wrap=True)  # label + secondary
        table.add_column(no_wrap=True, justify="right")  # stats
        table.add_row(cls._status_glyph(node, palette), label_text, stats_text)

        return Group(table)


__all__ = ["SubagentNode", "SubagentTree"]
