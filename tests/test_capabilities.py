"""v2 / Milestone 3 — capability URIs as the universal access primitive.

The guarantees that make this the AgentDrive moment:

1. **URIs round-trip deterministically.** ``parse_uri(cap.to_uri())`` is
   ``cap`` no matter how the original was constructed. Signature
   verification depends on this.
2. **Narrowness is the spine of subset minting + derivation.**
   ``is_narrower_than`` correctly orders caps so:
     - write covers read
     - swarm-wide covers sub-agent-scoped
     - tighter attenuations (lower max_hops, higher min_eval) narrow correctly
3. **Mint refuses to widen a cap.** A holder cannot mint something broader
   than what they hold.
4. **verify_request is the single arbiter.** Every Drive boundary calls
   it; valid+covering caps pass, invalid or insufficient ones raise.
5. **Signature tampering, revocation, expiry are all detected.**
"""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

import pytest

from agentdrive.cap import (
    Capability,
    CapDerivationError,
    CapInvalidError,
    CapStore,
    CapURIError,
    CapVerifyContext,
    InsufficientCapability,
    RequestAuthorizer,
    default_cap_store_path,
    get_default_cap_store,
    parse_uri,
)

# ─────────────────────────────────────────────────────────────────────
# 1. URI parsing + round-trip
# ─────────────────────────────────────────────────────────────────────


def test_parse_basic_uri() -> None:
    cap = parse_uri("drive:read:swarm:demo-2026")
    assert cap.scheme == "drive"
    assert cap.action == "read"
    assert cap.resource_kind == "swarm"
    assert cap.resource_id == "demo-2026"
    assert cap.attenuations == ()


def test_parse_uri_with_attenuations() -> None:
    cap = parse_uri("dna:pull:lineage:agent-7:max_hops=3:min_eval=0.7")
    assert cap.resource_kind == "lineage"
    assert cap.resource_id == "agent-7"
    assert cap.attenuation("max_hops") == "3"
    assert cap.attenuation("min_eval") == "0.7"


def test_parse_uri_with_hash_resource() -> None:
    """Content hashes contain a colon (sha256:abcd); the parser handles."""
    cap = parse_uri("drive:read:object:sha256:abcdef1234")
    assert cap.resource_kind == "object"
    assert cap.resource_id == "sha256:abcdef1234"


def test_uri_round_trips_deterministically() -> None:
    """Same Capability → same URI string, regardless of attenuation order."""
    cap_a = Capability(
        scheme="dna",
        action="pull",
        resource_kind="lineage",
        resource_id="x",
        attenuations=(("max_hops", "3"), ("min_eval", "0.7")),
    )
    cap_b = Capability(
        scheme="dna",
        action="pull",
        resource_kind="lineage",
        resource_id="x",
        attenuations=(("min_eval", "0.7"), ("max_hops", "3")),
    )
    # The dataclass keeps tuples as-given, but to_uri must canonicalize:
    assert cap_a.to_uri() == cap_b.to_uri()
    assert parse_uri(cap_a.to_uri()) == parse_uri(cap_b.to_uri())


def test_parse_rejects_malformed() -> None:
    for bad in [
        "",
        "drive:read",  # too short
        "unknown:read:swarm:x",  # bad scheme
        "drive:teleport:swarm:x",  # bad action
        "drive:read:unknown_kind:x",  # bad resource kind
        "drive:read:swarm:x:max_hops=3:extra",  # resource segment after attenuation
    ]:
        with pytest.raises(CapURIError):
            parse_uri(bad)


# ─────────────────────────────────────────────────────────────────────
# 2. Narrowness — the ordering on caps
# ─────────────────────────────────────────────────────────────────────


def test_write_covers_read() -> None:
    write = parse_uri("drive:write:swarm:demo")
    read = parse_uri("drive:read:swarm:demo")
    assert read.is_narrower_than(write)
    assert not write.is_narrower_than(read)


def test_exec_covers_everything() -> None:
    exec_cap = parse_uri("drive:exec:agent:a")
    assert parse_uri("drive:read:agent:a").is_narrower_than(exec_cap)
    assert parse_uri("drive:write:agent:a").is_narrower_than(exec_cap)


def test_same_action_same_resource_is_self_narrowing() -> None:
    cap = parse_uri("drive:read:swarm:x")
    assert cap.is_narrower_than(cap)


def test_lower_max_hops_is_narrower() -> None:
    broad = parse_uri("dna:pull:lineage:a:max_hops=5")
    tight = parse_uri("dna:pull:lineage:a:max_hops=2")
    assert tight.is_narrower_than(broad)
    assert not broad.is_narrower_than(tight)


def test_higher_min_eval_is_narrower() -> None:
    broad = parse_uri("dna:pull:lineage:a:min_eval=0.5")
    tight = parse_uri("dna:pull:lineage:a:min_eval=0.9")
    assert tight.is_narrower_than(broad)


def test_unbounded_child_cannot_be_narrower_than_bounded_parent() -> None:
    parent = parse_uri("dna:pull:lineage:a:max_hops=3")
    child = parse_uri("dna:pull:lineage:a")  # no max_hops → unbounded
    assert not child.is_narrower_than(parent)


def test_different_schemes_never_cover() -> None:
    drive_cap = parse_uri("drive:read:agent:a")
    dna_cap = parse_uri("dna:pull:agent:a")
    assert not drive_cap.is_narrower_than(dna_cap)
    assert not dna_cap.is_narrower_than(drive_cap)


# ─────────────────────────────────────────────────────────────────────
# 3. CapStore — mint / derive / verify
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def store(tmp_path: Path) -> CapStore:
    return CapStore(tmp_path / "caps.db")


def test_minted_cap_verifies(store: CapStore) -> None:
    cap = store.mint(
        issuer="alice",
        capability=parse_uri("drive:read:swarm:demo"),
    )
    store.verify(cap)


def test_default_cap_store_uses_active_agentdrive_home(isolated_savant_home: Path) -> None:
    assert default_cap_store_path() == isolated_savant_home / "cap" / "_caps.db"
    assert get_default_cap_store().db_path == default_cap_store_path()


def test_unknown_trust_root_rejected(tmp_path: Path) -> None:
    """Caps signed by an agent the store has never seen should not verify."""
    store_a = CapStore(tmp_path / "a.db")
    cap = store_a.mint(issuer="alice", capability=parse_uri("drive:read:swarm:demo"))

    # Fresh store on a different DB — has no record of alice's pubkey.
    store_b = CapStore(tmp_path / "b.db")
    with pytest.raises(CapInvalidError, match="trust roots"):
        store_b.verify(cap)


def test_tampered_cap_uri_rejected(store: CapStore) -> None:
    cap = store.mint(issuer="alice", capability=parse_uri("drive:read:swarm:demo"))
    tampered = replace(
        cap,
        uri="drive:read:swarm:other",
        capability=parse_uri("drive:read:swarm:other"),
    )

    with pytest.raises(CapInvalidError, match="signature"):
        store.verify(tampered)


def test_revoked_cap_rejected(store: CapStore) -> None:
    cap = store.mint(issuer="alice", capability=parse_uri("drive:read:swarm:demo"))
    assert store.revoke(cap.cap_id)
    with pytest.raises(CapInvalidError, match="revoked"):
        store.verify(cap)


def test_expired_attenuation_rejected(store: CapStore) -> None:
    cap = store.mint(
        issuer="alice",
        capability=parse_uri(f"drive:read:swarm:demo:expires={time.time() - 1}"),
    )
    with pytest.raises(CapInvalidError, match="expired"):
        store.verify(cap)


def test_session_cap_authorizes_until_expiry(
    store: CapStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 1_000.0
    monkeypatch.setattr("agentdrive.cap.store.time.time", lambda: now)
    cap = store.mint_session(
        issuer="alice",
        capability=parse_uri("drive:read:swarm:demo"),
        ttl_seconds=5,
    )
    ctx = CapVerifyContext(
        scheme="drive",
        action="read",
        resource_kind="swarm",
        resource_id="demo",
    )

    store.verify_request(cap, ctx)
    now = 1_006.0
    with pytest.raises(CapInvalidError, match="expired"):
        store.verify_request(cap, ctx)


def test_session_cap_rejects_invalid_ttl(store: CapStore) -> None:
    with pytest.raises(ValueError, match="positive"):
        store.mint_session(
            issuer="alice",
            capability=parse_uri("drive:read:swarm:demo"),
            ttl_seconds=0,
        )


# ─────────────────────────────────────────────────────────────────────
# 4. Subset minting + derivation
# ─────────────────────────────────────────────────────────────────────


def test_subset_mint_succeeds(store: CapStore) -> None:
    parent = store.mint(issuer="alice", capability=parse_uri("drive:write:swarm:demo"))
    # Derive a read cap (narrower).
    child = store.mint(
        issuer="alice",
        capability=parse_uri("drive:read:swarm:demo"),
        parent_cap_id=parent.cap_id,
    )
    store.verify(child)


def test_widening_mint_refused(store: CapStore) -> None:
    """A holder cannot mint a cap WIDER than their parent."""
    parent = store.mint(
        issuer="alice",
        capability=parse_uri("dna:pull:lineage:a:max_hops=2"),
    )
    with pytest.raises(CapDerivationError, match="not narrower"):
        store.mint(
            issuer="alice",
            capability=parse_uri("dna:pull:lineage:a:max_hops=5"),
            parent_cap_id=parent.cap_id,
        )


def test_derive_helper_produces_narrower(store: CapStore) -> None:
    parent = store.mint(issuer="alice", capability=parse_uri("drive:write:swarm:demo"))
    derived = store.derive(parent_cap_id=parent.cap_id, action="read")
    assert derived.capability.action == "read"
    store.verify(derived)


def test_derive_can_add_attenuations(store: CapStore) -> None:
    parent = store.mint(
        issuer="alice",
        capability=parse_uri("dna:pull:lineage:a"),
    )
    derived = store.derive(
        parent_cap_id=parent.cap_id,
        extra_attenuations={"max_hops": "3"},
    )
    assert derived.capability.attenuation("max_hops") == "3"


# ─────────────────────────────────────────────────────────────────────
# 5. verify_request — the single Drive-boundary arbiter
# ─────────────────────────────────────────────────────────────────────


def test_verify_request_authorizes_when_cap_covers(store: CapStore) -> None:
    cap = store.mint(issuer="alice", capability=parse_uri("drive:write:swarm:demo"))
    # A read on the same swarm is covered by a write cap.
    ctx = CapVerifyContext(
        scheme="drive",
        action="read",
        resource_kind="swarm",
        resource_id="demo",
    )
    store.verify_request(cap, ctx)  # must not raise


def test_verify_request_rejects_action_mismatch(store: CapStore) -> None:
    cap = store.mint(issuer="alice", capability=parse_uri("drive:read:swarm:demo"))
    ctx = CapVerifyContext(
        scheme="drive",
        action="write",  # asking for more than we hold
        resource_kind="swarm",
        resource_id="demo",
    )
    with pytest.raises(InsufficientCapability):
        store.verify_request(cap, ctx)


def test_verify_request_rejects_resource_mismatch(store: CapStore) -> None:
    cap = store.mint(issuer="alice", capability=parse_uri("drive:read:swarm:demo"))
    ctx = CapVerifyContext(
        scheme="drive",
        action="read",
        resource_kind="swarm",
        resource_id="other-swarm",
    )
    with pytest.raises(InsufficientCapability):
        store.verify_request(cap, ctx)


def test_verify_request_rejects_revoked_cap(store: CapStore) -> None:
    cap = store.mint(issuer="alice", capability=parse_uri("drive:read:swarm:demo"))
    store.revoke(cap.cap_id)
    ctx = CapVerifyContext(
        scheme="drive",
        action="read",
        resource_kind="swarm",
        resource_id="demo",
    )
    with pytest.raises(CapInvalidError, match="revoked"):
        store.verify_request(cap, ctx)


def test_verify_request_attenuation_must_be_at_least_as_tight(store: CapStore) -> None:
    """Hold a max_hops=2 cap; can't request max_hops=5."""
    cap = store.mint(
        issuer="alice",
        capability=parse_uri("dna:pull:lineage:a:max_hops=2"),
    )
    ctx = CapVerifyContext(
        scheme="dna",
        action="pull",
        resource_kind="lineage",
        resource_id="a",
        attenuations=(("max_hops", "5"),),  # asking for wider — should fail
    )
    with pytest.raises(InsufficientCapability):
        store.verify_request(cap, ctx)


def test_verify_request_attenuation_within_bounds_passes(store: CapStore) -> None:
    cap = store.mint(
        issuer="alice",
        capability=parse_uri("dna:pull:lineage:a:max_hops=5"),
    )
    ctx = CapVerifyContext(
        scheme="dna",
        action="pull",
        resource_kind="lineage",
        resource_id="a",
        attenuations=(("max_hops", "2"),),  # asking for tighter — fine
    )
    store.verify_request(cap, ctx)


def test_request_authorizer_verifies_dna_pull_boundary(store: CapStore) -> None:
    cap = store.mint_session(
        issuer="alice",
        capability=parse_uri("dna:pull:lineage:root:max_hops=3:min_eval=0.7"),
        ttl_seconds=60,
    )
    authorizer = RequestAuthorizer(store)

    authorizer.verify_dna_pull(cap, lineage_id="root", max_hops=2, min_eval=0.8)


def test_request_authorizer_rejects_widened_dna_pull(store: CapStore) -> None:
    cap = store.mint_session(
        issuer="alice",
        capability=parse_uri("dna:pull:lineage:root:max_hops=3:min_eval=0.7"),
        ttl_seconds=60,
    )
    authorizer = RequestAuthorizer(store)

    with pytest.raises(InsufficientCapability):
        authorizer.verify_dna_pull(cap, lineage_id="root", max_hops=4, min_eval=0.8)
    with pytest.raises(InsufficientCapability):
        authorizer.verify_dna_pull(cap, lineage_id="root", max_hops=2, min_eval=0.1)
