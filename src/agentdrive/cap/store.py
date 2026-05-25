"""CapStore — mint, derive, verify capability URIs.

The 30-line cap resolver promised in the v2 architecture lives here, in
``CapStore.verify_request()``. Every Drive boundary (ingest, query,
inherited-pull, snapshot, peer push) goes through that single call. If
it returns silently, the access is authorized; if it raises, the request
is rejected. That's the AgentDrive moment.

**Storage.** A SQLite table at ``<home>/cap/_caps.db`` holding minted
capabilities + per-agent Ed25519 keypairs. Reuses the same key-management
pattern that ``dna.grants.GrantStore`` already established — but with
the cap as the unified primitive instead of grant-specific bespoke types.

**Signing.** Ed25519, same as grants. The signed payload is the
*canonical URI form* of the capability — so the URI string itself is the
authentic record. Tampering with any field changes the URI, which
changes the signed bytes, which fails verification.

**Trust roots.** Every cap is signed by an *issuer agent*. To trust a
cap, the verifier must either (a) recognize the issuer as a known root
(its public key is in the local trust store), or (b) verify a chain
upward to a known root via parent-cap signatures. v3 will add proper
chain verification; for v2 / M3, single-hop signing is enough and we
document the limit explicitly.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from agentdrive.constants import get_agentdrive_home

from .uri import Capability, parse_uri

logger = logging.getLogger(__name__)


class CapInvalidError(Exception):
    """Raised when a cap fails signature / expiry / revocation checks."""


class CapDerivationError(Exception):
    """Raised when a mint or derive op would produce an illegal cap
    (e.g. wider than the parent, or with conflicting attenuations)."""


class InsufficientCapability(CapInvalidError):
    """Specific subclass for the common case: the cap is valid, but its
    scope does not cover the requested action. Lets callers tell apart
    'someone presented junk' from 'they have a real cap that just
    doesn't grant this'."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS caps (
  cap_id        TEXT PRIMARY KEY,
  uri           TEXT NOT NULL,
  issuer        TEXT NOT NULL,
  signature     TEXT NOT NULL,
  issuer_pubkey TEXT NOT NULL,
  issued_at     REAL NOT NULL,
  parent_cap_id TEXT,                 -- NULL for root caps; else the cap that minted this
  revoked       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_caps_issuer ON caps(issuer);

CREATE TABLE IF NOT EXISTS cap_keys (
  agent_id    TEXT PRIMARY KEY,
  privkey_hex TEXT NOT NULL,
  pubkey_hex  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cap_trust_roots (
  agent_id   TEXT PRIMARY KEY,
  pubkey_hex TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class SignedCap:
    """A capability bundled with its signature + signer identity.

    Caps move around the system as ``SignedCap`` records. Their persistent
    form lives in the SQLite ``caps`` table; their wire form is the URI +
    the (cap_id, signature, pubkey) triple.
    """

    cap_id: str
    uri: str
    capability: Capability  # parsed form of the URI for fast access
    issuer: str
    signature_hex: str
    issuer_pubkey_hex: str
    issued_at: float
    parent_cap_id: str | None
    revoked: bool = False


@dataclass(frozen=True)
class CapVerifyContext:
    """What the caller is asking permission for. Passed to
    ``verify_request`` alongside the cap they're presenting.

    The check is: does this cap (when valid) authorize THIS context?
    """

    scheme: str
    action: str
    resource_kind: str
    resource_id: str
    attenuations: tuple[tuple[str, str], ...] = ()

    def as_capability(self) -> Capability:
        return Capability(
            scheme=self.scheme,
            action=self.action,
            resource_kind=self.resource_kind,
            resource_id=self.resource_id,
            attenuations=tuple(sorted(self.attenuations)),
        )


def default_cap_store_path() -> Path:
    """Default CapStore DB path under the active ``AGENTDRIVE_HOME``."""
    return get_agentdrive_home() / "cap" / "_caps.db"


_default_cap_store: CapStore | None = None


def get_default_cap_store() -> CapStore:
    """Process-local default CapStore, rebuilt if ``AGENTDRIVE_HOME`` changes."""
    global _default_cap_store
    expected_path = default_cap_store_path()
    if _default_cap_store is None or _default_cap_store.db_path != expected_path:
        _default_cap_store = CapStore(expected_path)
    return _default_cap_store


def _request_scope(capability: Capability) -> Capability:
    """Return only the fields that constrain a requested operation.

    ``expires`` is a validity attenuation checked by ``verify()``. It
    should not force every caller to echo a timestamp in their request
    context.
    """
    return Capability(
        scheme=capability.scheme,
        action=capability.action,
        resource_kind=capability.resource_kind,
        resource_id=capability.resource_id,
        attenuations=tuple((k, v) for k, v in capability.attenuations if k != "expires"),
    )


class CapStore:
    """Mint, derive, verify capability URIs. The single arbiter of access."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        from agentdrive.db_pragmas import apply_pragmas

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        apply_pragmas(conn)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript(_SCHEMA)

    # ── key + trust management ─────────────────────────────────────────────

    def get_or_create_keypair(self, agent_id: str) -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
        """Ensure an agent has a keypair; return it. Idempotent."""
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT privkey_hex FROM cap_keys WHERE agent_id = ?", (agent_id,)
            ).fetchone()
            if row is not None:
                priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(row["privkey_hex"]))
                return priv, priv.public_key()

            priv = Ed25519PrivateKey.generate()
            pub = priv.public_key()
            priv_bytes = priv.private_bytes(
                encoding=Encoding.Raw,
                format=PrivateFormat.Raw,
                encryption_algorithm=NoEncryption(),
            )
            pub_bytes = pub.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
            c.execute(
                "INSERT INTO cap_keys(agent_id, privkey_hex, pubkey_hex) VALUES (?, ?, ?)",
                (agent_id, priv_bytes.hex(), pub_bytes.hex()),
            )
            c.execute(
                "INSERT OR IGNORE INTO cap_trust_roots(agent_id, pubkey_hex) VALUES (?, ?)",
                (agent_id, pub_bytes.hex()),
            )
            return priv, pub

    def trust_root(self, agent_id: str, pubkey_hex: str) -> None:
        """Register an external agent's public key as a trust root.

        Caps signed by this agent will verify. In v2/M3 this is the only
        chain mechanism; v3 will add multi-hop chain walking.
        """
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO cap_trust_roots(agent_id, pubkey_hex) VALUES (?, ?)",
                (agent_id, pubkey_hex),
            )

    def is_trusted_root(self, agent_id: str, pubkey_hex: str) -> bool:
        with self._conn() as c:
            row = c.execute(
                "SELECT pubkey_hex FROM cap_trust_roots WHERE agent_id = ?", (agent_id,)
            ).fetchone()
        return row is not None and row["pubkey_hex"] == pubkey_hex

    # ── mint ───────────────────────────────────────────────────────────────

    def mint(
        self,
        *,
        issuer: str,
        capability: Capability,
        parent_cap_id: str | None = None,
    ) -> SignedCap:
        """Sign and persist a new capability.

        If ``parent_cap_id`` is set, the new cap must be narrower than
        the parent (subset minting). Root caps (parent=None) can be
        minted only by the issuer themselves — the trust root model.
        """
        if parent_cap_id is not None:
            parent = self.get(parent_cap_id)
            if parent.issuer != issuer:
                raise CapDerivationError(
                    f"issuer {issuer!r} cannot mint from parent cap "
                    f"{parent_cap_id!r} held by {parent.issuer!r}"
                )
            if not capability.is_narrower_than(parent.capability):
                raise CapDerivationError(
                    f"minted cap {capability.to_uri()!r} is not narrower than parent {parent.uri!r}"
                )

        priv, pub = self.get_or_create_keypair(issuer)
        pub_hex = pub.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw).hex()
        cap_id = str(uuid.uuid4())
        uri = capability.to_uri()
        signature = priv.sign(uri.encode("utf-8")).hex()
        issued_at = time.time()

        with self._lock, self._conn() as c:
            c.execute(
                """
                INSERT INTO caps(cap_id, uri, issuer, signature, issuer_pubkey,
                                 issued_at, parent_cap_id, revoked)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (cap_id, uri, issuer, signature, pub_hex, issued_at, parent_cap_id),
            )

        signed = SignedCap(
            cap_id=cap_id,
            uri=uri,
            capability=capability,
            issuer=issuer,
            signature_hex=signature,
            issuer_pubkey_hex=pub_hex,
            issued_at=issued_at,
            parent_cap_id=parent_cap_id,
            revoked=False,
        )
        from agentdrive.utils.log_safe import safe_for_log

        logger.info(
            "Capability minted",
            extra={
                "cap_id": safe_for_log(cap_id),
                "issuer": safe_for_log(issuer),
                "uri": safe_for_log(uri),
            },
        )
        return signed

    def mint_session(
        self,
        *,
        issuer: str,
        capability: Capability,
        ttl_seconds: int = 300,
        parent_cap_id: str | None = None,
    ) -> SignedCap:
        """Mint a short-lived cap using the existing signed-cap primitive.

        The helper only adds an ``expires`` attenuation before delegating to
        ``mint()``. If the caller already supplied ``expires``, the stricter
        earlier deadline wins.
        """
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")

        now = time.time()
        deadline = now + ttl_seconds
        existing = capability.attenuation("expires")
        if existing is not None:
            try:
                deadline = min(deadline, float(existing))
            except ValueError as exc:
                raise CapDerivationError(f"cap has malformed expires={existing!r}") from exc
            if deadline <= now:
                raise CapDerivationError("session cap expiry must be in the future")

        return self.mint(
            issuer=issuer,
            capability=capability.with_attenuation("expires", f"{deadline:.6f}"),
            parent_cap_id=parent_cap_id,
        )

    # ── derive ─────────────────────────────────────────────────────────────

    def derive(
        self,
        *,
        parent_cap_id: str,
        action: str | None = None,
        extra_attenuations: dict[str, str] | None = None,
    ) -> SignedCap:
        """Convenience over ``mint``: produce a narrower cap from a parent.

        Common uses: a write-cap holder derives the corresponding read-cap;
        a swarm-cap holder derives a sub-agent-scoped cap; a holder narrows
        the eval threshold or shrinks max_hops.
        """
        parent = self.get(parent_cap_id)
        cap = parent.capability
        if action is not None and action != cap.action:
            cap = Capability(
                scheme=cap.scheme,
                action=action,
                resource_kind=cap.resource_kind,
                resource_id=cap.resource_id,
                attenuations=cap.attenuations,
            )
        if extra_attenuations:
            for k, v in extra_attenuations.items():
                cap = cap.with_attenuation(k, v)
        return self.mint(
            issuer=parent.issuer,
            capability=cap,
            parent_cap_id=parent_cap_id,
        )

    # ── lookup ─────────────────────────────────────────────────────────────

    def get(self, cap_id: str) -> SignedCap:
        with self._conn() as c:
            row = c.execute("SELECT * FROM caps WHERE cap_id = ?", (cap_id,)).fetchone()
        if row is None:
            raise CapInvalidError(f"cap {cap_id!r} not found")
        return SignedCap(
            cap_id=row["cap_id"],
            uri=row["uri"],
            capability=parse_uri(row["uri"]),
            issuer=row["issuer"],
            signature_hex=row["signature"],
            issuer_pubkey_hex=row["issuer_pubkey"],
            issued_at=row["issued_at"],
            parent_cap_id=row["parent_cap_id"],
            revoked=bool(row["revoked"]),
        )

    def revoke(self, cap_id: str) -> bool:
        with self._lock, self._conn() as c:
            cur = c.execute("UPDATE caps SET revoked = 1 WHERE cap_id = ?", (cap_id,))
            return cur.rowcount > 0

    # ── the 30-line cap resolver — the AgentDrive moment ───────────────────

    def verify(self, cap: SignedCap) -> None:
        """Structural verification: signature OK, not revoked, trust root
        recognized. Does NOT check whether the cap covers any particular
        request — that's ``verify_request``."""
        # Signature
        try:
            pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(cap.issuer_pubkey_hex))
            pub.verify(bytes.fromhex(cap.signature_hex), cap.uri.encode("utf-8"))
        except (InvalidSignature, ValueError) as exc:
            raise CapInvalidError(f"signature check failed: {exc}") from exc
        # Trust root
        if not self.is_trusted_root(cap.issuer, cap.issuer_pubkey_hex):
            raise CapInvalidError(f"issuer {cap.issuer!r} not in trust roots — refuse to honor cap")
        # Expiry attenuation (separate from any grant TTL)
        expires = cap.capability.attenuation("expires")
        if expires is not None:
            try:
                if time.time() > float(expires):
                    raise CapInvalidError(f"cap expired at {expires}")
            except ValueError:
                raise CapInvalidError(f"cap has malformed expires={expires!r}")
        # Revocation
        fresh = self.get(cap.cap_id)
        if fresh.revoked:
            raise CapInvalidError(f"cap {cap.cap_id} has been revoked")

    def verify_request(self, cap: SignedCap, context: CapVerifyContext) -> None:
        """The single arbiter. Every Drive boundary calls this.

        Raises ``InsufficientCapability`` if the cap is valid but its
        scope doesn't cover the requested context. Raises
        ``CapInvalidError`` on signature / expiry / revocation failure.
        Returns silently if access is authorized.
        """
        self.verify(cap)
        requested = context.as_capability()
        if not requested.is_narrower_than(_request_scope(cap.capability)):
            raise InsufficientCapability(
                f"cap {cap.uri!r} does not authorize request {requested.to_uri()!r}"
            )


class RequestAuthorizer:
    """Small boundary helper around ``CapStore.verify_request()``.

    Call sites should build the concrete request through these methods so
    every boundary uses the same CapStore semantics while still making the
    protected operation obvious in code.
    """

    def __init__(self, store: CapStore | None = None):
        self.store = store or get_default_cap_store()

    def verify(self, cap: SignedCap, context: CapVerifyContext) -> SignedCap:
        self.store.verify_request(cap, context)
        return cap

    def verify_drive_read(self, cap: SignedCap, *, swarm_id: str) -> SignedCap:
        return self.verify(
            cap,
            CapVerifyContext(
                scheme="drive",
                action="read",
                resource_kind="swarm",
                resource_id=swarm_id,
            ),
        )

    def verify_drive_write(
        self,
        cap: SignedCap,
        *,
        swarm_id: str,
        subagent_id: str | None = None,
    ) -> SignedCap:
        attenuations = (("sub", subagent_id),) if subagent_id else ()
        return self.verify(
            cap,
            CapVerifyContext(
                scheme="drive",
                action="write",
                resource_kind="swarm",
                resource_id=swarm_id,
                attenuations=attenuations,
            ),
        )

    def verify_dna_pull(
        self,
        cap: SignedCap,
        *,
        lineage_id: str,
        max_hops: int | None = None,
        min_eval: float | None = None,
    ) -> SignedCap:
        attenuations: list[tuple[str, str]] = []
        if max_hops is not None:
            attenuations.append(("max_hops", str(max_hops)))
        if min_eval is not None:
            attenuations.append(("min_eval", str(min_eval)))
        return self.verify(
            cap,
            CapVerifyContext(
                scheme="dna",
                action="pull",
                resource_kind="lineage",
                resource_id=lineage_id,
                attenuations=tuple(attenuations),
            ),
        )
