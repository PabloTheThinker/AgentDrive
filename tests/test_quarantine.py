"""Tests for the trust-gated quarantine module.

Quarantine sits in FRONT of AgentDrive.ingest for all externally-sourced
DNA. These tests cover submission, validation, approval/rejection/hold,
the audit log, dedup, and event emission.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentdrive.drive.drive import AgentDrive
from agentdrive.events import (
    Event,
    QuarantineApproved,
    QuarantineRejected,
    QuarantineSubmitted,
    QuarantineValidated,
    default_bus,
)
from agentdrive.genome.models import Genome, GenomeManifest
from agentdrive.quarantine import (
    NoExecutables,
    Quarantine,
    QuarantineStatus,
    SchemaValid,
    SizeLimit,
)
from agentdrive.registry import GenomeRegistry

# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _make_valid_genome_dir(parent: Path, gid: str = "vetted-capability") -> Path:
    """Materialize a minimal but fully valid genome directory on disk."""
    gdir = parent / f"{gid}-src"
    gdir.mkdir(parents=True, exist_ok=True)
    manifest = GenomeManifest(
        id=gid,
        version="1.0.0",
        content_hash="sha256:" + "deadbeef" * 8,
        created=datetime.now(UTC),
        authors=[],
    )
    g = Genome(manifest=manifest, framework={"steps": [{"id": "1", "name": "ok"}]})
    g.save(gdir)
    return gdir


@pytest.fixture
def clean_bus() -> Iterator[None]:
    """Snapshot + restore default_bus subscribers around each test."""
    with default_bus._lock:  # type: ignore[attr-defined]
        saved = list(default_bus._subs)  # type: ignore[attr-defined]
        default_bus._subs.clear()  # type: ignore[attr-defined]
    try:
        yield
    finally:
        with default_bus._lock:  # type: ignore[attr-defined]
            default_bus._subs = saved  # type: ignore[attr-defined]


# ─────────────────────────────────────────────────────────────────────
# submit / dedup
# ─────────────────────────────────────────────────────────────────────


def test_submit_creates_entry_and_copies_genome_dir(
    isolated_agentdrive_home: Path, tmp_path: Path
) -> None:
    src = _make_valid_genome_dir(tmp_path)
    q = Quarantine()

    entry = q.submit(src, source_peer="agentdrive://peer-alpha")

    assert entry.quarantine_id
    assert entry.source_peer == "agentdrive://peer-alpha"
    assert entry.status == QuarantineStatus.PENDING
    assert entry.genome_id == "vetted-capability@1.0.0"
    assert entry.sha256 and len(entry.sha256) == 64

    # The candidate dir was copied (not moved), source still intact.
    assert (entry.genome_dir / "manifest.yaml").is_file()
    assert (src / "manifest.yaml").is_file()
    assert entry.genome_dir != src

    # Entry persisted to disk under entries/.
    entry_file = isolated_agentdrive_home / "quarantine" / "entries" / f"{entry.quarantine_id}.json"
    assert entry_file.is_file()


def test_two_submissions_with_same_content_dedupe_via_sha256(
    isolated_agentdrive_home: Path, tmp_path: Path
) -> None:
    src = _make_valid_genome_dir(tmp_path)
    q = Quarantine()

    first = q.submit(src, source_peer="peer-1")
    second = q.submit(src, source_peer="peer-2")

    assert first.quarantine_id == second.quarantine_id
    assert first.sha256 == second.sha256
    assert len(q.list()) == 1


# ─────────────────────────────────────────────────────────────────────
# validate
# ─────────────────────────────────────────────────────────────────────


def test_validate_runs_all_rules_and_records_reasons(
    isolated_agentdrive_home: Path, tmp_path: Path
) -> None:
    src = _make_valid_genome_dir(tmp_path)
    q = Quarantine()
    entry = q.submit(src, source_peer="peer-x")

    results = q.validate(entry.quarantine_id)
    rule_names = {name for name, _ok, _r in results}
    assert {
        "schema_valid",
        "size_limit",
        "no_executables",
        "prompt_sanity",
        "signature_valid",
    } <= rule_names
    assert all(ok for _name, ok, _r in results), [r for r in results if not r[1]]

    refreshed = q.get(entry.quarantine_id)
    assert refreshed is not None
    assert refreshed.reasons == []  # no failures recorded


def test_schema_validation_rule_catches_missing_required_fields(
    tmp_path: Path,
) -> None:
    gdir = tmp_path / "broken"
    gdir.mkdir()
    (gdir / "manifest.yaml").write_text("id: broken-genome\n")  # missing version etc.

    ok, reason = SchemaValid().check(gdir)
    assert ok is False
    assert "missing" in reason


def test_no_executables_rule_rejects_shared_object(tmp_path: Path) -> None:
    gdir = tmp_path / "with-so"
    gdir.mkdir()
    (gdir / "manifest.yaml").write_text("id: x\nversion: 1.0.0\n")
    (gdir / "evil.so").write_bytes(b"\x7fELF...")

    ok, reason = NoExecutables().check(gdir)
    assert ok is False
    assert "evil.so" in reason


def test_size_limit_rule_rejects_oversized_dir(tmp_path: Path) -> None:
    gdir = tmp_path / "big"
    gdir.mkdir()
    (gdir / "bulk.bin").write_bytes(b"\x00" * (200 * 1024))

    rule = SizeLimit(max_bytes=64 * 1024)  # 64 KB cap
    ok, reason = rule.check(gdir)
    assert ok is False
    assert "size exceeds" in reason


# ─────────────────────────────────────────────────────────────────────
# approve / reject / hold
# ─────────────────────────────────────────────────────────────────────


def test_approve_ingests_into_pool_only_if_validation_passes(
    isolated_agentdrive_home: Path, tmp_path: Path
) -> None:
    # Bad candidate: missing manifest fields → validation fails.
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    (bad_dir / "manifest.yaml").write_text("id: incomplete\n")

    pool = AgentDrive(registry=GenomeRegistry())
    q = Quarantine()
    bad_entry = q.submit(bad_dir, source_peer="peer-bad")

    released = q.approve(bad_entry.quarantine_id, pool)
    assert released is False
    assert pool.get_pool_stats()["ingest_events"] == 0
    refreshed_bad = q.get(bad_entry.quarantine_id)
    assert refreshed_bad is not None
    assert refreshed_bad.status == QuarantineStatus.PENDING  # not approved
    assert refreshed_bad.reasons  # populated by validate

    # Good candidate: full valid genome dir → validates + ingests.
    good_dir = _make_valid_genome_dir(tmp_path, gid="good-genome")
    good_entry = q.submit(good_dir, source_peer="peer-good")

    released_good = q.approve(good_entry.quarantine_id, pool, note="vetted")
    assert released_good is True
    refreshed_good = q.get(good_entry.quarantine_id)
    assert refreshed_good is not None
    assert refreshed_good.status == QuarantineStatus.APPROVED
    assert pool.get_pool_stats()["ingest_events"] == 1
    assert any("quarantine:approved" in e.get("source", "") for e in pool.get_ingest_history())


def test_reject_marks_entry_and_does_not_ingest(
    isolated_agentdrive_home: Path, tmp_path: Path
) -> None:
    src = _make_valid_genome_dir(tmp_path)
    pool = AgentDrive(registry=GenomeRegistry())
    q = Quarantine()
    entry = q.submit(src, source_peer="peer-shady")

    assert q.reject(entry.quarantine_id, reason="untrusted peer") is True

    refreshed = q.get(entry.quarantine_id)
    assert refreshed is not None
    assert refreshed.status == QuarantineStatus.REJECTED
    assert any("untrusted peer" in r for r in refreshed.reasons)
    assert pool.get_pool_stats()["ingest_events"] == 0


def test_hold_keeps_entry_quarantined_status(
    isolated_agentdrive_home: Path, tmp_path: Path
) -> None:
    src = _make_valid_genome_dir(tmp_path)
    q = Quarantine()
    entry = q.submit(src, source_peer="peer-q")

    assert q.hold(entry.quarantine_id, reason="needs human review") is True

    refreshed = q.get(entry.quarantine_id)
    assert refreshed is not None
    assert refreshed.status == QuarantineStatus.QUARANTINED
    assert any("needs human review" in r for r in refreshed.reasons)


# ─────────────────────────────────────────────────────────────────────
# audit log + list filter + events
# ─────────────────────────────────────────────────────────────────────


def test_audit_log_jsonl_records_every_transition(
    isolated_agentdrive_home: Path, tmp_path: Path
) -> None:
    src = _make_valid_genome_dir(tmp_path)
    pool = AgentDrive(registry=GenomeRegistry())
    q = Quarantine()
    entry = q.submit(src, source_peer="peer-audit")
    q.validate(entry.quarantine_id)
    q.approve(entry.quarantine_id, pool)

    src2 = _make_valid_genome_dir(tmp_path, gid="other-cap")
    e2 = q.submit(src2, source_peer="peer-2")
    q.reject(e2.quarantine_id, reason="not allowed")

    src3 = _make_valid_genome_dir(tmp_path, gid="hold-cap")
    e3 = q.submit(src3, source_peer="peer-3")
    q.hold(e3.quarantine_id, reason="pending key check")

    log_path = isolated_agentdrive_home / "quarantine" / "log.jsonl"
    assert log_path.is_file()
    lines = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
    actions = [l["action"] for l in lines]
    # submit + validate + approve + submit + reject + submit + hold = 7
    assert actions.count("submit") == 3
    assert actions.count("validate") >= 1
    assert "approve" in actions
    assert "reject" in actions
    assert "hold" in actions
    for line in lines:
        assert "quarantine_id" in line
        assert "timestamp" in line


def test_list_filters_by_status(isolated_agentdrive_home: Path, tmp_path: Path) -> None:
    pool = AgentDrive(registry=GenomeRegistry())
    q = Quarantine()

    a_dir = _make_valid_genome_dir(tmp_path, gid="aaa")
    b_dir = _make_valid_genome_dir(tmp_path, gid="bbb")
    c_dir = _make_valid_genome_dir(tmp_path, gid="ccc")

    a = q.submit(a_dir, source_peer="peer-a")
    b = q.submit(b_dir, source_peer="peer-b")
    c = q.submit(c_dir, source_peer="peer-c")

    q.approve(a.quarantine_id, pool)
    q.reject(b.quarantine_id, reason="bad")
    # c stays pending

    pending = q.list(status=QuarantineStatus.PENDING)
    approved = q.list(status=QuarantineStatus.APPROVED)
    rejected = q.list(status=QuarantineStatus.REJECTED)
    held = q.list(status=QuarantineStatus.QUARANTINED)

    assert [e.quarantine_id for e in pending] == [c.quarantine_id]
    assert [e.quarantine_id for e in approved] == [a.quarantine_id]
    assert [e.quarantine_id for e in rejected] == [b.quarantine_id]
    assert held == []
    assert len(q.list()) == 3  # no filter → all


def test_quarantine_events_emitted_at_each_transition(
    isolated_agentdrive_home: Path, tmp_path: Path, clean_bus: None
) -> None:
    captured: list[Event] = []
    default_bus.subscribe(
        captured.append,
        event_types=(
            QuarantineSubmitted,
            QuarantineValidated,
            QuarantineApproved,
            QuarantineRejected,
        ),
    )

    pool = AgentDrive(registry=GenomeRegistry())
    q = Quarantine()

    good = _make_valid_genome_dir(tmp_path, gid="event-good")
    g_entry = q.submit(good, source_peer="peer-ok")
    q.validate(g_entry.quarantine_id)
    q.approve(g_entry.quarantine_id, pool)

    bad = _make_valid_genome_dir(tmp_path, gid="event-bad")
    b_entry = q.submit(bad, source_peer="peer-no")
    q.reject(b_entry.quarantine_id, reason="not trusted")

    kinds = [type(e).__name__ for e in captured]
    assert "QuarantineSubmitted" in kinds
    # validate is emitted explicitly AND once more inside approve
    assert kinds.count("QuarantineValidated") >= 2
    assert "QuarantineApproved" in kinds
    assert "QuarantineRejected" in kinds

    approved = next(e for e in captured if isinstance(e, QuarantineApproved))
    assert approved.quarantine_id == g_entry.quarantine_id
    assert approved.genome_id == "event-good@1.0.0"


def test_submit_dedup_under_concurrent_threads(isolated_agentdrive_home):
    """Concurrent submits of the same content must collapse to one entry."""
    import threading

    from agentdrive.quarantine import Quarantine

    q = Quarantine()
    src = isolated_agentdrive_home / "candidate_dir"
    src.mkdir(parents=True)
    (src / "manifest.yaml").write_text("id: dup-form\nversion: 1.0.0\n")

    results = []
    barrier = threading.Barrier(4)

    def worker():
        barrier.wait()
        entry = q.submit(src, source_peer="race-test")
        results.append(entry.quarantine_id)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All four submits should observe the same quarantine_id.
    assert len(set(results)) == 1, f"dedup race: got distinct ids {set(results)}"
    pending = q.list()
    assert len(pending) == 1


def test_approve_blocked_when_entry_not_pending(isolated_agentdrive_home):
    """A REJECTED entry must NOT be silently re-approved on a clean revalidate."""
    from agentdrive.drive.drive import AgentDrive
    from agentdrive.quarantine import Quarantine, QuarantineStatus
    from agentdrive.registry import GenomeRegistry

    q = Quarantine()
    src = isolated_agentdrive_home / "candidate"
    src.mkdir(parents=True)
    (src / "manifest.yaml").write_text("id: g\nversion: 1.0.0\n")
    entry = q.submit(src, source_peer="x")

    # Operator rejects it.
    assert q.reject(entry.quarantine_id, reason="operator policy") is True

    # Sanity check: status now REJECTED on disk.
    reloaded = q.get(entry.quarantine_id)
    assert reloaded.status == QuarantineStatus.REJECTED

    # Now try to approve. Must return False without touching the pool.
    pool = AgentDrive(registry=GenomeRegistry(root=isolated_agentdrive_home / "genomes"))
    assert q.approve(entry.quarantine_id, pool) is False

    # Status must remain REJECTED, NOT flip to APPROVED.
    after = q.get(entry.quarantine_id)
    assert after.status == QuarantineStatus.REJECTED
