"""Anomaly detector — find the one observation that doesn't fit.

Core DNA extraction primitive in the Savant reasoning suite.

Savant role:
- DNA Scanners call `detect_anomalies` on run observations / events /
  ledger entries to surface rare events, state outliers, stale data,
  or novel identities.
- Results go into `genome.reasoning_patterns["anomalies"]` and can drive
  enrichment, or flag genomes that need human review.
- Heuristics remain pure structural (rare-kind, state-outlier, stale,
  identity-novel) — savant precision, zero hallucination.

Adapted: docs updated for Genome model; same API and severity ordering.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Anomaly:
    rule: str
    kind: str
    identity: str
    rationale: str
    severity: float = 0.5
    citation: dict[str, Any] = field(default_factory=dict)


def detect_anomalies(
    observations: Iterable[Any],
    *,
    prior_observations: Iterable[Any] | None = None,
    rare_threshold: float = 0.05,
    stale_threshold_seconds: float = 86_400.0,
) -> list[Anomaly]:
    """Walk the observation stream and return every misfit it finds."""
    rows = list(observations)
    if not rows:
        return []

    total = len(rows)
    kinds = [_get(o, "kind") or "unknown" for o in rows]
    kind_counts: dict[str, int] = {}
    for k in kinds:
        kind_counts[str(k)] = kind_counts.get(str(k), 0) + 1

    anomalies: list[Anomaly] = []

    # 1) Rare-kind rule.
    for k, n in kind_counts.items():
        if n / max(1, total) < rare_threshold and n > 0:
            example = next(o for o in rows if _get(o, "kind") == k)
            anomalies.append(
                Anomaly(
                    rule="rare-kind",
                    kind=k,
                    identity=str(_get(example, "identity") or ""),
                    rationale=f"{k!r} accounts for {n}/{total} = "
                    f"{n / total:.1%} (< threshold {rare_threshold:.0%})",
                    severity=0.4,
                    citation={"observed_at": _get(example, "observed_at")},
                )
            )

    # 2) State-outlier rule (per kind).
    by_kind_state: dict[str, dict[str, list[Any]]] = {}
    for o in rows:
        k = str(_get(o, "kind") or "unknown")
        s = str(_get(o, "state") or "unknown")
        by_kind_state.setdefault(k, {}).setdefault(s, []).append(o)
    for kind, states in by_kind_state.items():
        if len(states) < 2:
            continue
        total_in_kind = sum(len(v) for v in states.values())
        for state, items in states.items():
            if len(items) / max(1, total_in_kind) <= 0.10:
                example = items[0]
                anomalies.append(
                    Anomaly(
                        rule="state-outlier",
                        kind=kind,
                        identity=str(_get(example, "identity") or ""),
                        rationale=f"only {len(items)}/{total_in_kind} {kind!r} "
                        f"observations are in state {state!r}",
                        severity=0.6,
                        citation={"state": state},
                    )
                )

    # 3) Stale rule.
    timestamps = [float(_get(o, "observed_at") or 0.0) for o in rows if _get(o, "observed_at")]
    if len(timestamps) >= 3:
        median_ts = statistics.median(timestamps)
        for o in rows:
            ts = float(_get(o, "observed_at") or 0.0)
            if ts and median_ts - ts > stale_threshold_seconds:
                anomalies.append(
                    Anomaly(
                        rule="stale",
                        kind=str(_get(o, "kind") or ""),
                        identity=str(_get(o, "identity") or ""),
                        rationale=f"observation is {median_ts - ts:.0f}s behind "
                        f"the median of {int(median_ts)}",
                        severity=0.5,
                        citation={"observed_at": ts, "median": median_ts},
                    )
                )

    # 4) Identity-novel rule (requires prior snapshot).
    if prior_observations is not None:
        prior_keys = {f"{_get(p, 'kind')}:{_get(p, 'identity')}" for p in prior_observations}
        for o in rows:
            k = str(_get(o, "kind") or "")
            iid = str(_get(o, "identity") or "")
            if k and iid and f"{k}:{iid}" not in prior_keys:
                anomalies.append(
                    Anomaly(
                        rule="identity-novel",
                        kind=k,
                        identity=iid,
                        rationale=f"{k}:{iid} not present in prior snapshot",
                        severity=0.3,
                        citation={"prior_size": len(prior_keys)},
                    )
                )

    anomalies.sort(key=lambda a: -a.severity)
    return anomalies


def _get(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def explain_anomaly(a: Anomaly) -> str:
    """Format an anomaly for chat output or genome metadata."""
    return (
        f"[{a.rule}] kind={a.kind!r} identity={a.identity!r} "
        f"severity={a.severity:.2f} — {a.rationale}"
    )


def now() -> float:
    return time.time()
