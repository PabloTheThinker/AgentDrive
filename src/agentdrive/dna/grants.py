"""LineageShareGrant — sideways DNA sharing across cousin agents.

The opt-in opposite of forward-only ancestry inheritance. When two agents
from different swarms (or different lineages entirely) want to share DNA,
the *issuing* agent mints a signed grant naming the *grantee*, the scope
of Genomes that may be pulled, the eval threshold the grantee will apply,
and a TTL after which the grant stops issuing new access.

Note the careful wording: **the grant gates new issuance, not data
already received.** Once a grantee pulls a Genome through a grant, it's
theirs forever — matches the Avatar mental model Pablo specified (no
decay, inheritance is permanent). The TTL stops the *flow*, not the
already-flowed.

Three failure modes the grant model deliberately defends against:

1. **Poisoned cousin.** Granted DNA never lands in the grantee's active
   pool directly; it goes through the existing ``quarantine`` machinery
   for explicit operator (or automated eval) approval.
2. **Sybil flooding.** Per-issuer quotas cap the number of active grants
   an agent can mint in a window.
3. **Cousin disagreement / contradicting Genomes.** The grant carries a
   ``reducer`` hint telling the grantee how to merge with its own DNA:
   ``append`` (keep both), ``overwrite`` (prefer cousin), or
   ``prefer-higher-eval`` (let scores decide).

Ed25519 signing because it's tiny, fast, and present in the standard
``cryptography`` library that's already a transitive dep.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

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

logger = logging.getLogger(__name__)


ReducerKind = Literal["append", "overwrite", "prefer-higher-eval"]


# ─────────────────────────────────────────────────────────────────────
# Grant payload
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GrantScope:
    """What a grant authorizes the grantee to pull.

    All fields are optional filters; if every filter is unset, the grant
    is wide-open (the issuer's entire DNA Drive). Specific is safer.
    """

    topics: tuple[str, ...] = field(default_factory=tuple)
    """Genome topic / domain filters (matched against
    ``Genome.applicability.domains``). Empty tuple = no topic filter."""

    min_eval: float = 0.7
    """Eval-score floor applied to every Genome before it crosses the
    grant boundary. Default 0.7 for cross-source pulls per the v2 design."""

    content_hashes: tuple[str, ...] = field(default_factory=tuple)
    """If non-empty, the grant is restricted to exactly these content
    hashes. The narrowest possible grant — useful for one-shot transfers."""


@dataclass(frozen=True)
class LineageShareGrant:
    """A signed, scoped, time-bounded authorization for one agent to pull
    DNA from another. Serialize/deserialize via ``to_dict`` / ``from_dict``;
    sign / verify via the ``GrantStore``.
    """

    grant_id: str
    issuer: str
    grantee: str
    scope: GrantScope
    reducer: ReducerKind
    ttl_seconds: int
    issued_at: float
    signature: str  # hex-encoded Ed25519 signature over canonical bytes
    issuer_pubkey: str  # hex-encoded Ed25519 public key (for verification)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["scope"] = asdict(self.scope)
        d["scope"]["topics"] = list(self.scope.topics)
        d["scope"]["content_hashes"] = list(self.scope.content_hashes)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> LineageShareGrant:
        scope_d = d["scope"]
        scope = GrantScope(
            topics=tuple(scope_d.get("topics", [])),
            min_eval=float(scope_d.get("min_eval", 0.7)),
            content_hashes=tuple(scope_d.get("content_hashes", [])),
        )
        return cls(
            grant_id=d["grant_id"],
            issuer=d["issuer"],
            grantee=d["grantee"],
            scope=scope,
            reducer=d["reducer"],
            ttl_seconds=int(d["ttl_seconds"]),
            issued_at=float(d["issued_at"]),
            signature=d["signature"],
            issuer_pubkey=d["issuer_pubkey"],
        )

    def is_expired(self, *, now: float | None = None) -> bool:
        """Has the issuance TTL elapsed? (Data already received is not affected.)"""
        ts = now if now is not None else time.time()
        return ts > self.issued_at + self.ttl_seconds

    def canonical_signing_payload(self) -> bytes:
        """The exact bytes signed when the grant was minted. Excludes the
        signature itself and the issuer_pubkey (the latter is identity, not
        payload). Deterministic JSON so verification is reproducible."""
        body = {
            "grant_id": self.grant_id,
            "issuer": self.issuer,
            "grantee": self.grantee,
            "scope": {
                "topics": list(self.scope.topics),
                "min_eval": self.scope.min_eval,
                "content_hashes": list(self.scope.content_hashes),
            },
            "reducer": self.reducer,
            "ttl_seconds": self.ttl_seconds,
            "issued_at": self.issued_at,
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


# ─────────────────────────────────────────────────────────────────────
# Grant store
# ─────────────────────────────────────────────────────────────────────


class GrantQuotaExceededError(Exception):
    """Raised when an issuer tries to mint more grants than the quota allows."""


class GrantInvalidError(Exception):
    """Raised when a grant fails signature, expiry, or scope checks."""


_GRANT_SCHEMA = """
CREATE TABLE IF NOT EXISTS grants (
  grant_id     TEXT PRIMARY KEY,
  issuer       TEXT NOT NULL,
  grantee      TEXT NOT NULL,
  scope_json   TEXT NOT NULL,
  reducer      TEXT NOT NULL,
  ttl_seconds  INTEGER NOT NULL,
  issued_at    REAL NOT NULL,
  signature    TEXT NOT NULL,
  issuer_pubkey TEXT NOT NULL,
  revoked      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_grant_issuer  ON grants(issuer);
CREATE INDEX IF NOT EXISTS idx_grant_grantee ON grants(grantee);

CREATE TABLE IF NOT EXISTS issuer_keys (
  agent_id    TEXT PRIMARY KEY,
  privkey_hex TEXT NOT NULL,
  pubkey_hex  TEXT NOT NULL
);
"""


class GrantStore:
    """SQLite-backed grant registry + key store.

    For v2 / Milestone 2c the key store holds Ed25519 private keys directly
    in the DB. This is fine for a local-first system where the whole
    AgentDrive home directory is already the trust boundary; a future
    milestone can swap in OS keychain integration without changing the
    public API.
    """

    DEFAULT_QUOTA_PER_ISSUER = 50
    """Max active (non-revoked, non-expired) grants per issuer. Sybil
    flood defense — see ``docs/AGENTDRIVE-V2-INHERITANCE.md``."""

    def __init__(self, db_path: Path | str, *, quota_per_issuer: int | None = None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.quota = (
            quota_per_issuer if quota_per_issuer is not None else self.DEFAULT_QUOTA_PER_ISSUER
        )
        self._lock = threading.RLock()
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript(_GRANT_SCHEMA)

    # ── key management ──────────────────────────────────────────────────────

    def get_or_create_keypair(self, agent_id: str) -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
        """Return the agent's Ed25519 keypair, creating it on first use."""
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT privkey_hex, pubkey_hex FROM issuer_keys WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()
            if row is not None:
                priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(row["privkey_hex"]))
                pub = priv.public_key()
                return priv, pub

            priv = Ed25519PrivateKey.generate()
            pub = priv.public_key()
            priv_bytes = priv.private_bytes(
                encoding=Encoding.Raw,
                format=PrivateFormat.Raw,
                encryption_algorithm=NoEncryption(),
            )
            pub_bytes = pub.public_bytes(
                encoding=Encoding.Raw,
                format=PublicFormat.Raw,
            )
            c.execute(
                "INSERT INTO issuer_keys(agent_id, privkey_hex, pubkey_hex) VALUES (?, ?, ?)",
                (agent_id, priv_bytes.hex(), pub_bytes.hex()),
            )
            return priv, pub

    def get_pubkey(self, agent_id: str) -> Ed25519PublicKey | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT pubkey_hex FROM issuer_keys WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()
        if row is None:
            return None
        return Ed25519PublicKey.from_public_bytes(bytes.fromhex(row["pubkey_hex"]))

    # ── grant minting ──────────────────────────────────────────────────────

    def issue(
        self,
        *,
        issuer: str,
        grantee: str,
        scope: GrantScope | None = None,
        reducer: ReducerKind = "append",
        ttl_seconds: int = 7 * 24 * 3600,
    ) -> LineageShareGrant:
        """Issue a new signed grant. Enforces the per-issuer quota and
        rejects if exceeded."""
        if self._active_grant_count(issuer) >= self.quota:
            raise GrantQuotaExceededError(
                f"agent {issuer!r} has reached the active-grant quota ({self.quota})"
            )

        priv, pub = self.get_or_create_keypair(issuer)
        scope = scope or GrantScope()
        pub_bytes = pub.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)

        # Build the grant body (without signature), sign it, then materialize.
        grant_id = str(uuid.uuid4())
        unsigned = LineageShareGrant(
            grant_id=grant_id,
            issuer=issuer,
            grantee=grantee,
            scope=scope,
            reducer=reducer,
            ttl_seconds=ttl_seconds,
            issued_at=time.time(),
            signature="",  # filled below
            issuer_pubkey=pub_bytes.hex(),
        )
        signature = priv.sign(unsigned.canonical_signing_payload())
        grant = LineageShareGrant(
            grant_id=unsigned.grant_id,
            issuer=unsigned.issuer,
            grantee=unsigned.grantee,
            scope=unsigned.scope,
            reducer=unsigned.reducer,
            ttl_seconds=unsigned.ttl_seconds,
            issued_at=unsigned.issued_at,
            signature=signature.hex(),
            issuer_pubkey=unsigned.issuer_pubkey,
        )

        with self._lock, self._conn() as c:
            c.execute(
                """
                INSERT INTO grants(grant_id, issuer, grantee, scope_json, reducer,
                                   ttl_seconds, issued_at, signature, issuer_pubkey)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    grant.grant_id,
                    grant.issuer,
                    grant.grantee,
                    json.dumps(grant.to_dict()["scope"], sort_keys=True),
                    grant.reducer,
                    grant.ttl_seconds,
                    grant.issued_at,
                    grant.signature,
                    grant.issuer_pubkey,
                ),
            )

        logger.info(
            "Issued lineage_share grant",
            extra={
                "grant_id": grant.grant_id,
                "issuer": issuer,
                "grantee": grantee,
                "ttl_seconds": ttl_seconds,
            },
        )
        return grant

    def _active_grant_count(self, issuer: str) -> int:
        now = time.time()
        with self._conn() as c:
            rows = c.execute(
                "SELECT issued_at, ttl_seconds FROM grants WHERE issuer = ? AND revoked = 0",
                (issuer,),
            ).fetchall()
        return sum(1 for r in rows if now <= r["issued_at"] + r["ttl_seconds"])

    # ── grant verification + lookup ─────────────────────────────────────────

    def verify(self, grant: LineageShareGrant) -> None:
        """Verify a grant's signature, expiry, and revocation status. Raises
        ``GrantInvalidError`` on any failure; returns silently if valid."""
        # Signature
        try:
            pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(grant.issuer_pubkey))
            pub.verify(bytes.fromhex(grant.signature), grant.canonical_signing_payload())
        except (InvalidSignature, ValueError) as exc:
            raise GrantInvalidError(f"signature check failed: {exc}") from exc

        # Expiry
        if grant.is_expired():
            raise GrantInvalidError(f"grant {grant.grant_id} expired")

        # Revocation
        with self._conn() as c:
            row = c.execute(
                "SELECT revoked FROM grants WHERE grant_id = ?", (grant.grant_id,)
            ).fetchone()
        if row is None:
            raise GrantInvalidError(f"grant {grant.grant_id} not found in store")
        if row["revoked"]:
            raise GrantInvalidError(f"grant {grant.grant_id} has been revoked")

    def revoke(self, grant_id: str) -> bool:
        """Mark a grant as revoked. Future ``verify()`` calls will reject it.
        Returns True if a row was updated, False if the grant wasn't found."""
        with self._lock, self._conn() as c:
            cur = c.execute("UPDATE grants SET revoked = 1 WHERE grant_id = ?", (grant_id,))
            return cur.rowcount > 0

    def grants_for_grantee(self, grantee: str) -> list[LineageShareGrant]:
        """All non-revoked, non-expired grants where this agent is the grantee."""
        now = time.time()
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM grants WHERE grantee = ? AND revoked = 0",
                (grantee,),
            ).fetchall()
        out: list[LineageShareGrant] = []
        for r in rows:
            if now > r["issued_at"] + r["ttl_seconds"]:
                continue
            scope_d = json.loads(r["scope_json"])
            out.append(
                LineageShareGrant(
                    grant_id=r["grant_id"],
                    issuer=r["issuer"],
                    grantee=r["grantee"],
                    scope=GrantScope(
                        topics=tuple(scope_d.get("topics", [])),
                        min_eval=float(scope_d.get("min_eval", 0.7)),
                        content_hashes=tuple(scope_d.get("content_hashes", [])),
                    ),
                    reducer=r["reducer"],
                    ttl_seconds=r["ttl_seconds"],
                    issued_at=r["issued_at"],
                    signature=r["signature"],
                    issuer_pubkey=r["issuer_pubkey"],
                )
            )
        return out


# ─────────────────────────────────────────────────────────────────────
# Cross-cousin pull
# ─────────────────────────────────────────────────────────────────────


def pull_via_grant(grant: LineageShareGrant, store: GrantStore) -> list[InheritedGenome]:
    """Execute a grant: verify it, walk the issuer's DNA Drive, return
    every Genome the grant scope authorizes.

    The grantee's local DNADrive should call this and route the results
    through quarantine (NOT auto-publish) per the memory-poisoning
    defense in the v2 design doc.
    """
    from agentdrive.drive.content_store import ContentStore

    from .drive import InheritedGenome, _agent_dna_root

    store.verify(grant)
    issuer_store = ContentStore(_agent_dna_root(grant.issuer) / "drive")

    # Hash filter — if scope lists specific hashes, only those.
    if grant.scope.content_hashes:
        candidate_hashes = list(grant.scope.content_hashes)
    else:
        candidate_hashes = list(issuer_store.iter_hashes())

    results: list[InheritedGenome] = []
    for content_hash in candidate_hashes:
        payload = issuer_store.get_payload(content_hash)
        if payload is None:
            continue

        # Topic filter — payload has no manifest, so we look at framework
        # tags if the issuer happened to embed them. Topics are best-effort
        # for v2c; richer manifest-traveling metadata is M2d's problem.
        if grant.scope.topics:
            framework = payload.get("framework") or {}
            payload_topics: list[str] = []
            if isinstance(framework, dict):
                if isinstance(framework.get("domains"), list):
                    payload_topics.extend(framework["domains"])
            if not any(t in payload_topics for t in grant.scope.topics):
                continue

        # Eval gate — same logic as forward inheritance.
        if grant.scope.min_eval > 0.0:
            evals = payload.get("evaluations") or {}
            score = 0.0
            if isinstance(evals, dict):
                scored = [v for v in evals.values() if isinstance(v, (int, float))]
                score = max(scored) if scored else 0.0
            if score < grant.scope.min_eval:
                continue

        results.append(
            InheritedGenome(
                content_hash=content_hash,
                source_agent=grant.issuer,
                depth=-1,  # -1 marks cross-source: NOT a forward-line ancestor
                payload=payload,
            )
        )
    return results
