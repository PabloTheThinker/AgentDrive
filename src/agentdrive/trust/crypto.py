"""Crypto primitives for the trust circle — P-384 ECDSA + ECDH + AES-GCM.

All primitives come from the ``cryptography`` library (already a declared
dep). We keep the surface tiny on purpose: every other module imports from
here so the choice of curve / KDF / AEAD lives in exactly one place. Future
upgrades (X448, ChaCha20-Poly1305) become a single-file edit.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# ─── canonical bytes ────────────────────────────────────────────────────────


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    """Deterministic JSON encoding — every signature is over these bytes."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


# ─── keypair ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class KeyPair:
    """A P-384 keypair with PEM-serialized accessors."""

    private_key: ec.EllipticCurvePrivateKey

    @property
    def public_key(self) -> ec.EllipticCurvePublicKey:
        return self.private_key.public_key()

    def public_pem(self) -> str:
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

    def private_pem(self) -> bytes:
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )


def generate_keypair() -> KeyPair:
    """Fresh P-384 device keypair."""
    return KeyPair(ec.generate_private_key(ec.SECP384R1()))


def load_private_key(pem: bytes) -> KeyPair:
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise ValueError("Expected EC private key")
    if not isinstance(key.curve, ec.SECP384R1):
        raise ValueError(f"Expected P-384, got {key.curve.name}")
    return KeyPair(key)


def load_public_key(pem: str) -> ec.EllipticCurvePublicKey:
    key = serialization.load_pem_public_key(pem.encode("ascii"))
    if not isinstance(key, ec.EllipticCurvePublicKey):
        raise ValueError("Expected EC public key")
    if not isinstance(key.curve, ec.SECP384R1):
        raise ValueError(f"Expected P-384, got {key.curve.name}")
    return key


def device_id_from_public_key(public_pem: str) -> str:
    """Stable 16-char hex device id derived from the public key bytes."""
    return hashlib.sha256(public_pem.encode("ascii")).hexdigest()[:16]


# ─── sign / verify ──────────────────────────────────────────────────────────


def sign_canonical(keypair: KeyPair, payload: dict[str, Any]) -> str:
    sig = keypair.private_key.sign(canonical_bytes(payload), ec.ECDSA(hashes.SHA384()))
    return b64e(sig)


def verify_canonical(public_pem: str, payload: dict[str, Any], signature_b64: str) -> bool:
    try:
        load_public_key(public_pem).verify(
            b64d(signature_b64),
            canonical_bytes(payload),
            ec.ECDSA(hashes.SHA384()),
        )
        return True
    except (InvalidSignature, ValueError):
        return False


# ─── seal / open (ECDH → HKDF → AES-256-GCM) ────────────────────────────────


_HKDF_INFO = b"agentdrive-trust-v1/sync-envelope"


def _derive_aes_key(
    sender_keypair: KeyPair,
    recipient_public: ec.EllipticCurvePublicKey,
    salt: bytes,
) -> bytes:
    shared = sender_keypair.private_key.exchange(ec.ECDH(), recipient_public)
    return HKDF(
        algorithm=hashes.SHA384(),
        length=32,
        salt=salt,
        info=_HKDF_INFO,
    ).derive(shared)


def seal(
    sender_keypair: KeyPair,
    recipient_public_pem: str,
    plaintext: bytes,
) -> tuple[bytes, bytes]:
    """Encrypt + authenticate ``plaintext`` for the recipient.

    Returns ``(nonce, ciphertext)``. Nonce is 12 bytes (AES-GCM standard) and
    also serves as the HKDF salt — fresh per envelope so the derived key is
    fresh per envelope (no nonce reuse risk).
    """
    nonce = os.urandom(12)
    recipient_public = load_public_key(recipient_public_pem)
    key = _derive_aes_key(sender_keypair, recipient_public, salt=nonce)
    aead = AESGCM(key)
    ciphertext = aead.encrypt(nonce, plaintext, associated_data=None)
    return nonce, ciphertext


def open_sealed(
    recipient_keypair: KeyPair,
    sender_public_pem: str,
    nonce: bytes,
    ciphertext: bytes,
) -> bytes:
    """Decrypt a previously sealed payload. Raises on tampering / wrong key."""
    sender_public = load_public_key(sender_public_pem)
    key = _derive_aes_key(recipient_keypair, sender_public, salt=nonce)
    aead = AESGCM(key)
    return aead.decrypt(nonce, ciphertext, associated_data=None)
