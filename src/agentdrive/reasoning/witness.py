"""Numeric witness — every claim must carry a count + timestamp + source + citation.

Core reasoning primitive in Savant for witnessing/validating numeric claims
in DNA extraction and Genome enrichment.

Savant usage:
- Scanners use `witness_claim` and `audit_vagueness` when extracting
  numeric assertions from agent run logs, traces, or outputs.
- Ensures that `reasoning_patterns` in a Genome contain only high-signal,
  citable, non-vague claims.
- Feeds directly into contradictions detector and ledger entries.
- Part of the "savant-like precision": vague language is rejected at
  extraction time.

Preserved: Citation, NumericClaim, VaguenessReport, audit_vagueness,
witness_claim, witness_many.

Adapted: default paths and docs point to Savant; no behavior change.
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

_VAGUE_QUANTIFIERS = (
    "some",
    "many",
    "a few",
    "several",
    "lots of",
    "a lot of",
    "most",
    "various",
    "numerous",
    "plenty of",
    "a number of",
)
_VAGUE_TIMES = (
    "recently",
    "earlier",
    "a while ago",
    "lately",
    "soon",
    "sometime",
    "before",
    "after a bit",
    "in the past",
)


@dataclass(slots=True)
class Citation:
    source: str  # e.g. "ecosystem-snapshot" or "run-123:step-7"
    source_id: str  # e.g. "1715712642" or "genome@1.2.3:trace-42"
    fields: dict[str, Any] = field(default_factory=dict)
    observed_at: float = field(default_factory=time.time)

    def render(self) -> str:
        body = ", ".join(f"{k}={v}" for k, v in self.fields.items()) or ""
        return (
            f"[{self.source}:{self.source_id} @ {int(self.observed_at)}"
            + (f" {body}" if body else "")
            + "]"
        )


@dataclass(slots=True)
class NumericClaim:
    statement: str  # natural-language assertion
    count: int  # the load-bearing number
    citations: list[Citation] = field(default_factory=list)
    confidence: float = 1.0

    def render(self) -> str:
        cites = " ".join(c.render() for c in self.citations) or "[no citation]"
        return f"{self.statement} (n={self.count}) {cites}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "statement": self.statement,
            "count": self.count,
            "confidence": self.confidence,
            "citations": [asdict(c) for c in self.citations],
        }


@dataclass(slots=True)
class VaguenessReport:
    ok: bool
    issues: list[str] = field(default_factory=list)


def audit_vagueness(text: str) -> VaguenessReport:
    """Flag every banned vague quantifier or hand-wavy time word."""
    issues: list[str] = []
    lowered = text.lower()
    for q in _VAGUE_QUANTIFIERS:
        if re.search(rf"\b{re.escape(q)}\b", lowered):
            issues.append(f"vague quantifier: {q!r}")
    for t in _VAGUE_TIMES:
        if re.search(rf"\b{re.escape(t)}\b", lowered):
            issues.append(f"vague time: {t!r}")
    return VaguenessReport(ok=not issues, issues=issues)


def witness_claim(
    statement: str,
    *,
    count: int,
    source: str,
    source_id: str,
    fields: dict[str, Any] | None = None,
    confidence: float = 1.0,
) -> NumericClaim:
    """Build a NumericClaim with a single citation."""
    return NumericClaim(
        statement=statement,
        count=int(count),
        confidence=float(confidence),
        citations=[Citation(source=source, source_id=source_id, fields=fields or {})],
    )


def witness_many(rows: list[dict[str, Any]]) -> list[NumericClaim]:
    """Construct a batch of claims from a list of dicts.

    Each dict must carry ``statement``, ``count``, ``source``, ``source_id``;
    optional ``fields`` and ``confidence``.
    """
    out: list[NumericClaim] = []
    for r in rows:
        out.append(
            witness_claim(
                statement=str(r["statement"]),
                count=int(r["count"]),
                source=str(r["source"]),
                source_id=str(r["source_id"]),
                fields=r.get("fields") or {},
                confidence=float(r.get("confidence", 1.0)),
            )
        )
    return out
