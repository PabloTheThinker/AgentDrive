"""Integration tests for v2 / M4 ingest behavior — CRDT merge + conflict copies.

Two scenarios actually matter end-to-end:

1. Two siblings ingest the same crdt-counter / crdt-set Genome with different
   per-actor state. The registry must end up with one Genome whose state is the
   commutative merge. Insertion order must not affect the result.
2. Two siblings ingest the same last-write Genome with different content. The
   first wins, the second becomes a conflict copy at ``<id>-conflict-<sha8>-<actor>``.
   The original is untouched.

Both must be flag-controllable so an operator can fall back to v1 behavior
during incident response.
"""

from __future__ import annotations

from typing import Any

import pytest

from agentdrive.drive.drive import AgentDrive
from agentdrive.genome.models import Genome


def _counter_genome(
    gid: str,
    state: dict[str, int],
    *,
    author: str = "sub:alpha",
) -> Genome:
    return Genome(
        manifest={
            "id": gid,
            "version": "1.0.0",
            "content_hash": "sha256:pending",
            "created": "2026-05-25T00:00:00",
            "authors": [{"type": "agent", "id": author, "name": author}],
            "merge_strategy": "crdt-counter",
            "crdt_state": state,
        },
    )


def _set_genome(gid: str, members: list[str], *, author: str = "sub:alpha") -> Genome:
    return Genome(
        manifest={
            "id": gid,
            "version": "1.0.0",
            "content_hash": "sha256:pending",
            "created": "2026-05-25T00:00:00",
            "authors": [{"type": "agent", "id": author, "name": author}],
            "merge_strategy": "crdt-set",
            "crdt_state": {"members": members},
        },
    )


def _lw_genome(gid: str, body: dict[str, Any], *, author: str = "sub:alpha") -> Genome:
    return Genome(
        manifest={
            "id": gid,
            "version": "1.0.0",
            "content_hash": "sha256:pending",
            "created": "2026-05-25T00:00:00",
            "authors": [{"type": "agent", "id": author, "name": author}],
        },
        framework=body,
    )


# ─── CRDT counter ───────────────────────────────────────────────────────────


def test_two_sibling_counters_merge() -> None:
    drive = AgentDrive()
    drive.ingest(
        _counter_genome("pattern-hits", {"sub-a": 3}, author="sub:a"),
        source="sibling-a",
    )
    drive.ingest(
        _counter_genome("pattern-hits", {"sub-b": 5}, author="sub:b"),
        source="sibling-b",
    )
    latest = drive.registry.load("pattern-hits")
    assert latest is not None
    assert latest.manifest.merge_strategy == "crdt-counter"
    assert latest.manifest.crdt_state == {"sub-a": 3, "sub-b": 5}


def test_counter_merge_idempotent_under_replay() -> None:
    drive = AgentDrive()
    g = _counter_genome("retries", {"sub-a": 10}, author="sub:a")
    drive.ingest(g, source="replay")
    drive.ingest(g, source="replay")
    drive.ingest(g, source="replay")
    latest = drive.registry.load("retries")
    assert latest is not None
    assert latest.manifest.crdt_state == {"sub-a": 10}


# ─── CRDT set ───────────────────────────────────────────────────────────────


def test_two_sibling_sets_union() -> None:
    drive = AgentDrive()
    drive.ingest(
        _set_genome("executed-hashes", ["aaa", "bbb"], author="sub:a"),
        source="sibling-a",
    )
    drive.ingest(
        _set_genome("executed-hashes", ["bbb", "ccc"], author="sub:b"),
        source="sibling-b",
    )
    latest = drive.registry.load("executed-hashes")
    assert latest is not None
    assert latest.manifest.crdt_state == {"members": ["aaa", "bbb", "ccc"]}


# ─── Last-write conflict copy ───────────────────────────────────────────────


def test_last_write_collision_emits_conflict_copy() -> None:
    drive = AgentDrive()
    drive.ingest(
        _lw_genome("plan", {"steps": ["first"]}, author="sub:a"),
        source="first-writer",
        actor="sub:a",
    )
    drive.ingest(
        _lw_genome("plan", {"steps": ["second"]}, author="sub:b"),
        source="second-writer",
        actor="sub:b",
    )

    # Original is untouched
    original = drive.registry.load("plan")
    assert original is not None
    assert original.framework == {"steps": ["first"]}

    # Conflict copy lives under plan-conflict-*-sub-b. The registry lists ids
    # with their version subdir suffix, so we slice the leading id segment.
    all_ids = {name for name in drive.registry.list_genomes()}
    conflict_ids = [name.split("/", 1)[0] for name in all_ids if name.startswith("plan-conflict-")]
    assert len(conflict_ids) == 1
    assert conflict_ids[0].endswith("-sub-b")


def test_identical_last_write_is_dedup_not_conflict() -> None:
    drive = AgentDrive()
    g = _lw_genome("dedup-target", {"steps": ["same"]}, author="sub:a")
    drive.ingest(g, source="first", actor="sub:a")
    # Re-finalize hash on a fresh instance with the same content
    g2 = _lw_genome("dedup-target", {"steps": ["same"]}, author="sub:a")
    drive.ingest(g2, source="retry", actor="sub:a")
    all_ids = {name for name in drive.registry.list_genomes()}
    conflict_ids = [name for name in all_ids if name.startswith("dedup-target-conflict-")]
    assert conflict_ids == []


def test_m4_disabled_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """When AGENTDRIVE_M4_DISABLE=1, last-write collisions skip the conflict
    copy emission — the registry just overwrites (v1 behavior)."""
    monkeypatch.setenv("AGENTDRIVE_M4_DISABLE", "1")
    drive = AgentDrive()
    drive.ingest(_lw_genome("legacy", {"steps": ["a"]}), source="first")
    drive.ingest(_lw_genome("legacy", {"steps": ["b"]}), source="second")
    all_ids = {name for name in drive.registry.list_genomes()}
    conflict_ids = [name for name in all_ids if name.startswith("legacy-conflict-")]
    assert conflict_ids == []
