"""
Render representative Savant TUI frames to SVG for the README.

Uses real Savant render code paths (chrome, board_view) against a synthetic
in-memory MissionBoard so the screenshots match production exactly.

Outputs:
- docs/assets/mission-board.svg
- docs/assets/welcome.svg
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Isolate AGENTDRIVE_HOME so we never touch the real one.
_tmp = tempfile.mkdtemp(prefix="savant-screenshot-")
os.environ["AGENTDRIVE_HOME"] = _tmp

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from rich.align import Align  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402
from rich.text import Text  # noqa: E402

from agentdrive.board.mission_board import Mission, MissionBoard, MissionStatus  # noqa: E402
from agentdrive.tui.board_view import render_board  # noqa: E402
from agentdrive.tui.chrome import Palette  # noqa: E402

ASSETS = REPO / "docs" / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

PALETTE = Palette()


def _seed_board() -> MissionBoard:
    board = MissionBoard()

    def add(title, status, **kw):
        m = Mission.create(title, **kw)
        m.status = status
        board.add(m)

    add("Ingest payments-2025-Q4 audit corpus", MissionStatus.DONE,
        genome_id="security-incident-postmortem-1.0.0",
        swarm_id="payments-review",
        subagent_id="ingest-1",
        duration_s=42.7)
    add("Cross-reference vendor SOC2 evidence", MissionStatus.DONE,
        genome_id="evidence-trace-0.3.1",
        swarm_id="payments-review",
        subagent_id="trace-2",
        duration_s=18.4)
    add("Score risk against control catalog v3", MissionStatus.RUNNING,
        genome_id="risk-scorer-1.2.0",
        swarm_id="payments-review",
        subagent_id="scorer-1",
        duration_s=6.1)
    add("Draft incident remediation playbook", MissionStatus.RUNNING,
        genome_id="postmortem-author-0.9.0",
        swarm_id="payments-review",
        subagent_id="author-1",
        duration_s=3.0)
    add("Notify on-call rotation via Slack", MissionStatus.PENDING,
        swarm_id="payments-review")
    add("Generate exec-summary for CFO review", MissionStatus.PENDING,
        swarm_id="payments-review")
    add("Vector embed of FY24 audit deltas", MissionStatus.FAILED,
        genome_id="embed-bulk-0.5.0",
        swarm_id="payments-review",
        subagent_id="embed-3",
        duration_s=12.0,
        outcome={"error": "rate-limited by upstream provider"})
    add("Q3 vendor risk baseline (archived)", MissionStatus.ARCHIVED,
        swarm_id="payments-review-q3",
        duration_s=128.0)

    return board


def render_mission_board():
    console = Console(record=True, width=140, force_terminal=True, color_system="truecolor")
    board = _seed_board()
    render_board(board, PALETTE, console)
    out = ASSETS / "mission-board.svg"
    console.save_svg(
        str(out),
        title="savant board",
        code_format=(
            '<svg class="rich-terminal" viewBox="0 0 {width} {height}" '
            'xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">'
            '<style>{styles}</style>{chrome}{backgrounds}<g transform="translate(9, 41)" clip-path="url(#terminal-clip)">{matrix}</g></svg>'
        ),
    )
    print(f"[OK] {out}")


def render_welcome():
    """Render the welcome / what-it-is frame.

    A clean Savant intro card built with the same Rich primitives the TUI uses.
    """
    console = Console(record=True, width=120, force_terminal=True, color_system="truecolor")

    p = PALETTE

    title = Text()
    title.append("Savant", style=f"bold {p.accent}")
    title.append("  Living DNA for AI agents", style=f"{p.muted}")

    body = Text()
    body.append("Every agent, every sub-agent — its own private DNA pool.\n", style=f"{p.text}")
    body.append("Pools start empty. They grow with proven frameworks,\n", style=f"{p.muted}")
    body.append("reasoning patterns, and outcomes from real work.\n\n", style=f"{p.muted}")
    body.append("You own all of it.\n", style=f"bold {p.text}")

    panel = Panel(
        Align.center(body, vertical="middle"),
        title=title,
        title_align="left",
        border_style=p.accent,
        padding=(2, 4),
        width=100,
    )

    stats = Table.grid(padding=(0, 4))
    stats.add_column(justify="right", style=p.muted)
    stats.add_column(style=f"bold {p.text}")
    stats.add_row("genomes loaded", "47")
    stats.add_row("active swarms", "3")
    stats.add_row("sub-agent pools", "12")
    stats.add_row("runs ingested (24h)", "1,284")

    footer = Panel(
        Align.center(stats),
        border_style=p.muted,
        padding=(1, 2),
        width=100,
        title="pool status",
        title_align="left",
    )

    console.print()
    console.print(Align.center(panel))
    console.print()
    console.print(Align.center(footer))
    console.print()

    out = ASSETS / "welcome.svg"
    console.save_svg(str(out), title="savant")
    print(f"[OK] {out}")


if __name__ == "__main__":
    render_mission_board()
    render_welcome()
