"""Tests for the federated peer registry (proposal #6).

Covers PeerRegistry CRUD + persistence, the LocalFilePeerAdapter, and
the sync_peer flow. The single most load-bearing assertion in this file
is ``test_sync_peer_never_calls_pool_ingest_directly``: peer DNA MUST
route through quarantine — no fast path, no trust-shortcut.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentdrive.drive.drive import AgentDrive
from agentdrive.events import (
    Event,
    PeerSyncCompleted,
    PeerSyncStarted,
    PeerTrustChanged,
    default_bus,
)
from agentdrive.genome.models import Genome, GenomeManifest
from agentdrive.peers import (
    LocalFilePeerAdapter,
    PeerEntry,
    PeerRegistry,
    PeerSyncResult,
    get_adapter_for,
    sync_peer,
)
from agentdrive.registry import GenomeRegistry

# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _make_valid_genome_dir(parent: Path, gid: str = "peer-genome") -> Path:
    """Materialize a minimal, valid genome directory."""
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


def _make_peer_home(parent: Path, *gids: str) -> Path:
    """Build a fake AGENTDRIVE_HOME-like directory with a populated genomes/ tree.

    Returns the home root (so peer.address points at the home dir).
    """
    home = parent / "peer-home"
    genomes_root = home / "genomes"
    genomes_root.mkdir(parents=True, exist_ok=True)
    for gid in gids:
        gdir = genomes_root / gid
        gdir.mkdir(parents=True, exist_ok=True)
        manifest = GenomeManifest(
            id=gid,
            version="1.0.0",
            content_hash="sha256:" + "feedface" * 8,
            created=datetime.now(UTC),
            authors=[],
        )
        g = Genome(manifest=manifest, framework={"steps": [{"id": "1", "name": "ok"}]})
        g.save(gdir)
    return home


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
# Registry CRUD
# ─────────────────────────────────────────────────────────────────────


def test_add_persists_entry_to_disk(isolated_savant_home: Path) -> None:
    reg = PeerRegistry()
    entry = reg.add("alpha", "file:///tmp/peer-alpha", notes="machine in basement")

    assert entry.peer_id == "alpha"
    assert entry.trust_level == "untrusted"
    assert entry.address == "file:///tmp/peer-alpha"
    assert entry.notes == "machine in basement"
    assert entry.last_sync_iso is None

    on_disk = isolated_savant_home / "peers" / "alpha.json"
    assert on_disk.is_file()
    payload = json.loads(on_disk.read_text(encoding="utf-8"))
    assert payload["peer_id"] == "alpha"
    assert payload["address"] == "file:///tmp/peer-alpha"
    assert payload["trust_level"] == "untrusted"


def test_remove_deletes_entry(isolated_savant_home: Path) -> None:
    reg = PeerRegistry()
    reg.add("beta", "file:///tmp/peer-beta")
    assert reg.get("beta") is not None
    assert reg.remove("beta") is True
    assert reg.get("beta") is None
    assert not (isolated_savant_home / "peers" / "beta.json").exists()
    # Removing again is a no-op (returns False), not an error.
    assert reg.remove("beta") is False


def test_set_trust_updates_level_and_emits_event(
    isolated_savant_home: Path, clean_bus: None
) -> None:
    captured: list[Event] = []
    default_bus.subscribe(captured.append, event_types=(PeerTrustChanged,))

    reg = PeerRegistry()
    reg.add("gamma", "file:///tmp/peer-gamma", trust_level="untrusted")

    assert reg.set_trust("gamma", "review") is True
    refreshed = reg.get("gamma")
    assert refreshed is not None
    assert refreshed.trust_level == "review"

    assert reg.set_trust("gamma", "trusted") is True
    refreshed = reg.get("gamma")
    assert refreshed is not None
    assert refreshed.trust_level == "trusted"

    events = [e for e in captured if isinstance(e, PeerTrustChanged)]
    assert len(events) == 2
    assert events[0].old_level == "untrusted"
    assert events[0].new_level == "review"
    assert events[1].old_level == "review"
    assert events[1].new_level == "trusted"

    # Bad level rejected.
    with pytest.raises(ValueError):
        reg.set_trust("gamma", "ultra-trusted")


def test_list_returns_all_peers(isolated_savant_home: Path) -> None:
    reg = PeerRegistry()
    assert reg.list() == []

    reg.add("aaa", "file:///tmp/a")
    reg.add("bbb", "file:///tmp/b", trust_level="trusted")
    reg.add("ccc", "file:///tmp/c", trust_level="review")

    listed = reg.list()
    ids = sorted(e.peer_id for e in listed)
    assert ids == ["aaa", "bbb", "ccc"]
    levels = {e.peer_id: e.trust_level for e in listed}
    assert levels == {"aaa": "untrusted", "bbb": "trusted", "ccc": "review"}


# ─────────────────────────────────────────────────────────────────────
# LocalFilePeerAdapter
# ─────────────────────────────────────────────────────────────────────


def test_local_file_adapter_finds_new_genomes_since_iso(
    isolated_savant_home: Path, tmp_path: Path
) -> None:
    peer_home = _make_peer_home(tmp_path, "cap-one", "cap-two")

    # Backdate one genome's mtime so it falls before "since".
    old_gdir = peer_home / "genomes" / "cap-one"
    long_ago = time.time() - (10 * 365 * 24 * 3600)  # ~10 years ago
    for root, _dirs, files in os.walk(old_gdir):
        for f in files:
            fp = Path(root) / f
            os.utime(fp, (long_ago, long_ago))
    os.utime(old_gdir, (long_ago, long_ago))

    # Pick a "since" cutoff well after the backdated dir but before now.
    since = datetime.fromtimestamp(time.time() - 3600, tz=UTC).isoformat()

    peer = PeerEntry(peer_id="local", address=f"file://{peer_home}")
    adapter = LocalFilePeerAdapter()
    found = list(adapter.fetch_new_genomes(peer, since))

    # cap-two has fresh mtime, cap-one is stale → only cap-two yielded.
    names = [p.name for p in found]
    assert "cap-two" in names
    assert "cap-one" not in names

    # With an epoch since, BOTH should surface.
    all_found = list(adapter.fetch_new_genomes(peer, "1970-01-01T00:00:00+00:00"))
    assert {p.name for p in all_found} == {"cap-one", "cap-two"}


def test_get_adapter_for_resolves_file_scheme(isolated_savant_home: Path) -> None:
    peer_file = PeerEntry(peer_id="x", address="file:///tmp/foo")
    peer_bare = PeerEntry(peer_id="y", address="/tmp/foo")
    peer_https = PeerEntry(peer_id="z", address="https://example.com")

    assert isinstance(get_adapter_for(peer_file), LocalFilePeerAdapter)
    assert isinstance(get_adapter_for(peer_bare), LocalFilePeerAdapter)
    # No HTTPS adapter in v1.
    assert get_adapter_for(peer_https) is None


# ─────────────────────────────────────────────────────────────────────
# sync_peer
# ─────────────────────────────────────────────────────────────────────


def test_sync_peer_submits_each_genome_to_quarantine(
    isolated_savant_home: Path, tmp_path: Path
) -> None:
    peer_home = _make_peer_home(tmp_path, "g-one", "g-two", "g-three")

    reg = PeerRegistry()
    reg.add("partner", f"file://{peer_home}", trust_level="trusted")

    pool = AgentDrive(registry=GenomeRegistry())
    result = sync_peer("partner", target_pool=pool, registry=reg)

    assert isinstance(result, PeerSyncResult)
    assert result.submitted == 3
    assert len(result.quarantine_ids) == 3
    assert result.errors == []

    # Every candidate landed in quarantine, none in the live pool.
    from agentdrive.quarantine import QuarantineStatus, get_default_quarantine

    q = get_default_quarantine()
    pending = q.list(status=QuarantineStatus.PENDING)
    assert len(pending) == 3
    for entry in pending:
        assert entry.source_peer == "peer:partner"

    # Pool ingest log is empty — no direct ingestion happened.
    assert pool.get_pool_stats()["ingest_events"] == 0


def test_sync_peer_never_calls_pool_ingest_directly(
    isolated_savant_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The load-bearing assertion: the quarantine gate is unbypassable.

    Even when the peer is marked ``trusted``, ``sync_peer`` must NEVER
    call ``AgentDrive.ingest`` directly. We patch the pool's ingest to
    explode loudly if anyone touches it, and we patch
    ``Quarantine.submit`` to confirm that's where each candidate actually
    lands.
    """
    peer_home = _make_peer_home(tmp_path, "g-a", "g-b")

    reg = PeerRegistry()
    reg.add("vip", f"file://{peer_home}", trust_level="trusted")

    pool = AgentDrive(registry=GenomeRegistry())

    def _explode(*args, **kwargs):  # noqa: ARG001
        raise AssertionError(
            "pool.ingest must never be called from sync_peer — "
            "all peer DNA must route through Quarantine.submit"
        )

    monkeypatch.setattr(pool, "ingest", _explode)

    # Also patch the global default pool (in case anyone reached for it).
    from agentdrive.drive import drive as drive_mod

    monkeypatch.setattr(drive_mod, "get_default_drive", lambda: pool)

    # Track quarantine submissions to prove they happened.
    from agentdrive.quarantine import Quarantine, get_default_quarantine

    submit_calls: list[tuple[Path, str]] = []
    real_submit = Quarantine.submit

    def _tracking_submit(self, genome_dir, source_peer):
        submit_calls.append((Path(genome_dir), str(source_peer)))
        return real_submit(self, genome_dir, source_peer)

    monkeypatch.setattr(Quarantine, "submit", _tracking_submit)

    result = sync_peer("vip", target_pool=pool, registry=reg)

    # No exception → ingest was never invoked.
    assert result.errors == []
    assert result.submitted == 2
    assert len(submit_calls) == 2
    for _gdir, source in submit_calls:
        assert source == "peer:vip"

    # Sanity: the static import surface for peers.py contains no reference
    # to pool.ingest at all. (Defence-in-depth against a future regression.)
    peers_src = Path(__file__).resolve().parents[1] / "src" / "agentdrive" / "peers.py"
    text = peers_src.read_text(encoding="utf-8")
    assert ".ingest(" not in text, (
        "agentdrive.peers must not call .ingest() anywhere — peer DNA is "
        "quarantine-only by hard contract"
    )

    # Live pool stays empty.
    assert pool.get_pool_stats()["ingest_events"] == 0
    # And quarantine has the entries.
    q = get_default_quarantine()
    assert len(q.list()) == 2


def test_sync_peer_emits_started_and_completed_events(
    isolated_savant_home: Path, tmp_path: Path, clean_bus: None
) -> None:
    captured: list[Event] = []
    default_bus.subscribe(
        captured.append,
        event_types=(PeerSyncStarted, PeerSyncCompleted),
    )

    peer_home = _make_peer_home(tmp_path, "cap-x", "cap-y")
    reg = PeerRegistry()
    reg.add("evt-peer", f"file://{peer_home}")

    pool = AgentDrive(registry=GenomeRegistry())
    result = sync_peer("evt-peer", target_pool=pool, registry=reg)

    kinds = [type(e).__name__ for e in captured]
    assert kinds[0] == "PeerSyncStarted"
    assert kinds[-1] == "PeerSyncCompleted"

    started = next(e for e in captured if isinstance(e, PeerSyncStarted))
    completed = next(e for e in captured if isinstance(e, PeerSyncCompleted))
    assert started.peer_id == "evt-peer"
    assert completed.peer_id == "evt-peer"
    assert completed.submitted == result.submitted == 2
    assert completed.errors == 0
    assert completed.duration_ms >= 0


def test_sync_updates_last_sync_iso(isolated_savant_home: Path, tmp_path: Path) -> None:
    peer_home = _make_peer_home(tmp_path, "only-one")
    reg = PeerRegistry()
    reg.add("syncer", f"file://{peer_home}")

    before = reg.get("syncer")
    assert before is not None and before.last_sync_iso is None

    pool = AgentDrive(registry=GenomeRegistry())
    sync_peer("syncer", target_pool=pool, registry=reg)

    after = reg.get("syncer")
    assert after is not None
    assert after.last_sync_iso is not None
    # Parses as a valid ISO timestamp.
    parsed = datetime.fromisoformat(after.last_sync_iso)
    assert parsed.tzinfo is not None


def test_sync_handles_adapter_errors_per_candidate(
    isolated_savant_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One bad candidate must not abort the whole sync."""
    peer_home = _make_peer_home(tmp_path, "ok-one", "ok-two")
    reg = PeerRegistry()
    reg.add("flaky", f"file://{peer_home}")

    # Make Quarantine.submit fail on the FIRST candidate, succeed on the rest.
    from agentdrive.quarantine import Quarantine

    call_count = {"n": 0}
    real_submit = Quarantine.submit

    def _flaky_submit(self, genome_dir, source_peer):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated disk hiccup")
        return real_submit(self, genome_dir, source_peer)

    monkeypatch.setattr(Quarantine, "submit", _flaky_submit)

    pool = AgentDrive(registry=GenomeRegistry())
    result = sync_peer("flaky", target_pool=pool, registry=reg)

    # One submission succeeded; one error recorded; the sync did NOT crash.
    assert result.submitted == 1
    assert len(result.errors) == 1
    assert "simulated disk hiccup" in result.errors[0]
    # last_sync_iso still got bumped — partial success is still progress.
    after = reg.get("flaky")
    assert after is not None
    assert after.last_sync_iso is not None


def test_sync_peer_unknown_peer_returns_error_not_crash(
    isolated_savant_home: Path,
) -> None:
    reg = PeerRegistry()
    pool = AgentDrive(registry=GenomeRegistry())
    result = sync_peer("ghost", target_pool=pool, registry=reg)
    assert result.submitted == 0
    assert any("unknown peer" in e for e in result.errors)


def test_unknown_scheme_does_not_silently_fall_to_local_file(isolated_savant_home):
    """ftp:// (and any unknown scheme) must NOT be coerced into LocalFilePeerAdapter."""
    from agentdrive.peers import PeerRegistry, _address_scheme, sync_peer

    # _address_scheme returns the literal unknown scheme, not "file".
    assert _address_scheme("ftp://nowhere") == "ftp"
    assert _address_scheme("gopher://elsewhere") == "gopher"
    # Bare paths still resolve to file (preserved convention).
    assert _address_scheme("/tmp/local-dir") == "file"
    # Recognized schemes unchanged.
    assert _address_scheme("file:///tmp/x") == "file"

    reg = PeerRegistry()
    reg.add("borked", "ftp://nowhere", trust_level="trusted")

    # Fake target_pool; should never be touched on the no-adapter path.
    class _Sentinel:
        def ingest(self, *a, **k):
            raise AssertionError("pool must not be touched when adapter missing")

    result = sync_peer("borked", _Sentinel(), registry=reg)
    assert result.submitted == 0
    assert len(result.errors) >= 1
    assert "ftp" in " ".join(result.errors).lower() or "scheme" in " ".join(result.errors).lower()
