"""Content-addressed object store for AgentDrive v2 (Milestone 1).

Atom: a Genome. Address: SHA-256 of its canonical JSON.
On-disk path: ``<drive_root>/objects/<aa>/<rest-of-hash>.json``
(Git-style two-character sharding to keep any one directory's fanout bounded.)

What this module guarantees:

- **Deterministic hashing.** ``canonical_genome_json()`` is the single source of
  truth for what bytes get hashed. Same Genome → same hash, every time, on every
  machine, regardless of insertion order in dicts or whitespace style.
- **Dedup for free.** Two sub-agents that emit byte-identical Genomes write to
  the same path; the second write is a no-op (atomic skip).
- **Lookup by hash.** ``get(hash)`` returns the stored bytes (or None). The
  caller deserializes into whatever schema they want.
- **Sibling-blind.** The store knows nothing about authors, swarms, or
  capabilities — those layers ride on top in later milestones. Keeping this
  module narrow is the point.

What this module does NOT do (yet — explicit non-goals for Milestone 1):

- Encryption at rest. The on-disk bytes are plaintext JSON. Crypto lands in
  Milestone 3 alongside capability URIs.
- Garbage collection. Reference-counted GC lands in Milestone 4. For now the
  store is append-only and orphans linger.
- Network sync / federation. Cross-Drive replication is Milestone 5.

Backed by, and intentionally compatible with, the existing
``agentdrive.drive.drive.AgentDrive`` layout. v1 Genome directories at
``<root>/genomes/<id>/<version>/`` are not touched; the content store lives
beside them under ``<root>/objects/``. Migration is opt-in.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Two-character sharding keeps the fan-out of objects/ bounded.
# At 1M Genomes you average ~3.9k objects per shard — still fast on every FS.
_SHARD_LEN = 2


# ─────────────────────────────────────────────────────────────────────────────
# Canonical serialization
# ─────────────────────────────────────────────────────────────────────────────


def canonical_json(payload: dict[str, Any]) -> bytes:
    """Deterministic JSON serialization. The single rule the whole hash scheme rests on.

    - Keys sorted at every depth (``sort_keys=True``).
    - Minimal separators (no incidental whitespace differences).
    - ``ensure_ascii=False`` so unicode round-trips as itself, not as ``\\uXXXX``.
    - UTF-8 bytes (the only encoding that has any business being hashed).
    - ``default=str`` so datetimes etc. serialize predictably; callers that
      care about exact datetime shape should normalize before passing in.
    """
    text = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return text.encode("utf-8")


def hash_bytes(data: bytes) -> str:
    """SHA-256 over raw bytes, returned in our canonical ``sha256:<hex>`` form."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def hash_payload(payload: dict[str, Any]) -> str:
    """Convenience: canonicalize then hash. The two-step is exposed so callers
    that need both the bytes and the hash (e.g. ``put_payload``) don't double-encode.
    """
    return hash_bytes(canonical_json(payload))


def canonical_genome_payload(genome: Any) -> dict[str, Any]:
    """Extract the *content* of a Genome — the part that defines what it IS,
    not where it came from or who saw it last.

    The choice of fields is the spec of "same Genome." Two Genomes with the
    same framework / reasoning / tools / evaluations are the same Genome,
    regardless of who authored them, when, or under what version label.
    Author/timestamp/score live in the manifest but are NOT in the hash —
    they're observation metadata, not identity.

    Mirrors ``Genome.compute_content_hash`` so the same bytes get hashed in
    both places. If you change this, change that.
    """
    return {
        "framework": getattr(genome, "framework", None) or {},
        "reasoning_patterns": getattr(genome, "reasoning_patterns", {}) or {},
        "tool_compositions": getattr(genome, "tool_compositions", {}) or {},
        "evaluations": getattr(genome, "evaluations", {}) or {},
    }


def genome_hash(genome: Any) -> str:
    """Hash a Genome by its content payload. Matches ``Genome.compute_content_hash()``."""
    return hash_payload(canonical_genome_payload(genome))


# ─────────────────────────────────────────────────────────────────────────────
# Store
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PutResult:
    """Outcome of a single ``put`` call. ``existed=True`` means dedup hit."""

    hash: str
    path: Path
    existed: bool


class ContentStore:
    """Sharded, content-addressed object store rooted at ``<drive_root>/objects/``.

    Cheap to instantiate (no I/O until first put/get). Thread-safe for
    concurrent puts of the same hash because writes are atomic via
    rename-into-place — the worst case is two processes writing the same
    bytes to the same final path; the OS gives us one winner and the other
    becomes a no-op.
    """

    def __init__(self, drive_root: Path | str) -> None:
        self.root = Path(drive_root) / "objects"

    # ── identity / path math ────────────────────────────────────────────────

    def _path_for(self, content_hash: str) -> Path:
        """``sha256:abcdef…`` → ``<root>/ab/cdef….json``.

        We strip the ``sha256:`` prefix on disk because every file in the
        tree is sha256; encoding it in the path is just noise. The Python
        API still uses the prefixed form externally for clarity.
        """
        if not content_hash.startswith("sha256:"):
            raise ValueError(f"content_hash must be sha256-prefixed, got: {content_hash!r}")
        hexpart = content_hash[len("sha256:") :]
        if len(hexpart) < _SHARD_LEN + 1:
            raise ValueError(f"sha256 payload too short: {content_hash!r}")
        return self.root / hexpart[:_SHARD_LEN] / f"{hexpart[_SHARD_LEN:]}.json"

    # ── writes ──────────────────────────────────────────────────────────────

    def put_bytes(self, content_hash: str, data: bytes) -> PutResult:
        """Store raw canonical bytes under ``content_hash``. Idempotent.

        Atomic via tmp-file + ``os.replace``: a concurrent reader either sees
        the file fully written or doesn't see it at all — never partial.
        """
        target = self._path_for(content_hash)
        if target.exists():
            return PutResult(hash=content_hash, path=target, existed=True)

        target.parent.mkdir(parents=True, exist_ok=True)
        # NamedTemporaryFile in the same dir → rename is guaranteed atomic.
        fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=str(target.parent))
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, target)
        except Exception:
            # Best-effort cleanup; rename failure should be loud, not silent.
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
            raise
        return PutResult(hash=content_hash, path=target, existed=False)

    def put_payload(self, payload: dict[str, Any]) -> PutResult:
        """Hash + store a JSON-able payload. The hash is computed from the
        canonical bytes we're about to write, so what was hashed and what
        was stored are byte-identical by construction.
        """
        data = canonical_json(payload)
        return self.put_bytes(hash_bytes(data), data)

    def put_genome(self, genome: Any) -> PutResult:
        """Store a Genome's content payload, return the hash + path.

        The Genome's manifest and provenance are NOT in the content store —
        those are observation metadata kept in the registry layer. The
        content store holds only the identity-defining payload.
        """
        return self.put_payload(canonical_genome_payload(genome))

    # ── reads ───────────────────────────────────────────────────────────────

    def has(self, content_hash: str) -> bool:
        return self._path_for(content_hash).exists()

    def get_bytes(self, content_hash: str) -> bytes | None:
        path = self._path_for(content_hash)
        try:
            return path.read_bytes()
        except FileNotFoundError:
            return None

    def get_payload(self, content_hash: str) -> dict[str, Any] | None:
        raw = self.get_bytes(content_hash)
        if raw is None:
            return None
        return json.loads(raw.decode("utf-8"))

    # ── enumeration / stats ─────────────────────────────────────────────────

    def iter_hashes(self) -> Iterator[str]:
        """Walk every stored object. O(N) over the entire store — for stats
        and migration only, not for hot paths.
        """
        if not self.root.exists():
            return
        for shard in self.root.iterdir():
            if not shard.is_dir() or len(shard.name) != _SHARD_LEN:
                continue
            for obj in shard.iterdir():
                if obj.suffix == ".json" and not obj.name.startswith(".tmp-"):
                    yield "sha256:" + shard.name + obj.stem

    def count(self) -> int:
        return sum(1 for _ in self.iter_hashes())
