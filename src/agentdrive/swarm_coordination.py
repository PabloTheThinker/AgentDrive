"""
Swarm Coordination Layer (High-Continuity Conductor)

This is the central nervous system for AgentDrive role-swarm coordination.

Responsibilities:
- Allow role-swarm coordinators to discover each other's recent artifacts
- Provide shared context (progress, open tasks, cross-role dependencies)
- Help route work between specialized swarms
- Maintain the overall coordination roadmap as living genomes

All role-swarm participants should consult this.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime

from agentdrive import get_default_drive
from agentdrive.events import emit


@dataclass
class RoleSwarmStatus:
    swarm_id: str
    role: str
    last_active: str
    recent_deliverables: list[str] = field(default_factory=list)
    open_tasks: list[str] = field(default_factory=list)


class SwarmCoordinator:
    """
    Lightweight coordinator that role-swarms can use to stay synchronized.
    """

    def __init__(self, central_swarm_id: str = "agentdrive-coordinator"):
        self.central_swarm_id = central_swarm_id
        self.drive = get_default_drive()

    def report_status(
        self, role_swarm_id: str, role: str, deliverables: list[str], tasks: list[str]
    ):
        """A role-swarm calls this to publish its current state."""
        status = RoleSwarmStatus(
            swarm_id=role_swarm_id,
            role=role,
            last_active=datetime.now(UTC).isoformat(),
            recent_deliverables=deliverables,
            open_tasks=tasks,
        )
        emit(
            "role_swarm_status",
            {"swarm_id": role_swarm_id, "role": role, "status": status.__dict__},
        )
        print(f"[Coordinator] Recorded status from {role_swarm_id}")

    def get_team_status(self) -> list[RoleSwarmStatus]:
        """Read the latest known status from all role-swarms."""
        # In a real implementation this would query the drive events.
        # For now we return a static view that the sub-agents can update.
        return []

    def create_integration_proposal(self, title: str, description: str, related_roles: list[str]):
        """Conductor or any role can propose cross-role integration work."""
        emit(
            "integration_proposal",
            {
                "title": title,
                "description": description,
                "related_roles": related_roles,
                "proposed_by": os.environ.get("AGENTDRIVE_SUBAGENT_ID", "unknown"),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        print(f"[Coordinator] New integration proposal: {title}")


# Convenience for role-swarms
def get_coordinator() -> SwarmCoordinator:
    return SwarmCoordinator()
