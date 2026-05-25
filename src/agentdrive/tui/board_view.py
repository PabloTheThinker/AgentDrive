"""
Mission Board renderer — chrome-styled lane view for the Savant Mission Board.

Two rendering modes:
- `render_board(board, palette, console)`  full-screen lane view (board command)
- `render_board_inline(board, palette, console, limit=8)` compact tree inline
  in chat (the /board slash command)
"""

from __future__ import annotations

from typing import Any

from rich.console import Console, Group
from rich.markup import escape as rich_escape
from rich.text import Text

from agentdrive.board.mission_board import Mission, MissionBoard, MissionStatus
from agentdrive.tui.chrome import (
    Glyphs,
    Palette,
    Section,
    Tree,
    TreeRow,
    info_line,
    section_panel,
)

_LANE_LABELS = {
    MissionStatus.PENDING: ("Pending", Glyphs.PENDING),
    MissionStatus.RUNNING: ("Running", Glyphs.RUNNING),
    MissionStatus.DONE: ("Done", Glyphs.CHECK),
    MissionStatus.FAILED: ("Failed", Glyphs.CROSS),
    MissionStatus.ARCHIVED: ("Archived", Glyphs.SKIPPED),
}


def _lane_color(palette: Palette, status: MissionStatus) -> str:
    return {
        MissionStatus.PENDING: palette.muted,
        MissionStatus.RUNNING: palette.accent,
        MissionStatus.DONE: palette.ok,
        MissionStatus.FAILED: palette.error,
        MissionStatus.ARCHIVED: palette.muted,
    }.get(status, palette.muted)


def _mission_to_tree_row(m: Mission, palette: Palette) -> TreeRow:
    p = palette
    # `[xxxxx]` would be parsed as rich markup; escape so it renders literally.
    id_tag = rich_escape(f"[{m.id[-5:]}]")
    label = f"[bold]{rich_escape(m.title)}[/]  [{p.muted}]{id_tag}[/]"

    secondary_parts: list[str] = []
    if m.genome_id:
        secondary_parts.append(f"genome [{p.genome}]{rich_escape(m.genome_id)}[/]")
    if m.swarm_id:
        scope = f"swarm:{m.swarm_id}"
        if m.subagent_id:
            scope += f"/{m.subagent_id}"
        secondary_parts.append(rich_escape(scope))
    if m.duration_s:
        secondary_parts.append(f"{m.duration_s:.1f}s")
    if m.outcome.get("error"):
        secondary_parts.append(f"[{p.error}]error[/]")
    secondary = "  · ".join(secondary_parts)

    children: list[TreeRow] = []
    if m.description:
        children.append(TreeRow(label=f"[dim]{rich_escape(m.description[:80])}[/]"))
    if m.dna_used:
        dna_preview = ", ".join(rich_escape(d) for d in m.dna_used[:3])
        more = f" (+{len(m.dna_used) - 3})" if len(m.dna_used) > 3 else ""
        children.append(TreeRow(label=f"[dim]dna:[/] {dna_preview}{more}"))

    return TreeRow(label=label, secondary=secondary, children=children)


def render_board(board: MissionBoard, palette: Palette, console: Console) -> None:
    """Full board view: every lane rendered as its own Section with its missions."""
    p = palette
    lanes = board.lanes()
    stats = board.stats()

    summary_rows = [
        ("pending", f"[{p.muted}]{stats['pending']}[/]"),
        ("running", f"[bold {p.accent}]{stats['running']}[/]"),
        ("done", f"[bold {p.ok}]{stats['done']}[/]"),
        (
            "failed",
            f"[bold {p.error}]{stats['failed']}[/]" if stats["failed"] else f"[{p.muted}]0[/]",
        ),
        ("archived", f"[{p.muted}]{stats['archived']}[/]"),
        ("avg time", f"{stats['avg_duration_s']:.1f}s" if stats["avg_duration_s"] else "—"),
    ]

    sections: list[Any] = [Section("Lanes", summary_rows, palette=p, key_width=10)]

    for status in MissionStatus.lanes():
        missions = lanes.get(status, [])
        if not missions:
            continue
        label_text, glyph = _LANE_LABELS[status]
        color = _lane_color(p, status)

        # Custom heading + tree (lane heading uses lane-specific color)
        head = Text()
        head.append(f"{Glyphs.EXPANDED} ", style=p.accent)
        head.append(f"{label_text}", style=f"bold {color}")
        head.append(f"  ({len(missions)})", style=p.muted)

        rows = [_mission_to_tree_row(m, p) for m in missions[:10]]
        if len(missions) > 10:
            rows.append(TreeRow(label=f"[dim]+ {len(missions) - 10} more[/]"))

        sections.append(Group(head, Tree(rows, palette=p)))

    console.print()
    console.print(
        section_panel(
            *sections,
            title=f"{Glyphs.DIAMOND} Savant Mission Board",
            palette=p,
        )
    )


def render_board_inline(
    board: MissionBoard,
    palette: Palette,
    console: Console,
    limit: int = 8,
) -> None:
    """Compact inline view of the most recent missions across all lanes.
    Intended for `/board` in chat — show without breaking the flow."""
    p = palette
    recent = board.recent(limit=limit)
    if not recent:
        console.print()
        console.print(
            info_line(
                f"Board is empty. Missions get created when you [{p.accent}]run[/] a genome or [{p.accent}]/scan[/].",
                palette=p,
            )
        )
        return

    rows: list[TreeRow] = []
    for m in recent:
        lane_label, glyph = _LANE_LABELS[m.status]
        lane_color = _lane_color(p, m.status)
        id_tag = rich_escape(f"[{m.id[-5:]}]")

        label = (
            f"[bold {lane_color}]{glyph}[/]  "
            f"[bold]{rich_escape(m.title)}[/]  "
            f"[{p.muted}]{id_tag}[/]"
        )

        secondary_parts: list[str] = [f"[{lane_color}]{lane_label.lower()}[/]"]
        if m.genome_id:
            secondary_parts.append(f"genome [{p.genome}]{rich_escape(m.genome_id)}[/]")
        if m.duration_s:
            secondary_parts.append(f"{m.duration_s:.1f}s")
        if m.outcome.get("error"):
            secondary_parts.append(f"[{p.error}]error[/]")
        secondary = "  · ".join(secondary_parts)

        rows.append(TreeRow(label=label, secondary=secondary))

    stats = board.stats()
    head_parts = [
        f"[{p.accent}]{Glyphs.DIAMOND}[/] [bold {p.accent}]Mission Board[/]",
        f"[{p.muted}]{stats['pending']} pending · {stats['running']} running · {stats['done']} done[/]",
    ]
    if stats["failed"]:
        head_parts.append(f"[{p.error}]{stats['failed']} failed[/]")
    head = Text.from_markup("  ·  ".join(head_parts))

    console.print()
    console.print(
        section_panel(
            Group(head, Text(""), Tree(rows, palette=p)),
            palette=p,
        )
    )
