"""
Savant Mission Board — a Savant-native kanban for mission lifecycles.

While other terminal agents track tasks as ephemeral inline todos, the Savant
board treats *missions* as first-class persistent artifacts. Each mission
card carries its genome lineage, outcome metrics, swarm scope, and pool
contributions, and flows through lanes that map directly onto how Savant
agents actually do work:

    Pending → Running → Done | Failed → Archived

Use cases:
- A user planning a multi-step run can stage missions as Pending cards.
- A live `savant run` pushes its mission card through Running → Done|Failed
  with outcome metadata captured straight from the harness.
- A swarm of sub-agents claim cards from Pending and report Done back to the
  shared board.

Persisted at `$AGENTDRIVE_HOME/board/missions.jsonl` — append-only, audit-friendly.
"""

from agentdrive.board.mission_board import (
    Mission,
    MissionBoard,
    MissionStatus,
    get_default_board,
)

__all__ = [
    "Mission",
    "MissionStatus",
    "MissionBoard",
    "get_default_board",
]
