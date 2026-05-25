"""v2 / Milestone 2b — DNA Drive forward-only with ancestry closure table.

The load-bearing guarantees:

1. **Ancestry is a DAG by construction.** Cycles are impossible because
   a child must reference parents that already exist, and the
   ``created_at`` timestamp invariant is enforced at write time.
2. **Forward-only inheritance works end-to-end.** An agent's
   ``pull_inherited()`` returns Genomes published by every direct ancestor,
   with correct hop depth and full provenance.
3. **No decay.** Inherited Genomes don't expire — once in the lineage,
   always accessible (the Avatar mental model Pablo specified).
4. **Multi-parent DAG handled correctly.** When an agent has two parents
   that share a grandparent, the closure table records the SHORTER path
   to the shared ancestor.
5. **Eval gating works** — ``min_eval`` filters out low-quality inherited
   Genomes when the operator opts in.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from agentdrive.dna import Ancestry, AncestryClosureError, DNADrive
from agentdrive.genome.models import Genome


def _make_genome(gid: str, eval_score: float = 0.0) -> Genome:
    # eval_score goes into Genome.evaluations (the content field that travels
    # through the content store), NOT manifest.evaluation_score (observation
    # metadata that doesn't survive content-addressed inheritance). The DNA
    # Drive's min_eval gate reads the content-side field.
    return Genome.create(
        id=gid,
        version="1.0.0",
        framework={"steps": [{"id": "1", "name": gid}]},
        evaluations={"reference_tasks": eval_score} if eval_score else {},
    )


# ─────────────────────────────────────────────────────────────────────
# Ancestry — the closure table
# ─────────────────────────────────────────────────────────────────────


def test_root_agent_has_no_ancestors(tmp_path: Path) -> None:
    a = Ancestry(tmp_path / "ancestry.db")
    a.add_agent("root")

    assert a.ancestors_of("root") == []
    assert a.ancestors_of("root", include_self=True) == [("root", 0)]


def test_linear_chain_records_correct_depths(tmp_path: Path) -> None:
    a = Ancestry(tmp_path / "ancestry.db")
    a.add_agent("g0", created_at=1.0)
    a.add_agent("g1", parents=["g0"], created_at=2.0)
    a.add_agent("g2", parents=["g1"], created_at=3.0)
    a.add_agent("g3", parents=["g2"], created_at=4.0)

    assert a.ancestors_of("g3") == [("g2", 1), ("g1", 2), ("g0", 3)]
    assert a.descendants_of("g0") == [("g1", 1), ("g2", 2), ("g3", 3)]


def test_multi_parent_picks_shortest_path_to_shared_ancestor(tmp_path: Path) -> None:
    """The diamond pattern:
            g0
           /  \\
          g1   g2
           \\ /
            g3 (parents: g1, g2)
    g0 should appear as ancestor of g3 at depth=2 (the shortest), exactly once.
    """
    a = Ancestry(tmp_path / "ancestry.db")
    a.add_agent("g0", created_at=1.0)
    a.add_agent("g1", parents=["g0"], created_at=2.0)
    a.add_agent("g2", parents=["g0"], created_at=2.5)
    a.add_agent("g3", parents=["g1", "g2"], created_at=3.0)

    ancestors = a.ancestors_of("g3")
    g0_entries = [(aid, d) for aid, d in ancestors if aid == "g0"]
    assert g0_entries == [("g0", 2)], "shared ancestor must appear once at shortest depth"


def test_cycles_impossible_via_timestamp_invariant(tmp_path: Path) -> None:
    """An older agent cannot claim a younger agent as parent."""
    a = Ancestry(tmp_path / "ancestry.db")
    a.add_agent("young", created_at=10.0)
    with pytest.raises(AncestryClosureError, match="must be younger than parent"):
        a.add_agent("old", parents=["young"], created_at=5.0)


def test_parents_must_exist(tmp_path: Path) -> None:
    a = Ancestry(tmp_path / "ancestry.db")
    with pytest.raises(AncestryClosureError, match="does not exist"):
        a.add_agent("orphan", parents=["nonexistent"])


def test_add_agent_is_idempotent_with_matching_parents(tmp_path: Path) -> None:
    a = Ancestry(tmp_path / "ancestry.db")
    a.add_agent("p", created_at=1.0)
    a.add_agent("c", parents=["p"], created_at=2.0)

    # Same parents — no-op.
    a.add_agent("c", parents=["p"], created_at=99.0)
    assert a.parents_of("c") == ["p"]


def test_add_agent_with_different_parents_raises(tmp_path: Path) -> None:
    a = Ancestry(tmp_path / "ancestry.db")
    a.add_agent("p1", created_at=1.0)
    a.add_agent("p2", created_at=1.5)
    a.add_agent("c", parents=["p1"], created_at=2.0)

    with pytest.raises(AncestryClosureError, match="different parents"):
        a.add_agent("c", parents=["p2"], created_at=2.0)


def test_max_depth_filters_far_ancestors(tmp_path: Path) -> None:
    a = Ancestry(tmp_path / "ancestry.db")
    for i in range(5):
        a.add_agent(f"g{i}", parents=[f"g{i - 1}"] if i else [], created_at=float(i))

    assert a.ancestors_of("g4", max_depth=2) == [("g3", 1), ("g2", 2)]


# ─────────────────────────────────────────────────────────────────────
# DNADrive — the inheritance read path
# ─────────────────────────────────────────────────────────────────────


def test_root_agent_pulls_nothing(isolated_savant_home: Path) -> None:
    root = DNADrive("root-agent")
    assert root.pull_inherited() == []


def test_child_inherits_parent_genome(isolated_savant_home: Path) -> None:
    parent = DNADrive("parent-agent")
    parent.publish(_make_genome("parent-cap"))
    # Brief sleep so the child's created_at is strictly greater.
    time.sleep(0.01)

    child = DNADrive("child-agent", parents=["parent-agent"])

    inherited = child.pull_inherited()
    assert len(inherited) == 1
    assert inherited[0].source_agent == "parent-agent"
    assert inherited[0].depth == 1


def test_grandchild_inherits_full_lineage_with_correct_depths(
    isolated_savant_home: Path,
) -> None:
    grandparent = DNADrive("grandparent")
    grandparent.publish(_make_genome("ancestral-wisdom"))
    time.sleep(0.01)

    parent = DNADrive("parent", parents=["grandparent"])
    parent.publish(_make_genome("parent-wisdom"))
    time.sleep(0.01)

    child = DNADrive("child", parents=["parent"])
    inherited = child.pull_inherited()

    by_source = {ig.source_agent: ig.depth for ig in inherited}
    assert by_source == {"parent": 1, "grandparent": 2}


def test_inherited_results_are_depth_sorted(isolated_savant_home: Path) -> None:
    """Closer ancestors first — relevance ordering for the Harness query."""
    g0 = DNADrive("g0")
    g0.publish(_make_genome("a"))
    time.sleep(0.01)
    g1 = DNADrive("g1", parents=["g0"])
    g1.publish(_make_genome("b"))
    time.sleep(0.01)
    g2 = DNADrive("g2", parents=["g1"])
    g2.publish(_make_genome("c"))
    time.sleep(0.01)

    g3 = DNADrive("g3", parents=["g2"])
    depths = [ig.depth for ig in g3.pull_inherited()]
    assert depths == sorted(depths), "results must be sorted by depth ascending"


def test_min_eval_gate_filters_low_score_genomes(isolated_savant_home: Path) -> None:
    parent = DNADrive("p")
    parent.publish(_make_genome("good-cap", eval_score=0.9))
    parent.publish(_make_genome("weak-cap", eval_score=0.3))
    time.sleep(0.01)

    child = DNADrive("c", parents=["p"])

    all_inherited = child.pull_inherited()
    assert len(all_inherited) == 2

    gated = child.pull_inherited(min_eval=0.7)
    assert len(gated) == 1
    # Confirm the surviving one is the high-score Genome.
    framework_step = gated[0].payload["framework"]["steps"][0]["name"]
    assert framework_step == "good-cap"


def test_pull_inherited_does_not_include_own_by_default(
    isolated_savant_home: Path,
) -> None:
    """include_self=False by default — pull_inherited surfaces ancestors,
    not the agent's own published Genomes (that's what own() is for)."""
    parent = DNADrive("p")
    parent.publish(_make_genome("p-cap"))
    time.sleep(0.01)

    child = DNADrive("c", parents=["p"])
    child.publish(_make_genome("c-cap"))

    inherited = child.pull_inherited()
    sources = {ig.source_agent for ig in inherited}
    assert sources == {"p"}, "own published Genomes should not appear in pull_inherited()"

    own_hashes = child.own()
    assert len(own_hashes) == 1


def test_diamond_inheritance_does_not_duplicate_shared_ancestor_genomes(
    isolated_savant_home: Path,
) -> None:
    """If g3 has two parents (g1, g2) that share a grandparent g0,
    g0's Genomes should appear ONCE in the inherited list, not twice."""
    g0 = DNADrive("g0")
    g0.publish(_make_genome("ancestral"))
    time.sleep(0.01)
    DNADrive("g1", parents=["g0"])
    time.sleep(0.01)
    DNADrive("g2", parents=["g0"])
    time.sleep(0.01)
    g3 = DNADrive("g3", parents=["g1", "g2"])

    inherited = g3.pull_inherited()
    g0_entries = [ig for ig in inherited if ig.source_agent == "g0"]
    assert len(g0_entries) == 1, "shared ancestor's Genome must surface exactly once"
    assert g0_entries[0].depth == 2, "should report shortest path to shared ancestor"


def test_lineage_helper_returns_full_ancestry(isolated_savant_home: Path) -> None:
    DNADrive("g0")
    time.sleep(0.01)
    DNADrive("g1", parents=["g0"])
    time.sleep(0.01)
    g2 = DNADrive("g2", parents=["g1"])

    assert g2.lineage() == [("g1", 1), ("g0", 2)]
