"""Persistent trust circle — disk-backed state for cross-device sync.

Layout under ``<agentdrive_home>/trust/``::

    trust/
    ├── self.json            ← this device's identity (public + private pem)
    ├── members/
    │   └── <device_id>.json ← public identities of trusted devices
    └── nonces.log           ← seen voucher ids (replay protection)

Private key is written with mode ``0600``. Loss of the directory is loss of
this device's membership; recovery requires a fresh voucher from another
circle member. That matches the iCloud-keychain semantics: no central
authority means no recovery backdoor.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agentdrive.constants import get_agentdrive_home
from agentdrive.trust import crypto
from agentdrive.trust.models import DeviceIdentity, JoinVoucher, SyncEnvelope

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _voucher_canonical(voucher: JoinVoucher) -> dict:
    """The bytes a sponsor signs / a recipient verifies — signature excluded."""
    return {
        "voucher_id": voucher.voucher_id,
        "circle_id": voucher.circle_id,
        "sponsor_device_id": voucher.sponsor_device_id,
        "invitee_public_key_p384": voucher.invitee_public_key_p384,
        "issued_at": voucher.issued_at.isoformat(),
        "expires_at": voucher.expires_at.isoformat(),
    }


def _envelope_canonical(envelope: SyncEnvelope) -> dict:
    """The bytes a sender signs / a recipient verifies — signature excluded."""
    return {
        "envelope_version": envelope.envelope_version,
        "sender_device_id": envelope.sender_device_id,
        "recipient_device_id": envelope.recipient_device_id,
        "nonce_b64": envelope.nonce_b64,
        "ciphertext_b64": envelope.ciphertext_b64,
        "issued_at": envelope.issued_at.isoformat(),
    }


class TrustError(Exception):
    """Raised when a trust operation is rejected (bad signature, expired, replay, etc.)."""


class TrustStore:
    """Persistent multi-device trust circle. One instance per device."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else get_agentdrive_home() / "trust"
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "members").mkdir(parents=True, exist_ok=True)
        self.self_path = self.root / "self.json"
        self.members_dir = self.root / "members"
        self.nonces_path = self.root / "nonces.log"

        self._keypair: crypto.KeyPair | None = None
        self._self_identity: DeviceIdentity | None = None
        self._members: dict[str, DeviceIdentity] = {}
        self._seen_nonces: set[str] = set()

        self._load_self()
        self._load_members()
        self._load_nonces()

    # ─── persistence helpers ────────────────────────────────────────────────

    def _load_self(self) -> None:
        if not self.self_path.exists():
            return
        data = json.loads(self.self_path.read_text(encoding="utf-8"))
        identity = DeviceIdentity.model_validate(data["identity"])
        keypair = crypto.load_private_key(data["private_pem"].encode("ascii"))
        self._self_identity = identity
        self._keypair = keypair

    def _persist_self(self, identity: DeviceIdentity, keypair: crypto.KeyPair) -> None:
        payload = {
            "identity": identity.model_dump(mode="json"),
            "private_pem": keypair.private_pem().decode("ascii"),
        }
        text = json.dumps(payload, indent=2, default=str)
        # Write with restrictive perms — best-effort; tmp test FS may ignore mode.
        self.self_path.write_text(text, encoding="utf-8")
        try:
            os.chmod(self.self_path, 0o600)
        except OSError:
            logger.debug("Could not chmod 0600 on %s", self.self_path)

    def _load_members(self) -> None:
        for path in self.members_dir.glob("*.json"):
            try:
                ident = DeviceIdentity.model_validate_json(path.read_text(encoding="utf-8"))
                self._members[ident.device_id] = ident
            except Exception as exc:
                logger.warning("Skipping bad member file %s: %s", path, exc)

    def _persist_member(self, identity: DeviceIdentity) -> None:
        path = self.members_dir / f"{identity.device_id}.json"
        path.write_text(identity.model_dump_json(indent=2), encoding="utf-8")

    def _load_nonces(self) -> None:
        if not self.nonces_path.exists():
            return
        with self.nonces_path.open(encoding="utf-8") as f:
            for line in f:
                v = line.strip()
                if v:
                    self._seen_nonces.add(v)

    def _record_nonce(self, voucher_id: str) -> None:
        self._seen_nonces.add(voucher_id)
        with self.nonces_path.open("a", encoding="utf-8") as f:
            f.write(voucher_id + "\n")

    # ─── public API ─────────────────────────────────────────────────────────

    @property
    def self_identity(self) -> DeviceIdentity | None:
        return self._self_identity

    @property
    def members(self) -> dict[str, DeviceIdentity]:
        return dict(self._members)

    def is_trusted(self, device_id: str) -> bool:
        if self._self_identity and device_id == self._self_identity.device_id:
            return True
        return device_id in self._members

    def create_circle(self, device_name: str) -> DeviceIdentity:
        """Found a brand-new circle with this device as the seed member."""
        if self._self_identity is not None:
            raise TrustError("This device already belongs to a circle")
        keypair = crypto.generate_keypair()
        public_pem = keypair.public_pem()
        device_id = crypto.device_id_from_public_key(public_pem)
        circle_id = device_id  # founder's device id IS the circle id
        identity = DeviceIdentity(
            device_id=device_id,
            device_name=device_name,
            circle_id=circle_id,
            public_key_p384=public_pem,
            created_at=_utc_now(),
            sponsor_device_id=None,
        )
        self._persist_self(identity, keypair)
        self._persist_member(identity)
        self._self_identity = identity
        self._keypair = keypair
        self._members[identity.device_id] = identity
        return identity

    def issue_voucher(
        self,
        invitee_public_key_p384: str,
        ttl_seconds: int = 3600,
    ) -> JoinVoucher:
        """Sign an admission voucher for a prospective new member."""
        if self._self_identity is None or self._keypair is None:
            raise TrustError("Cannot issue voucher: this device has no identity yet")
        # Reject malformed invitee keys early.
        crypto.load_public_key(invitee_public_key_p384)
        issued_at = _utc_now()
        voucher = JoinVoucher(
            voucher_id=os.urandom(12).hex(),
            circle_id=self._self_identity.circle_id,
            sponsor_device_id=self._self_identity.device_id,
            invitee_public_key_p384=invitee_public_key_p384,
            issued_at=issued_at,
            expires_at=issued_at + timedelta(seconds=ttl_seconds),
            signature_b64="",
        )
        voucher.signature_b64 = crypto.sign_canonical(self._keypair, _voucher_canonical(voucher))
        return voucher

    def accept_voucher(self, voucher: JoinVoucher, device_name: str) -> DeviceIdentity:
        """Use a sponsor-issued voucher to bind this device to the circle.

        Must be called on a fresh ``TrustStore`` (no prior identity), with the
        public key in the voucher matching a keypair generated locally just
        before. Returns the bound identity.
        """
        if self._self_identity is not None:
            raise TrustError("Device already belongs to a circle")
        if voucher.voucher_id in self._seen_nonces:
            raise TrustError("Voucher already used (replay)")
        if voucher.expires_at <= _utc_now():
            raise TrustError("Voucher expired")
        sponsor_pem = self._sponsor_public_key(voucher)
        if not crypto.verify_canonical(
            sponsor_pem, _voucher_canonical(voucher), voucher.signature_b64
        ):
            raise TrustError("Voucher signature invalid")

        keypair = crypto.load_private_key(self._pending_private_pem())
        if keypair.public_pem().strip() != voucher.invitee_public_key_p384.strip():
            raise TrustError("Voucher public key does not match this device's pending keypair")

        device_id = crypto.device_id_from_public_key(voucher.invitee_public_key_p384)
        identity = DeviceIdentity(
            device_id=device_id,
            device_name=device_name,
            circle_id=voucher.circle_id,
            public_key_p384=voucher.invitee_public_key_p384,
            created_at=_utc_now(),
            sponsor_device_id=voucher.sponsor_device_id,
        )
        self._persist_self(identity, keypair)
        self._persist_member(identity)
        # Also persist the sponsor as a trusted member so future syncs work.
        sponsor_identity = self._members.get(voucher.sponsor_device_id) or DeviceIdentity(
            device_id=voucher.sponsor_device_id,
            device_name=f"sponsor:{voucher.sponsor_device_id}",
            circle_id=voucher.circle_id,
            public_key_p384=sponsor_pem,
            created_at=_utc_now(),
            sponsor_device_id=None,
        )
        self._persist_member(sponsor_identity)
        self._members[sponsor_identity.device_id] = sponsor_identity
        self._self_identity = identity
        self._keypair = keypair
        self._members[identity.device_id] = identity
        self._record_nonce(voucher.voucher_id)
        return identity

    def register_member(self, identity: DeviceIdentity) -> None:
        """Add a peer identity to the local member list (e.g. learned from a sponsor)."""
        if self._self_identity is None:
            raise TrustError("Cannot register member: this device has no identity")
        if identity.circle_id != self._self_identity.circle_id:
            raise TrustError("Member belongs to a different circle")
        self._persist_member(identity)
        self._members[identity.device_id] = identity

    def prepare_invitee_keypair(self) -> str:
        """Generate a fresh keypair for an unbound device and stash the private
        half on disk under ``trust/pending.pem``. Returns the public PEM the
        sponsor needs to issue a voucher.

        Pairs with :meth:`accept_voucher`. If the invitee process dies between
        this call and acceptance, the pending file can be re-read; if both are
        lost, just call this method again."""
        if self._self_identity is not None:
            raise TrustError("Device already has identity; no need to prepare invitee key")
        keypair = crypto.generate_keypair()
        pending = self.root / "pending.pem"
        pending.write_bytes(keypair.private_pem())
        try:
            os.chmod(pending, 0o600)
        except OSError:
            pass
        return keypair.public_pem()

    def _pending_private_pem(self) -> bytes:
        pending = self.root / "pending.pem"
        if not pending.exists():
            raise TrustError("No pending invitee keypair on disk — call prepare_invitee_keypair()")
        return pending.read_bytes()

    def _sponsor_public_key(self, voucher: JoinVoucher) -> str:
        sponsor = self._members.get(voucher.sponsor_device_id)
        if sponsor is not None:
            return sponsor.public_key_p384
        # First contact: trust-on-first-voucher. The voucher carries an
        # inviter identity, but for new devices we have nothing local — accept
        # and persist on success. This is the iCloud-keychain "first device
        # bootstrap" pattern.
        raise TrustError(
            "Unknown sponsor; provide sponsor DeviceIdentity via register_sponsor() first"
        )

    def register_sponsor(self, identity: DeviceIdentity) -> None:
        """Out-of-band-supplied sponsor identity, needed before accept_voucher
        on a brand-new device. The invitee gets this from whatever channel
        delivers the voucher (QR code, email, paired device pairing screen)."""
        self._persist_member(identity)
        self._members[identity.device_id] = identity

    # ─── sync envelope ──────────────────────────────────────────────────────

    def seal_for_peer(self, peer_device_id: str, payload: bytes) -> SyncEnvelope:
        if self._self_identity is None or self._keypair is None:
            raise TrustError("No local identity — call create_circle / accept_voucher first")
        if not self.is_trusted(peer_device_id):
            raise TrustError(f"Peer {peer_device_id!r} is not in this trust circle")
        peer = self._members[peer_device_id]
        nonce, ciphertext = crypto.seal(self._keypair, peer.public_key_p384, payload)
        envelope = SyncEnvelope(
            sender_device_id=self._self_identity.device_id,
            recipient_device_id=peer_device_id,
            nonce_b64=crypto.b64e(nonce),
            ciphertext_b64=crypto.b64e(ciphertext),
            signature_b64="",
            issued_at=_utc_now(),
        )
        envelope.signature_b64 = crypto.sign_canonical(self._keypair, _envelope_canonical(envelope))
        return envelope

    def open_envelope(self, envelope: SyncEnvelope) -> bytes:
        if self._self_identity is None or self._keypair is None:
            raise TrustError("No local identity to decrypt with")
        if envelope.recipient_device_id != self._self_identity.device_id:
            raise TrustError("Envelope not addressed to this device")
        sender = self._members.get(envelope.sender_device_id)
        if sender is None:
            raise TrustError(f"Sender {envelope.sender_device_id!r} not in trust circle")
        if not crypto.verify_canonical(
            sender.public_key_p384, _envelope_canonical(envelope), envelope.signature_b64
        ):
            raise TrustError("Envelope signature invalid")
        nonce = crypto.b64d(envelope.nonce_b64)
        ciphertext = crypto.b64d(envelope.ciphertext_b64)
        return crypto.open_sealed(self._keypair, sender.public_key_p384, nonce, ciphertext)
