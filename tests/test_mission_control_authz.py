"""Mission Control capability enforcement tests."""

from __future__ import annotations

import pytest

from agentdrive.mission_control.authz import (
    MissionCapDenied,
    mint_mission_control_cap,
    verify_mission_command,
)
from agentdrive.mission_control.server import MissionControlHub


def _force_cap_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "agentdrive.mission_control.authz.mission_cap_required",
        lambda host=None: True,
    )


def test_read_only_commands_pass_without_cap_when_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _force_cap_required(monkeypatch)
    for command in ("get_state", "replay_events", "request_briefing", "ping"):
        verify_mission_command(None, command)


def test_mutating_command_denied_without_cap_when_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _force_cap_required(monkeypatch)
    with pytest.raises(MissionCapDenied, match="cap required"):
        verify_mission_command(None, "start_static_fire")


def test_minted_cap_allows_mutating_command(
    monkeypatch: pytest.MonkeyPatch,
    isolated_agentdrive_home,
) -> None:
    _force_cap_required(monkeypatch)
    cap_id = mint_mission_control_cap(command="*")
    verify_mission_command(cap_id, "start_static_fire")
    verify_mission_command(cap_id, "parent_decision")


def test_dispatch_command_denies_mutating_without_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _force_cap_required(monkeypatch)
    hub = MissionControlHub()
    hub._current_mission = object()

    result = hub.dispatch_command("start_static_fire", duration_seconds=1.0)
    assert result["error"] == "cap_denied"


def test_dispatch_command_allows_mutating_with_minted_cap(
    monkeypatch: pytest.MonkeyPatch,
    isolated_agentdrive_home,
) -> None:
    _force_cap_required(monkeypatch)
    cap_id = mint_mission_control_cap(command="start_static_fire")
    hub = MissionControlHub()
    hub._current_mission = object()

    result = hub.dispatch_command(
        "start_static_fire",
        duration_seconds=1.0,
        cap_id=cap_id,
    )
    assert result.get("error") != "cap_denied"


def test_dispatch_command_operator_bypass_for_smoke(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _force_cap_required(monkeypatch)
    hub = MissionControlHub()
    hub._current_mission = object()

    result = hub.dispatch_command(
        "start_static_fire",
        duration_seconds=1.0,
        operator_bypass=True,
    )
    assert result.get("error") != "cap_denied"
