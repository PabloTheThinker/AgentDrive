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


def test_dna_grant_issue_and_revoke(tmp_path: Path) -> None:
    """POST /dna/grants persists an Ed25519-signed grant in GrantStore;
    POST /dna/grants/{grant_id}/revoke marks it revoked.
    """
    _clean_drives()
    grants_db = get_agentdrive_home() / "grants.db"
    if grants_db.exists():
        grants_db.unlink()

    client = _make_client(tmp_path)
    _login(client)

    r = client.post(
        "/dna/grants",
        data={
            "issuer": "agent-7",
            "grantee": "agent-12",
            "min_eval": "0.7",
            "ttl_hours": "24",
        },
    )
    assert r.status_code == 303
    assert "grant-" in r.headers["location"]

    # Verify on-disk via the GrantStore API directly.
    from agentdrive.dna.grants import GrantStore

    gs = GrantStore(db_path=grants_db)
    with gs._conn() as c:  # noqa: SLF001
        rows = list(c.execute("SELECT grant_id, issuer, grantee FROM grants WHERE revoked = 0"))
    assert any(r[1] == "agent-7" and r[2] == "agent-12" for r in rows), rows
    grant_id = rows[0][0]

    r = client.post(f"/dna/grants/{grant_id}/revoke")
    assert r.status_code == 303


def test_dna_grant_pull_routes_through_quarantine(tmp_path: Path) -> None:
    """End-to-end: publish a Genome into agent-7's DNA Drive, issue a
    grant agent-7 → agent-12, then POST /dna/grants/{id}/pull. Every
    inherited Genome must land in the quarantine queue PENDING.
    """
    _clean_drives()
    grants_db = get_agentdrive_home() / "grants.db"
    if grants_db.exists():
        grants_db.unlink()
    quarantine_root = get_agentdrive_home() / "quarantine"
    shutil.rmtree(quarantine_root, ignore_errors=True)

    # Seed: write one payload into agent-7's DNA Drive content store.
    from agentdrive.constants import get_agentdrive_home as _home
    from agentdrive.drive.content_store import ContentStore

    issuer_root = _home() / "dna" / "agent-7" / "drive"
    issuer_root.mkdir(parents=True, exist_ok=True)
    cs = ContentStore(issuer_root)
    payload = {
        "id": "shared-pattern",
        "version": "0.1.0",
        "framework": {"steps": [{"id": "x", "name": "X"}]},
        "evaluations": {"reference": 0.91},
    }
    cs.put_payload(payload)

    client = _make_client(tmp_path)
    _login(client)

    # Issue the grant via the web.
    r = client.post(
        "/dna/grants",
        data={
            "issuer": "agent-7",
            "grantee": "agent-12",
            "min_eval": "0.5",
            "ttl_hours": "1",
        },
    )
    assert r.status_code == 303

    # Pull the grant_id.
    from agentdrive.dna.grants import GrantStore

    gs = GrantStore(db_path=grants_db)
    with gs._conn() as c:  # noqa: SLF001
        grant_id = list(c.execute("SELECT grant_id FROM grants WHERE revoked = 0"))[0][0]

    # Run the pull.
    r = client.post(f"/dna/grants/{grant_id}/pull")
    assert r.status_code == 303
    assert "pulled-" in r.headers["location"]
    assert "into-quarantine" in r.headers["location"]

    # Verify it landed in quarantine PENDING.
    from agentdrive.quarantine import QuarantineStatus, get_default_quarantine

    pending = get_default_quarantine().list(status=QuarantineStatus.PENDING)
    assert len(pending) >= 1
    assert any(e.source_peer.startswith("grant:agent-7") for e in pending)


def test_dna_grant_rejects_bad_ids(tmp_path: Path) -> None:
    _clean_drives()
    client = _make_client(tmp_path)
    _login(client)
    r = client.post("/dna/grants", data={"issuer": "../etc/passwd", "grantee": "agent-12"})
    assert r.status_code == 303
    assert "error=bad-agent-id" in r.headers["location"]


def test_peers_add_and_list(tmp_path: Path) -> None:
    """POST /peers calls PeerRegistry.add(), and the new peer renders on GET /peers."""
    _clean_drives()
    shutil.rmtree(get_agentdrive_home() / "peers", ignore_errors=True)

    client = _make_client(tmp_path)
    _login(client)

    r = client.post(
        "/peers",
        data={
            "name": "peer-omega",
            "address": "https://peer.example",
            "public_key": "ed25519:abc",
            "trust": "trusted",
        },
    )
    assert r.status_code == 303
    assert "info=added-peer-omega" in r.headers["location"]

    r = client.get("/peers?info=added-peer-omega")
    assert r.status_code == 200
    assert "peer-omega" in r.text


def test_peers_reject_bad_name_and_trust(tmp_path: Path) -> None:
    _clean_drives()
    client = _make_client(tmp_path)
    _login(client)

    r = client.post("/peers", data={"name": "bad/name", "address": "x", "trust": "trusted"})
    assert r.status_code == 303
    assert "error=bad-name" in r.headers["location"]

    r = client.post("/peers", data={"name": "ok-name", "address": "x", "trust": "owner"})
    assert r.status_code == 303
    assert "error=bad-trust-level" in r.headers["location"]


def test_quarantine_approve_handles_unknown_id_gracefully(tmp_path: Path) -> None:
    """No 500 / no traceback in the response — redirect to /peers with an error param."""
    _clean_drives()
    client = _make_client(tmp_path)
    _login(client)

    r = client.post("/peers/quarantine/no-such-id/approve")
    assert r.status_code == 303
    assert "error=unknown-quarantine-id" in r.headers["location"]


def test_capabilities_requires_login(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    r = client.get("/capabilities")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"

    r = client.post("/capabilities", data={"uri": "drive:read:personal"})
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
