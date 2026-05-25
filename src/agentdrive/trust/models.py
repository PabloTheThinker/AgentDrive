"""Wire models for the trust circle. Pydantic v2.

All public keys are PEM-encoded SubjectPublicKeyInfo strings (the format
``cryptography.hazmat.primitives.serialization`` round-trips). All signatures
and ciphertexts are base64-encoded so the models JSON-serialize cleanly for
sync payloads and on-disk persistence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DeviceIdentity(BaseModel):
    """A device's stable identity within a trust circle."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True, str_strip_whitespace=True)

    device_id: str = Field(..., min_length=8, description="Hex-encoded SHA-256 of public key, 16ch")
    device_name: str = Field(..., min_length=1, max_length=64)
    circle_id: str = Field(..., min_length=8, description="Hex-encoded SHA-256 of founder pubkey")
    public_key_p384: str = Field(..., description="PEM-encoded P-384 public key")
    created_at: datetime
    sponsor_device_id: str | None = Field(
        default=None,
        description="Device id of the sponsor that admitted this device (None for the founder)",
    )


class JoinVoucher(BaseModel):
    """One-shot signed admission token from an existing member to a new device."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True, str_strip_whitespace=True)

    voucher_id: str = Field(..., min_length=16, description="Random nonce — replay anchor")
    circle_id: str
    sponsor_device_id: str
    invitee_public_key_p384: str
    issued_at: datetime
    expires_at: datetime
    signature_b64: str = Field(..., description="Sponsor's signature over the canonical voucher")


class SyncEnvelope(BaseModel):
    """An encrypted + signed payload between two circle members."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True, str_strip_whitespace=True)

    envelope_version: Literal[1] = 1
    sender_device_id: str
    recipient_device_id: str
    nonce_b64: str = Field(..., description="12-byte AES-GCM nonce")
    ciphertext_b64: str
    signature_b64: str = Field(..., description="Sender's signature over the canonical envelope")
    issued_at: datetime
