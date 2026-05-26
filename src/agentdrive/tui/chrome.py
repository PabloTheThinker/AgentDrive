"""
AgentDrive TUI Chrome — the unified UI primitives library.

Every Agent Drive surface (chat, doctor, onboarding, pool browser, genome views,
setup wizard) renders against the same primitives so the product feels like
one continuous experience instead of a dozen unrelated commands.

Design tenets (cribbed from the best terminal agents in the wild):
- Minimal decoration: messages flow with role glyphs + tree stems, panels
  only for *system* sections (welcome, /help, /sessions, /provider, /pool).
- One blank line between major blocks. No internal padding inside rows.
- Palette of semantic color slots — never hardcode hex in surface code.
- Glyphs are constants — every checkmark, every stem, every selector arrow
  resolves to the same symbol everywhere.
- Status rules pin the persistent state of the world after every turn.

Public surface:
    Glyphs            symbol constants
    Palette           semantic color slot accessor
    Section           sectioned panel: heading + key-value rows
    Tree              nested tree of rows with ├─ └─ │ stems
    status_rule       single-line "─ a ─ b ─ c ─"
    context_bar       colored progress bar [████░░░░░░] 45%
    result_panel      success / failure summary panel
    confirm_prompt    blocking yes/no with arrow-key selection
    select_prompt     blocking choose-one-of-N selector
    error_line        inline error glyph + message [+ suggestion]
    info_line         inline info glyph + message
    ok_line           inline ok glyph + message
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.text import Text

# ── Glyphs ────────────────────────────────────────────────────────────


class Glyphs:
    """Symbol constants — every Agent Drive surface uses the same characters."""

    USER = "❯"
    ASSISTANT = "✦"
    SYSTEM = "·"
    TOOL = "⚡"
    STREAM_CURSOR = "▍"

    # Status
    CHECK = "✓"
    CROSS = "✗"
    WARN = "!"
    INFO = "·"
    PENDING = "○"
    RUNNING = "◐"
    SKIPPED = "·"

    # Tree stems
    MID = "├─"
    END = "└─"
    VERT = "│"
    GUTTER = "│"

    # Section markers
    EXPANDED = "▾"
    COLLAPSED = "▸"
    BULLET = "•"

    # Selectors (used by confirm/select prompts)
    SELECTOR_ACTIVE = "▸"
    SELECTOR_IDLE = " "

    # Brand
    DIAMOND = "◆"
    SPARK = "✦"
    DOT_FILLED = "●"
    DOT_OPEN = "○"

    # Progress bar
    BAR_FILLED = "█"
    BAR_EMPTY = "░"


# ── Palette ───────────────────────────────────────────────────────────


@dataclass
class _PaletteSlots:
    """Defaults used when no skin is available."""

    accent: str = "cyan"
    title: str = "bold cyan"
    muted: str = "grey50"
    border: str = "cyan"
    text: str = "white"

    ok: str = "green"
    warn: str = "yellow"
    error: str = "red"

    genome: str = "green"
    framework: str = "cyan"
    evolution: str = "magenta"

    status_good: str = "green"
    status_warn: str = "yellow"
    status_bad: str = "orange1"
    status_critical: str = "red"


_FALLBACK = _PaletteSlots()


class Palette:
    """Semantic color accessor. Surfaces should ask Palette, never the skin."""

    def __init__(self, skin: Any = None):
        self.skin = skin
        c = skin.skin.get("colors", {}) if skin else {}
        self.accent = c.get("ui_accent", _FALLBACK.accent)
        self.title = "bold " + c.get("banner_title", c.get("ui_accent", _FALLBACK.accent))
        self.muted = c.get("status_bar_dim", _FALLBACK.muted)
        self.border = c.get("banner_border", _FALLBACK.border)
        self.text = c.get("banner_text", _FALLBACK.text)

        self.ok = c.get("ui_ok", _FALLBACK.ok)
        self.warn = c.get("ui_warn", _FALLBACK.warn)
        self.error = c.get("ui_error", _FALLBACK.error)

        self.genome = c.get("genome_id", _FALLBACK.genome)
        self.framework = c.get("framework_name", _FALLBACK.framework)
        self.evolution = c.get("evolution_step", _FALLBACK.evolution)

        self.status_good = c.get("status_bar_good", _FALLBACK.status_good)
        self.status_warn = c.get("status_bar_warn", _FALLBACK.status_warn)
        self.status_bad = c.get("status_bar_bad", _FALLBACK.status_bad)
        self.status_critical = c.get("status_bar_critical", _FALLBACK.status_critical)


def _pal_from(skin_or_palette: Any) -> Palette:
    if isinstance(skin_or_palette, Palette):
        return skin_or_palette
    return Palette(skin_or_palette)


# ── Section: sectioned panel content ──────────────────────────────────


def Section(
    title: str,
    rows: Sequence[tuple[str, str]],
    palette: Any = None,
    *,
    icon: str = Glyphs.EXPANDED,
    key_width: int = 10,
) -> Group:
    """Sectioned heading + tree-stemmed key-value rows.

    rows = [("label", "[rich-markup]value[/]"), ...]
    """
    p = _pal_from(palette)

    head = Text()
    head.append(f"{icon} ", style=p.accent)
    head.append(title, style=f"bold {p.accent}")

    lines: list[Text] = []
    n = len(rows)
    for i, (k, v) in enumerate(rows):
        is_last = i == n - 1
        stem = Glyphs.END if is_last else Glyphs.MID
        line = Text()
        line.append(f"  {stem} ", style=p.muted)
        line.append(f"{k:<{key_width}}", style=p.muted)
        line.append("  ")
        line.append_text(Text.from_markup(v))
        lines.append(line)

    return Group(head, *lines)


# ── Tree: nested rows ─────────────────────────────────────────────────


@dataclass
class TreeRow:
    """One row in a tree-stem rendering."""

    label: str  # rich-markup allowed
    secondary: str = ""  # right-side dim text (optional)
    children: list[TreeRow] = None  # type: ignore

    def __post_init__(self):
        if self.children is None:
            self.children = []


def Tree(
    rows: Sequence[TreeRow | tuple[str, str]],
    palette: Any = None,
    *,
    indent: int = 2,
) -> Group:
    """Render a nested tree with ├─ └─ │ stems.

    Each row may be a TreeRow or a (label, secondary) tuple.
    """
    p = _pal_from(palette)
    pad = " " * indent

    def _row_to_lines(row: TreeRow, prefix: str, is_last: bool) -> list[Text]:
        stem = Glyphs.END if is_last else Glyphs.MID
        line = Text()
        line.append(prefix, style=p.muted)
        line.append(stem, style=p.muted)
        line.append(" ")
        line.append_text(Text.from_markup(row.label))
        if row.secondary:
            line.append("  ")
            line.append_text(Text.from_markup(f"[{p.muted}]{row.secondary}[/]"))
        out = [line]
        if row.children:
            child_prefix = prefix + ("   " if is_last else f"{Glyphs.VERT}  ")
            for j, child in enumerate(row.children):
                out.extend(_row_to_lines(child, child_prefix, j == len(row.children) - 1))
        return out

    normalized: list[TreeRow] = []
    for r in rows:
        if isinstance(r, tuple):
            normalized.append(TreeRow(label=r[0], secondary=r[1] if len(r) > 1 else ""))
        else:
            normalized.append(r)

    all_lines: list[Text] = []
    n = len(normalized)
    for i, row in enumerate(normalized):
        all_lines.extend(_row_to_lines(row, pad, i == n - 1))
    return Group(*all_lines)


# ── status_rule: persistent state line ────────────────────────────────


def status_rule(*segments: str, palette: Any = None) -> Text:
    """Render a one-line `─ a ─ b ─ c ─` rule.

    Each segment is a rich-markup string. Empty / None segments are skipped.
    """
    p = _pal_from(palette)
    parts = [s for s in segments if s]
    if not parts:
        return Text("")
    sep = f" [{p.muted}]─[/] "
    body = sep.join(parts)
    return Text.from_markup(f"[{p.muted}]─[/] " + body + f" [{p.muted}]─[/]")


# ── context_bar: colored progress bar ─────────────────────────────────


def context_bar(
    used: int,
    total: int,
    palette: Any = None,
    *,
    width: int = 10,
    show_pct: bool = True,
) -> str:
    """Render `[████░░░░░░] 45%` with thresholded color.

    Color shift mirrors the patterns used in mature terminal agents:
        <50%   good
        50-80% warn
        80-95% bad
        >=95%  critical
    """
    if total <= 0:
        return ""
    p = _pal_from(palette)
    pct = min(1.0, max(0.0, used / total))
    pct100 = int(pct * 100)

    if pct >= 0.95:
        color = p.status_critical
    elif pct >= 0.80:
        color = p.status_bad
    elif pct >= 0.50:
        color = p.status_warn
    else:
        color = p.status_good

    filled = int(round(pct * width))
    empty = width - filled
    bar = Glyphs.BAR_FILLED * filled + Glyphs.BAR_EMPTY * empty
    if show_pct:
        return f"[{color}]{bar}[/] [dim]{pct100}%[/]"
    return f"[{color}]{bar}[/]"


# ── result_panel: success / failure summary ───────────────────────────


def result_panel(
    title: str,
    rows: Sequence[tuple[str, str]],
    *,
    success: bool = True,
    palette: Any = None,
    extras: Sequence[RenderableType] | None = None,
) -> Panel:
    p = _pal_from(palette)
    border = p.ok if success else p.error
    glyph = Glyphs.CHECK if success else Glyphs.CROSS

    head = Text()
    head.append(f"{glyph} ", style=f"bold {border}")
    head.append(title, style=f"bold {border}")

    body: list[RenderableType] = [head]
    if rows:
        rendered_rows: list[Text] = []
        for k, v in rows:
            line = Text()
            line.append(f"  {k:<10}", style=p.muted)
            line.append("  ")
            line.append_text(Text.from_markup(v))
            rendered_rows.append(line)
        body.extend(rendered_rows)
    if extras:
        for e in extras:
            body.append(e)

    return Panel(Group(*body), border_style=border, padding=(1, 2))


# ── confirm_prompt: blocking yes/no with arrow selection ──────────────


def confirm_prompt(
    console: Console,
    title: str,
    body: str = "",
    *,
    default_yes: bool = True,
    palette: Any = None,
    yes_label: str = "yes",
    no_label: str = "no",
    danger: bool = False,
) -> bool:
    """Show a modal confirm prompt. Arrow keys, 1/2 quick-pick, Enter.

    Falls back to a plain stdin read if prompt_toolkit isn't usable.
    Returns True for yes, False for no / cancellation.
    """
    p = _pal_from(palette)
    border = p.warn if danger else p.accent

    head = Text()
    head.append(f"{Glyphs.WARN if danger else Glyphs.INFO} ", style=f"bold {border}")
    head.append(title, style=f"bold {border}")

    parts: list[RenderableType] = [head]
    if body:
        body_lines = []
        for line in body.splitlines():
            t = Text("  ")
            t.append_text(Text.from_markup(line))
            body_lines.append(t)
        parts.extend(body_lines)
    parts.append(Text(""))

    options = [yes_label, no_label]
    idx = 0 if default_yes else 1

    # Non-interactive (no TTY): render the panel once, accept the default.
    # Prevents a double-rendered panel + the noisy "Input is not a terminal"
    # warning when commands are piped or invoked from automation.
    import sys as _sys

    if not (_sys.stdin.isatty() and _sys.stdout.isatty()):
        console.print(Panel(Group(*parts), border_style=border, padding=(1, 2)))
        return default_yes

    # Try prompt_toolkit-backed selection.
    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Layout
        from prompt_toolkit.layout.containers import HSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl

        # We render the modal panel up front, then drive a tiny chooser.
        console.print(Panel(Group(*parts), border_style=border, padding=(1, 2)))

        state = {"idx": idx, "submitted": None}
        kb = KeyBindings()

        def _render():
            lines = []
            for i, opt in enumerate(options):
                sel = Glyphs.SELECTOR_ACTIVE if i == state["idx"] else Glyphs.SELECTOR_IDLE
                if i == state["idx"]:
                    lines.append(("class:active", f"  {sel} {i + 1}. {opt}\n"))
                else:
                    lines.append(("", f"  {sel} {i + 1}. {opt}\n"))
            lines.append(("class:hint", "  ↑/↓ select · 1/2 quick · Enter confirm · Esc cancel"))
            return lines

        ft = FormattedTextControl(_render)
        layout = Layout(HSplit([Window(ft, height=3, dont_extend_height=True)]))

        @kb.add("up")
        def _(event):
            state["idx"] = (state["idx"] - 1) % len(options)
            event.app.invalidate()

        @kb.add("down")
        def _(event):
            state["idx"] = (state["idx"] + 1) % len(options)
            event.app.invalidate()

        @kb.add("1")
        def _(event):
            state["idx"] = 0
            state["submitted"] = True
            event.app.exit()

        @kb.add("2")
        def _(event):
            state["idx"] = 1
            state["submitted"] = True
            event.app.exit()

        @kb.add("enter")
        def _(event):
            state["submitted"] = True
            event.app.exit()

        @kb.add("escape")
        @kb.add("c-c")
        def _(event):
            state["idx"] = 1
            state["submitted"] = False
            event.app.exit()

        from prompt_toolkit.styles import Style

        style = Style.from_dict(
            {
                "active": f"bold {border}",
                "hint": p.muted,
            }
        )

        app = Application(layout=layout, key_bindings=kb, style=style, full_screen=False)
        app.run()

        if state["submitted"] is None:
            return False
        return state["idx"] == 0

    except Exception:
        # Plain-stdin fallback
        console.print(Panel(Group(*parts), border_style=border, padding=(1, 2)))
        try:
            raw = input(f"  [{yes_label}/{no_label}] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        if not raw:
            return default_yes
        return raw in ("y", "yes", "1", yes_label.lower())


# ── select_prompt: choose-one-of-N selector ───────────────────────────


def select_prompt(
    console: Console,
    question: str,
    options: Sequence[str],
    *,
    default_idx: int = 0,
    palette: Any = None,
) -> int | None:
    """Inline selector. Returns the chosen index, or None on cancellation."""
    p = _pal_from(palette)

    head = Text()
    head.append("ask ", style=f"bold {p.accent}")
    head.append(question)
    console.print()
    console.print(head)

    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Layout
        from prompt_toolkit.layout.containers import HSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.styles import Style

        state = {"idx": max(0, min(default_idx, len(options) - 1)), "submitted": None}
        kb = KeyBindings()

        def _render():
            lines = []
            for i, opt in enumerate(options):
                sel = Glyphs.SELECTOR_ACTIVE if i == state["idx"] else Glyphs.SELECTOR_IDLE
                if i == state["idx"]:
                    lines.append(("class:active", f"  {sel} {i + 1}. {opt}\n"))
                else:
                    lines.append(("", f"  {sel} {i + 1}. {opt}\n"))
            lines.append(
                (
                    "class:hint",
                    f"  ↑/↓ select · 1-{len(options)} quick · Enter confirm · Esc cancel",
                )
            )
            return lines

        ft = FormattedTextControl(_render)
        layout = Layout(HSplit([Window(ft, height=len(options) + 1, dont_extend_height=True)]))

        @kb.add("up")
        def _(event):
            state["idx"] = (state["idx"] - 1) % len(options)
            event.app.invalidate()

        @kb.add("down")
        def _(event):
            state["idx"] = (state["idx"] + 1) % len(options)
            event.app.invalidate()

        for i in range(min(len(options), 9)):

            @kb.add(str(i + 1))
            def _(event, _i=i):
                state["idx"] = _i
                state["submitted"] = True
                event.app.exit()

        @kb.add("enter")
        def _(event):
            state["submitted"] = True
            event.app.exit()

        @kb.add("escape")
        @kb.add("c-c")
        def _(event):
            state["submitted"] = False
            event.app.exit()

        style = Style.from_dict(
            {
                "active": f"bold {p.accent}",
                "hint": p.muted,
            }
        )

        app = Application(layout=layout, key_bindings=kb, style=style, full_screen=False)
        app.run()

        if not state["submitted"]:
            return None
        return state["idx"]

    except Exception:
        for i, opt in enumerate(options):
            console.print(f"  {i + 1}. {opt}")
        try:
            raw = input(f"  choose [1-{len(options)}, default {default_idx + 1}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if not raw:
            return default_idx
        try:
            n = int(raw) - 1
            if 0 <= n < len(options):
                return n
        except ValueError:
            pass
        return None


# ── Inline status lines (errors / info / ok) ──────────────────────────


def ok_line(message: str, palette: Any = None, *, secondary: str = "") -> Text:
    p = _pal_from(palette)
    line = Text()
    line.append(f"{Glyphs.CHECK}  ", style=f"bold {p.ok}")
    line.append_text(Text.from_markup(message))
    if secondary:
        line.append(f"  · {secondary}", style=p.muted)
    return line


def info_line(message: str, palette: Any = None, *, secondary: str = "") -> Text:
    p = _pal_from(palette)
    line = Text()
    line.append(f"{Glyphs.INFO}  ", style=p.muted)
    line.append_text(Text.from_markup(message))
    if secondary:
        line.append(f"  · {secondary}", style=p.muted)
    return line


def error_line(message: str, palette: Any = None, *, suggestion: str = "") -> Group:
    p = _pal_from(palette)
    line = Text()
    line.append(f"{Glyphs.CROSS}  ", style=f"bold {p.error}")
    line.append_text(Text.from_markup(message))
    parts: list[RenderableType] = [line]
    if suggestion:
        sug = Text()
        sug.append("   ", style=p.muted)
        sug.append("try: ", style=p.muted)
        sug.append_text(Text.from_markup(suggestion))
        parts.append(sug)
    return Group(*parts)


def warn_line(message: str, palette: Any = None, *, secondary: str = "") -> Text:
    p = _pal_from(palette)
    line = Text()
    line.append(f"{Glyphs.WARN}  ", style=f"bold {p.warn}")
    line.append_text(Text.from_markup(message))
    if secondary:
        line.append(f"  · {secondary}", style=p.muted)
    return line


# ── panel helpers ─────────────────────────────────────────────────────


def section_panel(
    *sections: Group | RenderableType | str,
    title: str | None = None,
    palette: Any = None,
    border_color: str | None = None,
    padding: tuple[int, int] = (1, 2),
) -> Panel:
    """Compose multiple Section() outputs into one panel with the right border."""
    p = _pal_from(palette)
    parts: list[RenderableType] = []

    if title:
        head = Text()
        head.append(title, style=f"bold {p.accent}")
        parts.append(head)
        parts.append(Text(""))

    for i, s in enumerate(sections):
        if isinstance(s, str):
            parts.append(Text.from_markup(s))
        else:
            parts.append(s)
        if i != len(sections) - 1:
            parts.append(Text(""))

    return Panel(
        Group(*parts),
        border_style=border_color or p.border,
        padding=padding,
    )
