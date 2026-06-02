"""Tests for the /onboarding wizard routes."""

from __future__ import annotations

import json
import stat
from pathlib import Path

from fastapi.testclient import TestClient

from agentdrive.web.app import create_app


def _make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "auth.db")
    return TestClient(app, follow_redirects=False)


def _login(client: TestClient) -> None:
    resp = client.post(
        "/setup",
        data={"username": "admin", "password": "admin password 123"},
    )
    assert resp.status_code == 303


def test_onboarding_get_redirects_unauthed(tmp_path: Path):
    client = _make_client(tmp_path)
    resp = client.get("/onboarding")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_onboarding_get_renders_for_authed(tmp_path: Path):
    client = _make_client(tmp_path)
    _login(client)
    resp = client.get("/onboarding")
    assert resp.status_code == 200
    assert "Agent Drive setup" in resp.text
    assert "1 · Welcome" in resp.text


def test_onboarding_step_clamped(tmp_path: Path):
    client = _make_client(tmp_path)
    _login(client)
    assert client.get("/onboarding?step=99").status_code == 200
    assert client.get("/onboarding?step=-1").status_code == 200


def test_onboarding_create_agent_writes_identity(
    tmp_path: Path,
    isolated_agentdrive_home: Path,
):
    client = _make_client(tmp_path)
    _login(client)
    resp = client.post(
        "/onboarding/agent",
        data={
            "agent_id": "high-continuity-conductor",
            "label": "High-Continuity Conductor",
            "identity": "You are a high-continuity Conductor node.",
        },
    )
    assert resp.status_code == 303
    assert resp.headers["location"].startswith(
        "/onboarding?step=3&agent_id=high-continuity-conductor"
    )

    identity_file = (
        isolated_agentdrive_home / "agents" / "high-continuity-conductor" / "identity.md"
    )
    assert identity_file.exists()
    body = identity_file.read_text(encoding="utf-8")
    assert "# High-Continuity Conductor" in body
    assert "You are a high-continuity Conductor node." in body


def test_onboarding_create_agent_rejects_bad_slug(tmp_path: Path):
    client = _make_client(tmp_path)
    _login(client)
    resp = client.post(
        "/onboarding/agent",
        data={"agent_id": "Bad Slug!", "label": "", "identity": ""},
    )
    assert resp.status_code == 200
    assert "Agent id must be a slug" in resp.text


def test_onboarding_set_runtime_writes_http_sse(
    tmp_path: Path,
    isolated_agentdrive_home: Path,
):
    client = _make_client(tmp_path)
    _login(client)
    resp = client.post(
        "/onboarding/runtime",
        data={
            "agent_id": "high-continuity-conductor",
            "kind": "http_sse",
            "url": "http://example.internal:8081/chat",
            "auth_env": "CONDUCTOR_RUNTIME_TOKEN",
            "provider": "",
        },
    )
    assert resp.status_code == 303
    assert resp.headers["location"].startswith(
        "/onboarding?step=4&agent_id=high-continuity-conductor"
    )

    rt = isolated_agentdrive_home / "agents" / "high-continuity-conductor" / "runtime.json"
    assert rt.exists()
    assert stat.S_IMODE(rt.stat().st_mode) == 0o600
    data = json.loads(rt.read_text(encoding="utf-8"))
    assert data["kind"] == "http_sse"
    assert data["url"] == "http://example.internal:8081/chat"
    assert data["auth_env"] == "CONDUCTOR_RUNTIME_TOKEN"


def test_onboarding_set_runtime_requires_url_for_http_sse(tmp_path: Path):
    client = _make_client(tmp_path)
    _login(client)
    resp = client.post(
        "/onboarding/runtime",
        data={
            "agent_id": "high-continuity-conductor",
            "kind": "http_sse",
            "url": "",
            "auth_env": "",
            "provider": "",
        },
    )
    assert resp.status_code == 200
    assert "Endpoint URL is required" in resp.text


def test_onboarding_step4_shows_runtime_kind(
    tmp_path: Path,
    isolated_agentdrive_home: Path,
):
    client = _make_client(tmp_path)
    _login(client)
    client.post(
        "/onboarding/runtime",
        data={
            "agent_id": "high-continuity-conductor",
            "kind": "http_sse",
            "url": "http://x/chat",
            "auth_env": "",
            "provider": "",
        },
    )
    resp = client.get("/onboarding?step=4&agent_id=high-continuity-conductor")
    assert resp.status_code == 200
    assert "http_sse" in resp.text
    assert "Open chat" in resp.text
