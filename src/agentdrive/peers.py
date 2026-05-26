"""Federated peer registry — opt-in trusted peer Agent Drives.

Operators register other Agent Drive instances they trust. The registry is the
public face of proposal #6 in ``docs/POOL-EVOLUTION.md``. A `sync_peer`
operation walks a peer's address through the matching `PeerAdapter`,
collects new genome directories produced since the last sync, and routes
every single one through ``quarantine.submit()``. There is no fast-path,
no "trusted" shortcut, no direct ``pool.ingest`` call anywhere in this
module — even peers marked ``trust_level="trusted"`` route through the
quarantine gate. ``trust_level`` only governs *defaults* for the operator
review step (auto-approve hints) once the trust store ships; it does NOT
bypass validation in v1.

Public key handling is a v1 placeholder. The ``public_key`` field
persists alongside each peer entry, but no signature verification runs
yet. Real ed25519 verification lands when the trust store ships
(see ``SignatureValid`` in ``agentdrive.quarantine``).

Adapter scope (v1):
    - ``LocalFilePeerAdapter`` (``file://`` and bare paths) — walks
      another AGENTDRIVE_HOME-like directory's ``genomes/`` tree. Enough to
      demo federation between two homes on the same machine.

Adapters for ``https://`` and ``agentdrive://`` schemes are intentionally
out of scope here. They plug in by subclassing ``PeerAdapter``, setting
``SCHEME``, and registering via ``register_adapter``.

On-disk layout (under $AGENTDRIVE_HOME/peers/):
    <peer_id>.json   — one file per peer, atomic-written

Module API:
    PeerEntry            — dataclass persisted per peer
    PeerRegistry         — add / remove / get / list / set_trust / touch_last_sync
    PeerAdapter          — abstract base for scheme handlers
    LocalFilePeerAdapter — v1 file-based adapter
    register_adapter     — install a custom adapter
    get_adapter_for      — adapter lookup by address scheme
    PeerSyncResult       — dataclass returned by sync_peer
    sync_peer            — top-level federation operation
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse

from agentdrive.constants import get_agentdrive_home
from agentdrive.events import (
    PeerAdded,
    PeerRemoved,
    PeerSyncCompleted,
    PeerSyncStarted,
    PeerTrustChanged,
    emit,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────

VALID_TRUST_LEVELS: tuple[str, ...] = ("untrusted", "review", "trusted")
_EPOCH_ISO = "1970-01-01T00:00:00+00:00"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ─────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────


@dataclass
class PeerEntry:
    """One registered peer Agent Drive.

    ``public_key`` is a placeholder slot in v1: it persists and round-trips
    but is not used for signature verification yet.
    """

    peer_id: str
    address: str
    public_key: str | None = None
    trust_level: str = "untrusted"
    last_sync_iso: str | None = None
    added_at: str = field(default_factory=_utc_now_iso)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PeerEntry:
        return cls(
            peer_id=str(data["peer_id"]),
            address=str(data["address"]),
            public_key=data.get("public_key") or None,
            trust_level=str(data.get("trust_level", "untrusted")),
            last_sync_iso=data.get("last_sync_iso") or None,
            added_at=str(data.get("added_at", _utc_now_iso())),
            notes=str(data.get("notes", "") or ""),
        )


@dataclass
class PeerSyncResult:
    """Outcome of one ``sync_peer`` invocation."""

    peer_id: str
    submitted: int = 0
    quarantine_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: int = 0


# ─────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────


class PeerRegistry:
    """Persistent peer directory.

    One JSON file per peer under ``$AGENTDRIVE_HOME/peers/<peer_id>.json``.
    Atomic writes via tempfile + rename so concurrent reads never see
    half-written records.
    """

    def __init__(self, root: Path | str | None = None) -> None:
        if root is None:
            root = get_agentdrive_home() / "peers"
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ---- on-disk paths ----

    def _entry_path(self, peer_id: str) -> Path:
        return self.root / f"{peer_id}.json"

    def _atomic_write(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, default=str)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    # ---- CRUD ----

    def add(
        self,
        peer_id: str,
        address: str,
        *,
        trust_level: str = "untrusted",
        notes: str = "",
        public_key: str | None = None,
    ) -> PeerEntry:
        """Register a peer. Raises ValueError on bad trust level or empty id."""
        peer_id = (peer_id or "").strip()
        if not peer_id:
            raise ValueError("peer_id cannot be empty")
        if trust_level not in VALID_TRUST_LEVELS:
            raise ValueError(
                f"trust_level must be one of {VALID_TRUST_LEVELS}, got {trust_level!r}"
            )

        entry = PeerEntry(
            peer_id=peer_id,
            address=str(address or "").strip(),
            public_key=public_key,
            trust_level=trust_level,
            notes=notes or "",
        )
        self._atomic_write(self._entry_path(peer_id), entry.to_dict())

        try:
            emit(
                PeerAdded(
                    peer_id=peer_id,
                    address=entry.address,
                    trust_level=trust_level,
                )
            )
        except Exception:
            logger.debug("failed to emit PeerAdded", exc_info=True)

        return entry

    def remove(self, peer_id: str) -> bool:
        p = self._entry_path(peer_id)
        if not p.is_file():
            return False
        try:
            p.unlink()
        except OSError:
            logger.debug("failed to remove peer entry %s", p, exc_info=True)
            return False
        try:
            emit(PeerRemoved(peer_id=peer_id))
        except Exception:
            logger.debug("failed to emit PeerRemoved", exc_info=True)
        return True

    def get(self, peer_id: str) -> PeerEntry | None:
        p = self._entry_path(peer_id)
        if not p.is_file():
            return None
        try:
            return PeerEntry.from_dict(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            logger.debug("failed to load peer entry %s", p, exc_info=True)
            return None

    def list(self) -> list[PeerEntry]:
        out: list[PeerEntry] = []
        if not self.root.is_dir():
            return out
        for p in sorted(self.root.glob("*.json")):
            entry = self.get(p.stem)
            if entry is not None:
                out.append(entry)
        return out

    def set_trust(self, peer_id: str, level: str) -> bool:
        if level not in VALID_TRUST_LEVELS:
            raise ValueError(f"trust_level must be one of {VALID_TRUST_LEVELS}, got {level!r}")
        entry = self.get(peer_id)
        if entry is None:
            return False
        old_level = entry.trust_level
        if old_level == level:
            return True
        entry.trust_level = level
        self._atomic_write(self._entry_path(peer_id), entry.to_dict())
        try:
            emit(
                PeerTrustChanged(
                    peer_id=peer_id,
                    old_level=old_level,
                    new_level=level,
                )
            )
        except Exception:
            logger.debug("failed to emit PeerTrustChanged", exc_info=True)
        return True

    def touch_last_sync(self, peer_id: str) -> None:
        entry = self.get(peer_id)
        if entry is None:
            return
        entry.last_sync_iso = _utc_now_iso()
        self._atomic_write(self._entry_path(peer_id), entry.to_dict())


# ─────────────────────────────────────────────────────────────────────
# Adapter protocol
# ─────────────────────────────────────────────────────────────────────


class PeerAdapter(ABC):
    """Scheme-specific knowledge of how to pull genome dirs from a peer.

    Concrete adapters yield local-filesystem paths to genome directories
    that ``sync_peer`` will hand to ``Quarantine.submit()``. Adapters
    that fetch from remote sources (future HTTPS, QUIC) are expected to
    materialize remote payloads into a temp dir and yield those paths.
    """

    SCHEME: ClassVar[str]

    @abstractmethod
    def fetch_new_genomes(self, peer: PeerEntry, since_iso: str) -> Iterator[Path]:
        """Yield local paths to genome directories added since ``since_iso``.

        Each yielded path MUST be a directory ready for
        ``Quarantine.submit()``. The adapter is responsible for any
        filtering by ``since_iso``; it is allowed to be conservative
        (yield more than strictly necessary) since quarantine dedupes by
        content sha.
        """
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────
# LocalFilePeerAdapter — v1 file:// adapter
# ─────────────────────────────────────────────────────────────────────


def _parse_file_address(address: str) -> Path | None:
    """Return the local path for a ``file://`` URL or bare path, else None."""
    if not address:
        return None
    if address.startswith("file://"):
        parsed = urlparse(address)
        # Accept both file:///abs/path and file://localhost/abs/path
        if parsed.netloc and parsed.netloc not in ("", "localhost"):
            return None
        return Path(parsed.path)
    if address.startswith(("https://", "http://", "agentdrive://")):
        return None
    # Bare path is acceptable (operator typed a directory).
    return Path(address)


def _has_manifest(path: Path) -> bool:
    return (path / "manifest.yaml").is_file() or (path / "manifest.json").is_file()


def _iter_genome_dirs(genomes_root: Path) -> Iterator[Path]:
    """Walk a AGENTDRIVE_HOME-style ``genomes/`` tree and yield genome dirs.

    Supports both layouts the local ``GenomeRegistry`` uses:
        - flat:        ``genomes/<dir_name>/manifest.{json,yaml}``
        - hierarchical: ``genomes/<id>/<version>/manifest.{json,yaml}``
    """
    if not genomes_root.is_dir():
        return
    for p in sorted(genomes_root.iterdir()):
        if not p.is_dir():
            continue
        if _has_manifest(p):
            yield p
            continue
        # hierarchical layout: one level of version subdirs
        for v in sorted(p.iterdir()):
            if v.is_dir() and _has_manifest(v):
                yield v


def _dir_mtime(path: Path) -> float:
    """Most-recent mtime across the dir tree, for since-filtering."""
    latest = path.stat().st_mtime
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                m = (Path(root) / f).stat().st_mtime
            except OSError:
                continue
            if m > latest:
                latest = m
    return latest


def _iso_to_epoch(iso: str) -> float:
    try:
        return datetime.fromisoformat(iso).timestamp()
    except Exception:
        return 0.0


class LocalFilePeerAdapter(PeerAdapter):
    """v1 adapter for peers reachable as a local filesystem path.

    ``peer.address`` is a ``file:///abs/path`` URL or a bare path pointing
    at another AGENTDRIVE_HOME-like directory (i.e. a directory containing a
    ``genomes/`` subdir, or a ``genomes/`` directory itself). The adapter
    walks that tree and yields genome dirs whose contents have been
    modified since ``since_iso``.
    """

    SCHEME = "file"

    def fetch_new_genomes(self, peer: PeerEntry, since_iso: str) -> Iterator[Path]:
        local = _parse_file_address(peer.address)
        if local is None:
            return
        if not local.exists():
            return

        # Accept either a AGENTDRIVE_HOME root (then we look at <home>/genomes)
        # or a direct genomes/ directory.
        if local.is_dir() and (local / "genomes").is_dir():
            genomes_root = local / "genomes"
        else:
            genomes_root = local

        since_epoch = _iso_to_epoch(since_iso) if since_iso else 0.0

        for gdir in _iter_genome_dirs(genomes_root):
            try:
                mtime = _dir_mtime(gdir)
            except OSError:
                continue
            if mtime >= since_epoch:
                yield gdir


# ─────────────────────────────────────────────────────────────────────
# Adapter registry
# ─────────────────────────────────────────────────────────────────────


_ADAPTERS: dict[str, PeerAdapter] = {}


def register_adapter(adapter: PeerAdapter) -> None:
    """Install or replace the adapter for a scheme."""
    _ADAPTERS[adapter.SCHEME] = adapter


def _address_scheme(address: str) -> str:
    if not address:
        return ""
    if address.startswith("file://"):
        return "file"
    if address.startswith("https://"):
        return "https"
    if address.startswith("http://"):
        return "http"
    if address.startswith("agentdrive://"):
        return "agentdrive"
    if "://" in address:
        # Unknown scheme (ftp://, gopher://, typos). Surface the literal
        # scheme so the adapter lookup returns None and sync_peer takes
        # the explicit "no adapter" error path — never silently coerce
        # into LocalFilePeerAdapter.
        return address.split("://", 1)[0].lower()
    # Bare path (no scheme prefix) → file convention.
    return "file"


def get_adapter_for(peer: PeerEntry) -> PeerAdapter | None:
    """Return the adapter registered for the peer's address scheme."""
    scheme = _address_scheme(peer.address)
    return _ADAPTERS.get(scheme)


# Register the only v1 adapter.
register_adapter(LocalFilePeerAdapter())


# ─────────────────────────────────────────────────────────────────────
# Sync flow
# ─────────────────────────────────────────────────────────────────────


def sync_peer(
    peer_id: str,
    target_pool: Any,  # AgentDrive — kept Any to dodge the import cycle
    *,
    registry: PeerRegistry | None = None,
) -> PeerSyncResult:
    """Pull new genomes from a peer and submit every one to quarantine.

    The hard contract: every byte from the peer goes through
    ``Quarantine.submit()``. There is no code path in this function that
    calls ``target_pool.ingest`` — that argument is accepted only so the
    later approve step (an explicit operator action via
    ``agentdrive quarantine approve``) can route into the right pool.

    Emits ``PeerSyncStarted`` once at the top, ``PeerSyncCompleted`` once
    on exit (even on errors). Per-candidate failures are accumulated in
    ``result.errors`` rather than aborting the sync.
    """
    started = time.time()
    reg = registry or PeerRegistry()
    result = PeerSyncResult(peer_id=peer_id)

    try:
        emit(PeerSyncStarted(peer_id=peer_id))
    except Exception:
        logger.debug("failed to emit PeerSyncStarted", exc_info=True)

    peer = reg.get(peer_id)
    if peer is None:
        result.errors.append(f"unknown peer: {peer_id}")
        result.duration_ms = int((time.time() - started) * 1000)
        _emit_completed(result)
        return result

    adapter = get_adapter_for(peer)
    if adapter is None:
        result.errors.append(f"no adapter registered for address scheme: {peer.address!r}")
        result.duration_ms = int((time.time() - started) * 1000)
        _emit_completed(result)
        return result

    # Lazy import keeps the module import cheap and dodges any chance of
    # circular deps with agentdrive.quarantine.
    from agentdrive.quarantine import get_default_quarantine

    quarantine = get_default_quarantine()
    since_iso = peer.last_sync_iso or _EPOCH_ISO

    try:
        candidate_iter = adapter.fetch_new_genomes(peer, since_iso)
    except Exception as exc:
        result.errors.append(f"adapter fetch failed: {exc}")
        result.duration_ms = int((time.time() - started) * 1000)
        _emit_completed(result)
        return result

    while True:
        try:
            genome_dir = next(candidate_iter)
        except StopIteration:
            break
        except Exception as exc:
            result.errors.append(f"adapter iteration failed: {exc}")
            break

        try:
            entry = quarantine.submit(
                genome_dir,
                source_peer=f"peer:{peer_id}",
            )
        except Exception as exc:
            result.errors.append(f"quarantine.submit failed for {genome_dir}: {exc}")
            continue

        result.submitted += 1
        result.quarantine_ids.append(entry.quarantine_id)

    reg.touch_last_sync(peer_id)
    result.duration_ms = int((time.time() - started) * 1000)
    _emit_completed(result)
    return result


def _emit_completed(result: PeerSyncResult) -> None:
    try:
        emit(
            PeerSyncCompleted(
                peer_id=result.peer_id,
                submitted=result.submitted,
                errors=len(result.errors),
                duration_ms=result.duration_ms,
            )
        )
    except Exception:
        logger.debug("failed to emit PeerSyncCompleted", exc_info=True)


__all__ = [
    "VALID_TRUST_LEVELS",
    "PeerEntry",
    "PeerRegistry",
    "PeerAdapter",
    "LocalFilePeerAdapter",
    "register_adapter",
    "get_adapter_for",
    "PeerSyncResult",
    "sync_peer",
]
