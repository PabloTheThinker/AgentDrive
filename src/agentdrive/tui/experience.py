"""
Terminal experience helpers — golden-path gate, ops-backed slash commands.

Bridges the CLI golden path into the TUI chat surface (UX-PROPOSAL Pattern 5).
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.text import Text

from agentdrive.golden_path import GOLDEN_STEPS, run_walkthrough, verify_all
from agentdrive.operations import run_operation
from agentdrive.tui.chrome import Group, Palette, Section, Tree, TreeRow, ok_line, section_panel, warn_line


def _golden_path_config() -> dict[str, Any]:
    try:
        from agentdrive.config import load_config

        cfg = load_config()
        gp = cfg.get("golden_path")
        return gp if isinstance(gp, dict) else {}
    except Exception:
        return {}


def is_golden_path_marked_complete() -> bool:
    return bool(_golden_path_config().get("completed"))


def mark_golden_path_complete(*, source: str = "tui") -> None:
    from datetime import UTC, datetime

    from agentdrive.config import load_config, save_config

    cfg = load_config()
    cfg.setdefault("golden_path", {})
    cfg["golden_path"]["completed"] = True
    cfg["golden_path"]["completed_at"] = datetime.now(UTC).isoformat()
    cfg["golden_path"]["source"] = source
    save_config(cfg)


def golden_path_verify_summary(*, include_optional: bool = True) -> dict[str, Any]:
    """Lightweight verify for status line and gate."""
    return verify_all(include_optional=include_optional)


def should_show_golden_path_gate() -> bool:
    """Show first-run gate when not marked complete and core steps incomplete."""
    if is_golden_path_marked_complete():
        return False
    summary = golden_path_verify_summary(include_optional=False)
    # Core: install + doctor + mcp must pass; learnings optional for gate
    steps = {s["step"]: s.get("success") for s in summary.get("steps", [])}
    core = ("install", "doctor", "mcp")
    if all(steps.get(k) for k in core):
        # MCP wired — only nag if learnings empty
        try:
            from agentdrive.learnings import LearningsStore

            if LearningsStore().count() > 0:
                return False
        except Exception:
            pass
        return not steps.get("learnings", False)
    return True


def golden_path_status_segment(palette: Palette | None = None) -> str:
    """One segment for the chat status rule."""
    p = palette or Palette(None)
    if is_golden_path_marked_complete():
        return f"[{p.ok}]golden ✓[/]"
    summary = golden_path_verify_summary(include_optional=False)
    passed = summary.get("passed", 0)
    total = summary.get("total", len(GOLDEN_STEPS))
    if summary.get("required_pass"):
        return f"[{p.ok}]golden {passed}/{total}[/]"
    return f"[{p.warn}]golden {passed}/{total}[/]"


def render_golden_path_gate(console: Console, *, palette: Palette | None = None) -> None:
    """Compact panel shown on first TUI/chat entry when gate is active."""
    p = palette or Palette(None)
    summary = golden_path_verify_summary(include_optional=False)
    rows: list[tuple[str, str]] = []
    for item in summary.get("steps", []):
        step_id = str(item.get("step", ""))
        ok = item.get("success", False)
        mark = f"[{p.ok}]✓[/]" if ok else f"[{p.warn}]○[/]"
        rows.append((step_id, mark))

    console.print()
    console.print(
        section_panel(
            Section(
                "First-run golden path",
                rows,
                palette=p,
                key_width=12,
            ),
            title="Complete the memory loop",
            palette=p,
            extras=[
                Text(""),
                Text.from_markup(
                    f"[{p.muted}]In chat:[/] [{p.accent}]/golden-path run[/]  "
                    f"[{p.muted}]· shell:[/] [{p.accent}]agentdrive golden-path run[/]"
                ),
                Text.from_markup(
                    f"[{p.muted}]Docs:[/] docs/GOLDEN_PATH.md"
                ),
            ],
        )
    )
    console.print()


def run_golden_path_interactive(
    console: Console,
    *,
    dry_run: bool = False,
    palette: Palette | None = None,
) -> int:
    """Run walkthrough from TUI; mark complete on success."""
    p = palette or Palette(None)
    result = run_walkthrough(dry_run=dry_run, stop_on_fail=False)
    passed = result.get("passed", 0)
    total = result.get("total", 0)
    ok = result.get("success", False)

    for item in result.get("steps", []):
        step = str(item.get("step", "?"))
        if item.get("skipped"):
            console.print(f"  [dim]○ {step}[/] skipped — {item.get('detail', '')}")
            continue
        style = p.ok if item.get("success") else p.warn
        glyph = "✓" if item.get("success") else "✗"
        note = item.get("hint") or item.get("detail") or item.get("note") or ""
        console.print(f"  [{style}]{glyph} {step}[/][dim] {note}[/]")

    if ok and not dry_run:
        mark_golden_path_complete(source="tui")
        console.print()
        console.print(ok_line(f"Golden path complete ({passed}/{total}).", palette=p))
    elif dry_run:
        console.print()
        console.print(ok_line(f"Dry-run plan ({passed}/{total} steps).", palette=p))
    else:
        console.print()
        console.print(
            warn_line(
                f"Golden path incomplete ({passed}/{total}). "
                f"Try [{p.accent}]agentdrive provider set <name>[/] then re-run.",
                palette=p,
            )
        )
    return 0 if ok else 1


def handle_ops_slash(
    console: Console,
    cmd: str,
    arg: str,
    *,
    palette: Palette | None = None,
    agent_id: str = "agentdrive-agent",
    current_session_id: str | None = None,
) -> None:
    """Dispatch /think, /learnings, /golden-path from chat (Pattern 5)."""
    p = palette or Palette(None)
    cmd = cmd.lower().strip()

    if cmd in ("/golden-path", "/golden"):
        sub = (arg.split()[0] if arg else "verify").lower()
        rest = arg[len(sub) :].strip() if arg else ""

        if sub in ("steps", "list"):
            for i, step in enumerate(GOLDEN_STEPS, 1):
                opt = " [dim](optional)[/]" if step.optional else ""
                console.print(
                    f"  [dim]{i}.[/] [{p.accent}]{step.title}[/]{opt} — {step.command}"
                )
        elif sub == "verify":
            summary = golden_path_verify_summary()
            for item in summary.get("steps", []):
                ok = item.get("success", False)
                glyph = "✓" if ok else "○"
                style = p.ok if ok else p.muted
                console.print(
                    f"  [{style}]{glyph}[/] {item.get('step')} — {item.get('detail', '')}"
                )
            console.print(
                f"\n  [dim]{summary.get('passed', 0)}/{summary.get('total', 0)} passed[/]"
            )
        elif sub == "run":
            dry = rest == "--dry-run" or "--dry-run" in rest
            run_golden_path_interactive(console, dry_run=dry, palette=p)
        else:
            console.print(
                warn_line(
                    "Usage: /golden-path steps|verify|run [--dry-run]",
                    palette=p,
                )
            )
        return

    if cmd == "/think":
        question = arg.strip() or "What should I know about my AgentDrive?"
        result = run_operation("think", question=question)
        if not result.get("success"):
            console.print(warn_line(str(result.get("error", "think failed")), palette=p))
            return
        payload = result.get("result") or {}
        answer = payload.get("answer") or payload.get("synthesis") or str(payload)
        console.print()
        console.print(str(answer))
        gaps = payload.get("gaps") or []
        if gaps:
            console.print()
            console.print(f"[{p.warn}]Gaps:[/]")
            for gap in gaps[:6]:
                console.print(f"  • {gap}")
        return

    if cmd == "/learnings":
        parts = arg.split(maxsplit=1) if arg else []
        sub = parts[0].lower() if parts else "list"
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "list":
            result = run_operation("learnings_list", limit=15)
            for entry in result.get("entries") or []:
                console.print(
                    f"  [{p.genome}]{entry.get('key')}[/] "
                    f"[dim]({entry.get('type')})[/] {entry.get('insight', '')}"
                )
        elif sub == "log":
            # /learnings log my-key insight text here
            log_parts = rest.split(maxsplit=1)
            if len(log_parts) < 2:
                console.print(
                    warn_line("Usage: /learnings log <key> <insight>", palette=p)
                )
                return
            key, insight = log_parts[0], log_parts[1]
            result = run_operation(
                "learnings_log",
                key=key,
                insight=insight,
                type="operational",
            )
            if result.get("success"):
                console.print(ok_line(f"Logged [{key}]", palette=p))
            else:
                console.print(warn_line(str(result.get("error")), palette=p))
        elif sub == "search":
            if not rest:
                console.print(warn_line("Usage: /learnings search <query>", palette=p))
                return
            from agentdrive.learnings import LearningsStore

            hits = LearningsStore().search(rest, limit=10)
            for entry in hits:
                console.print(
                    f"  [{p.genome}]{entry.get('key')}[/] {entry.get('insight', '')}"
                )
        else:
            console.print(
                warn_line("Usage: /learnings list|log|search ...", palette=p)
            )
        return

    if cmd == "/session":
        from agentdrive.session_events import (
            filter_events_by_type,
            format_event_summary,
            format_type_histogram,
            replay_events,
            resolve_session_id,
            session_events_path,
            summarize_event_types,
        )

        raw_tokens = arg.split() if arg else []
        type_filter: str | None = None
        tokens: list[str] = []
        idx = 0
        while idx < len(raw_tokens):
            if raw_tokens[idx] == "--type" and idx + 1 < len(raw_tokens):
                type_filter = raw_tokens[idx + 1]
                idx += 2
            else:
                tokens.append(raw_tokens[idx])
                idx += 1

        _SESSION_SUBS = {"events", "replay", "list", "panel", "filter", "types"}
        if not tokens:
            sub = "events"
            sid_token = current_session_id or ""
        elif tokens[0].lower() in _SESSION_SUBS:
            sub = tokens[0].lower()
            if sub == "filter":
                if len(tokens) < 2:
                    console.print(
                        warn_line(
                            "Usage: /session filter <Type> [session_id]",
                            palette=p,
                        )
                    )
                    return
                type_filter = tokens[1]
                sid_token = tokens[2] if len(tokens) > 2 else (current_session_id or "")
            elif sub == "types":
                sid_token = tokens[1] if len(tokens) > 1 else (current_session_id or "")
            else:
                sid_token = tokens[1] if len(tokens) > 1 else (current_session_id or "")
                if len(tokens) > 2 and type_filter is None:
                    type_filter = tokens[2]
        else:
            sub = "events"
            sid_token = tokens[0]

        if not sid_token:
            console.print(
                warn_line(
                    "Usage: /session events|replay|panel|filter|types [session_id] [--type T]",
                    palette=p,
                )
            )
            return

        resolved = resolve_session_id(agent_id, sid_token) or sid_token
        path = session_events_path(agent_id, resolved)
        events = replay_events(path)

        if not path.exists():
            console.print(warn_line(f"No events at {path}", palette=p))
            return

        filtered = filter_events_by_type(events, type_filter)
        counts = summarize_event_types(events)
        filter_note = f"  [dim]· filter {type_filter} ({len(filtered)}/{len(events)})[/]" if type_filter else ""

        if sub == "panel":
            type_rows = [(ev_type, str(n)) for ev_type, n in counts.items()]
            timeline_rows = [
                TreeRow(label=format_event_summary(ev))
                for ev in filtered[-60:]
            ]
            if len(filtered) > 60:
                timeline_rows.insert(
                    0,
                    TreeRow(
                        label=f"[{p.muted}]… {len(filtered) - 60} earlier events[/]",
                    ),
                )
            console.print(
                section_panel(
                    Section("Session", [(resolved, path.name), ("events", str(len(events)))], palette=p),
                    Section(
                        "Event types",
                        type_rows or [("(none)", "0")],
                        palette=p,
                        key_width=18,
                    ),
                    Group(
                        Text.from_markup(f"[bold {p.accent}]Timeline[/]{filter_note}"),
                        Tree(timeline_rows, palette=p) if timeline_rows else Text(""),
                    ),
                    title="Session replay",
                    palette=p,
                )
            )
            return

        console.print(
            f"  [dim]session[/] [{p.accent}]{resolved}[/]  "
            f"[dim]· {len(events)} events · {path.name}[/]{filter_note}"
        )
        if sub == "types":
            console.print(f"  [dim]{format_type_histogram(counts)}[/]")
            return

        console.print()

        if sub == "replay" or (sub == "filter" and type_filter):
            for idx, ev in enumerate(filtered, 1):
                console.print(f"  [dim]{idx:>3}[/]  {format_event_summary(ev)}")
        elif sub in ("events", "list"):
            for ev in filtered[-40:]:
                console.print(f"  {format_event_summary(ev)}")
            if len(filtered) > 40:
                console.print(f"  [dim]… {len(filtered) - 40} earlier events (use replay)[/]")
        else:
            console.print(
                warn_line(
                    "Usage: /session events|replay|panel|filter|types [session_id]",
                    palette=p,
                )
            )
        return

    if cmd in ("/skills", "/skill"):
        from agentdrive.skills import list_skills, run_skill
        from agentdrive.skills.runner import format_skill_result

        if cmd == "/skills":
            parts = arg.split() if arg else []
            sub = (parts[0] if parts else "list").lower()
            if sub == "list":
                entries = list_skills()
                if not entries:
                    console.print(warn_line("No skills found under ~/.agentdrive/skills", palette=p))
                    return
                for entry in entries:
                    op = f" [dim]→ {entry.operation}[/]" if entry.operation else ""
                    console.print(
                        f"  [{p.accent}]{entry.name}[/]{op}  "
                        f"[dim]{entry.description[:60]}[/]"
                    )
                console.print()
                console.print(
                    Text.from_markup(
                        f"[{p.muted}]Run:[/] [{p.accent}]/skill <name> [args][/]  "
                        f"[{p.muted}]Scaffold:[/] [{p.accent}]/skills init <name>[/]"
                    )
                )
            elif sub == "init":
                from agentdrive.skills.registry import init_skill

                name = parts[1] if len(parts) > 1 else ""
                if not name.strip():
                    console.print(warn_line("Usage: /skills init <name>", palette=p))
                    return
                try:
                    path = init_skill(name.strip())
                except FileExistsError as exc:
                    console.print(warn_line(str(exc), palette=p))
                    return
                except ValueError as exc:
                    console.print(warn_line(str(exc), palette=p))
                    return
                console.print(ok_line(f"Created {path}", palette=p))
            else:
                console.print(warn_line("Usage: /skills list|init <name>", palette=p))
            return

        # /skill <name> [args]
        parts = arg.split(maxsplit=1)
        if not parts:
            console.print(warn_line("Usage: /skill <name> [args]", palette=p))
            return
        name, skill_arg = parts[0], parts[1] if len(parts) > 1 else ""
        result = run_skill(name, skill_arg)
        if not result.get("success"):
            console.print(warn_line(str(result.get("error", "skill failed")), palette=p))
            return
        if summary := result.get("result"):
            if isinstance(summary, dict) and summary.get("steps"):
                for item in summary.get("steps", []):
                    ok = item.get("success", False)
                    glyph = "✓" if ok else "○"
                    style = p.ok if ok else p.muted
                    console.print(
                        f"  [{style}]{glyph}[/] {item.get('step')} — {item.get('detail', '')}"
                    )
                return
        console.print()
        console.print(format_skill_result(result))
        return

    console.print(warn_line(f"Unknown ops slash: {cmd}", palette=p))