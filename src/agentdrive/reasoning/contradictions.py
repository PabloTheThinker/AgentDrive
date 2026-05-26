"""Contradiction detector — flag NumericClaims that disagree.

Core reasoning primitive in Agent Drive for detecting contradictions in claims
and observations during DNA extraction and Genome enrichment.

In Agent Drive context:
- Used by DNA Scanners to detect inconsistencies in run data / claims
  extracted from agent executions.
- Populates `genome.reasoning_patterns["contradictions"]` for audit and
  evolutionary selection (contradiction-free genomes are preferred).
- Maintains the agentdrive-like zero-tolerance for vagueness and inconsistency.

Original design preserved: offline heuristics, normalized templates,
citation back to sources. No LLM.

See also: witness.py (NumericClaim), ledger.py (for audit trail of detections).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Contradiction:
    template: str  # the normalized statement
    counts: list[int] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    rationale: str = ""

    def render(self) -> str:
        return (
            f"contradiction on {self.template!r}: counts={self.counts} "
            f"sources={self.sources} — {self.rationale}"
        )


def detect_contradictions(claims: Iterable[Any]) -> list[Contradiction]:
    """Group claims by normalized statement; flag any group with > 1 distinct count."""
    by_template: dict[str, dict[str, Any]] = {}
    for claim in claims:
        statement = _statement(claim)
        if not statement:
            continue
        template = _normalize(statement)
        count = _count(claim)
        bucket = by_template.setdefault(template, {"counts": [], "sources": []})
        bucket["counts"].append(count)
        bucket["sources"].append(_source(claim))

    contradictions: list[Contradiction] = []
    for template, bucket in by_template.items():
        distinct = {c for c in bucket["counts"] if c is not None}
        if len(distinct) >= 2:
            contradictions.append(
                Contradiction(
                    template=template,
                    counts=list(bucket["counts"]),
                    sources=list(bucket["sources"]),
                    rationale=(
                        f"{len(distinct)} distinct counts {sorted(distinct)} "
                        f"reported across {len(bucket['counts'])} claim(s)"
                    ),
                )
            )
    return contradictions


def _statement(claim: Any) -> str:
    if isinstance(claim, dict):
        return str(claim.get("statement") or "")
    return str(getattr(claim, "statement", "") or "")


def _count(claim: Any) -> int | None:
    if isinstance(claim, dict):
        value = claim.get("count")
    else:
        value = getattr(claim, "count", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _source(claim: Any) -> str:
    citations = (
        claim.get("citations") if isinstance(claim, dict) else getattr(claim, "citations", None)
    )
    if not citations:
        return ""
    first = citations[0]
    if isinstance(first, dict):
        return f"{first.get('source', '?')}:{first.get('source_id', '?')}"
    return f"{getattr(first, 'source', '?')}:{getattr(first, 'source_id', '?')}"


_NUMBER_RE = re.compile(r"\b\d+(\.\d+)?\b")


def _normalize(statement: str) -> str:
    """Drop literal numbers + whitespace so '18 containers' == '17 containers'."""
    no_numbers = _NUMBER_RE.sub("<n>", statement.lower())
    return re.sub(r"\s+", " ", no_numbers).strip()
