"""Tests for the agent-facing spec served at /.well-known/agent-drive.html."""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from agentdrive import AGENTDRIVE_VERSION
from agentdrive.web.app import create_app


def _make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "auth.db")
    return TestClient(app, follow_redirects=False)


def test_spec_served_publicly(tmp_path: Path):
    client = _make_client(tmp_path)
    resp = client.get("/.well-known/agent-drive.html")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")


def test_spec_embeds_machine_readable_json(tmp_path: Path):
    client = _make_client(tmp_path)
    body = client.get("/.well-known/agent-drive.html").text

    m = re.search(
        r'<script type="application/json" id="agent-drive-spec">(.*?)</script>',
        body,
        flags=re.DOTALL,
    )
    assert m, "missing embedded JSON spec block"
    spec = json.loads(m.group(1))
    assert spec["version"] == AGENTDRIVE_VERSION
    assert set(spec.keys()) >= {"version", "runtime_kinds", "sse_events", "endpoints"}
    assert "http_sse" in spec["runtime_kinds"]
    assert "model" in spec["runtime_kinds"]


def test_spec_documents_runtime_kinds_and_protocol(tmp_path: Path):
    client = _make_client(tmp_path)
    body = client.get("/.well-known/agent-drive.html").text
    assert "runtime.json" in body
    assert "http_sse" in body
    assert "text/event-stream" in body
    assert "event: done" in body
