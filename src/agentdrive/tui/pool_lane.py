"""
Persistent pool activity line for chat streaming (UX Pattern 3).

Shows the latest substantive pool event as a thin status row below the
streaming body while a turn is in flight.
"""

from __future__ import annotations

import threading
from typing import Any

from rich.text import Text

from agentdrive.events import (
    GenomeEvolved,
    PoolIngest,
    PoolMatch,
    PoolOutcome,
    subscribe,
    unsubscribe,
)
from agentdrive.tui.chrome import Palette


class PoolActivityLane:
    """Thread-safe one-line pool status driven by the event bus."""

    def __init__(self, *, palette: Palette | None = None) -> None:
        self.palette = palette or Palette(None)
        self._lock = threading.Lock()
        self._line: str | None = None
        self._tokens: list[Any] = []

    def attach(self) -> None:
        if self._tokens:
            return

        def _set(line: str) -> None:
            with self._lock:
                self._line = line

        def _on_match(ev: PoolMatch) -> None:
            p = self.palette
            if not ev.genomes:
                _set(f"[{p.muted}]▸ no DNA matched · pure model[/]")
                return
            scores = " ".join(f"{s:.2f}" for s in (ev.scores or [])[:3])
            extra = len(ev.genomes) - 3
            tail = f" +{extra}" if extra > 0 else ""
            _set(
                f"[{p.genome}]▸ matched {len(ev.genomes)} genomes[/] [{p.muted}]({scores}{tail})[/]"
            )

        def _on_ingest(ev: PoolIngest) -> None:
            p = self.palette
            _set(f"[{p.genome}]▸ ingested {ev.genome_id}[/] [{p.muted}]· {ev.source}[/]")

        def _on_outcome(ev: PoolOutcome) -> None:
            p = self.palette
            _set(
                f"[{p.ok}]▸ recorded outcome[/] [{p.genome}]{ev.genome_id}[/] "
                f"[{p.muted}]· score {ev.score:.2f}[/]"
            )

        def _on_evolved(ev: GenomeEvolved) -> None:
            p = self.palette
            _set(f"[bold {p.accent}]▸ evolved {ev.genome_id} → ultimate[/]")

        for handler, types in (
            (_on_match, [PoolMatch]),
            (_on_ingest, [PoolIngest]),
            (_on_outcome, [PoolOutcome]),
            (_on_evolved, [GenomeEvolved]),
        ):
            self._tokens.append(subscribe(handler, types))

    def detach(self) -> None:
        for tok in self._tokens:
            try:
                unsubscribe(tok)
            except Exception:
                pass
        self._tokens.clear()

    def reset(self) -> None:
        """Clear between turns (PoolMatch on the next turn repopulates)."""
        with self._lock:
            self._line = None

    def renderable(self) -> Text | None:
        with self._lock:
            if not self._line:
                return None
            p = self.palette
            text = Text()
            text.append("  ─ pool ", style=p.muted)
            text.append_text(Text.from_markup(self._line))
            text.append(" ─", style=p.muted)
            return text
