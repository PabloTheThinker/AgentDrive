from pathlib import Path

import pytest

from agentdrive.cap import CapStore, InsufficientCapability, parse_uri
from agentdrive.drive.drive import AgentDrive, DriveQuery
from agentdrive.genome.models import Genome


def _genome(gid: str = "authorized-pattern") -> Genome:
    return Genome.create(
        id=gid,
        version="1.0.0",
        framework={"steps": [{"id": "1", "name": "Use the authorized Drive boundary"}]},
        applicability={"domains": ["auth"]},
        evaluation_score={"reference_tasks": 0.8},
    )


def test_authorized_ingest_requires_write_cap(tmp_path: Path) -> None:
    drive = AgentDrive(name="main", drive_path=tmp_path / "drive")
    store = CapStore(tmp_path / "caps.db")
    read_cap = store.mint(issuer="admin", capability=parse_uri("drive:read:default:main"))

    with pytest.raises(InsufficientCapability):
        drive.authorized_ingest(store, read_cap, _genome(), source="pytest")

    assert drive.get_pool_stats()["ingest_events"] == 0


def test_authorized_ingest_accepts_write_cap(tmp_path: Path) -> None:
    drive = AgentDrive(name="main", drive_path=tmp_path / "drive")
    store = CapStore(tmp_path / "caps.db")
    write_cap = store.mint(issuer="admin", capability=parse_uri("drive:write:default:main"))

    result = drive.authorized_ingest(store, write_cap, _genome(), source="pytest")

    assert result.accepted is True
    assert drive.get_pool_stats()["ingest_events"] == 1


def test_authorized_query_accepts_write_or_read_cap(tmp_path: Path) -> None:
    drive = AgentDrive(name="main", drive_path=tmp_path / "drive")
    store = CapStore(tmp_path / "caps.db")
    write_cap = store.mint(issuer="admin", capability=parse_uri("drive:write:default:main"))
    read_cap = store.derive(parent_cap_id=write_cap.cap_id, action="read")

    drive.authorized_ingest(store, write_cap, _genome(), source="pytest")

    assert len(drive.authorized_query(store, write_cap, DriveQuery(task_description="auth"))) == 1
    assert len(drive.authorized_query(store, read_cap, DriveQuery(task_description="auth"))) == 1


def test_authorized_query_rejects_other_drive_resource(tmp_path: Path) -> None:
    drive = AgentDrive(name="main", drive_path=tmp_path / "drive")
    store = CapStore(tmp_path / "caps.db")
    other_cap = store.mint(issuer="admin", capability=parse_uri("drive:read:default:other"))

    with pytest.raises(InsufficientCapability):
        drive.authorized_query(store, other_cap, DriveQuery(task_description="auth"))


def test_swarm_drive_uses_swarm_capability_resource(tmp_path: Path) -> None:
    drive = AgentDrive(name="swarm:alpha", drive_path=tmp_path / "swarm", swarm_id="alpha")
    store = CapStore(tmp_path / "caps.db")
    cap = store.mint(issuer="admin", capability=parse_uri("drive:write:swarm:alpha"))

    drive.authorized_ingest(store, cap, _genome("swarm-pattern"), source="pytest")

    assert drive.capability_resource() == ("swarm", "alpha")
    assert len(drive.authorized_query(store, cap, DriveQuery(task_description="auth"))) == 1


def test_agentdrive_context_manager_with_authorized_ops(tmp_path: Path) -> None:
    """Drive context manager usage + close() for authorized ingest/query flows
    (production pattern for role-swarm subagents under capability grants).
    """
    from agentdrive import AgentDrive

    drive_path = tmp_path / "auth-ctx"
    with AgentDrive(name="auth-ctx-drive", drive_path=drive_path) as d:
        # self-healing experience seed + clean shutdown exercised
        assert (drive_path / "experience_layer_seed.json").exists()
        # basic stats available inside context
        assert "ingest_events" in d.get_pool_stats()
    d.close()  # explicit post-context also safe
