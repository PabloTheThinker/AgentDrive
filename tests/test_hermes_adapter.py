from __future__ import annotations

import os
from pathlib import Path

import pytest

from agentdrive.adapters import activate_for_hermes, get_agentdrive_adapter
from agentdrive.adapters.hermes_adapter import HermesAgentDriveAdapter


@pytest.mark.parametrize("name", ["hermes", "nous", "ilo"])
def test_factory_returns_hermes_adapter(name: str) -> None:
    adapter = get_agentdrive_adapter(name)
    assert isinstance(adapter, HermesAgentDriveAdapter)
    assert adapter.get_name() == "hermes"


def test_activate_for_current_session_sets_swarm_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "ad-home"
    home.mkdir()
    monkeypatch.delenv("AGENTDRIVE_SWARM_ID", raising=False)
    monkeypatch.setenv("AGENTDRIVE_HOME", str(home))

    adapter = HermesAgentDriveAdapter()
    adapter.activate_for_current_session(swarm_id="hermes-test-swarm")

    assert os.environ["AGENTDRIVE_SWARM_ID"] == "hermes-test-swarm"
    assert os.environ["AGENTDRIVE_HOME"] == str(home)


def test_activate_sets_home_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTDRIVE_HOME", raising=False)
    monkeypatch.delenv("AGENTDRIVE_SWARM_ID", raising=False)

    adapter = HermesAgentDriveAdapter()
    adapter.activate_for_current_session(swarm_id="test-swarm")

    assert os.environ["AGENTDRIVE_SWARM_ID"] == "test-swarm"
    assert os.environ.get("AGENTDRIVE_HOME")


def test_activate_swarm_id_setdefault_preserves_existing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTDRIVE_SWARM_ID", "existing-swarm")

    adapter = HermesAgentDriveAdapter()
    adapter.activate_for_current_session(swarm_id="new-swarm")

    assert os.environ["AGENTDRIVE_SWARM_ID"] == "existing-swarm"


def test_activate_for_hermes_returns_activated_adapter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "ad-home"
    home.mkdir()
    monkeypatch.setenv("AGENTDRIVE_HOME", str(home))
    monkeypatch.delenv("AGENTDRIVE_SWARM_ID", raising=False)

    adapter = activate_for_hermes(swarm_id="mission-1")

    assert isinstance(adapter, HermesAgentDriveAdapter)
    assert os.environ["AGENTDRIVE_SWARM_ID"] == "mission-1"
    assert "agentdrive experience context-pack" in capsys.readouterr().out


def test_health_after_activation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = tmp_path / "ad-home"
    home.mkdir()
    monkeypatch.setenv("AGENTDRIVE_HOME", str(home))

    adapter = get_agentdrive_adapter("hermes")
    adapter.activate_for_current_session(swarm_id="health-check")
    assert adapter.health() is True
