"""Integration tests for v2 / M5 trust circle.

Three guarantees this milestone has to deliver:

1. **Voucher admission.** Device A founds a circle, signs a voucher, device B
   uses it to join. Both end up able to enumerate each other and sync.
2. **Sealed cross-device sync.** Payloads between members round-trip
   plaintext under encryption + signature; untrusted devices cannot decrypt
   or be decrypted-from.
3. **Persistence + replay protection.** Trust state survives restart from
   disk; a voucher cannot be replayed twice; expired vouchers are rejected.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentdrive.trust import TrustStore
from agentdrive.trust.crypto import (
    b64d,
    b64e,
    canonical_bytes,
    generate_keypair,
    load_public_key,
    sign_canonical,
    verify_canonical,
)
from agentdrive.trust.store import TrustError

# ─── crypto unit tests ──────────────────────────────────────────────────────


def test_keygen_serialization_roundtrip() -> None:
    kp = generate_keypair()
    pem = kp.public_pem()
    assert pem.startswith("-----BEGIN PUBLIC KEY-----")
    # Loadable round-trip
    load_public_key(pem)


def test_sign_verify_roundtrip() -> None:
    kp = generate_keypair()
    payload = {"hello": "world", "n": 7}
    sig = sign_canonical(kp, payload)
    assert verify_canonical(kp.public_pem(), payload, sig)


def test_verify_rejects_tampered_payload() -> None:
    kp = generate_keypair()
    sig = sign_canonical(kp, {"a": 1})
    assert not verify_canonical(kp.public_pem(), {"a": 2}, sig)


def test_verify_rejects_wrong_key() -> None:
    kp1 = generate_keypair()
    kp2 = generate_keypair()
    sig = sign_canonical(kp1, {"x": 1})
    assert not verify_canonical(kp2.public_pem(), {"x": 1}, sig)


def test_canonical_bytes_deterministic() -> None:
    assert canonical_bytes({"a": 1, "b": 2}) == canonical_bytes({"b": 2, "a": 1})


def test_b64_roundtrip() -> None:
    assert b64d(b64e(b"hello world")) == b"hello world"


# ─── trust store: create_circle + issue_voucher ─────────────────────────────


def _fresh(tmp_path: Path, name: str) -> TrustStore:
    return TrustStore(root=tmp_path / name / "trust")


def test_create_circle_founder_identity(tmp_path: Path) -> None:
    a = _fresh(tmp_path, "device-a")
    identity = a.create_circle("laptop")
    assert identity.device_name == "laptop"
    assert identity.circle_id == identity.device_id  # founder's id IS the circle
    assert identity.sponsor_device_id is None
    assert a.is_trusted(identity.device_id)


def test_create_circle_twice_rejected(tmp_path: Path) -> None:
    a = _fresh(tmp_path, "device-a")
    a.create_circle("laptop")
    with pytest.raises(TrustError):
        a.create_circle("laptop")


# ─── two-device voucher admission ───────────────────────────────────────────


def test_two_device_voucher_admission(tmp_path: Path) -> None:
    a = _fresh(tmp_path, "device-a")
    sponsor = a.create_circle("laptop")

    b = _fresh(tmp_path, "device-b")
    invitee_pub = b.prepare_invitee_keypair()

    voucher = a.issue_voucher(invitee_pub, ttl_seconds=600)

    b.register_sponsor(sponsor)  # out-of-band identity drop
    invitee_identity = b.accept_voucher(voucher, device_name="phone")

    # B knows itself + A
    assert b.self_identity is not None
    assert b.is_trusted(sponsor.device_id)
    assert b.is_trusted(invitee_identity.device_id)


def test_voucher_replay_rejected(tmp_path: Path) -> None:
    a = _fresh(tmp_path, "device-a")
    sponsor = a.create_circle("laptop")

    b = _fresh(tmp_path, "device-b")
    invitee_pub = b.prepare_invitee_keypair()
    voucher = a.issue_voucher(invitee_pub, ttl_seconds=600)
    b.register_sponsor(sponsor)
    b.accept_voucher(voucher, device_name="phone")

    # Reset B's runtime state and try to replay the same voucher on a fresh device.
    c = _fresh(tmp_path, "device-c")
    c.prepare_invitee_keypair()
    # Different invitee key — voucher should fail on key mismatch (not replay,
    # because c is a different store). Confirm.
    c.register_sponsor(sponsor)
    with pytest.raises(TrustError):
        c.accept_voucher(voucher, device_name="other")

    # And the original B cannot reuse the voucher on a fresh accept either
    # (its store records the nonce as seen).
    b2 = TrustStore(root=tmp_path / "device-b" / "trust")  # reload from disk
    # B already has identity loaded; accept_voucher refuses to bind twice.
    with pytest.raises(TrustError):
        b2.accept_voucher(voucher, device_name="phone-again")


def test_expired_voucher_rejected(tmp_path: Path) -> None:
    a = _fresh(tmp_path, "device-a")
    sponsor = a.create_circle("laptop")

    b = _fresh(tmp_path, "device-b")
    invitee_pub = b.prepare_invitee_keypair()
    voucher = a.issue_voucher(invitee_pub, ttl_seconds=600)
    # Force expiry by mutating the voucher's expires_at
    voucher.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    b.register_sponsor(sponsor)
    with pytest.raises(TrustError):
        b.accept_voucher(voucher, device_name="phone")


def test_tampered_voucher_rejected(tmp_path: Path) -> None:
    a = _fresh(tmp_path, "device-a")
    sponsor = a.create_circle("laptop")
    b = _fresh(tmp_path, "device-b")
    invitee_pub = b.prepare_invitee_keypair()
    voucher = a.issue_voucher(invitee_pub, ttl_seconds=600)

    # Tamper with the voucher post-signing
    voucher.circle_id = "different-circle"

    b.register_sponsor(sponsor)
    with pytest.raises(TrustError):
        b.accept_voucher(voucher, device_name="phone")


# ─── sealed sync envelopes ──────────────────────────────────────────────────


def _join_two_devices(tmp_path: Path) -> tuple[TrustStore, TrustStore]:
    a = _fresh(tmp_path, "device-a")
    sponsor = a.create_circle("laptop")
    b = _fresh(tmp_path, "device-b")
    invitee_pub = b.prepare_invitee_keypair()
    voucher = a.issue_voucher(invitee_pub, ttl_seconds=600)
    b.register_sponsor(sponsor)
    b_identity = b.accept_voucher(voucher, device_name="phone")
    # A also needs to know B in its member list (sponsor side learns later;
    # in production this would be conveyed back after first sync).
    a.register_member(b_identity)
    return a, b


def test_seal_open_roundtrip(tmp_path: Path) -> None:
    a, b = _join_two_devices(tmp_path)
    envelope = a.seal_for_peer(b.self_identity.device_id, b"swarm-sync-payload")
    plaintext = b.open_envelope(envelope)
    assert plaintext == b"swarm-sync-payload"


def test_seal_rejects_untrusted_peer(tmp_path: Path) -> None:
    a, _ = _join_two_devices(tmp_path)
    with pytest.raises(TrustError):
        a.seal_for_peer("unknown-device-id", b"payload")


def test_open_rejects_wrong_recipient(tmp_path: Path) -> None:
    a, b = _join_two_devices(tmp_path)
    envelope = a.seal_for_peer(b.self_identity.device_id, b"payload")
    envelope.recipient_device_id = "some-other-id"
    with pytest.raises(TrustError):
        b.open_envelope(envelope)


def test_open_rejects_tampered_ciphertext(tmp_path: Path) -> None:
    a, b = _join_two_devices(tmp_path)
    envelope = a.seal_for_peer(b.self_identity.device_id, b"payload")
    # Flip a byte in the ciphertext
    tampered = bytearray(b64d(envelope.ciphertext_b64))
    tampered[-1] ^= 0x01
    envelope.ciphertext_b64 = b64e(bytes(tampered))
    with pytest.raises(Exception):  # AESGCM raises InvalidTag; we re-raise
        b.open_envelope(envelope)


# ─── persistence ────────────────────────────────────────────────────────────


def test_trust_state_survives_restart(tmp_path: Path) -> None:
    a, b = _join_two_devices(tmp_path)
    a_id = a.self_identity.device_id
    b_id = b.self_identity.device_id

    # Reload both stores from disk
    a2 = TrustStore(root=tmp_path / "device-a" / "trust")
    b2 = TrustStore(root=tmp_path / "device-b" / "trust")

    assert a2.self_identity is not None
    assert b2.self_identity is not None
    assert a2.self_identity.device_id == a_id
    assert b2.self_identity.device_id == b_id
    assert a2.is_trusted(b_id)
    assert b2.is_trusted(a_id)

    # And a sealed envelope still round-trips across the restart
    env = a2.seal_for_peer(b_id, b"after restart")
    assert b2.open_envelope(env) == b"after restart"
