"""CRDT primitives for AgentDrive v2 / Milestone 4.

Two strategies, both add-only in v1 (removals deliberately deferred):

* ``crdt-counter`` — per-actor max merge, summed across actors. This is a
  PN-Counter without the negative half: each actor's local count only grows,
  and the global render is the sum of those per-actor maxes. Decrements would
  require an OR-Set-style tombstone; we accept the simpler shape now and can
  upgrade later without breaking on-disk state.

* ``crdt-set`` — grow-only set (G-Set). Membership is the deterministic union;
  removals are not expressible. Same upgrade story as the counter.

Both ``merge_counters`` and ``merge_sets`` are pure, total, associative,
commutative, and idempotent. Inputs are validated; negative counter values are
rejected at the boundary so corrupt state cannot poison a merge.
"""

from __future__ import annotations

from typing import Iterable


def merge_counters(a: dict[str, int], b: dict[str, int]) -> dict[str, int]:
    """Per-actor max merge for crdt-counter state.

    Each key is an actor id (sub-agent id, peer id, etc.); each value is that
    actor's monotonically increasing local count. The merged state takes the
    max per actor — that's the LUB of two states reachable from the same
    history. Associative, commutative, idempotent.
    """
    _validate_counter(a)
    _validate_counter(b)
    out: dict[str, int] = dict(a)
    for actor, value in b.items():
        if value > out.get(actor, 0):
            out[actor] = value
    return out


def merge_sets(a: Iterable[str], b: Iterable[str]) -> list[str]:
    """Grow-only set union, deterministically sorted.

    Returns a sorted list so two devices that merge in different orders end
    up with byte-identical state — important for content-addressing the
    merged Genome.
    """
    members: set[str] = set()
    for item in a:
        if not isinstance(item, str):
            raise TypeError(f"crdt-set members must be str, got {type(item).__name__}")
        members.add(item)
    for item in b:
        if not isinstance(item, str):
            raise TypeError(f"crdt-set members must be str, got {type(item).__name__}")
        members.add(item)
    return sorted(members)


def render_counter(state: dict[str, int]) -> int:
    """Collapse a crdt-counter state to its rendered total."""
    _validate_counter(state)
    return sum(state.values())


def _validate_counter(state: dict[str, int]) -> None:
    if not isinstance(state, dict):
        raise TypeError(f"crdt-counter state must be dict, got {type(state).__name__}")
    for actor, value in state.items():
        if not isinstance(actor, str):
            raise TypeError(f"crdt-counter actor key must be str, got {type(actor).__name__}")
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(
                f"crdt-counter value for {actor!r} must be int, got {type(value).__name__}"
            )
        if value < 0:
            raise ValueError(
                f"crdt-counter value for {actor!r} must be non-negative (got {value}); "
                "v1 is add-only — decrements are not supported"
            )
