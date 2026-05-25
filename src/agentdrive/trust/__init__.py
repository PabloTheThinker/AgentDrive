"""Trust circle for AgentDrive v2 / Milestone 5 — cross-device sync.

Two devices that want to share a swarm Drive form a P-384 ECDSA circle. New
devices join via a signed voucher from an existing member. Sync payloads
between members are sealed with ECDH + HKDF + AES-256-GCM. No central
authority; loss of every circle member is loss of the circle (the iCloud
keychain semantics, which match AgentDrive's local-first stance).

Public surface:

* :class:`DeviceIdentity` — a device's public-key bound circle membership
* :class:`JoinVoucher` — a one-shot signed admission token
* :class:`SyncEnvelope` — an encrypted + signed payload between two devices
* :class:`TrustStore` — persistent circle state with create/join/seal/open
"""

from agentdrive.trust.models import DeviceIdentity, JoinVoucher, SyncEnvelope
from agentdrive.trust.store import TrustStore

__all__ = ["DeviceIdentity", "JoinVoucher", "SyncEnvelope", "TrustStore"]
