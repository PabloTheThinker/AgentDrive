"""Capability enforcement on mutating routes.

Three principals to cover:
- **Anonymous** (no session, no Bearer) → must be DENIED.
- **Admin session** (cookie) → implicit owner cap; existing tests still cover this.
- **Bearer cap** → must verify against the route's required scope; allow on match,
  deny on mismatch.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agentdrive.constants import get_agentdrive_home
from agentdrive.web.app import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path / "auth.db"), follow_redirects=False)


def _admin_login(client: TestClient) -> None:
    r = client.post("/setup", data={"username": "admin", "password": "admin password 123"})
    assert r.status_code == 303


def _clean_caps_db() -> Path:
    caps = get_agentdrive_home() / "caps.db"
    if caps.exists():
        caps.unlink()
    # WAL sidecars
    for ext in ("-wal", "-shm"):
        side = caps.with_name(caps.name + ext)
        if side.exists():
            side.unlink()
    return caps


# ── deny by default ───────────────────────────────────────────────────


def test_anonymous_mutations_are_denied(tmp_path: Path) -> None:
    """No session + no Bearer = 401 on every mutating route."""
    _clean_caps_db()
    client = _client(tmp_path)
    # We still need an admin user to exist so that the setup wizard isn't
    # the only path; create one then drop the cookie.
    _admin_login(client)
    client.cookies.clear()

    routes_and_data = [
        ("/personal/import", {"genome_json": "{}"}),
        ("/capabilities", {"uri": "drive:read:agent:personal"}),
        ("/swarms", {"swarm_id": "anon-test"}),
        ("/snapshots", {"agent_id": "personal"}),
        ("/dna/grants", {"issuer": "a", "grantee": "b"}),
        ("/peers", {"name": "anon-peer", "address": "x"}),
    ]
    for path, data in routes_and_data:
        r = client.post(path, data=data)
        # 401 (cap required) or 303 (legacy require_user redirect) are both correct rejections.
        assert r.status_code in (401, 303), f"{path}: expected reject, got {r.status_code}"


# ── bearer cap happy + sad paths ──────────────────────────────────────


def test_bearer_cap_allows_when_scope_matches(tmp_path: Path) -> None:
    _clean_caps_db()
    client = _client(tmp_path)
    _admin_login(client)

    # Mint a cap that covers drive:write:agent:personal via the admin session.
    r = client.post("/capabilities", data={"uri": "drive:write:agent:personal"})
    assert r.status_code == 200, r.text

    # Pull the cap_id straight out of the response.
    import re

    m = re.search(r"/capabilities/([a-f0-9-]{36})/revoke", r.text)
    assert m, "expected to find the new cap_id rendered in the page"
    cap_id = m.group(1)

    # Now ditch the session and replay the import as a non-browser caller.
    client.cookies.clear()
    r = client.post(
        "/personal/import",
        data={"genome_json": "{not-json"},
        headers={"Authorization": f"Bearer {cap_id}"},
    )
    # Cap should have authorized us through — we should reach the route
    # body and get a 400 for the malformed JSON, NOT a 401.
    assert r.status_code == 400, r.text
    assert "parse genome" in r.text.lower() or "could not parse" in r.text.lower()


def test_bearer_cap_denies_when_scope_too_narrow(tmp_path: Path) -> None:
    """A read-only cap should not authorize a write."""
    _clean_caps_db()
    client = _client(tmp_path)
    _admin_login(client)

    # Mint a read-only cap.
    r = client.post("/capabilities", data={"uri": "drive:read:agent:personal"})
    assert r.status_code == 200, r.text
    import re

    cap_id = re.search(r"/capabilities/([a-f0-9-]{36})/revoke", r.text).group(1)

    client.cookies.clear()
    r = client.post(
        "/personal/import",
        data={"genome_json": "{}"},
        headers={"Authorization": f"Bearer {cap_id}"},
    )
    assert r.status_code == 403
    assert "cap_denied" in r.text or "denied" in r.text.lower()


def test_bearer_cap_denies_on_unknown_id(tmp_path: Path) -> None:
    _clean_caps_db()
    client = _client(tmp_path)
    _admin_login(client)
    client.cookies.clear()

    r = client.post(
        "/swarms",
        data={"swarm_id": "ghost-test"},
        headers={"Authorization": "Bearer 00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 403


# ── audit log ─────────────────────────────────────────────────────────


def test_audit_log_records_allow_and_deny(tmp_path: Path) -> None:
    audit_path = get_agentdrive_home() / "audit.log"
    if audit_path.exists():
        audit_path.unlink()

    _clean_caps_db()
    client = _client(tmp_path)
    _admin_login(client)

    # Admin allow path.
    r = client.post("/swarms", data={"swarm_id": "audit-allow-test"})
    assert r.status_code == 200, r.text

    # Bearer deny path (unknown cap).
    client.cookies.clear()
    r = client.post(
        "/swarms",
        data={"swarm_id": "audit-deny-test"},
        headers={"Authorization": "Bearer not-a-real-cap-id"},
    )
    assert r.status_code == 403

    # Anonymous deny.
    r = client.post("/swarms", data={"swarm_id": "audit-anon-test"})
    assert r.status_code in (401, 303)

    # Audit log must contain at least an allow and a deny record.
    assert audit_path.exists(), "audit log was never written"
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    decisions = []
    for line in lines:
        import json as _json

        try:
            decisions.append(_json.loads(line)["decision"])
        except Exception:
            continue
    assert "allow" in decisions
    assert "deny" in decisions
