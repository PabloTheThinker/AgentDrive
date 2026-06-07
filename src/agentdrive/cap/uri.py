"""Capability URI — human-readable wire form for a permission.

Grammar (informal):

    <scheme>:<action>:<resource>[:<key=value>...]

Examples:

    drive:read:swarm:demo-2026
    drive:write:swarm:demo-2026:sub=planner
    drive:read:object:sha256:abcdef...
    dna:pull:lineage:agent-7:max_hops=3:min_eval=0.7
    backup:restore:agent:agent-7

Schemes:
    drive  — Drive content surface (swarm, default, peer, object)
    dna    — DNA Drive surface (lineage, ancestor pulls)
    backup — Snapshot Backup surface (list / restore / pin)

Actions:
    read   — see the resource
    write  — add to the resource (ingest, publish, snapshot)
    exec   — act as the resource (sub-agent impersonation, restore)
    pull   — DNA-specific shorthand for "read ancestral Genomes from this lineage"

Resource selectors:
    object:<hash>          one specific content-addressed Genome
    swarm:<id>             entire swarm Drive (all sub-agents)
    swarm:<id>:sub=<sid>   single sub-agent's writes within a swarm
    agent:<id>             one agent's Personal Drive
    lineage:<ancestor_id>  DNA ancestral subtree rooted at ancestor_id
    peer:<peer_id>         federation peer

Attenuations (k=v after the resource):
    max_hops=<int>   DNA: limit depth from the resource
    min_eval=<f>     DNA / drive: minimum eval score for surfaced Genomes
    sub=<id>         drive: restrict to one sub-agent's namespace
    topic=<t>        any: restrict to one topic/domain
    expires=<unix>   any: hard expiry (separate from grant TTL for revocation flow)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


class CapURIError(ValueError):
    """Raised when a capability URI is malformed."""


_VALID_SCHEMES = {"drive", "dna", "backup", "mission"}
_VALID_ACTIONS = {"read", "write", "exec", "pull", "command"}
_VALID_RESOURCE_KINDS = {"object", "swarm", "agent", "lineage", "peer", "default", "control"}


@dataclass(frozen=True)
class Capability:
    """Structured form of a parsed capability URI.

    Frozen + slotted so caps are hashable, comparable, and cheap to pass
    around. Conversion back to the URI form via ``to_uri()`` is
    deterministic: keys are sorted, no incidental whitespace, so the
    same Capability always serializes to the same bytes (the property
    that makes signature verification reproducible).
    """

    scheme: str  # "drive" | "dna" | "backup"
    action: str  # "read" | "write" | "exec" | "pull"
    resource_kind: str  # "swarm" | "agent" | "object" | "lineage" | "peer" | "default"
    resource_id: str  # the identifier (swarm-name, agent-id, hash, etc.)
    attenuations: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    """Key/value attenuations as a sorted tuple-of-pairs. Sorted so the
    URI form is deterministic regardless of the order callers passed
    arguments. Stored as strings — typed parsing happens at use time."""

    def to_uri(self) -> str:
        # Always rebuild in canonical order: scheme:action:kind:id then sorted k=v.
        base = f"{self.scheme}:{self.action}:{self.resource_kind}:{self.resource_id}"
        if not self.attenuations:
            return base
        kv = ":".join(f"{k}={v}" for k, v in sorted(self.attenuations))
        return f"{base}:{kv}"

    def attenuation(self, key: str) -> str | None:
        for k, v in self.attenuations:
            if k == key:
                return v
        return None

    def with_attenuation(self, key: str, value: str) -> Capability:
        """Return a NEW Capability with one extra attenuation. Replacing
        an existing key returns the new value. Used by ``derive`` to
        produce narrower caps from broader ones."""
        merged: dict[str, str] = dict(self.attenuations)
        merged[key] = value
        return Capability(
            scheme=self.scheme,
            action=self.action,
            resource_kind=self.resource_kind,
            resource_id=self.resource_id,
            attenuations=tuple(sorted(merged.items())),
        )

    # ── narrowness check — the spine of subset minting and derivation ──────

    def is_narrower_than(self, other: Capability) -> bool:
        """True iff every action this cap authorizes is also authorized
        by ``other``. The fundamental ordering on capabilities.

        Used by the mint path: a holder can only mint caps that are
        narrower (or equal) to their own. Lifted out as a method so the
        same check serves derivation, verification, and policy.
        """
        if self.scheme != other.scheme:
            return False
        if not _action_covers(other.action, self.action):
            return False
        if not _resource_covers(other, self):
            return False
        # Every attenuation on `other` must also constrain `self` at least
        # as tightly. Attenuations only on `self` make it narrower — fine.
        for k, v in other.attenuations:
            self_v = self.attenuation(k)
            if self_v is None:
                # `other` says max_hops=3 but `self` is unbounded → wider, fail.
                return False
            if not _attenuation_at_least_as_tight(k, self_v, v):
                return False
        return True


# ─────────────────────────────────────────────────────────────────────
# Action / resource / attenuation coverage rules
# ─────────────────────────────────────────────────────────────────────


def _action_covers(broader: str, narrower: str) -> bool:
    """Does ``broader`` authorize ``narrower``? Write implies read."""
    if broader == narrower:
        return True
    if broader == "write" and narrower in ("read", "pull"):
        return True
    if broader == "exec" and narrower in ("read", "write", "pull"):
        return True
    return False


def _resource_covers(broader: Capability, narrower: Capability) -> bool:
    """Does ``broader``'s resource selector cover ``narrower``'s?

    Coverage rules:
      - Same (kind, id) → covers
      - swarm:<id>           covers swarm:<id> with any sub attenuation
      - lineage:<id>         covers descendants of <id> in the same lineage
        scheme (the actual descendant check happens at verify time against
        the Ancestry table — here we just say "lineage of the same root
        could potentially cover"; verify is the authoritative check).
      - object:<hash>        only covers that exact hash
    """
    if (
        broader.resource_kind == narrower.resource_kind
        and broader.resource_id == narrower.resource_id
    ):
        return True
    # Wildcard resource_id (e.g. mission:command:control:*) covers any id
    # within the same resource kind.
    if broader.resource_id == "*" and broader.resource_kind == narrower.resource_kind:
        return True
    # A swarm cap covers any sub-attenuated cap into that swarm.
    if (
        broader.resource_kind == "swarm"
        and narrower.resource_kind == "swarm"
        and broader.resource_id == narrower.resource_id
    ):
        return True
    return False


def _attenuation_at_least_as_tight(key: str, child: str, parent: str) -> bool:
    """Is the child's value of attenuation ``key`` at least as tight as
    the parent's? Numerics: child must be <= parent for caps, >= for floors.
    Strings (sub, topic, peer): child must equal parent.
    """
    if key in ("max_hops",):
        try:
            return int(child) <= int(parent)
        except ValueError:
            return False
    if key in ("min_eval",):
        try:
            return float(child) >= float(parent)
        except ValueError:
            return False
    if key == "expires":
        try:
            return float(child) <= float(parent)
        except ValueError:
            return False
    # Default: string equality — narrowing means matching exactly.
    return child == parent


# ─────────────────────────────────────────────────────────────────────
# Parser
# ─────────────────────────────────────────────────────────────────────

_KV = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.+)$")


def parse_uri(uri: str) -> Capability:
    """Parse a capability URI string into a ``Capability``.

    Strict on shape — schemes, actions, and resource_kinds must be in the
    known sets. Unknown attenuations are accepted but stored as strings;
    verifiers that don't understand them can ignore.
    """
    if not isinstance(uri, str) or not uri:
        raise CapURIError("capability URI must be a non-empty string")

    parts = uri.split(":")
    if len(parts) < 4:
        raise CapURIError(
            f"capability URI too short — expected <scheme>:<action>:<kind>:<id>, got {uri!r}"
        )

    scheme, action, kind, rest = parts[0], parts[1], parts[2], parts[3:]
    if scheme not in _VALID_SCHEMES:
        raise CapURIError(f"unknown scheme {scheme!r} in {uri!r}")
    if action not in _VALID_ACTIONS:
        raise CapURIError(f"unknown action {action!r} in {uri!r}")
    if kind not in _VALID_RESOURCE_KINDS:
        raise CapURIError(f"unknown resource kind {kind!r} in {uri!r}")

    # The resource_id may itself contain a colon — content hashes look
    # like 'sha256:abcd...' and that's a feature. We greedily consume
    # everything that isn't an attenuation (k=v).
    attenuations: list[tuple[str, str]] = []
    resource_parts: list[str] = [rest[0]] if rest else []
    started_attenuations = False
    for piece in rest[1:]:
        if _KV.match(piece):
            started_attenuations = True
            k, v = piece.split("=", 1)
            attenuations.append((k, v))
        else:
            if started_attenuations:
                raise CapURIError(
                    f"resource segment {piece!r} appeared after attenuations in {uri!r}"
                )
            resource_parts.append(piece)

    if not resource_parts or not resource_parts[0]:
        raise CapURIError(f"missing resource id in {uri!r}")

    return Capability(
        scheme=scheme,
        action=action,
        resource_kind=kind,
        resource_id=":".join(resource_parts),
        attenuations=tuple(sorted(attenuations)),
    )
