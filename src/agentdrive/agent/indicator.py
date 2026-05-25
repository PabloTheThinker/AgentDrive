"""
Rotating status indicator — emoji / ascii / unicode / kaomoji styles
with verb rotation and elapsed time. Designed for chat streaming UX.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

# Frame sets per style
_FRAMES = {
    "unicode": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
    "ascii": ["|", "/", "-", "\\"],
    "emoji": ["⚕", "⚗", "🔬", "✨", "🧬", "🌀"],
    "kaomoji": [
        "٩(◕‿◕｡)۶",
        "(´・ω・`)",
        "(•̀ᴗ•́)و",
        "(ง •̀_•́)ง",
        "(っ˘ω˘ς)",
        "(★ω★)/",
    ],
}

# Frame intervals (ms)
_INTERVAL_MS = {
    "unicode": 80,
    "ascii": 100,
    "emoji": 480,
    "kaomoji": 350,
}

# Verbs that rotate alongside the spinner
_VERBS = [
    "thinking",
    "reasoning",
    "consulting DNA",
    "synthesizing",
    "weighing patterns",
    "drafting",
]

_VERB_INTERVAL_S = 2.4


@dataclass
class Indicator:
    """A stateful status indicator. Call .frame() to get the current render string."""

    style: str = "unicode"
    show_verb: bool = True
    show_elapsed: bool = True
    _start: float = 0.0
    _verb_idx: int = 0
    _verb_last_switch: float = 0.0

    def __post_init__(self) -> None:
        if self.style not in _FRAMES:
            self.style = "unicode"
        self._start = time.monotonic()
        self._verb_last_switch = self._start

    @classmethod
    def styles(cls) -> list[str]:
        return list(_FRAMES.keys())

    def reset(self) -> None:
        self._start = time.monotonic()
        self._verb_last_switch = self._start
        self._verb_idx = 0

    def _current_frame(self) -> str:
        frames = _FRAMES[self.style]
        interval_s = _INTERVAL_MS[self.style] / 1000.0
        idx = int((time.monotonic() - self._start) / interval_s) % len(frames)
        return frames[idx]

    def _current_verb(self) -> str:
        now = time.monotonic()
        if now - self._verb_last_switch > _VERB_INTERVAL_S:
            self._verb_idx = (self._verb_idx + 1) % len(_VERBS)
            self._verb_last_switch = now
        return _VERBS[self._verb_idx]

    def elapsed_s(self) -> float:
        return time.monotonic() - self._start

    def frame(self, override_verb: str | None = None) -> str:
        """Render the indicator as a single rich-markup string."""
        spinner = self._current_frame()
        parts = [f"[agentdrive.accent]{spinner}[/]"]

        if self.show_verb:
            verb = override_verb if override_verb is not None else self._current_verb()
            parts.append(f"[dim]{verb}[/]")

        if self.show_elapsed:
            parts.append(f"[dim]· {self.elapsed_s():.1f}s[/]")

        return " ".join(parts)
