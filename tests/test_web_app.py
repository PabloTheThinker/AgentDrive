from pathlib import Path

from fastapi.testclient import TestClient

from agentdrive.drive.drive import AgentDrive
from agentdrive.genome.models import Genome
from agentdrive.web.app import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "auth.db")
    return TestClient(app, follow_redirects=False)


def login(client: TestClient) -> None:
    response = client.post(
        "/setup",
        data={"username": "admin", "password": "admin password 123"},
    )
    assert response.status_code == 303


def seed_genome() -> str:
    genome = Genome.create(
        id="incident-response",
        version="1.0.0",
        framework={"steps": [{"id": "triage", "name": "Triage incident"}]},
        authors=[{"type": "agent", "id": "agent:alpha", "name": "Alpha"}],
        applicability={"domains": ["security"]},
        evaluation_score={"reference_tasks": 0.87},
    )
    drive = AgentDrive()
    result = drive.ingest(
        genome,
        source="web-test",
        actor="agent-alpha",
        subagent_id="worker-1",
    )
    return result.genome_id


def test_personal_requires_login(tmp_path: Path):
    client = make_client(tmp_path)
    response = client.get("/personal")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_personal_lists_agentdrive_genomes(tmp_path: Path):
    seed_genome()
    client = make_client(tmp_path)
    login(client)

    response = client.get("/personal")

    assert response.status_code == 200
    assert "incident-response" in response.text
    assert "1.0.0" in response.text
    assert "0.870" in response.text
    assert "web-test / agent-alpha / sub:worker-1" in response.text
    assert "sha256:" in response.text


def test_snapshots_require_login_for_reads_and_writes(tmp_path: Path):
    client = make_client(tmp_path)

    response = client.get("/snapshots")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

    response = client.post("/snapshots", data={"agent_id": "personal"})
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_snapshots_create_pin_restore_and_delete(tmp_path: Path):
    seed_genome()
    client = make_client(tmp_path)
    login(client)

    response = client.get("/snapshots")
    assert response.status_code == 200
    assert "No snapshots yet" in response.text

    response = client.post("/snapshots", data={"agent_id": "personal"})
    assert response.status_code == 303
    assert response.headers["location"].startswith("/snapshots?agent_id=personal")

    response = client.get("/snapshots?agent_id=personal")
    assert response.status_code == 200
    assert "web" in response.text
    assert "Restore hashes" in response.text
    snapshot_id = response.text.split("/personal/")[1].split("/restore", 1)[0]

    response = client.post(f"/snapshots/personal/{snapshot_id}/pin", data={"pinned": "true"})
    assert response.status_code == 303

    response = client.get("/snapshots?agent_id=personal")
    assert response.status_code == 200
    assert ">yes<" in response.text

    response = client.post(f"/snapshots/personal/{snapshot_id}/delete")
    assert response.status_code == 409
    assert "pinned" in response.text

    response = client.post(f"/snapshots/personal/{snapshot_id}/pin", data={"pinned": "false"})
    assert response.status_code == 303

    response = client.post(f"/snapshots/personal/{snapshot_id}/restore")
    assert response.status_code == 200
    assert "Restore hashes for" in response.text
    assert "sha256:" in response.text

    response = client.post(f"/snapshots/personal/{snapshot_id}/delete")
    assert response.status_code == 303

    response = client.get("/snapshots?agent_id=personal")
    assert response.status_code == 200
    assert "No snapshots yet" in response.text
