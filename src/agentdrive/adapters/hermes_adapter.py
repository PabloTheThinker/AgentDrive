"""
Hermes Agent Drive Adapter — thin activation for Hermes / Nous / ILO agent chassis.

Hermes is the runtime many Nous and ILO agents actually run on. This adapter wires
that chassis into AgentDrive without reimplementing the capability funnel:

    Observe/Decide → Experience Graph → Growth Merge → Memory Bank → Skills → Genomes

Concept map (Hermes ↔ AgentDrive — documentation only, no runtime translation):

- Hermes **skills** → AgentDrive procedures / learned playbooks
- Hermes **hot memory** → AgentDrive Memory Bank facts
- AgentDrive **Experience Graph** → decision *shape* (structural reasoning traces)

How the user instructs a Hermes agent (copy-paste this exact text to the model):

================================================================================
Participate in AgentDrive for this mission. At session start execute:

    from agentdrive.adapters.hermes_adapter import HermesAgentDriveAdapter
    adapter = HermesAgentDriveAdapter()
    adapter.activate_for_current_session(swarm_id="task-2026-09-14-my-mission")

If MCP is connected, your first tool call is always agentdrive_mcp_catalog().

Before similar work, pull structural context:
    agentdrive experience context-pack
    # or: agentdrive think

After material sittings (decisions, completed work), record reasoning shape:
    agentdrive experience record --summary "why we chose this approach"

Confirm by calling adapter.health().
================================================================================
"""

from __future__ import annotations

import logging
import os
from typing import Any

from agentdrive.adapters.base import AgentDriveAdapterBase
from agentdrive.constants import get_agentdrive_home

logger = logging.getLogger(__name__)


def get_agentdrive_instructions_for_hermes(swarm_id: str = "current-mission") -> str:
    """Return copy-paste instruction text for Hermes / Nous / ILO agents."""
    return f"""
Use AgentDrive for all work in this mission (swarm id: {swarm_id}).

Activation (execute immediately):

from agentdrive.adapters.hermes_adapter import HermesAgentDriveAdapter
adapter = HermesAgentDriveAdapter()
adapter.activate_for_current_session(swarm_id="{swarm_id}")

If MCP is connected, call agentdrive_mcp_catalog() first.

Before similar work:
    agentdrive experience context-pack
    # or: agentdrive think

After material sittings:
    agentdrive experience record --summary "..."

Confirm with adapter.health().
""".strip()


class HermesAgentDriveAdapter(AgentDriveAdapterBase):
    """Thin adapter for Hermes-style agent runtimes (Nous / ILO chassis).

    Sets AGENTDRIVE_SWARM_ID and AGENTDRIVE_HOME when unset so CLI and MCP
    share the same scoped Drive as in-process Python calls.
    """

    def __init__(self, swarm_id: str | None = None, **kwargs: Any):
        super().__init__(name="hermes", default_swarm_id=swarm_id, **kwargs)
        self._swarm_id = swarm_id

    def get_name(self) -> str:
        return "hermes"

    def activate(self, swarm_id: str | None = None, **options: Any) -> None:
        if swarm_id:
            self._swarm_id = swarm_id
        if options.get("subagent_id"):
            os.environ.setdefault("AGENTDRIVE_SUBAGENT_ID", options["subagent_id"])
            self._default_sub = options["subagent_id"]
        if self._swarm_id:
            os.environ.setdefault("AGENTDRIVE_SWARM_ID", self._swarm_id)
            self._default_swarm = self._swarm_id
        os.environ.setdefault("AGENTDRIVE_HOME", str(get_agentdrive_home()))

        self._activated = True
        logger.info("HermesAgentDriveAdapter activated (swarm=%s)", self._swarm_id)

    def activate_for_current_session(self, swarm_id: str, **options: Any) -> None:
        """Convenient alias used in the copy-paste instructions."""
        self.activate(swarm_id=swarm_id, **options)

    def health(self) -> bool:
        return super().health()


__all__ = [
    "HermesAgentDriveAdapter",
    "get_agentdrive_instructions_for_hermes",
]
