"""v2 / Milestone 2c — lineage_share grants.

Sideways cousin sharing across lineages, gated by signed grants. The
guarantees we lock in:

1. **Signatures actually verify.** A grant minted by issuer A and signed
   with A's Ed25519 key passes ``verify()``. Tampering with any field
   fails verification.
2. **Expiry is honored.** TTL elapsed → ``verify()`` rejects the grant.
3. **Revocation is honored.** ``revoke(grant_id)`` → future ``verify()``
   rejects.
4. **Quota stops Sybil flooding.** An issuer cannot exceed
   ``DEFAULT_QUOTA_PER_ISSUER`` active grants.
5. **Scope filters work.** ``min_eval`` blocks low-score Genomes;
   ``content_hashes`` restricts to a specific set.
6. **End-to-end pull works.** Issuer publishes; grantee receives a grant;
   ``pull_via_grant`` returns the issuer's Genomes marked depth=-1
   (the cross-source signal that distinguishes them from forward-line
   ancestral pulls).
"""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

import pytest

from agentdrive.dna import DNADrive
from agentdrive.dna.grants import (
    GrantInvalidError,
    GrantQuotaExceededError,
    GrantScope,
    GrantStore,
    LineageShareGrant,
    pull_via_grant,
)
from agentdrive.genome.models import Genome


def _make_genome(gid: str, eval_score: float = 0.0) -> Genome:
    return Genome.create(
        id=gid,
        version="1.0.0",
        framework={"steps": [{"id": "1", "name": gid}]},
        evaluations={"reference_tasks": eval_score} if eval_score else {},
    )


@pytest.fixture
def store(tmp_path: Path) -> GrantStore:
    return GrantStore(tmp_path / "grants.db", quota_per_issuer=5)


# ─────────────────────────────────────────────────────────────────────
# 1. Signing + verification
# ─────────────────────────────────────────────────────────────────────


def test_freshly_issued_grant_verifies(store: GrantStore) -> None:
    grant = store.issue(issuer="alice", grantee="bob", ttl_seconds=60)
    store.verify(grant)  # must not raise


def test_tampered_grantee_fails_verification(store: GrantStore) -> None:
    grant = store.issue(issuer="alice", grantee="bob", ttl_seconds=60)
    tampered = replace(grant, grantee="mallory")  # change a signed field

    with pytest.raises(GrantInvalidError, match="signature"):
        store.verify(tampered)


def test_tampered_scope_fails_verification(store: GrantStore) -> None:
    grant = store.issue(
        issuer="alice",
        grantee="bob",
        scope=GrantScope(min_eval=0.9),
        ttl_seconds=60,
    )
    tampered = replace(grant, scope=GrantScope(min_eval=0.0))  # widen the gate

    with pytest.raises(GrantInvalidError, match="signature"):
        store.verify(tampered)


# ─────────────────────────────────────────────────────────────────────
# 2. Expiry
# ─────────────────────────────────────────────────────────────────────


def test_expired_grant_rejected(store: GrantStore) -> None:
    grant = store.issue(issuer="alice", grantee="bob", ttl_seconds=0)
    time.sleep(0.05)
    with pytest.raises(GrantInvalidError, match="expired"):
        store.verify(grant)


def test_is_expired_helper_consistent_with_verify(store: GrantStore) -> None:
    grant = store.issue(issuer="alice", grantee="bob", ttl_seconds=0)
    time.sleep(0.05)
    assert grant.is_expired()


# ─────────────────────────────────────────────────────────────────────
# 3. Revocation
# ─────────────────────────────────────────────────────────────────────


def test_revoked_grant_rejected(store: GrantStore) -> None:
    grant = store.issue(issuer="alice", grantee="bob", ttl_seconds=60)
    assert store.revoke(grant.grant_id) is True

    with pytest.raises(GrantInvalidError, match="revoked"):
        store.verify(grant)


def test_revoke_unknown_grant_returns_false(store: GrantStore) -> None:
    assert store.revoke("definitely-not-a-real-grant") is False


# ─────────────────────────────────────────────────────────────────────
# 4. Quota — Sybil flood defense
# ─────────────────────────────────────────────────────────────────────


def test_quota_caps_active_grants_per_issuer(store: GrantStore) -> None:
    # Fixture's quota is 5.
    for i in range(5):
        store.issue(issuer="alice", grantee=f"grantee-{i}", ttl_seconds=60)

    with pytest.raises(GrantQuotaExceededError):
        store.issue(issuer="alice", grantee="overflow", ttl_seconds=60)


def test_quota_only_counts_active_grants(store: GrantStore) -> None:
    """Expired and revoked grants don't count against the quota."""
    store.issue(issuer="alice", grantee="g1", ttl_seconds=60)
    store.issue(issuer="alice", grantee="g2", ttl_seconds=0)  # already expired
    g3 = store.issue(issuer="alice", grantee="g3", ttl_seconds=60)
    store.revoke(g3.grant_id)

    time.sleep(0.05)  # ensure g2 is past expiry
    # Active count is now 1 (just g1). Quota of 5 leaves room for 4 more.
    for i in range(4):
        store.issue(issuer="alice", grantee=f"new-{i}", ttl_seconds=60)


def test_different_issuers_have_independent_quotas(store: GrantStore) -> None:
    for i in range(5):
        store.issue(issuer="alice", grantee=f"g-{i}", ttl_seconds=60)
    # bob is unaffected by alice's quota
    store.issue(issuer="bob", grantee="b-1", ttl_seconds=60)


# ─────────────────────────────────────────────────────────────────────
# 5. Round-tripping + lookup
# ─────────────────────────────────────────────────────────────────────


def test_grant_serializes_round_trip(store: GrantStore) -> None:
    original = store.issue(
        issuer="alice",
        grantee="bob",
        scope=GrantScope(topics=("planning",), min_eval=0.8),
        ttl_seconds=60,
    )
    d = original.to_dict()
    rebuilt = LineageShareGrant.from_dict(d)

    assert rebuilt == original
    store.verify(rebuilt)  # still verifies after round-trip


def test_grants_for_grantee_filters_correctly(store: GrantStore) -> None:
    store.issue(issuer="alice", grantee="bob", ttl_seconds=60)
    store.issue(issuer="alice", grantee="carol", ttl_seconds=60)
    store.issue(issuer="alice", grantee="bob", ttl_seconds=0)
    revoked = store.issue(issuer="alice", grantee="bob", ttl_seconds=60)
    store.revoke(revoked.grant_id)

    time.sleep(0.05)
    bobs = store.grants_for_grantee("bob")
    assert len(bobs) == 1  # only the active, non-revoked, non-expired one


# ─────────────────────────────────────────────────────────────────────
# 6. End-to-end cross-cousin pull
# ─────────────────────────────────────────────────────────────────────


def test_pull_via_grant_returns_issuers_genomes(
    isolated_savant_home: Path,
    tmp_path: Path,
) -> None:
    """The whole point of M2c: cousin-A publishes; cousin-B receives a
    grant; cousin-B pulls and sees cousin-A's work — without any
    ancestral relationship between them."""
    store = GrantStore(isolated_savant_home / "dna" / "_grants.db")

    cousin_a = DNADrive("cousin-a")
    cousin_a.publish(_make_genome("cousin-a-cap", eval_score=0.9))

    grant = store.issue(
        issuer="cousin-a",
        grantee="cousin-b",
        scope=GrantScope(min_eval=0.0),
        ttl_seconds=60,
    )

    received = pull_via_grant(grant, store)
    assert len(received) == 1
    assert received[0].source_agent == "cousin-a"
    assert received[0].depth == -1, "cross-source pulls must be marked with depth=-1"


def test_pull_via_grant_applies_min_eval_gate(isolated_savant_home: Path) -> None:
    store = GrantStore(isolated_savant_home / "dna" / "_grants.db")

    cousin_a = DNADrive("cousin-a")
    cousin_a.publish(_make_genome("strong-cap", eval_score=0.9))
    cousin_a.publish(_make_genome("weak-cap", eval_score=0.4))

    grant = store.issue(
        issuer="cousin-a",
        grantee="cousin-b",
        scope=GrantScope(min_eval=0.7),
        ttl_seconds=60,
    )

    received = pull_via_grant(grant, store)
    assert len(received) == 1
    framework_step = received[0].payload["framework"]["steps"][0]["name"]
    assert framework_step == "strong-cap"


def test_pull_via_grant_restricted_to_content_hashes(isolated_savant_home: Path) -> None:
    store = GrantStore(isolated_savant_home / "dna" / "_grants.db")
    cousin_a = DNADrive("cousin-a")
    h1 = cousin_a.publish(_make_genome("a"))
    cousin_a.publish(_make_genome("b"))
    cousin_a.publish(_make_genome("c"))

    grant = store.issue(
        issuer="cousin-a",
        grantee="cousin-b",
        # min_eval=0 because the Genomes here have no eval scores; the
        # restriction we're testing is the content_hashes whitelist itself.
        scope=GrantScope(content_hashes=(h1,), min_eval=0.0),
        ttl_seconds=60,
    )

    received = pull_via_grant(grant, store)
    assert len(received) == 1
    assert received[0].content_hash == h1


def test_pull_via_grant_rejects_revoked_grant(isolated_savant_home: Path) -> None:
    store = GrantStore(isolated_savant_home / "dna" / "_grants.db")
    cousin_a = DNADrive("cousin-a")
    cousin_a.publish(_make_genome("a"))

    grant = store.issue(issuer="cousin-a", grantee="cousin-b", ttl_seconds=60)
    store.revoke(grant.grant_id)

    with pytest.raises(GrantInvalidError, match="revoked"):
        pull_via_grant(grant, store)
