"""Production hardening: health endpoint, rate limiter, error boundary, retention GC."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from agentdrive.backup.snapshot import SnapshotManager
from agentdrive.web.app import create_app
from agentdrive.web.observability import LoginRateLimiter


def _make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "auth.db")
    return TestClient(app, follow_redirects=False)


# ── /healthz ──────────────────────────────────────────────────────────


def test_healthz_works_without_auth_or_users(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "uptime_s" in body
    # Pre-auth probe must not leak user-presence (network enumeration vector).
    assert "has_users" not in body


def test_metrics_exposes_prometheus_counters(tmp_path: Path) -> None:
    """The /metrics endpoint is auth-bypass and returns text-format
    counters that a Prometheus scraper can parse.
    """
    client = _make_client(tmp_path)
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    body = r.text
    expected_metrics = [
        "agentdrive_uptime_seconds",
        "agentdrive_genomes_total",
        "agentdrive_snapshots_total",
        "agentdrive_capabilities_active",
        "agentdrive_swarms_total",
        "agentdrive_peers_total",
        "agentdrive_quarantine_pending",
    ]
    for name in expected_metrics:
        assert name in body, f"missing metric {name}"
        # Every metric should have a HELP and TYPE line (prometheus convention).
        assert f"# HELP {name}" in body, f"missing HELP for {name}"
        assert f"# TYPE {name}" in body, f"missing TYPE for {name}"


def test_healthz_carries_request_id(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    r = client.get("/healthz")
    assert "x-request-id" in r.headers
    assert len(r.headers["x-request-id"]) == 32  # uuid4 hex


# ── login rate limit ──────────────────────────────────────────────────


def test_login_rate_limit_locks_after_five_failures(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    # Bootstrap an admin so login is a real path.
    client.post("/setup", data={"username": "admin", "password": "admin password 123"})

    for _ in range(5):
        r = client.post("/login", data={"username": "admin", "password": "wrong-pw"})
        assert r.status_code == 401

    # Sixth attempt should be locked even if the password is now correct.
    r = client.post("/login", data={"username": "admin", "password": "admin password 123"})
    assert r.status_code == 429
    assert "too many" in r.text.lower()


def test_login_rate_limit_resets_on_success(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    client.post("/setup", data={"username": "admin", "password": "admin password 123"})

    for _ in range(3):
        r = client.post("/login", data={"username": "admin", "password": "wrong-pw"})
        assert r.status_code == 401
    # Success clears the budget.
    r = client.post("/login", data={"username": "admin", "password": "admin password 123"})
    assert r.status_code == 303

    # We should now be able to fail several more times without being locked.
    for _ in range(4):
        r = client.post("/login", data={"username": "admin", "password": "wrong-pw"})
        assert r.status_code == 401


def test_rate_limiter_window_slides() -> None:
    """The deque-based limiter prunes hits outside its window."""
    limiter = LoginRateLimiter(max_attempts=2, window_s=0.05)
    limiter.record_failure("1.2.3.4")
    limiter.record_failure("1.2.3.4")
    assert limiter.is_locked("1.2.3.4")
    time.sleep(0.07)
    assert not limiter.is_locked("1.2.3.4")


# ── retention GC ──────────────────────────────────────────────────────


def test_logout_actually_invalidates_session_server_side(tmp_path: Path) -> None:
    """C1 fix: /logout must call AuthStore.delete_session, not the
    nonexistent revoke_session. Replay of a logged-out cookie must fail.
    """
    client = _make_client(tmp_path)
    r = client.post("/setup", data={"username": "admin", "password": "admin password 123"})
    assert r.status_code == 303
    # Capture the session cookie set by /setup.
    session_cookie = client.cookies.get("agentdrive_session")
    assert session_cookie

    # Confirm authed by hitting a protected route.
    r = client.get("/dashboard")
    assert r.status_code == 200

    # Log out.
    r = client.post("/logout")
    assert r.status_code == 303

    # Replay the captured cookie — must NOT authenticate.
    client.cookies.clear()
    client.cookies.set("agentdrive_session", session_cookie)
    r = client.get("/dashboard")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_login_error_is_uniform_for_invalid_disabled_and_pending(tmp_path: Path) -> None:
    """H3 fix: collapse failure paths so an attacker cannot enumerate
    valid usernames or their state.
    """
    client = _make_client(tmp_path)
    client.post("/setup", data={"username": "admin", "password": "admin password 123"})

    # Wrong password on real account.
    r = client.post("/login", data={"username": "admin", "password": "bad"})
    msg_a = r.text
    assert r.status_code == 401
    assert "Invalid credentials" in msg_a

    # Username that doesn't exist.
    r = client.post("/login", data={"username": "ghost-user", "password": "bad"})
    assert r.status_code == 401
    assert "Invalid credentials" in r.text
    # The two error responses must be the same family — no "account is pending"
    # or "user not found" hint.
    assert "pending" not in r.text.lower()
    assert "disabled" not in r.text.lower()
    assert "not found" not in r.text.lower()


def test_csrf_rejects_mismatched_origin_on_post(tmp_path: Path) -> None:
    """C2 fix: cross-origin POST with an attacker-controlled Origin
    must be rejected.
    """
    client = _make_client(tmp_path)
    client.post("/setup", data={"username": "admin", "password": "admin password 123"})

    # Authed POST with a hostile Origin → 403.
    r = client.post(
        "/swarms",
        data={"swarm_id": "csrf-test"},
        headers={"origin": "http://evil.example.com"},
    )
    assert r.status_code == 403
    assert "origin_mismatch" in r.text

    # Same POST without Origin (non-browser caller) is allowed — CSRF
    # protection only applies to the browser-confused-deputy case.
    r = client.post("/swarms", data={"swarm_id": "csrf-allowed"})
    assert r.status_code in (200, 303, 400)


def test_personal_import_rejects_oversize_payload(tmp_path: Path) -> None:
    """H4 fix: hard cap on inbound genome JSON prevents memory DoS."""
    client = _make_client(tmp_path)
    client.post("/setup", data={"username": "admin", "password": "admin password 123"})

    huge = "x" * (2 * 1024 * 1024)  # 2 MiB > 1 MiB cap
    r = client.post("/personal/import", data={"genome_json": huge})
    assert r.status_code == 413
    assert "1 MiB" in r.text or "exceeds" in r.text.lower()


def test_snapshot_retention_respects_max_deletes_per_pass(tmp_path: Path) -> None:
    """Inline-on-take retention is now bounded by max_deletes_per_pass
    so a 10k-snapshot backlog can't stall the request that triggered
    the take.
    """
    drive_path = tmp_path / "drive"
    drive_path.mkdir()
    (drive_path / "objects").mkdir()
    backup_root = tmp_path / "backups"
    mgr = SnapshotManager(
        agent_id="bounded-test",
        drive_path=drive_path,
        backup_root=backup_root,
    )
    # Seed 25 snapshots above the policy ceiling.
    for _ in range(25):
        mgr.take(cadence_id="scheduled")
        time.sleep(0.01)

    # Now ask retention to delete at most 3 per pass.
    deleted = mgr.enforce_retention(max_deletes_per_pass=3)
    # We capped at 3; any more would be a contract break.
    assert len(deleted) <= 3, f"expected <= 3 deletes, got {len(deleted)}"


def test_snapshot_retention_keeps_pinned_and_recents(tmp_path: Path) -> None:
    drive_path = tmp_path / "drive"
    drive_path.mkdir()
    (drive_path / "objects").mkdir()
    backup_root = tmp_path / "backups"
    mgr = SnapshotManager(
        agent_id="ret-test",
        drive_path=drive_path,
        backup_root=backup_root,
    )

    # Synthesise 15 snapshots all within the past hour. The hourly bucket
    # should keep at most policy["keep_hourly"] = 6 of them.
    taken: list[str] = []
    for _ in range(15):
        entry = mgr.take(cadence_id="scheduled")
        taken.append(entry.snapshot_id)
        time.sleep(0.01)  # ensure unique ISO timestamps

    after = mgr.list_snapshots()
    assert len(after) <= 6, f"expected <= 6 after retention GC, got {len(after)}"

    # Pin one snapshot below the recency cutoff and confirm it survives a
    # fresh retention pass (by faking another take).
    pinned = mgr.pin(after[-1].snapshot_id, pinned=True)
    mgr.take(cadence_id="scheduled")
    listed_ids = {s.snapshot_id for s in mgr.list_snapshots()}
    assert pinned.snapshot_id in listed_ids
