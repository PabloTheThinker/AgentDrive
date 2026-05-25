"""Unit tests for v2 / M4 CRDT primitives — drive/crdt.py.

The merge functions are the load-bearing pieces of M4. Two siblings on a shared
swarm Drive race each other; their writes have to reconcile *the same way* no
matter which order the parent sees them. That's the commutative + associative +
idempotent contract these tests pin down. If any of these break, sibling
learning silently diverges between devices.
"""

from __future__ import annotations

import pytest

from agentdrive.drive.crdt import merge_counters, merge_sets, render_counter

# ─── counter merge ──────────────────────────────────────────────────────────


def test_counter_merge_commutative() -> None:
    a = {"sub-a": 3, "sub-b": 5}
    b = {"sub-b": 2, "sub-c": 7}
    assert merge_counters(a, b) == merge_counters(b, a)


def test_counter_merge_idempotent() -> None:
    a = {"sub-a": 3, "sub-b": 5}
    once = merge_counters(a, a)
    twice = merge_counters(once, a)
    assert once == a
    assert twice == a


def test_counter_merge_associative() -> None:
    a = {"sub-a": 1}
    b = {"sub-b": 2}
    c = {"sub-a": 4, "sub-c": 3}
    left = merge_counters(merge_counters(a, b), c)
    right = merge_counters(a, merge_counters(b, c))
    assert left == right == {"sub-a": 4, "sub-b": 2, "sub-c": 3}


def test_counter_per_actor_max_wins() -> None:
    a = {"sub-a": 10}
    b = {"sub-a": 3}
    assert merge_counters(a, b) == {"sub-a": 10}


def test_negative_counter_rejected() -> None:
    with pytest.raises(ValueError):
        merge_counters({"sub-a": -1}, {})
    with pytest.raises(ValueError):
        merge_counters({}, {"sub-b": -1})


def test_counter_type_validation() -> None:
    with pytest.raises(TypeError):
        merge_counters({"sub-a": "3"}, {})  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        merge_counters("not a dict", {})  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        merge_counters({1: 3}, {})  # type: ignore[dict-item]


def test_render_counter_sums_actors() -> None:
    assert render_counter({"sub-a": 3, "sub-b": 5, "sub-c": 7}) == 15
    assert render_counter({}) == 0


# ─── set merge ──────────────────────────────────────────────────────────────


def test_set_merge_commutative() -> None:
    a = ["x", "y", "z"]
    b = ["y", "w"]
    assert merge_sets(a, b) == merge_sets(b, a) == ["w", "x", "y", "z"]


def test_set_merge_idempotent() -> None:
    a = ["x", "y", "z"]
    once = merge_sets(a, a)
    assert once == sorted(set(a))
    assert merge_sets(once, a) == once


def test_set_merge_associative() -> None:
    a = ["x", "y"]
    b = ["y", "z"]
    c = ["q"]
    left = merge_sets(merge_sets(a, b), c)
    right = merge_sets(a, merge_sets(b, c))
    assert left == right == ["q", "x", "y", "z"]


def test_set_merge_deterministic_order() -> None:
    # Two different insertion orders MUST produce byte-identical lists so
    # content-addressing of the merged Genome stays stable.
    assert merge_sets(["b", "a"], ["c"]) == merge_sets(["c"], ["a", "b"])


def test_set_rejects_non_string_members() -> None:
    with pytest.raises(TypeError):
        merge_sets(["a", 1], ["b"])  # type: ignore[list-item]
    with pytest.raises(TypeError):
        merge_sets(["a"], [None])  # type: ignore[list-item]
