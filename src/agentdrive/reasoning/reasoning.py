"""Reasoning reconstructor — walk the ledger, surface the chain of thought.

Core foundational reasoning primitive in Agent Drive for extracting patterns
from agent runs into Genomes.

Agent Drive / DNA Scanner role:
- Given ledger entries (or any run trace data shaped like LedgerEntry),
  `reconstruct_trace` produces a typed `ReasoningTrace` with ordered
  `TraceStep`s, counts moved, citations, failures, durations.
- This trace becomes the backbone of `genome.reasoning_patterns["trace"]`
  or `["reasoning_trace"]`.
- Enables "show your working" for any extracted Genome, supports
  causality mining, postmortem-style analysis, and evolutionary
  debugging of why a genome succeeded or failed.
- Pure structural reconstruction — the "whiteboard *is* the reasoning".

Preserved exactly: TraceStep (with duration_ms), ReasoningTrace,
reconstruct_trace, explain_trace, render methods.

Used by: causality.py, future scanners, evolutionary engine, audit ledgers.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TraceStep:
    seq: int
    operation: str
    started_at: float
    finished_at: float
    ok: bool
    summary: str
    counts: dict[str, int] = field(default_factory=dict)
    citations: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    @property
    def duration_ms(self) -> int:
        if not self.finished_at or not self.started_at:
            return 0
        return int(max(0.0, self.finished_at - self.started_at) * 1000)


@dataclass(slots=True)
class ReasoningTrace:
    steps: list[TraceStep] = field(default_factory=list)
    operation_counts: dict[str, int] = field(default_factory=dict)
    failed: list[TraceStep] = field(default_factory=list)
    total_duration_ms: int = 0
    citations_summary: dict[str, int] = field(default_factory=dict)

    def render(self) -> str:
        if not self.steps:
            return "(empty trace)"
        lines = [
            f"reasoning trace — {len(self.steps)} step(s), "
            f"{self.total_duration_ms}ms total, "
            f"{len(self.failed)} failure(s)"
        ]
        for step in self.steps:
            marker = "✓" if step.ok else "✗"
            counts = ", ".join(f"{k}={v}" for k, v in step.counts.items())
            counts = f" [{counts}]" if counts else ""
            lines.append(
                f"  {step.seq:>2} {marker} {step.operation:<32} "
                f"{step.duration_ms:>5}ms{counts}  {step.summary[:80]}"
            )
        return "\n".join(lines)


def reconstruct_trace(entries: Iterable[dict[str, Any]]) -> ReasoningTrace:
    """Walk the ledger and emit a typed ``ReasoningTrace``."""
    rows = sorted(
        [e for e in entries if isinstance(e, dict)],
        key=lambda e: float(e.get("started_at") or 0.0),
    )
    # The ledger writes one "open" entry + one "close" entry per record
    # context. Collapse them by id so each step shows up once with its
    # finalized ok/error/counts.
    by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for e in rows:
        rid = str(e.get("id") or "")
        if not rid:
            continue
        if rid in by_id:
            # Treat the later entry as the close; merge into the first.
            target = by_id[rid]
            for key in ("finished_at", "ok", "summary", "error"):
                if e.get(key) is not None and e.get(key) != "":
                    target[key] = e[key]
            for k, v in (e.get("counts") or {}).items():
                target.setdefault("counts", {})[k] = v
            for cite in e.get("citations") or []:
                target.setdefault("citations", []).append(cite)
        else:
            by_id[rid] = dict(e)
            order.append(rid)

    steps: list[TraceStep] = []
    op_counter: Counter = Counter()
    citation_counter: Counter = Counter()
    for idx, rid in enumerate(order, start=1):
        e = by_id[rid]
        step = TraceStep(
            seq=idx,
            operation=str(e.get("operation") or ""),
            started_at=float(e.get("started_at") or 0.0),
            finished_at=float(e.get("finished_at") or 0.0),
            ok=bool(e.get("ok")) if e.get("ok") is not None else True,
            summary=str(e.get("summary") or "")[:240],
            counts={
                k: int(v) for k, v in (e.get("counts") or {}).items() if isinstance(v, (int, float))
            },
            citations=list(e.get("citations") or []),
            error=e.get("error"),
        )
        steps.append(step)
        op_counter[step.operation] += 1
        for cite in step.citations:
            if isinstance(cite, dict):
                source = str(cite.get("source") or "")
                if source:
                    citation_counter[source] += 1

    total_duration = sum(s.duration_ms for s in steps)
    failed = [s for s in steps if not s.ok or s.error]

    return ReasoningTrace(
        steps=steps,
        operation_counts=dict(op_counter),
        failed=failed,
        total_duration_ms=total_duration,
        citations_summary=dict(citation_counter),
    )


def explain_trace(trace: ReasoningTrace) -> str:
    """Render a one-paragraph diagnostic of the trace."""
    if not trace.steps:
        return "no ledger entries to reason from."
    top_ops = ", ".join(
        f"{op}({n})" for op, n in sorted(trace.operation_counts.items(), key=lambda p: -p[1])[:5]
    )
    top_sources = (
        ", ".join(
            f"{src}({n})"
            for src, n in sorted(trace.citations_summary.items(), key=lambda p: -p[1])[:5]
        )
        or "(no citations recorded)"
    )
    fail_summary = (
        f"; {len(trace.failed)} failure(s): " + ", ".join(f.operation for f in trace.failed[:3])
        if trace.failed
        else ""
    )
    return (
        f"{len(trace.steps)} step(s) in {trace.total_duration_ms}ms. "
        f"Top operations: {top_ops}. Sources cited: {top_sources}.{fail_summary}"
    )
