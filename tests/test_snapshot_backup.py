"""v2 / Milestone 2d — Snapshot Backup + localhost UI.

What this milestone has to deliver:

1. Snapshots capture every content hash in a Drive as a pointer-only
   manifest. Zero content bytes are duplicated.
2. ``snapshot_if_due()`` respects the cadence window — back-to-back
   calls within ``cadence_seconds`` are no-ops.
3. Restore is read-only. ``restore(sid)`` returns the captured hashes
   but does not mutate Drive state.
4. Pin / delete behave as documented (pinned snapshots refuse deletion).
5. The localhost UI listens on ``127.0.0.1`` by default and exposes the
   documented routes (list / take / restore / pin / delete / health).
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

import pytest

from agentdrive.backup import DEFAULT_CADENCE_SECONDS, SnapshotError, SnapshotManager
from agentdrive.backup.ui import serve
from agentdrive.drive.content_store import ContentStore

# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _seed_drive(drive_path: Path, n: int = 3) -> list[str]:
    """Drop ``n`` distinct objects into a fresh content store, return hashes."""
    drive_path.mkdir(parents=True, exist_ok=True)
    store = ContentStore(drive_path)
    return [store.put_payload({"i": i, "kind": "test"}).hash for i in range(n)]


@pytest.fixture
def drive_and_backup(tmp_path: Path) -> tuple[Path, Path]:
    drive = tmp_path / "drive"
    backup = tmp_path / "backups"
    return drive, backup


# ─────────────────────────────────────────────────────────────────────
# 1. take() / list_snapshots() / restore()
# ─────────────────────────────────────────────────────────────────────


def test_snapshot_captures_every_content_hash(drive_and_backup) -> None:
    drive, backup = drive_and_backup
    expected = sorted(_seed_drive(drive, 5))

    mgr = SnapshotManager(agent_id="alice", drive_path=drive, backup_root=backup)
    entry = mgr.take()

    assert entry.hashes == expected
    assert entry.agent_id == "alice"
    assert entry.cadence_id == "on-demand"

    # On-disk manifest is what we'd later restore from.
    manifest_path = backup / "alice" / entry.snapshot_id / "manifest.json"
    assert manifest_path.exists()
    d = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert d["hashes"] == expected


def test_snapshot_is_pointer_only_no_content_duplication(drive_and_backup) -> None:
    """The Drive's objects/ directory should be the ONLY place content
    bytes live. Snapshot dirs hold only manifest.json."""
    drive, backup = drive_and_backup
    _seed_drive(drive, 3)
    mgr = SnapshotManager(agent_id="alice", drive_path=drive, backup_root=backup)

    entry = mgr.take()
    snap_dir = backup / "alice" / entry.snapshot_id

    files = list(snap_dir.iterdir())
    assert [f.name for f in files] == ["manifest.json"]


def test_list_snapshots_sorted_newest_first(drive_and_backup) -> None:
    drive, backup = drive_and_backup
    _seed_drive(drive, 1)
    mgr = SnapshotManager(agent_id="alice", drive_path=drive, backup_root=backup)

    a = mgr.take()
    time.sleep(1.1)  # ISO IDs have 1s resolution
    b = mgr.take()
    time.sleep(1.1)
    c = mgr.take()

    snaps = mgr.list_snapshots()
    assert [s.snapshot_id for s in snaps] == [c.snapshot_id, b.snapshot_id, a.snapshot_id]


def test_restore_returns_captured_hashes(drive_and_backup) -> None:
    drive, backup = drive_and_backup
    hashes = sorted(_seed_drive(drive, 4))
    mgr = SnapshotManager(agent_id="alice", drive_path=drive, backup_root=backup)
    entry = mgr.take()

    restored = mgr.restore(entry.snapshot_id)
    assert restored == hashes


def test_restore_does_not_mutate_drive(drive_and_backup) -> None:
    """Read-only restore: the Drive's content store is untouched."""
    drive, backup = drive_and_backup
    _seed_drive(drive, 2)
    mgr = SnapshotManager(agent_id="alice", drive_path=drive, backup_root=backup)
    entry = mgr.take()

    store = ContentStore(drive)
    before = sorted(store.iter_hashes())
    mgr.restore(entry.snapshot_id)
    after = sorted(store.iter_hashes())

    assert before == after


def test_restore_missing_snapshot_raises(drive_and_backup) -> None:
    drive, backup = drive_and_backup
    _seed_drive(drive, 1)
    mgr = SnapshotManager(agent_id="alice", drive_path=drive, backup_root=backup)

    with pytest.raises(SnapshotError, match="not found"):
        mgr.restore("2026-01-01T00:00:00Z")


def test_restore_detects_missing_underlying_objects(drive_and_backup) -> None:
    drive, backup = drive_and_backup
    hashes = _seed_drive(drive, 2)
    mgr = SnapshotManager(agent_id="alice", drive_path=drive, backup_root=backup)
    entry = mgr.take()

    # Wipe one of the underlying content objects.
    store = ContentStore(drive)
    one_path = store._path_for(hashes[0])
    one_path.unlink()

    with pytest.raises(SnapshotError, match="no longer in the content store"):
        mgr.restore(entry.snapshot_id)


# ─────────────────────────────────────────────────────────────────────
# 2. Cadence
# ─────────────────────────────────────────────────────────────────────


def test_snapshot_if_due_takes_first_snapshot(drive_and_backup) -> None:
    drive, backup = drive_and_backup
    _seed_drive(drive, 1)
    mgr = SnapshotManager(
        agent_id="alice",
        drive_path=drive,
        backup_root=backup,
        cadence_seconds=3600,
    )
    first = mgr.snapshot_if_due()
    assert first is not None


def test_snapshot_if_due_respects_window(drive_and_backup) -> None:
    drive, backup = drive_and_backup
    _seed_drive(drive, 1)
    mgr = SnapshotManager(
        agent_id="alice",
        drive_path=drive,
        backup_root=backup,
        cadence_seconds=3600,
    )
    mgr.snapshot_if_due()
    # Immediately calling again should be a no-op (under the cadence window).
    second = mgr.snapshot_if_due()
    assert second is None


def test_snapshot_if_due_fires_after_window(drive_and_backup) -> None:
    drive, backup = drive_and_backup
    _seed_drive(drive, 1)
    mgr = SnapshotManager(
        agent_id="alice",
        drive_path=drive,
        backup_root=backup,
        cadence_seconds=1,
    )
    mgr.snapshot_if_due()
    time.sleep(1.2)
    after = mgr.snapshot_if_due()
    assert after is not None


def test_default_cadence_is_six_hours() -> None:
    assert DEFAULT_CADENCE_SECONDS == 6 * 60 * 60


# ─────────────────────────────────────────────────────────────────────
# 3. Pin / delete
# ─────────────────────────────────────────────────────────────────────


def test_pin_protects_from_delete(drive_and_backup) -> None:
    drive, backup = drive_and_backup
    _seed_drive(drive, 1)
    mgr = SnapshotManager(agent_id="alice", drive_path=drive, backup_root=backup)
    entry = mgr.take()

    pinned = mgr.pin(entry.snapshot_id, pinned=True)
    assert pinned.pinned

    with pytest.raises(SnapshotError, match="pinned"):
        mgr.delete(entry.snapshot_id)

    # Unpin and try again.
    mgr.pin(entry.snapshot_id, pinned=False)
    assert mgr.delete(entry.snapshot_id) is True


def test_delete_unknown_snapshot_returns_false(drive_and_backup) -> None:
    drive, backup = drive_and_backup
    _seed_drive(drive, 1)
    mgr = SnapshotManager(agent_id="alice", drive_path=drive, backup_root=backup)
    assert mgr.delete("2099-01-01T00:00:00Z") is False


# ─────────────────────────────────────────────────────────────────────
# 4. Localhost UI
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def running_ui(tmp_path: Path):
    """Start the UI on a random unused localhost port."""
    import socket

    drive = tmp_path / "drive"
    backup = tmp_path / "backups"
    _seed_drive(drive, 2)

    # Pick a free port deterministically.
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    def resolve(agent_id: str) -> Path:
        return drive  # all agents in this test share the same Drive

    server = serve(
        host="127.0.0.1",
        port=port,
        backup_root=backup,
        resolve_drive_path=resolve,
        blocking=False,
    )
    try:
        yield port, drive, backup
    finally:
        server.shutdown()


def _get(port: int, path: str) -> dict:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=2) as r:
        return json.loads(r.read().decode("utf-8"))


def _post(port: int, path: str) -> dict:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method="POST")
    with urllib.request.urlopen(req, timeout=2) as r:
        return json.loads(r.read().decode("utf-8"))


def test_ui_health(running_ui) -> None:
    port, _, _ = running_ui
    assert _get(port, "/api/health") == {"ok": True}


def test_ui_lists_and_takes_snapshots(running_ui) -> None:
    port, _, _ = running_ui

    # Initially empty.
    initial = _get(port, "/api/snapshots?agent_id=alice")
    assert initial["snapshots"] == []

    # Take one via POST.
    created = _post(port, "/api/snapshots?agent_id=alice")
    assert "snapshot" in created
    assert created["snapshot"]["cadence_id"] == "on-demand"

    # Listed now.
    after = _get(port, "/api/snapshots?agent_id=alice")
    assert len(after["snapshots"]) == 1


def test_ui_dashboard_html_renders(running_ui) -> None:
    port, _, _ = running_ui
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
        body = r.read().decode("utf-8")
    assert "AgentDrive Snapshots" in body
    assert "loadAgent()" in body  # the script wired up the take-snapshot button


def test_ui_pin_endpoint(running_ui) -> None:
    port, _, _ = running_ui
    entry = _post(port, "/api/snapshots?agent_id=alice")["snapshot"]
    sid = entry["snapshot_id"]

    pinned = _post(port, f"/api/pin?agent_id=alice&id={sid}&pinned=true")
    assert pinned["snapshot"]["pinned"] is True


# ─────────────────────────────────────────────────────────────────────
# 5. Security — path traversal + CSRF (added during repo audit)
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "bad",
    [
        "../etc",
        "../../passwd",
        "a/b",
        "foo\x00bar",
        ".",
        "..",
        "",
        "x" * 200,  # exceeds 128-char cap
        "with space",
        "name;with;semicolon",
    ],
)
def test_path_traversal_rejected_in_agent_id(tmp_path: Path, bad: str) -> None:
    """SnapshotManager refuses any agent_id that could escape backup_root.
    Regression for the v2 / M2d audit finding."""
    with pytest.raises((ValueError, SnapshotError)):
        SnapshotManager(
            agent_id=bad,
            drive_path=tmp_path / "drive",
            backup_root=tmp_path / "backups",
        )


def test_path_traversal_rejected_in_snapshot_id(drive_and_backup) -> None:
    drive, backup = drive_and_backup
    _seed_drive(drive, 1)
    mgr = SnapshotManager(agent_id="alice", drive_path=drive, backup_root=backup)
    for bad in ["../etc", "..", "foo/bar"]:
        with pytest.raises(SnapshotError):
            mgr.get(bad)


def test_ui_rejects_cross_origin_post(running_ui) -> None:
    """CSRF defense: a POST from a foreign Origin must be refused even
    though the bind is localhost-only, because the user's browser is the
    attacker's transport."""
    port, _, _ = running_ui
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/snapshots?agent_id=alice",
        method="POST",
        headers={"Origin": "http://evil.example.com"},
    )
    try:
        urllib.request.urlopen(req, timeout=2)
        raised = None
    except urllib.error.HTTPError as exc:
        raised = exc.code
    assert raised == 403, f"cross-origin POST should be rejected with 403, got {raised}"


def test_ui_allows_same_origin_post(running_ui) -> None:
    """The same defense must not block legitimate same-origin requests."""
    port, _, _ = running_ui
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/snapshots?agent_id=alice",
        method="POST",
        headers={"Origin": f"http://127.0.0.1:{port}"},
    )
    with urllib.request.urlopen(req, timeout=2) as r:
        body = json.loads(r.read().decode("utf-8"))
    assert "snapshot" in body


def test_ui_rejects_traversal_agent_id_with_400(running_ui) -> None:
    port, _, _ = running_ui
    try:
        urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/snapshots?agent_id=../../etc",
            timeout=2,
        )
        raised = None
    except urllib.error.HTTPError as exc:
        raised = exc.code
    assert raised == 400, f"traversal agent_id should 400, got {raised}"


def test_ui_responses_carry_hardening_headers(running_ui) -> None:
    port, _, _ = running_ui
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as r:
        headers = {k.lower(): v for k, v in r.getheaders()}
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
