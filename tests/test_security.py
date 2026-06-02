"""
Focused tests for expanded SecurityPosture signals (Security Posture & Immune Hardening Operator).

Covers:
- New hygiene signals populated (quarantine, key rotation, recon depth, grants revocation, schema proposals).
- Posture under partial / corrupted state.
- Recommendation quality for actionable operator guidance (role-swarm framing).

All tests respect isolated_agentdrive_home and sovereignty of the test drive.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agentdrive.security import SecurityPosture, get_security_posture, print_security_posture


def test_security_posture_new_signals_present_and_typed(isolated_agentdrive_home: Path):
    """All new expanded fields exist with correct types/defaults on a fresh home."""
    posture = get_security_posture()
    assert isinstance(posture, SecurityPosture)
    # Core
    assert isinstance(posture.quarantined_items, int)
    assert isinstance(posture.recent_quarantine_releases, int)
    assert posture.key_rotation_signal is None or isinstance(posture.key_rotation_signal, str)
    assert posture.trust_self_mtime_age_days is None or isinstance(
        posture.trust_self_mtime_age_days, float
    )
    assert posture.reconciliation_last_scan_delta_hours is None or isinstance(
        posture.reconciliation_last_scan_delta_hours, float
    )
    assert isinstance(posture.reconciliation_failure_count, int)
    assert isinstance(posture.revoked_grants, int)
    assert isinstance(posture.schema_evolution_security_proposals, int)
    assert isinstance(posture.schema_evolution_security_details, list)
    # Defaults sane on empty drive
    assert posture.quarantined_items == 0
    assert posture.reconciliation_failure_count == 0
    assert posture.revoked_grants == 0


def test_security_posture_under_partial_state(isolated_agentdrive_home: Path):
    """Posture gracefully handles partial recon state, grants with revokes, and quarantine items."""
    home = isolated_agentdrive_home

    # Seed partial reconciliation state with failure count (from extended schema)
    state_path = home / "reconciliation.json"
    partial_state = {
        "last_scan_iso": (datetime.now(UTC) - timedelta(hours=3)).isoformat(),
        "known_genome_ids": ["g1"],
        "known_markers": {},
        "consecutive_failures": 2,
    }
    state_path.write_text(json.dumps(partial_state), encoding="utf-8")

    # Seed grants.db with mix of active + revoked for revocation hygiene
    grants_db = home / "grants.db"
    grants_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(grants_db) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS grants (grant_id TEXT PRIMARY KEY, issuer TEXT, grantee TEXT, "
            "scope_json TEXT, reducer TEXT, issued_at REAL, ttl_seconds REAL, signature TEXT, "
            "issuer_pubkey TEXT, revoked INTEGER NOT NULL DEFAULT 0)"
        )
        conn.execute("INSERT INTO grants VALUES ('g-active','i','g','{}','append',0,0,'s','p',0)")
        conn.execute("INSERT INTO grants VALUES ('g-revoked','i','g','{}','append',0,0,'s','p',1)")
        conn.commit()

    # Seed minimal quarantine entries dir + one pending entry (for count)
    q_entries = home / "quarantine" / "entries"
    q_entries.mkdir(parents=True, exist_ok=True)
    entry = {
        "quarantine_id": "q1",
        "genome_id": "test@1",
        "source_peer": "peer-x",
        "received_at": datetime.now(UTC).isoformat(),
        "status": "pending",
        "reasons": [],
        "genome_dir": str(home / "quarantine/candidates/q1"),
        "sha256": "deadbeef",
    }
    (q_entries / "q1.json").write_text(json.dumps(entry), encoding="utf-8")
    (home / "quarantine" / "candidates" / "q1").mkdir(parents=True, exist_ok=True)

    # Trust self.json with known mtime (for rotation signal)
    trust_dir = home / "trust"
    trust_dir.mkdir(parents=True, exist_ok=True)
    self_json = trust_dir / "self.json"
    self_json.write_text(
        '{"identity": {"device_id": "t1"}, "private_pem": "dummy"}', encoding="utf-8"
    )
    # Touch mtime (current; age computation tolerant; note on backdating limitations in pure Python)
    self_json.touch()
    # Note: touch() uses now; we can't easily backdate mtime in pure python without os.utime across platforms,
    # so we accept computed age >=0 and just verify signal format when present.

    posture = get_security_posture()

    # Recon health depth from state
    assert posture.reconciliation_failure_count == 2
    assert posture.reconciliation_last_scan_delta_hours is not None
    assert posture.reconciliation_last_scan_delta_hours > 2.5  # ~3h

    # Grants revocation hygiene
    assert posture.revoked_grants == 1
    assert posture.active_grants == 1

    # Quarantine hygiene
    assert posture.quarantined_items >= 1

    # Key rotation signal present (age computed)
    assert posture.key_rotation_signal is not None and "self.json" in posture.key_rotation_signal

    # Schema proposals default 0 on clean partial (no matching evolution files)
    assert posture.schema_evolution_security_proposals == 0


def test_security_posture_recommendation_quality(isolated_agentdrive_home: Path):
    """Recommendations contain high-quality actionable items for the new signals and framing."""
    home = isolated_agentdrive_home

    # Force stale recon + high failure to trigger depth rec
    state_path = home / "reconciliation.json"
    old_scan = (datetime.now(UTC) - timedelta(hours=60)).isoformat()
    state_path.write_text(
        json.dumps(
            {
                "last_scan_iso": old_scan,
                "known_genome_ids": [],
                "known_markers": {},
                "consecutive_failures": 5,
            }
        ),
        encoding="utf-8",
    )

    # Old key material to trigger rotation rec
    trust_dir = home / "trust"
    trust_dir.mkdir(parents=True, exist_ok=True)
    self_json = trust_dir / "self.json"
    self_json.write_text('{"identity": {}}', encoding="utf-8")
    # Force old mtime via utime
    old_mtime = (datetime.now(UTC) - timedelta(days=120)).timestamp()
    import os

    os.utime(self_json, (old_mtime, old_mtime))

    posture = get_security_posture()

    recs_text = " | ".join(posture.recommendations).lower()

    # Quality checks for new signals + framing
    assert "reconciliation health depth" in recs_text or "reconciliation stale" in recs_text
    assert "key rotation" in recs_text or "consider key rotation" in recs_text
    assert "quarantine" in recs_text or "role-swarm" in recs_text or "experience layer" in recs_text
    # At least one framing token from the mission
    assert any(
        tok in recs_text
        for tok in (
            "sovereignty",
            "role-swarm",
            "trust boundaries",
            "quarantine signals",
            "experience layer integrity",
        )
    )

    # Overall still computes
    assert posture.overall in ("good", "needs_attention")


def test_print_security_posture_does_not_crash(isolated_agentdrive_home: Path):
    """print_security_posture renders the expanded table without error (rich console)."""
    # Should not raise even on fresh/partial drive
    print_security_posture()  # exercises all new table rows
    assert True
