"""
Micro-animation kit for short-lived TUI operations.

The Agent Drive chat experience leans on minimal visual polish.
Most operations finish in 1-3 seconds — a full progress bar feels heavy;
a tiny spinner with a one-line label feels just right.

Provides:
- ``MicroSpinner``: context manager wrapping a rich.Live with one of four
  frame sets (braille, dots, pulse, scan), an optional rotating label,
  and a clean done/fail state.
- ``StepProgress``: lightweight multi-step indicator for sequenced work
  (e.g., the agentdrive update flow) — each step shows pending / running /
  done / failed with the matching glyph.

Designed to be drop-in: ``with MicroSpinner(console, "loading pool…"):``.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum

from rich.console import Console, Group
from rich.live import Live
from rich.text import Text

# ── Frame sets ────────────────────────────────────────────────────────

_FRAMES = {
    "braille": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
    "dots": ["·  ", " · ", "  ·", " · "],
    "pulse": ["●  ", "○● ", "○○●", "○● ", "●  "],
    "scan": ["▱▱▱", "▰▱▱", "▰▰▱", "▰▰▰", "▱▰▰", "▱▱▰"],
    "arc": ["◜", "◠", "◝", "◞", "◡", "◟"],
}

_INTERVAL_S = {
    "braille": 0.08,
    "dots": 0.18,
    "pulse": 0.16,
    "scan": 0.14,
    "arc": 0.12,
}


# ── MicroSpinner ──────────────────────────────────────────────────────


class MicroSpinner:
    """A tiny inline spinner with a one-line label.

    Usage:

        with MicroSpinner(console, "loading pool…") as s:
            do_work()
            s.update("almost done…")

    On exit (no exception), the spinner is replaced by a check + duration:
        ✓  loading pool…  · 0.4s

    On exception, the spinner is replaced by a cross:
        ✗  loading pool…  · 0.4s
    """

    def __init__(
        self,
        console: Console,
        label: str,
        style: str = "braille",
        accent: str = "cyan",
        success_color: str = "green",
        fail_color: str = "red",
        muted: str = "grey50",
        leave_summary: bool = True,
    ):
        self.console = console
        self.label = label
        self.style = style if style in _FRAMES else "braille"
        self.accent = accent
        self.success_color = success_color
        self.fail_color = fail_color
        self.muted = muted
        self.leave_summary = leave_summary
        self._start = 0.0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._live: Live | None = None
        self._lock = threading.Lock()
        self._failed = False

    # ── frame render ──
    def _frame(self) -> Text:
        frames = _FRAMES[self.style]
        interval = _INTERVAL_S[self.style]
        idx = int((time.monotonic() - self._start) / interval) % len(frames)
        glyph = frames[idx]

        line = Text()
        line.append(glyph, style=self.accent)
        line.append("  ")
        line.append(self.label)
        line.append(f"  · {time.monotonic() - self._start:.1f}s", style=self.muted)
        return line

    def update(self, label: str) -> None:
        with self._lock:
            self.label = label

    # ── lifecycle ──
    def __enter__(self) -> MicroSpinner:
        self._start = time.monotonic()
        self._live = Live(
            self._frame(),
            console=self.console,
            refresh_per_second=15,
            transient=not self.leave_summary,
        )
        self._live.__enter__()

        def loop() -> None:
            while not self._stop_event.is_set():
                with self._lock:
                    self._live.update(self._frame()) if self._live else None
                time.sleep(1 / 15.0)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()
        return self

    def fail(self) -> None:
        self._failed = True

    def __exit__(self, exc_type, exc, tb) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=0.5)

        if self._live:
            if exc_type is not None or self._failed:
                glyph = "✗"
                color = self.fail_color
            else:
                glyph = "✓"
                color = self.success_color

            final = Text()
            final.append(glyph, style=color)
            final.append("  ")
            final.append(self.label)
            final.append(f"  · {time.monotonic() - self._start:.1f}s", style=self.muted)

            if self.leave_summary:
                self._live.update(final)
            self._live.__exit__(exc_type, exc, tb)


@contextmanager
def micro_spinner(
    console: Console,
    label: str,
    style: str = "braille",
    accent: str = "cyan",
):
    """Functional shorthand for MicroSpinner."""
    with MicroSpinner(console, label, style=style, accent=accent) as s:
        yield s


# ── StepProgress ──────────────────────────────────────────────────────


class StepState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Step:
    label: str
    state: StepState = StepState.PENDING
    detail: str = ""
    duration_s: float = 0.0
    _start: float = 0.0


class StepProgress:
    """Sequenced multi-step indicator with live render.

    Usage:

        steps = StepProgress(console, [
            "Check current version",
            "Fetch latest from GitHub",
            "Install upgrade",
            "Verify installation",
        ])
        steps.start()
        steps.advance("found update: ddc873f → 6d964d4")
        ...
        steps.finish()
    """

    GLYPHS = {
        StepState.PENDING: "○",
        StepState.RUNNING: "◐",  # placeholder; we animate frame() to spin this
        StepState.DONE: "✓",
        StepState.FAILED: "✗",
        StepState.SKIPPED: "·",
    }

    STATE_COLORS = {
        StepState.PENDING: "grey50",
        StepState.RUNNING: "cyan",
        StepState.DONE: "green",
        StepState.FAILED: "red",
        StepState.SKIPPED: "grey50",
    }

    # Running animation
    _SPIN = ["◐", "◓", "◑", "◒"]

    def __init__(
        self,
        console: Console,
        labels: Iterable[str],
        title: str | None = None,
        muted: str = "grey50",
    ):
        self.console = console
        self.steps: list[Step] = [Step(label=lbl) for lbl in labels]
        self.title = title
        self.muted = muted
        self._idx = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._live: Live | None = None
        self._lock = threading.Lock()
        self._spin_start = 0.0

    # ── render ──
    def _glyph(self, step: Step) -> Text:
        if step.state == StepState.RUNNING:
            frame_idx = int((time.monotonic() - self._spin_start) / 0.1) % len(self._SPIN)
            return Text(self._SPIN[frame_idx], style=self.STATE_COLORS[step.state])
        return Text(self.GLYPHS[step.state], style=self.STATE_COLORS[step.state])

    def render(self) -> Group:
        lines: list[Text] = []
        if self.title:
            t = Text()
            t.append(self.title, style="bold cyan")
            lines.append(t)
            lines.append(Text(""))

        for step in self.steps:
            line = Text()
            line.append("  ")
            line.append_text(self._glyph(step))
            line.append("  ")
            color = self.STATE_COLORS[step.state]
            label_style = f"bold {color}" if step.state == StepState.RUNNING else color
            line.append(step.label, style=label_style)
            if step.detail:
                line.append(f"  · {step.detail}", style=self.muted)
            if step.state in (StepState.DONE, StepState.FAILED) and step.duration_s > 0:
                line.append(f"  · {step.duration_s:.1f}s", style=self.muted)
            lines.append(line)
        return Group(*lines)

    # ── lifecycle ──
    def start(self) -> None:
        self._spin_start = time.monotonic()
        if self.steps:
            self.steps[0].state = StepState.RUNNING
            self.steps[0]._start = time.monotonic()
        self._live = Live(
            self.render(), console=self.console, refresh_per_second=15, transient=False
        )
        self._live.__enter__()

        def loop() -> None:
            while not self._stop.is_set():
                with self._lock:
                    if self._live:
                        self._live.update(self.render())
                time.sleep(1 / 15.0)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def detail(self, msg: str) -> None:
        """Update the detail string of the currently running step."""
        with self._lock:
            if 0 <= self._idx < len(self.steps):
                self.steps[self._idx].detail = msg

    def advance(self, detail: str = "") -> None:
        """Mark current step done, move to next."""
        with self._lock:
            if 0 <= self._idx < len(self.steps):
                step = self.steps[self._idx]
                step.state = StepState.DONE
                step.duration_s = time.monotonic() - step._start
                if detail:
                    step.detail = detail
            self._idx += 1
            if self._idx < len(self.steps):
                self.steps[self._idx].state = StepState.RUNNING
                self.steps[self._idx]._start = time.monotonic()

    def fail(self, detail: str = "") -> None:
        with self._lock:
            if 0 <= self._idx < len(self.steps):
                step = self.steps[self._idx]
                step.state = StepState.FAILED
                step.duration_s = time.monotonic() - step._start
                if detail:
                    step.detail = detail

    def skip(self, detail: str = "") -> None:
        with self._lock:
            if 0 <= self._idx < len(self.steps):
                step = self.steps[self._idx]
                step.state = StepState.SKIPPED
                if detail:
                    step.detail = detail
            self._idx += 1
            if self._idx < len(self.steps):
                self.steps[self._idx].state = StepState.RUNNING
                self.steps[self._idx]._start = time.monotonic()

    def finish(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.5)
        if self._live:
            # One final render to settle
            self._live.update(self.render())
            self._live.__exit__(None, None, None)
