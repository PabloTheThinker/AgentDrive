"""Tests for the content-addressed object store — v2 / Milestone 1.

Three guarantees we need to lock in before anything else in v2 can be built:

1. Determinism: same Genome content → same hash, regardless of insertion
   order, whitespace, or process identity.
2. Dedup: writing the same content twice produces ONE object on disk; the
   second put reports ``existed=True``.
3. Drive integration: ingesting a Genome both saves it via the registry
   (legacy path) AND writes it content-addressed (new path), and the Drive
   exposes lookup-by-hash.

If any of these break, downstream milestones (caps, supersedes-DAG, peer sync)
all rest on the wrong foundation. These tests are load-bearing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentdrive.drive.content_store import (
    ContentStore,
    canonical_genome_payload,
    canonical_json,
    genome_hash,
    hash_bytes,
    hash_payload,
)
from agentdrive.drive.drive import AgentDrive
from agentdrive.genome.models import Genome, GenomeManifest
from agentdrive.registry import GenomeRegistry

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_genome(gid: str = "test-cap", framework: dict | None = None) -> Genome:
    framework = framework if framework is not None else {"steps": [{"id": "1", "name": "do"}]}
    manifest = GenomeManifest(
        id=gid,
        version="1.0.0",
        content_hash="sha256:pending",
        created=datetime.now(UTC),
        authors=[],
    )
    return Genome(manifest=manifest, framework=framework)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Determinism — the hash MUST NOT depend on incidental ordering
# ─────────────────────────────────────────────────────────────────────────────


def test_canonical_json_is_key_order_independent() -> None:
    a = canonical_json({"b": 1, "a": 2, "c": {"y": 1, "x": 2}})
    b = canonical_json({"a": 2, "c": {"x": 2, "y": 1}, "b": 1})
    assert a == b
    assert hash_bytes(a) == hash_bytes(b)


def test_hash_payload_stable_across_calls() -> None:
    payload = {"framework": {"steps": [{"id": "1", "name": "ok"}]}}
    first = hash_payload(payload)
    for _ in range(5):
        assert hash_payload(payload) == first


def test_genome_hash_matches_models_compute_content_hash() -> None:
    """``Genome.compute_content_hash()`` and ``content_store.genome_hash()``
    MUST agree. They're two paths to the same idea; if they drift, every
    cross-layer assumption (ingest log content_hash, supersedes references)
    silently corrupts.
    """
    g = _make_genome()
    assert genome_hash(g) == g.compute_content_hash()


def test_genome_hash_matches_compute_content_hash_with_unicode() -> None:
    """Regression: the legacy compute_content_hash used ensure_ascii=True
    while the new canonical_json uses ensure_ascii=False, producing different
    bytes (and different hashes) for any content containing non-ASCII
    characters — em-dashes, smart quotes, accented names, anything.
    A real session caught this in smoke. Lock it in here so it never drifts."""
    g = _make_genome(
        framework={
            "steps": [
                {"id": "1", "name": "Audit the surface — class, kwarg, env, log"},
                {"id": "2", "name": "Don't sed across layers in one pass"},
            ],
        }
    )
    assert genome_hash(g) == g.compute_content_hash()


def test_two_genomes_with_same_content_hash_identical() -> None:
    g1 = _make_genome(gid="alpha")
    g2 = _make_genome(gid="beta")  # different id, identical content
    assert genome_hash(g1) == genome_hash(g2)


def test_canonical_payload_omits_observation_metadata() -> None:
    """Content hash is identity, not provenance. Authors / timestamps /
    scores belong in the manifest, NOT in the hashed payload."""
    payload = canonical_genome_payload(_make_genome())
    assert set(payload.keys()) == {
        "framework",
        "reasoning_patterns",
        "tool_compositions",
        "evaluations",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. Store mechanics — write, read, dedup
# ─────────────────────────────────────────────────────────────────────────────


def test_put_then_get_roundtrips(tmp_path: Path) -> None:
    store = ContentStore(tmp_path)
    payload = {"framework": {"steps": []}}
    put = store.put_payload(payload)

    assert put.existed is False
    assert put.path.exists()
    assert put.path.read_bytes() == canonical_json(payload)
    assert store.get_payload(put.hash) == payload


def test_put_same_payload_twice_dedups(tmp_path: Path) -> None:
    store = ContentStore(tmp_path)
    payload = {"framework": {"steps": [{"id": "1"}]}}

    first = store.put_payload(payload)
    second = store.put_payload(payload)

    assert first.hash == second.hash
    assert first.path == second.path
    assert second.existed is True, "second put of identical bytes must be a dedup hit"
    assert store.count() == 1


def test_put_different_payloads_distinct_paths(tmp_path: Path) -> None:
    store = ContentStore(tmp_path)
    store.put_payload({"framework": {"steps": [{"id": "1"}]}})
    store.put_payload({"framework": {"steps": [{"id": "2"}]}})
    assert store.count() == 2


def test_put_genome_uses_content_payload_not_full_model(tmp_path: Path) -> None:
    """Two Genomes with same content but different manifests must dedup —
    that's the whole point. Manifest data must not enter the hash."""
    store = ContentStore(tmp_path)
    g1 = _make_genome(gid="alpha")
    g2 = _make_genome(gid="beta")  # different id, identical framework

    put1 = store.put_genome(g1)
    put2 = store.put_genome(g2)

    assert put1.hash == put2.hash
    assert put2.existed is True
    assert store.count() == 1


def test_get_missing_returns_none(tmp_path: Path) -> None:
    store = ContentStore(tmp_path)
    fake = "sha256:" + "0" * 64
    assert store.has(fake) is False
    assert store.get_bytes(fake) is None
    assert store.get_payload(fake) is None


def test_invalid_hash_format_rejected(tmp_path: Path) -> None:
    store = ContentStore(tmp_path)
    with pytest.raises(ValueError):
        store.put_bytes("md5:nope", b"x")
    with pytest.raises(ValueError):
        store.put_bytes("sha256:x", b"x")  # too short


def test_sharded_layout(tmp_path: Path) -> None:
    """objects/<aa>/<rest>.json — two-char shard prefix.
    Validates the on-disk layout assumption that backups / migration / GC tools
    will rely on.
    """
    store = ContentStore(tmp_path)
    put = store.put_payload({"x": 1})

    rel = put.path.relative_to(tmp_path / "objects")
    parts = rel.parts
    assert len(parts) == 2
    assert len(parts[0]) == 2
    assert parts[1].endswith(".json")
    # Hex chars only — no accidental path-traversal characters.
    assert all(c in "0123456789abcdef" for c in parts[0])


def test_iter_hashes_finds_what_was_put(tmp_path: Path) -> None:
    store = ContentStore(tmp_path)
    hashes = set()
    for i in range(5):
        hashes.add(store.put_payload({"i": i}).hash)
    assert set(store.iter_hashes()) == hashes


# ─────────────────────────────────────────────────────────────────────────────
# 3. Drive integration — ingest writes to BOTH registry and content store
# ─────────────────────────────────────────────────────────────────────────────


def test_drive_ingest_populates_content_store(tmp_path: Path) -> None:
    """A successful ingest must leave the Genome both in the registry AND in
    the content-addressed store. The ingest-log entry records both paths and
    the content hash."""
    drive = AgentDrive(
        registry=GenomeRegistry(root=tmp_path / "genomes"),
        drive_path=tmp_path,
    )
    g = _make_genome()
    expected_hash = genome_hash(g)

    drive.ingest(g, source="test")

    assert drive.has_content(expected_hash), "ingest must populate the content store"
    assert drive.content_count() == 1

    # Ingest log carries the content hash for downstream provenance walks.
    log = drive.get_ingest_history(limit=1)
    assert log
    assert log[0]["content_hash"] == expected_hash
    assert log[0]["deduped"] is False


def test_drive_ingest_dedups_on_repeat_content(tmp_path: Path) -> None:
    """Same content ingested twice → registry may grow (id/version differ)
    but the content store stays at one object. The 'deduped' flag in the
    ingest log is how operators see the saving."""
    drive = AgentDrive(
        registry=GenomeRegistry(root=tmp_path / "genomes"),
        drive_path=tmp_path,
    )
    drive.ingest(_make_genome(gid="alpha"), source="test")
    drive.ingest(_make_genome(gid="beta"), source="test")  # different id, same content

    assert drive.content_count() == 1, "identical content → one object"
    log = drive.get_ingest_history(limit=2)
    deduped_flags = [e["deduped"] for e in log]
    # At least one of the two was a dedup hit.
    assert True in deduped_flags


def test_drive_get_content_returns_canonical_payload(tmp_path: Path) -> None:
    drive = AgentDrive(
        registry=GenomeRegistry(root=tmp_path / "genomes"),
        drive_path=tmp_path,
    )
    g = _make_genome()
    drive.ingest(g, source="test")

    payload = drive.get_content(genome_hash(g))
    assert payload is not None
    assert payload == canonical_genome_payload(g)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Supersedes-DAG — the lineage edge introduced in this milestone
# ─────────────────────────────────────────────────────────────────────────────


def test_manifest_supersedes_field_defaults_empty() -> None:
    g = _make_genome()
    assert g.manifest.supersedes == []


def test_manifest_supersedes_round_trips_through_save_load(tmp_path: Path) -> None:
    parent = _make_genome(gid="parent-cap")
    parent_hash = genome_hash(parent)

    child = _make_genome(gid="child-cap", framework={"steps": [{"id": "2", "name": "improved"}]})
    child.manifest.supersedes = [parent_hash]

    save_dir = tmp_path / "child"
    child.save(save_dir)
    loaded = Genome.load(save_dir)
    assert loaded.manifest.supersedes == [parent_hash]
