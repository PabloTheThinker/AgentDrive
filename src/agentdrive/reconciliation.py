"""Pool reconciliation routine — periodic background pool scan.

Every Savant agent should be able to notice, without the operator asking,
that new DNA has landed in its pool. Sub-agents push genomes in via the
inheritance loop, quarantine releases candidates after approval, peer
adapters drop entries through their own ingest paths. This module is the
loop that *sees* those arrivals and surfaces them on the event bus so
chat ribbons and other subscribers can render the Drive growing in real
time.

Single responsibility: scan, diff, emit. We do NOT absorb anything
here — quarantine + inheritance own that. We only observe what already
landed in the local Drive and tell the bus about the delta since the
previous scan.

State on disk (under ``$AGENTDRIVE_HOME/reconciliation.json``)::

    {
      "last_scan_iso": "2026-05-24T00:00:00+00:00",
      "known_genome_ids": ["genome-a", "genome-b"],
      "known_markers": {"genome-a": {"stars": 3, "ultimate": false}}
    }

Two new events on every pass: ``ReconciliationCompleted`` (always) and
``ReconciliationDelta`` (only when new_genomes or updated_genomes is
non-empty). Both ride the existing default bus.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentdrive.constants import get_agentdrive_home
from agentdrive.events import (
    ReconciliationCompleted,
    ReconciliationDelta,
    emit,
)

if TYPE_CHECKING:  # pragma: no cover
    from agentdrive.drive.drive import AgentDrive
    from agentdrive.registry import GenomeRegistry

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Constants + helpers
# ─────────────────────────────────────────────────────────────────────


STATE_FILENAME: str = "reconciliation.json"
_EPOCH_ISO: str = "1970-01-01T00:00:00+00:00"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_iso(value: str) -> datetime | None:
    """Best-effort ISO-8601 parser. Returns None if value is junk."""
    if not value:
        return None
    try:
        # ``datetime.fromisoformat`` handles "+00:00" suffixes natively on
        # 3.11+. We always emit timezone-aware strings ourselves so this is
        # safe in both directions.
        dt = datetime.fromisoformat(value)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _ingest_event_iso(entry: dict[str, Any]) -> str | None:
    """Pull an ISO timestamp out of a pool ingest log entry.

    The pool stores ``timestamp`` as an epoch float (see ``AgentDrive.ingest``).
    Convert it so we can compare against ``last_scan_iso`` consistently.
    """
    raw = entry.get("timestamp")
    if raw is None:
        return None
    try:
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(float(raw), tz=UTC).isoformat()
        if isinstance(raw, str):
            # Already ISO? Parse to validate then re-emit.
            dt = _parse_iso(raw)
            if dt is not None:
                return dt.isoformat()
    except Exception:
        return None
    return None


def _atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically (temp file + rename).

    Crashes mid-write cannot corrupt the on-disk state.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                # fsync is best-effort; some filesystems reject it.
                pass
        os.replace(tmp_name, path)
    except Exception:
        # Make sure we never leave a half-written temp file behind.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


# ─────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────


@dataclass
class ReconciliationReport:
    """One scan's worth of "what changed in the Drive since last time"."""

    since: str = _EPOCH_ISO
    until: str = field(default_factory=_utc_now_iso)
    new_genomes: list[str] = field(default_factory=list)
    updated_genomes: list[str] = field(default_factory=list)
    new_ingest_events: int = 0
    pending_quarantine: int = 0
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────


class ReconciliationRunner:
    """Synchronous + background scanner for a single (registry, pool) pair.

    Caller owns lifecycle: build it, call ``scan_once()`` for one-shot
    reports, or ``start_background()`` to spawn a daemon thread that
    repeats every ``interval_s``. ``stop_background()`` flips a
    ``threading.Event`` so the loop exits cooperatively at its next tick.
    """

    def __init__(
        self,
        registry: GenomeRegistry,
        pool: AgentDrive,
        state_path: Path | None = None,
        interval_s: float = 30.0,
    ) -> None:
        self.registry = registry
        self.pool = pool
        self.interval_s = max(0.1, float(interval_s))
        if state_path is None:
            state_path = get_agentdrive_home() / STATE_FILENAME
        self.state_path = Path(state_path)

        # Background plumbing — initialised lazily by start_background().
        self._stop_event: threading.Event = threading.Event()
        self._thread: threading.Thread | None = None
        self._thread_lock: threading.Lock = threading.Lock()

    # ---- state IO -----------------------------------------------------

    def _load_state(self) -> dict[str, Any]:
        """Read the on-disk state file. Returns a sane default if absent."""
        if not self.state_path.is_file():
            return {
                "last_scan_iso": _EPOCH_ISO,
                "known_genome_ids": [],
                "known_markers": {},
            }
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            logger.debug(
                "reconciliation: failed to read state at %s; treating as fresh",
                self.state_path,
                exc_info=True,
            )
            return {
                "last_scan_iso": _EPOCH_ISO,
                "known_genome_ids": [],
                "known_markers": {},
            }

        if not isinstance(raw, dict):
            return {
                "last_scan_iso": _EPOCH_ISO,
                "known_genome_ids": [],
                "known_markers": {},
            }
        # Normalise shape so callers can rely on keys existing.
        raw.setdefault("last_scan_iso", _EPOCH_ISO)
        raw.setdefault("known_genome_ids", [])
        raw.setdefault("known_markers", {})
        return raw

    def _persist_state(
        self,
        last_scan_iso: str,
        known_ids: list[str],
        known_markers: dict[str, dict[str, Any]],
    ) -> None:
        payload = {
            "last_scan_iso": last_scan_iso,
            "known_genome_ids": sorted(set(known_ids)),
            "known_markers": known_markers,
        }
        try:
            _atomic_write_text(self.state_path, json.dumps(payload, indent=2, default=str))
        except Exception:
            logger.debug(
                "reconciliation: failed to persist state to %s",
                self.state_path,
                exc_info=True,
            )

    # ---- marker collection -------------------------------------------

    def _collect_markers(self, genome_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Snapshot confidence stars + ultimate presence for each genome.

        Reads sidecars only (``confidence.json`` / ``ultimate.json``). We
        never write to the genome dir from here — quarantine and the
        confidence module own those files.
        """
        # Lazy import to dodge an import cycle: confidence/ultimate both
        # type-hint AgentDrive, which type-hints us indirectly through
        # the event bus.
        try:
            from agentdrive.confidence import get_rating
            from agentdrive.ultimate import get_ultimate_info
        except Exception:
            logger.debug("reconciliation: confidence/ultimate import failed", exc_info=True)
            return {gid: {"stars": 0, "ultimate": False} for gid in genome_ids}

        out: dict[str, dict[str, Any]] = {}
        for gid in genome_ids:
            stars = 0
            ultimate = False
            try:
                rating = get_rating(gid, self.registry)
                if rating is not None:
                    stars = int(rating.stars or 0)
            except Exception:
                logger.debug("reconciliation: get_rating failed for %s", gid, exc_info=True)
            try:
                info = get_ultimate_info(gid, self.registry)
                ultimate = info is not None
            except Exception:
                logger.debug(
                    "reconciliation: get_ultimate_info failed for %s",
                    gid,
                    exc_info=True,
                )
            out[gid] = {"stars": stars, "ultimate": ultimate}
        return out

    # ---- pending quarantine ------------------------------------------

    def _pending_quarantine_count(self) -> int:
        """Count entries currently in PENDING status, defensively."""
        try:
            from agentdrive.quarantine import (
                QuarantineStatus,
                get_default_quarantine,
            )
        except Exception:
            logger.debug("reconciliation: quarantine import failed", exc_info=True)
            return 0
        try:
            q = get_default_quarantine()
            return len(q.list(status=QuarantineStatus.PENDING))
        except Exception:
            logger.debug("reconciliation: pending quarantine lookup failed", exc_info=True)
            return 0

    # ---- public: one-shot scan ---------------------------------------

    def scan_once(self) -> ReconciliationReport:
        """Run a single reconciliation pass and emit the resulting events."""
        t0 = time.monotonic()

        state = self._load_state()
        since_iso: str = str(state.get("last_scan_iso") or _EPOCH_ISO)
        prior_ids = set(state.get("known_genome_ids") or [])
        prior_markers = dict(state.get("known_markers") or {})

        until_iso = _utc_now_iso()

        # 1) Genome diff.
        try:
            current_ids_list = self.registry.list_genomes()
        except Exception:
            logger.debug("reconciliation: registry.list_genomes failed", exc_info=True)
            current_ids_list = []
        current_ids = set(current_ids_list)
        new_genomes = sorted(current_ids - prior_ids)

        # 2) Pool ingest events since last scan.
        new_ingest_events = 0
        try:
            since_dt = _parse_iso(since_iso) or datetime.fromtimestamp(0, tz=UTC)
            for entry in getattr(self.pool, "_ingest_log", []) or []:
                iso = _ingest_event_iso(entry)
                if iso is None:
                    continue
                dt = _parse_iso(iso)
                if dt is None:
                    continue
                if dt > since_dt:
                    new_ingest_events += 1
        except Exception:
            logger.debug("reconciliation: ingest-event walk failed", exc_info=True)

        # 3) Marker diff (confidence stars + ultimate presence).
        current_markers = self._collect_markers(sorted(current_ids))
        updated_genomes: list[str] = []
        for gid, marker in current_markers.items():
            prior = prior_markers.get(gid)
            if prior is None:
                # Brand-new genome — already covered by new_genomes; only
                # count as "updated" if it carries non-default markers.
                if marker.get("stars", 0) or marker.get("ultimate", False):
                    if gid not in new_genomes:
                        updated_genomes.append(gid)
                continue
            if int(prior.get("stars", 0) or 0) != int(marker.get("stars", 0) or 0) or bool(
                prior.get("ultimate", False)
            ) != bool(marker.get("ultimate", False)):
                updated_genomes.append(gid)
        updated_genomes.sort()

        # 4) Pending quarantine count.
        pending = self._pending_quarantine_count()

        # 5) Persist fresh state.
        self._persist_state(
            last_scan_iso=until_iso,
            known_ids=list(current_ids),
            known_markers=current_markers,
        )

        duration_ms = int((time.monotonic() - t0) * 1000)

        report = ReconciliationReport(
            since=since_iso,
            until=until_iso,
            new_genomes=new_genomes,
            updated_genomes=updated_genomes,
            new_ingest_events=new_ingest_events,
            pending_quarantine=pending,
            duration_ms=duration_ms,
        )

        # 6) Emit events.
        self._emit_completed(report)
        if new_genomes or updated_genomes:
            self._emit_delta(report)

        return report

    # ---- emit helpers ------------------------------------------------

    def _emit_completed(self, report: ReconciliationReport) -> None:
        try:
            emit(
                ReconciliationCompleted(
                    new_genomes_count=len(report.new_genomes),
                    updated_genomes_count=len(report.updated_genomes),
                    new_ingest_events=report.new_ingest_events,
                    pending_quarantine=report.pending_quarantine,
                    duration_ms=report.duration_ms,
                )
            )
        except Exception:
            logger.debug(
                "reconciliation: emit(ReconciliationCompleted) failed",
                exc_info=True,
            )

    def _emit_delta(self, report: ReconciliationReport) -> None:
        try:
            emit(
                ReconciliationDelta(
                    new_genomes=list(report.new_genomes),
                    updated_genomes=list(report.updated_genomes),
                )
            )
        except Exception:
            logger.debug("reconciliation: emit(ReconciliationDelta) failed", exc_info=True)

    # ---- public: background loop -------------------------------------

    def start_background(self) -> None:
        """Spawn the daemon scanner thread. Idempotent.

        A second call while the first thread is alive is a silent no-op.
        Use ``stop_background()`` first if you want to rebuild.
        """
        with self._thread_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event = threading.Event()
            t = threading.Thread(
                target=self._run_loop,
                name="savant-reconciliation",
                daemon=True,
            )
            self._thread = t
            t.start()

    def stop_background(self, timeout: float = 5.0) -> None:
        """Signal the loop to exit and wait up to ``timeout`` seconds."""
        with self._thread_lock:
            thread = self._thread
            self._stop_event.set()
        if thread is None:
            return
        thread.join(timeout=timeout)
        with self._thread_lock:
            if not thread.is_alive():
                self._thread = None

    def _run_loop(self) -> None:
        """Inner background loop. Cooperatively stoppable via _stop_event."""
        while not self._stop_event.is_set():
            try:
                self.scan_once()
            except Exception:
                logger.debug(
                    "reconciliation: scan_once raised in background loop",
                    exc_info=True,
                )
            # ``Event.wait(timeout)`` returns True as soon as the event is
            # set, so stop_background() never has to wait a full interval.
            if self._stop_event.wait(timeout=self.interval_s):
                break


__all__ = [
    "ReconciliationReport",
    "ReconciliationRunner",
    "STATE_FILENAME",
]
