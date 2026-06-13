"""Typed event bus for Agent Drive.

Decouples backend state changes (chat, pool, harness, sub-agents) from the
TUI. Producers emit dataclass events; subscribers render or record them.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import IO

logger = logging.getLogger(__name__)

EventHandler = Callable[["Event"], None]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_event_id() -> str:
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Event hierarchy
# ---------------------------------------------------------------------------


@dataclass
class Event:
    """Base event. Subclasses add typed fields after these defaults."""

    event_id: str = field(default_factory=_new_event_id)
    timestamp: str = field(default_factory=_utc_now_iso)
    session_id: str | None = None
    swarm_id: str | None = None
    subagent_id: str | None = None


@dataclass
class MessageStart(Event):
    role: str = "user"  # "user" | "assistant"


@dataclass
class MessageDelta(Event):
    text: str = ""


@dataclass
class MessageComplete(Event):
    text: str = ""
    tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class ThinkingDelta(Event):
    text: str = ""


@dataclass
class ToolStart(Event):
    tool: str = ""
    args: dict = field(default_factory=dict)


@dataclass
class ToolProgress(Event):
    tool: str = ""
    message: str = ""


@dataclass
class ToolComplete(Event):
    tool: str = ""
    ok: bool = True
    result_summary: str = ""


@dataclass
class PoolMatch(Event):
    genomes: list[str] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)


@dataclass
class PoolIngest(Event):
    genome_id: str = ""
    source: str = ""
    actor: str = ""


@dataclass
class PoolOutcome(Event):
    genome_id: str = ""
    score: float = 0.0


@dataclass
class GenomeEvolved(Event):
    """A genome crossed the Ultimate-form promotion threshold."""

    genome_id: str = ""
    ultimate_version: str = ""
    evidence: dict = field(default_factory=dict)


@dataclass
class ConfidenceUpdated(Event):
    """A genome's encounter-graded confidence rating was recomputed."""

    genome_id: str = ""
    stars: int = 0
    encounters: int = 0


@dataclass
class InheritanceReceived(Event):
    """An inheritance manifest from a sub-agent was absorbed into a pool."""

    genomes_absorbed: list[str] = field(default_factory=list)
    genomes_rejected: list[str] = field(default_factory=list)
    skills_absorbed: list[str] = field(default_factory=list)
    skills_rejected: list[str] = field(default_factory=list)


@dataclass
class InheritanceAbsorbed(Event):
    """A single foreign genome was absorbed via an inheritance manifest."""

    genome_id: str = ""
    skill_name: str = ""
    source_subagent_id: str = ""
    parent_pool: str = ""


@dataclass
class SubagentSpawn(Event):
    parent_id: str = ""
    # subagent_id is inherited from Event; spec asks for it as a field, so
    # we keep using the inherited slot rather than shadowing it.
    label: str = ""


@dataclass
class SubagentTool(Event):
    tool: str = ""


@dataclass
class SubagentTokens(Event):
    tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class SubagentDone(Event):
    ok: bool = True
    duration_s: float = 0.0


@dataclass
class StatusUpdate(Event):
    message: str = ""
    level: str = "info"  # "info" | "warn" | "error"


@dataclass
class MissionTransition(Event):
    mission_id: str = ""
    from_status: str = ""
    to_status: str = ""


@dataclass
class QuarantineSubmitted(Event):
    """A candidate genome was placed into quarantine pending validation."""

    quarantine_id: str = ""
    genome_id: str = ""
    source_peer: str = ""


@dataclass
class QuarantineValidated(Event):
    """Validation rules ran against a quarantined candidate."""

    quarantine_id: str = ""
    all_passed: bool = False
    failed_rules: list[str] = field(default_factory=list)


@dataclass
class QuarantineApproved(Event):
    """A quarantined candidate was approved and released into the Drive."""

    quarantine_id: str = ""
    genome_id: str = ""
    approved_by: str = ""


@dataclass
class QuarantineRejected(Event):
    """A quarantined candidate was explicitly blocked."""

    quarantine_id: str = ""
    genome_id: str = ""
    reason: str = ""


@dataclass
class PeerAdded(Event):
    """A federated peer Agent Drive was registered."""

    peer_id: str = ""
    address: str = ""
    trust_level: str = ""


@dataclass
class PeerRemoved(Event):
    """A federated peer Agent Drive was unregistered."""

    peer_id: str = ""


@dataclass
class PeerTrustChanged(Event):
    """A peer's trust level was changed."""

    peer_id: str = ""
    old_level: str = ""
    new_level: str = ""


@dataclass
class PeerSyncStarted(Event):
    """A peer-sync operation began."""

    peer_id: str = ""


@dataclass
class PeerSyncCompleted(Event):
    """A peer-sync operation finished (success or partial failure)."""

    peer_id: str = ""
    submitted: int = 0
    errors: int = 0
    duration_ms: int = 0


@dataclass
class ReconciliationCompleted(Event):
    """A pool reconciliation pass finished — fires every scan."""

    new_genomes_count: int = 0
    updated_genomes_count: int = 0
    new_ingest_events: int = 0
    pending_quarantine: int = 0
    duration_ms: int = 0


@dataclass
class ReconciliationDelta(Event):
    """A reconciliation pass found at least one new or updated genome."""

    new_genomes: list[str] = field(default_factory=list)
    updated_genomes: list[str] = field(default_factory=list)


@dataclass
class HealingSignalEvent(Event):
    """Role-swarm immune response trigger for experience layer regeneration.
    Captures autonomous damage signals (worker/adapter exhaustion after retries,
    DurableJobSupervisor job failure after leases+backoff, reconciliation corruption,
    high synthesis contradiction clusters or persistent gaps, security posture
    "needs_attention", promotion/ingest rejections, LineageImmune CRITICAL threats,
    first-run/sparse cold-start reasoning failures) with mandatory correlation_id
    for full trace continuity across Drive.think, run_synthesis, LineageImmuneSystem,
    and durable healing jobs.

    Rich context always includes: error/trace details, affected genomes + KG neighborhood
    (graph signals), recent experience layer items (living-experience / daily-present etc
    via schema pack), LineageImmune assessment (ThreatLevel + incident memory).
    """

    signal_type: str = ""  # e.g. "worker_execution_exhaust", "durable_job_exhaust", ...
    correlation_id: str = ""
    context: dict = field(default_factory=dict)
    source_component: str = ""
    recommended_priority: str = "medium"  # low | medium | high | critical for healing job priority


@dataclass
class HealingSignalResolved(Event):
    """Successful closure of an experience layer regeneration loop.
    Emitted after healing_attempt ingest + typed KG edges (healed_by, regenerated_from,
    damage_cause, strengthened_resilience) for high-signal prevention learning.
    """

    signal_event_id: str = ""
    healing_id: str = ""
    correlation_id: str = ""
    artifacts_ingested: list[str] = field(default_factory=list)
    resilience_delta: float = 0.0


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubscriptionToken:
    """Opaque handle returned by ``subscribe``; pass to ``unsubscribe``."""

    id: int


class _Subscription:
    __slots__ = ("token", "handler", "event_types")

    def __init__(
        self,
        token: SubscriptionToken,
        handler: EventHandler,
        event_types: tuple[type[Event], ...] | None,
    ) -> None:
        self.token = token
        self.handler = handler
        self.event_types = event_types  # None means "all"

    def matches(self, event: Event) -> bool:
        if self.event_types is None:
            return True
        return isinstance(event, self.event_types)


class EventBus:
    """Synchronous, thread-safe fan-out pub/sub."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subs: list[_Subscription] = []
        self._next_id = 0

    def subscribe(
        self,
        handler: EventHandler,
        event_types: Iterable[type[Event]] | None = None,
    ) -> SubscriptionToken:
        types_tuple: tuple[type[Event], ...] | None = (
            tuple(event_types) if event_types is not None else None
        )
        with self._lock:
            token = SubscriptionToken(self._next_id)
            self._next_id += 1
            self._subs.append(_Subscription(token, handler, types_tuple))
            return token

    def unsubscribe(self, token: SubscriptionToken) -> None:
        with self._lock:
            self._subs = [s for s in self._subs if s.token != token]

    def emit(self, event: Event) -> None:
        # Snapshot under lock, dispatch outside lock so a slow handler does
        # not block subscribe/unsubscribe from other threads.
        with self._lock:
            targets = [s for s in self._subs if s.matches(event)]
        for sub in targets:
            try:
                sub.handler(event)
            except Exception:
                logger.exception("EventBus subscriber raised on %s", type(event).__name__)

    def clear(self) -> None:
        with self._lock:
            self._subs.clear()


# ---------------------------------------------------------------------------
# EventRecorder
# ---------------------------------------------------------------------------


class EventRecorder:
    """Append-only JSONL recorder for an event stream."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # buffering=1 gives line-buffered text mode.
        self._fh: IO[str] | None = open(self.path, "a", buffering=1, encoding="utf-8")
        self._lock = threading.Lock()

    def record(self, event: Event) -> None:
        if self._fh is None:
            raise RuntimeError("EventRecorder is closed")
        payload = asdict(event)
        payload["type"] = type(event).__name__
        line = json.dumps(payload, default=str)
        with self._lock:
            if self._fh is None:
                raise RuntimeError("EventRecorder is closed")
            self._fh.write(line + "\n")

    def close(self) -> None:
        with self._lock:
            if self._fh is not None:
                self._fh.flush()
                self._fh.close()
                self._fh = None

    def attach(self, bus: EventBus) -> SubscriptionToken:
        return bus.subscribe(self.record)

    def __enter__(self) -> EventRecorder:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Module-level default bus
# ---------------------------------------------------------------------------


default_bus = EventBus()


def emit(event: Event) -> None:
    default_bus.emit(event)


def subscribe(
    handler: EventHandler,
    event_types: Iterable[type[Event]] | None = None,
) -> SubscriptionToken:
    return default_bus.subscribe(handler, event_types)


def unsubscribe(token: SubscriptionToken) -> None:
    default_bus.unsubscribe(token)


__all__ = [
    "Event",
    "MessageStart",
    "MessageDelta",
    "MessageComplete",
    "ThinkingDelta",
    "ToolStart",
    "ToolProgress",
    "ToolComplete",
    "PoolMatch",
    "PoolIngest",
    "PoolOutcome",
    "GenomeEvolved",
    "ConfidenceUpdated",
    "InheritanceReceived",
    "InheritanceAbsorbed",
    "SubagentSpawn",
    "SubagentTool",
    "SubagentTokens",
    "SubagentDone",
    "StatusUpdate",
    "MissionTransition",
    "QuarantineSubmitted",
    "QuarantineValidated",
    "QuarantineApproved",
    "QuarantineRejected",
    "PeerAdded",
    "PeerRemoved",
    "PeerTrustChanged",
    "PeerSyncStarted",
    "PeerSyncCompleted",
    "ReconciliationCompleted",
    "ReconciliationDelta",
    "HealingSignalEvent",
    "HealingSignalResolved",
    "EventBus",
    "EventRecorder",
    "SubscriptionToken",
    "default_bus",
    "emit",
    "subscribe",
    "unsubscribe",
]
