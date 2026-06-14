"""
Bus-driven transcript ribbons for chat (UX Pattern 1).

Subscribes to pool/evolution/confidence/inheritance/quarantine/peer/
reconciliation events on the default bus and prints dim ribbon lines into
the chat transcript. Thread-safe: handlers may run on the agent worker
thread while Rich Console.print is safe concurrently.
"""

from __future__ import annotations

import threading
from typing import Any, Callable

from rich.console import Console

from agentdrive.events import (
    ConfidenceUpdated,
    GenomeEvolved,
    InheritanceAbsorbed,
    InheritanceReceived,
    PeerSyncCompleted,
    PeerSyncStarted,
    PeerTrustChanged,
    PoolIngest,
    PoolOutcome,
    QuarantineApproved,
    QuarantineRejected,
    QuarantineSubmitted,
    ReconciliationDelta,
    subscribe,
    unsubscribe,
)
from agentdrive.tui.chrome import Palette


class TranscriptLane:
    """Thread-safe transcript ribbons driven by the event bus."""

    def __init__(
        self,
        console: Console,
        palette: Palette | None = None,
        *,
        on_line: Callable[[], None] | None = None,
    ) -> None:
        self.console = console
        self.palette = palette or Palette(None)
        self._on_line = on_line
        self._lock = threading.Lock()
        self._line_count = 0
        self._tokens: list[Any] = []

    @property
    def line_count(self) -> int:
        with self._lock:
            return self._line_count

    def _print(self, markup: str) -> None:
        with self._lock:
            self.console.print(markup)
            self._line_count += 1
            if self._on_line is not None:
                self._on_line()

    def attach(self) -> None:
        if self._tokens:
            return

        p = self.palette

        def _ribbon_ingest(ev: PoolIngest) -> None:
            self._print(
                f"  [dim]▸ pool · ingested[/] [{p.genome}]{ev.genome_id}[/]  "
                f"[dim]src {ev.source} · actor {ev.actor}[/]"
            )

        def _ribbon_outcome(ev: PoolOutcome) -> None:
            self._print(
                f"  [dim]▸ pool · outcome[/] [{p.genome}]{ev.genome_id}[/]  "
                f"[dim]score {ev.score:.2f}[/]"
            )

        def _ribbon_evolved(ev: GenomeEvolved) -> None:
            uses = ev.evidence.get("uses", 0) if isinstance(ev.evidence, dict) else 0
            avg = ev.evidence.get("avg_score", 0.0) if isinstance(ev.evidence, dict) else 0.0
            try:
                avg_f = float(avg)
            except (TypeError, ValueError):
                avg_f = 0.0
            self._print(
                f"  [bold magenta]▸ EVOLVED · {ev.genome_id} → ultimate · "
                f"uses={uses} · avg={avg_f:.2f}[/]"
            )

        def _ribbon_confidence(ev: ConfidenceUpdated) -> None:
            stars = "★" * ev.stars + "☆" * (5 - ev.stars)
            self._print(
                f"  [dim]▸ confidence ·[/] [{p.genome}]{ev.genome_id}[/] "
                f"[bold {p.accent}]{stars}[/] [dim]({ev.encounters} encounters)[/]"
            )

        def _ribbon_inheritance_received(ev: InheritanceReceived) -> None:
            n_in = len(ev.genomes_absorbed)
            n_out = len(ev.genomes_rejected)
            origin = ev.subagent_id or "swarm"
            self._print(
                f"  [dim]▸ inheritance ·[/] [{p.framework}]{origin}[/] returned · "
                f"[dim]{n_in} absorbed · {n_out} rejected[/]"
            )

        def _ribbon_inheritance_absorbed(ev: InheritanceAbsorbed) -> None:
            self._print(
                f"  [dim]▸ inheritance · absorbed[/] [{p.genome}]{ev.genome_id}[/] "
                f"[dim]from {ev.source_subagent_id}[/]"
            )

        def _ribbon_quarantine_submitted(ev: QuarantineSubmitted) -> None:
            self._print(
                f"  [bold {p.warn}]▸ quarantine · pending review[/] "
                f"[{p.genome}]{ev.genome_id or '—'}[/] "
                f"[dim]from {ev.source_peer} · {ev.quarantine_id[:8]}[/]"
            )

        def _ribbon_quarantine_approved(ev: QuarantineApproved) -> None:
            self._print(
                f"  [{p.ok}]▸ quarantine · approved[/] "
                f"[{p.genome}]{ev.genome_id or '—'}[/] "
                f"[dim]by {ev.approved_by}[/]"
            )

        def _ribbon_quarantine_rejected(ev: QuarantineRejected) -> None:
            self._print(
                f"  [{p.error}]▸ quarantine · rejected[/] "
                f"[{p.genome}]{ev.genome_id or '—'}[/] "
                f"[dim]{ev.reason}[/]"
            )

        def _ribbon_reconciliation_delta(ev: ReconciliationDelta) -> None:
            n_new = len(ev.new_genomes)
            n_upd = len(ev.updated_genomes)
            if n_new == 0 and n_upd == 0:
                return
            parts = []
            if n_new:
                parts.append(f"{n_new} new")
            if n_upd:
                parts.append(f"{n_upd} updated")
            self._print(f"  [dim]▸ reconciliation ·[/] [{p.accent}]{' · '.join(parts)}[/]")

        def _ribbon_peer_sync_started(ev: PeerSyncStarted) -> None:
            self._print(f"  [dim]▸ peer sync ·[/] [{p.framework}]{ev.peer_id}[/] [dim]…[/]")

        def _ribbon_peer_sync_completed(ev: PeerSyncCompleted) -> None:
            tone = p.ok if ev.errors == 0 else p.warn
            self._print(
                f"  [{tone}]▸ peer sync ·[/] [{p.framework}]{ev.peer_id}[/] "
                f"[dim]{ev.submitted} submitted to quarantine · "
                f"{ev.errors} error{'s' if ev.errors != 1 else ''} · "
                f"{ev.duration_ms} ms[/]"
            )

        def _ribbon_peer_trust(ev: PeerTrustChanged) -> None:
            self._print(
                f"  [dim]▸ peer ·[/] [{p.framework}]{ev.peer_id}[/] "
                f"[dim]trust:[/] {ev.old_level} → [bold]{ev.new_level}[/]"
            )

        for handler, types in (
            (_ribbon_ingest, [PoolIngest]),
            (_ribbon_outcome, [PoolOutcome]),
            (_ribbon_evolved, [GenomeEvolved]),
            (_ribbon_confidence, [ConfidenceUpdated]),
            (_ribbon_inheritance_received, [InheritanceReceived]),
            (_ribbon_inheritance_absorbed, [InheritanceAbsorbed]),
            (_ribbon_quarantine_submitted, [QuarantineSubmitted]),
            (_ribbon_quarantine_approved, [QuarantineApproved]),
            (_ribbon_quarantine_rejected, [QuarantineRejected]),
            (_ribbon_reconciliation_delta, [ReconciliationDelta]),
            (_ribbon_peer_sync_started, [PeerSyncStarted]),
            (_ribbon_peer_sync_completed, [PeerSyncCompleted]),
            (_ribbon_peer_trust, [PeerTrustChanged]),
        ):
            self._tokens.append(subscribe(handler, types))

    def detach(self) -> None:
        for tok in self._tokens:
            try:
                unsubscribe(tok)
            except Exception:
                pass
        self._tokens.clear()
