"""Capability enforcement for Mission Control mutating commands.

Read-only observation commands (get_state, replay_events, ping, etc.) never
require a cap. Mutating commands (start_static_fire, parent_decision, pause,
inject, etc.) require a valid ``mission:command:control:<name>`` capability
when ``mission_cap_required()`` is true.

Enforcement is opt-in on localhost (default bind 127.0.0.1) and mandatory
when the MC daemon is exposed on a non-loopback host, when
``mission_control.require_cap`` is set in config, or when
``AGENTDRIVE_MC_REQUIRE_CAP=1``.
"""

from __future__ import annotations

import os

from agentdrive.cap import Capability, CapInvalidError, CapStore, InsufficientCapability
from agentdrive.cap.store import CapVerifyContext, get_default_cap_store
from agentdrive.config import get_config_value

READ_ONLY_MISSION_COMMANDS: frozenset[str] = frozenset(
    {
        "request_briefing",
        "get_parent_actionable_briefing",
        "get_state",
        "get_loop_state",
        "get_fabric",
        "get_metacognitive_briefing",
        "get_overseer_briefing",
        "list_recent_fires",
        "recent_fires",
        "compare_fires",
        "compare_static_fires",
        "replay_events",
        "ping",
        "heartbeat",
        "pong",
        "get_council_activity",
        "council_activity",
    }
)

MUTATING_MISSION_COMMANDS: frozenset[str] = frozenset(
    {
        "trigger_densification",
        "trigger_graph_densification",
        "parent_decision",
        "record_parent_decision",
        "start_static_fire",
        "suggest_connection_improvements",
        "suggest_weak_links",
        "overseer_force_hunch",
        "trigger_overseer_hunch",
        "pause_evolution_context",
        "pause_evolution",
        "resume_evolution_context",
        "resume_evolution",
        "inject_custom_observation",
        "inject_observation",
        "emit_test_fabric_lift",
        "test_fabric_lift",
        "review_code_action",
        "approve_code_action",
        "override_code_action",
        "review_inhabitant_code_action",
    }
)

_LOCALHOST_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class MissionCapDenied(Exception):
    """Raised when a mutating MC command lacks a valid capability."""


def mission_cap_required(host: str | None = None) -> bool:
    """Return True when MC mutating commands must present a capability."""
    if get_config_value("mission_control.require_cap", False):
        return True
    if os.environ.get("AGENTDRIVE_MC_REQUIRE_CAP", "").strip() in {"1", "true", "yes"}:
        return True
    if host is not None and host not in _LOCALHOST_HOSTS:
        return True
    return False


def verify_mission_command(
    cap_id: str | None,
    command: str,
    *,
    operator_bypass: bool = False,
    host: str | None = None,
) -> None:
    """Verify ``cap_id`` authorizes ``command`` when enforcement is active."""
    if operator_bypass:
        return
    if command in READ_ONLY_MISSION_COMMANDS:
        return
    if not mission_cap_required(host):
        return
    if not cap_id:
        raise MissionCapDenied(f"cap required for mutating mission command {command!r}")

    store = get_default_cap_store()
    try:
        signed = store.get(cap_id)
        ctx = CapVerifyContext(
            scheme="mission",
            action="command",
            resource_kind="control",
            resource_id=command,
        )
        store.verify_request(signed, ctx)
    except (CapInvalidError, InsufficientCapability) as exc:
        raise MissionCapDenied(str(exc)) from exc


def mint_mission_control_cap(
    issuer: str = "operator",
    command: str = "*",
    *,
    store: CapStore | None = None,
) -> str:
    """Mint a Mission Control command capability and return its ``cap_id``."""
    cap_store = store or get_default_cap_store()
    signed = cap_store.mint(
        issuer=issuer,
        capability=Capability(
            scheme="mission",
            action="command",
            resource_kind="control",
            resource_id=command,
        ),
    )
    return signed.cap_id