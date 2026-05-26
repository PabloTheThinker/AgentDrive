"""
dilation — detect operator-offline windows and allocate dream tick budgets.

Design goals:
- Prefer conservative wake/sleep boundaries over aggressive background work.
- Translate wall-clock quiet into bounded simulated reasoning time.
- No new magic — just disciplined composition + Agent Drive / Genome idioms.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentdrive.genome.models import Genome


@dataclass
class DilationPolicy:
    """Policy for opening, sustaining, and closing a sleep window."""

    runtime_root: Path = field(default_factory=lambda: Path("~/.agentdrive").expanduser())
    quiet_period_seconds: int = 900
    min_window_seconds: int = 300
    max_window_seconds: int = 1_800
    dilation_ratio: float = 24.0
    ticks_per_simulated_hour: int = 60
    wake_paths: list[Path] = field(
        default_factory=lambda: [
            Path("~/.agentdrive/pool/ingest.jsonl").expanduser(),
            Path("~/.agentdrive/swarms").expanduser(),
            Path("~/.agentdrive/reasoning/ledger").expanduser(),
        ]
    )


@dataclass
class SleepWindow:
    """Computed sleep window and tick budget for one dream run."""

    opened_at: float = 0.0
    last_operator_activity: float = 0.0
    wall_budget_seconds: int = 0
    simulated_hours: float = 0.0
    tick_budget: int = 0
    wake_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def estimate_operator_last_activity(policy: DilationPolicy) -> float:
    """Estimate the most recent operator or waking-state activity timestamp."""
    mtimes: list[float] = []
    for path in policy.wake_paths:
        if not path.exists():
            continue
        if path.is_file():
            mtimes.append(path.stat().st_mtime)
            continue
        for child in path.rglob("*"):
            if child.is_file():
                mtimes.append(child.stat().st_mtime)
    return max(mtimes) if mtimes else time.time()


def compute_tick_budget(window_seconds: int, policy: DilationPolicy) -> int:
    """Translate wall-clock sleep time into a bounded simulated tick budget."""
    simulated_hours = (window_seconds / 3600.0) * policy.dilation_ratio
    tick_budget = int(simulated_hours * policy.ticks_per_simulated_hour)
    max_ticks = int(
        (policy.max_window_seconds / 3600.0)
        * policy.dilation_ratio
        * policy.ticks_per_simulated_hour
    )
    return max(0, min(tick_budget, max_ticks))


def detect_sleep_window(policy: DilationPolicy) -> SleepWindow | None:
    """Detect whether the substrate is sufficiently idle to start dreaming."""
    now = time.time()
    last_activity = estimate_operator_last_activity(policy)
    quiet_for = now - last_activity
    if quiet_for < policy.quiet_period_seconds:
        return None
    wall_budget = min(max(int(quiet_for), policy.min_window_seconds), policy.max_window_seconds)
    tick_budget = compute_tick_budget(wall_budget, policy)
    return SleepWindow(
        opened_at=now,
        last_operator_activity=last_activity,
        wall_budget_seconds=wall_budget,
        simulated_hours=(wall_budget / 3600.0) * policy.dilation_ratio,
        tick_budget=tick_budget,
        metadata={"runtime_root": str(policy.runtime_root)},
    )


def should_wake(window: SleepWindow, policy: DilationPolicy) -> bool:
    """Check whether current conditions should terminate the sleep window."""
    latest_activity = estimate_operator_last_activity(policy)
    return latest_activity > window.opened_at


def genome_dilation_anchor(genome: Genome | None) -> str:
    """Return a stable Genome anchor for future dilation profiles."""
    return genome.genome_id if genome else ""
