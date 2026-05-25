"""v2 / Milestone 2a — shared swarm Drive.

Two guarantees that have to hold:

1. All sub-agents in a swarm land on the **same** AgentDrive instance,
   backed by ``<swarms>/<swarm_id>/drive/`` — not the default Drive, not
   per-sub-agent subdirectories. The v1 bug where ``get_or_create_pool``
   returned a Drive pointing at the default location must be gone.
2. Writes from different sub-agents into the shared Drive are correctly
   attributed via the Genome author field, and the Drive exposes them
   via ``writers()`` and ``genomes_by_subagent()``.

Membership tracking (``list_active_swarms`` showing both sub-agents as
members of the same swarm) is the auxiliary signal that the manager
correctly handled the cache-hit path for the second sub-agent.

Tests rely on the autouse ``isolated_savant_home`` fixture from conftest
to scope ``~/.agentdrive`` to a temp dir per test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from agentdrive.constants import get_swarm_drive_path
from agentdrive.drive.swarm_manager import SwarmDriveManager
from agentdrive.drive.swarm_policy import SwarmDrivePolicy
from agentdrive.genome.models import Genome, GenomeManifest


def _make_genome(gid: str, framework: dict | None = None) -> Genome:
    return Genome(
        manifest=GenomeManifest(
            id=gid,
            version="1.0.0",
            content_hash="sha256:pending",
            created=datetime.now(UTC),
            authors=[],
        ),
        framework=framework or {"steps": [{"id": "1", "name": "do"}]},
    )


# ─────────────────────────────────────────────────────────────────────
# 1. Path + cache behavior
# ─────────────────────────────────────────────────────────────────────


def test_get_swarm_drive_path_is_subagent_agnostic(isolated_savant_home: Path) -> None:
    """v1 path encoded subagent into the directory; v2 collapses to per-swarm.
    Backwards-compatible signature, new behavior."""
    base = get_swarm_drive_path("alpha")
    with_a = get_swarm_drive_path("alpha", "worker-a")
    with_b = get_swarm_drive_path("alpha", "worker-b")

    assert base == with_a == with_b, "all sub-agents in a swarm share one Drive path"
    assert base.parent.name == "alpha"
    assert base.name == "drive"


def test_two_subagents_get_same_drive_instance(isolated_savant_home: Path) -> None:
    """Calling get_or_create_pool with two different sub-agent IDs but the
    same swarm returns the SAME AgentDrive object. The v1 bug returned a
    fresh-but-broken Drive each time."""
    mgr = SwarmDriveManager()

    drive_a = mgr.get_or_create_pool(swarm_id="beta", subagent_id="worker-a")
    drive_b = mgr.get_or_create_pool(swarm_id="beta", subagent_id="worker-b")

    assert drive_a is drive_b, "siblings in the same swarm must share one Drive"


def test_drive_path_is_the_real_swarm_path(isolated_savant_home: Path) -> None:
    """v1 bug regression: the constructed Drive's drive_path used to default
    to the global Drive, not the swarm path. Lock that down."""
    mgr = SwarmDriveManager()

    drive = mgr.get_or_create_pool(swarm_id="gamma", subagent_id="lead")

    expected = isolated_savant_home / "swarms" / "gamma" / "drive"
    assert drive.drive_path == expected, (
        f"Drive landed at {drive.drive_path}, expected {expected} — "
        "the drive_path bug surfaced by examples/03_swarm.py is back"
    )


def test_different_swarms_get_different_drives(isolated_savant_home: Path) -> None:
    mgr = SwarmDriveManager()

    delta = mgr.get_or_create_pool(swarm_id="delta", subagent_id="a")
    epsilon = mgr.get_or_create_pool(swarm_id="epsilon", subagent_id="a")

    assert delta is not epsilon
    assert delta.drive_path != epsilon.drive_path


# ─────────────────────────────────────────────────────────────────────
# 2. Membership tracking
# ─────────────────────────────────────────────────────────────────────


def test_swarm_tracks_all_subagent_members(isolated_savant_home: Path) -> None:
    """Both first-create and cache-hit paths must register the sub-agent."""
    mgr = SwarmDriveManager()

    mgr.get_or_create_pool(swarm_id="zeta", subagent_id="alpha-worker")
    mgr.get_or_create_pool(swarm_id="zeta", subagent_id="beta-worker")  # cache hit
    mgr.get_or_create_pool(swarm_id="zeta", subagent_id="gamma-worker")

    swarms = mgr.list_active_swarms()
    assert "zeta" in swarms
    assert set(swarms["zeta"]["members"]) == {"alpha-worker", "beta-worker", "gamma-worker"}


# ─────────────────────────────────────────────────────────────────────
# 3. Sibling attribution — the sibling-learning primitive
# ─────────────────────────────────────────────────────────────────────


def test_subagent_writes_are_author_tagged(isolated_savant_home: Path) -> None:
    """A Genome ingested with subagent_id gets an author entry stamped
    ``sub:<id>`` so siblings can attribute and filter each other's work."""
    mgr = SwarmDriveManager()
    drive = mgr.get_or_create_pool(swarm_id="eta", subagent_id="planner")

    g = _make_genome("plan-cap")
    drive.ingest(g, source="test", subagent_id="planner")

    author_ids = [a.id for a in g.manifest.authors]
    assert "sub:planner" in author_ids


def test_subagent_writes_dont_double_tag(isolated_savant_home: Path) -> None:
    """Re-ingesting the same Genome from the same sub-agent must not pile
    up duplicate author entries."""
    mgr = SwarmDriveManager()
    drive = mgr.get_or_create_pool(swarm_id="theta", subagent_id="planner")

    g = _make_genome("idempotent-cap")
    drive.ingest(g, source="test", subagent_id="planner")
    drive.ingest(g, source="test", subagent_id="planner")
    drive.ingest(g, source="test", subagent_id="planner")

    tagged = [a for a in g.manifest.authors if a.id == "sub:planner"]
    assert len(tagged) == 1, "author tag must be idempotent across re-ingest"


def test_writers_lists_every_subagent_that_contributed(isolated_savant_home: Path) -> None:
    mgr = SwarmDriveManager()
    drive = mgr.get_or_create_pool(swarm_id="iota", subagent_id="root")

    drive.ingest(_make_genome("planner-cap-1"), source="test", subagent_id="planner")
    drive.ingest(_make_genome("planner-cap-2"), source="test", subagent_id="planner")
    drive.ingest(_make_genome("critic-cap-1"), source="test", subagent_id="critic")
    drive.ingest(_make_genome("anon-cap"), source="test")  # no subagent_id

    assert drive.writers() == ["critic", "planner"]


def test_genomes_by_subagent_filters_correctly(isolated_savant_home: Path) -> None:
    """The sibling-learning query: 'what did cousin-B write?'"""
    mgr = SwarmDriveManager()
    drive = mgr.get_or_create_pool(swarm_id="kappa", subagent_id="root")

    drive.ingest(_make_genome("a-cap-1"), source="test", subagent_id="alpha")
    drive.ingest(_make_genome("b-cap-1"), source="test", subagent_id="beta")
    drive.ingest(_make_genome("b-cap-2"), source="test", subagent_id="beta")

    a_entries = drive.genomes_by_subagent("alpha")
    b_entries = drive.genomes_by_subagent("beta")

    assert len(a_entries) == 1
    assert len(b_entries) == 2
    assert all(e["subagent_id"] == "beta" for e in b_entries)


# ─────────────────────────────────────────────────────────────────────
# 4. The sibling-learning scenario end-to-end
# ─────────────────────────────────────────────────────────────────────


def test_sibling_can_read_what_another_sibling_wrote(isolated_savant_home: Path) -> None:
    """The whole point of Milestone 2a — sub-agent A writes, sub-agent B
    obtains the same Drive instance and sees A's work without any
    cross-config required."""
    mgr = SwarmDriveManager()

    drive_a = mgr.get_or_create_pool(swarm_id="lambda", subagent_id="agent-a")
    drive_a.ingest(
        _make_genome("postmortem-cap"),
        source="agent-a",
        subagent_id="agent-a",
    )

    drive_b = mgr.get_or_create_pool(swarm_id="lambda", subagent_id="agent-b")
    # Same Drive, so the content-store hash count includes agent-a's work.
    assert drive_b.content_count() >= 1, "agent-b must see agent-a's writes in the shared Drive"

    # agent-b can ask 'what did agent-a write?'
    a_writes = drive_b.genomes_by_subagent("agent-a")
    assert any(e["genome_id"].startswith("postmortem-cap") for e in a_writes)


# ─────────────────────────────────────────────────────────────────────
# 5. Policy defaults — sibling sharing is now on
# ─────────────────────────────────────────────────────────────────────


def test_default_policy_allows_sibling_sharing() -> None:
    """v2 / Milestone 2a flip: out of the box, siblings see each other's work."""
    policy = SwarmDrivePolicy()
    assert policy.isolation_level == "swarm"
    assert policy.sibling_sharing == "read"
