"""End-to-end web flows for newly-wired interactive features.

Covers:
- Mint capability (form POST) → cap appears in list with sha256-prefixed key style URI.
- Revoke capability (form POST) → cap disappears.
- Import genome (paste JSON) → genome shows up on /personal with proper id/version/score.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from agentdrive.constants import get_agentdrive_home, get_default_drive_path
from agentdrive.web.app import create_app


def _make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "auth.db")
    return TestClient(app, follow_redirects=False)


def _login(client: TestClient) -> None:
    r = client.post("/setup", data={"username": "admin", "password": "admin password 123"})
    assert r.status_code == 303


def _clean_drives() -> None:
    """Clear local Drive + cap store between tests so we don't see prior state."""
    shutil.rmtree(get_default_drive_path(), ignore_errors=True)
    caps_db = get_agentdrive_home() / "caps.db"
    if caps_db.exists():
        caps_db.unlink()


def test_capabilities_mint_and_revoke(tmp_path: Path) -> None:
    _clean_drives()
    client = _make_client(tmp_path)
    _login(client)

    # Empty state.
    r = client.get("/capabilities")
    assert r.status_code == 200
    assert "No active capabilities" in r.text

    # Mint.
    r = client.post("/capabilities", data={"uri": "drive:read:swarm:demo"})
    assert r.status_code == 200
    assert "Minted capability" in r.text
    assert "drive:read:swarm:demo" in r.text

    # Confirm it shows up on a fresh fetch.
    r = client.get("/capabilities")
    assert r.status_code == 200
    assert "drive:read:swarm:demo" in r.text
    # cap_id is rendered as first 8 hex chars + ellipsis
    assert "Revoke" in r.text

    # Pull cap_id from the form action attribute.
    import re

    m = re.search(r"/capabilities/([a-f0-9-]{36})/revoke", r.text)
    assert m, "expected revoke form action with cap_id UUID"
    cap_id = m.group(1)

    # Revoke.
    r = client.post(f"/capabilities/{cap_id}/revoke")
    assert r.status_code == 200
    assert "Revoked" in r.text

    # Should be gone from the active list — check the cap_id (unique) no longer renders.
    r = client.get("/capabilities")
    assert cap_id not in r.text
    assert "No active capabilities" in r.text


def test_capabilities_reject_invalid_uri(tmp_path: Path) -> None:
    _clean_drives()
    client = _make_client(tmp_path)
    _login(client)

    r = client.post("/capabilities", data={"uri": "not a real cap uri"})
    assert r.status_code == 400
    assert "Invalid capability URI" in r.text


def test_personal_import_genome_flow(tmp_path: Path) -> None:
    _clean_drives()
    client = _make_client(tmp_path)
    _login(client)

    # Empty state.
    r = client.get("/personal")
    assert r.status_code == 200
    assert "No genomes yet" in r.text

    # Import via form post.
    payload = {
        "id": "recovery-playbook",
        "version": "0.1.0",
        "framework": {"steps": [{"id": "isolate", "name": "Isolate scope"}]},
        "authors": [{"type": "agent", "id": "agent:alpha", "name": "Alpha"}],
        "applicability": {"domains": ["sre"]},
        "evaluation_score": {"reference_tasks": 0.92},
    }
    r = client.post("/personal/import", data={"genome_json": json.dumps(payload)})
    assert r.status_code == 200
    assert "Imported genome" in r.text
    assert "recovery-playbook" in r.text

    # Page refresh — should still be there.
    r = client.get("/personal")
    assert r.status_code == 200
    assert "recovery-playbook" in r.text
    assert "0.1.0" in r.text
    assert "0.920" in r.text  # 3-decimal score formatted by the row builder
    assert "sha256:" in r.text


def test_personal_import_rejects_malformed_json(tmp_path: Path) -> None:
    _clean_drives()
    client = _make_client(tmp_path)
    _login(client)

    r = client.post("/personal/import", data={"genome_json": "{not json"})
    assert r.status_code == 400
    assert "Could not parse genome" in r.text


def test_swarms_spawn_flow(tmp_path: Path) -> None:
    """Spawning a swarm via the web form creates the Drive on disk."""
    _clean_drives()
    swarms_root = get_agentdrive_home() / "swarms"
    shutil.rmtree(swarms_root, ignore_errors=True)

    client = _make_client(tmp_path)
    _login(client)

    r = client.get("/swarms")
    assert r.status_code == 200
    assert "No swarm Drives yet" in r.text

    r = client.post("/swarms", data={"swarm_id": "test-swarm-001"})
    assert r.status_code == 200
    assert "Spawned swarm Drive: test-swarm-001" in r.text

    # Disk verification — the swarm dir actually exists now.
    assert (swarms_root / "test-swarm-001").exists()

    # And a fresh GET shows it in the list.
    r = client.get("/swarms")
    assert "test-swarm-001" in r.text

    # Invalid IDs are rejected.
    r = client.post("/swarms", data={"swarm_id": "bad/id with spaces"})
    assert r.status_code == 400
    assert "swarm_id must be" in r.text


def test_capabilities_requires_login(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    r = client.get("/capabilities")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"

    r = client.post("/capabilities", data={"uri": "drive:read:personal"})
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
