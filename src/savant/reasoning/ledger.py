"""Audit-first ledger — write the claim before you act.

Core reasoning primitive in Savant for auditable claims and operations in
Genomes and scanners.

Savant role for DNA extraction and Genome enrichment:
- Every scanner pass, pattern extraction, anomaly run, causal analysis,
  or evolutionary proposal can (and should) be auditable via Ledger.
- `genome.provenance["ledger_refs"]` or per-genome ledgers record the
  exact sequence of structural operations that produced or improved
  the genome.
- `audited` decorator and `record` context manager guarantee that the
  audit trail exists *before* any risky action (matching the original
  "whiteboard is the reasoning" philosophy).
- Default storage: `~/.savant/reasoning/ledger/YYYYMMDD.jsonl`
- Can be instantiated per-genome: Ledger(actor=f"genome:{genome_id}")

Preserved in full: LedgerEntry, Ledger class, log_entry, audited decorator,
record context, tail, finalize, etc. Thread-safe appends. Only path
constants and docs updated for Savant.

This is the audit ledger primitive for genomes.
"""

from __future__ import annotations

import functools
import inspect
import json
import logging
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

logger = logging.getLogger(__name__)


_SAVANT_REASONING_ROOT = Path.home() / ".savant" / "reasoning"
_DEFAULT_ROOT = _SAVANT_REASONING_ROOT / "ledger"
_LOCK = threading.Lock()


def ledger_path(root: Path | None = None,
                 day: str | None = None) -> Path:
    base = (root or _DEFAULT_ROOT)
    base.mkdir(parents=True, exist_ok=True)
    if day is None:
        day = time.strftime("%Y%m%d", time.gmtime())
    return base / f"{day}.jsonl"


@dataclass(slots=True)
class LedgerEntry:
    id: str
    actor: str
    operation: str
    started_at: float
    finished_at: float = 0.0
    ok: bool = False
    summary: str = ""
    counts: dict[str, int] = field(default_factory=dict)
    citations: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_jsonl(self) -> str:
        return json.dumps({
            "id": self.id, "actor": self.actor,
            "operation": self.operation,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "ok": self.ok, "summary": self.summary,
            "counts": dict(self.counts),
            "citations": list(self.citations),
            "metadata": dict(self.metadata),
            "error": self.error,
        }, ensure_ascii=False, sort_keys=True) + "\n"


class Ledger:
    """Append-only jsonl ledger keyed to UTC day. Savant-adapted for genomes."""

    def __init__(self, root: Path | None = None,
                  actor: str = "savant") -> None:
        self.root = root or _DEFAULT_ROOT
        self.actor = actor

    def log_entry(self, *, operation: str, summary: str = "",
                    counts: dict[str, int] | None = None,
                    citations: list[dict[str, Any]] | None = None,
                    metadata: dict[str, Any] | None = None) -> LedgerEntry:
        entry = LedgerEntry(
            id=f"led-{uuid.uuid4().hex[:10]}",
            actor=self.actor, operation=operation,
            started_at=time.time(),
            summary=summary,
            counts=dict(counts or {}),
            citations=list(citations or []),
            metadata=dict(metadata or {}),
        )
        self._append(entry)
        return entry

    def finalize(self, entry: LedgerEntry, *, ok: bool = True,
                   error: str | None = None,
                   summary: str | None = None,
                   counts: dict[str, int] | None = None) -> None:
        entry.finished_at = time.time()
        entry.ok = ok
        if error is not None:
            entry.error = error
        if summary is not None:
            entry.summary = summary
        if counts:
            entry.counts.update(counts)
        self._append(entry)

    @contextmanager
    def record(self, operation: str, **kwargs: Any) -> Iterator[LedgerEntry]:
        """Context manager that opens an entry, then finalizes on exit."""
        entry = self.log_entry(operation=operation, **kwargs)
        try:
            yield entry
        except Exception as exc:
            self.finalize(entry, ok=False, error=str(exc))
            raise
        else:
            if entry.finished_at == 0.0:
                self.finalize(entry, ok=True)

    def tail(self, *, limit: int = 50,
              day: str | None = None) -> list[dict[str, Any]]:
        path = ledger_path(self.root, day=day)
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        out: list[dict[str, Any]] = []
        for raw in lines[-limit:]:
            raw = raw.strip()
            if not raw:
                continue
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return out

    def _append(self, entry: LedgerEntry) -> None:
        path = ledger_path(self.root)
        with _LOCK:
            try:
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(entry.to_jsonl())
            except OSError:
                logger.exception("ledger append failed for %s", path)


def log_entry(operation: str, *, summary: str = "",
                counts: dict[str, int] | None = None,
                citations: list[dict[str, Any]] | None = None,
                metadata: dict[str, Any] | None = None,
                root: Path | None = None,
                actor: str = "savant") -> LedgerEntry:
    """Convenience: one-shot append to the default Savant reasoning ledger."""
    return Ledger(root=root, actor=actor).log_entry(
        operation=operation, summary=summary,
        counts=counts, citations=citations, metadata=metadata,
    )


def audited(operation: str, *, actor: str = "savant",
              root: Path | None = None) -> Callable:
    """Decorator: write an entry **before** the function runs, finalize on return.

    Works on sync and async callables. Counts pulled from the return
    value if it's a dict with a ``counts`` key.
    """
    ledger = Ledger(root=root, actor=actor)

    def decorator(fn: Callable) -> Callable:
        is_coro = inspect.iscoroutinefunction(fn)

        if is_coro:
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with ledger.record(operation=operation,
                                      metadata={"args": _short(args),
                                                  "kwargs": _short(kwargs)}) as entry:
                    result = await fn(*args, **kwargs)
                    _absorb_counts(result, entry)
                    return result
            return async_wrapper

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with ledger.record(operation=operation,
                                  metadata={"args": _short(args),
                                              "kwargs": _short(kwargs)}) as entry:
                result = fn(*args, **kwargs)
                _absorb_counts(result, entry)
                return result
        return sync_wrapper

    return decorator


def _short(value: Any) -> Any:
    """Render call args compactly for the ledger metadata."""
    rendered = repr(value)
    return rendered if len(rendered) <= 400 else rendered[:400] + "…"


def _absorb_counts(result: Any, entry: LedgerEntry) -> None:
    if isinstance(result, dict) and isinstance(result.get("counts"), dict):
        entry.counts.update({k: int(v) for k, v in result["counts"].items()
                                if isinstance(v, int)})
