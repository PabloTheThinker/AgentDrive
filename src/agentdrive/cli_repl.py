"""
Operator REPL for AgentDrive (UX Pattern 5).

Dispatches typed lines through the same ``argparse`` handlers as ``agentdrive``
subcommands — one code path for CLI and interactive shell.
"""

from __future__ import annotations

import argparse
import shlex
import sys
from typing import Any

from rich.console import Console
from rich.markup import escape as rich_escape

from agentdrive.cli_catalog import CATALOG, search_catalog

console = Console()

_EXIT_WORDS = frozenset({"exit", "quit", "q", ":q"})
_META_WORDS = frozenset({"help", "?", "commands"})


def _catalog_completions() -> list[str]:
    """Distinct command prefixes for tab completion."""
    seen: set[str] = set()
    out: list[str] = []
    for entry in CATALOG:
        cmd = entry.command.strip()
        if cmd and cmd not in seen:
            seen.add(cmd)
            out.append(cmd)
    return sorted(out)


def dispatch_line(line: str, parser: argparse.ArgumentParser) -> int | None:
    """Parse and run one REPL line.

    Returns:
        ``None`` when the line was empty (continue REPL).
        ``-1`` when the user asked to exit the REPL.
        Otherwise the handler exit code (0 = success).
    """
    stripped = line.strip()
    if not stripped:
        return None

    if stripped.lower() in _EXIT_WORDS:
        return -1

    if stripped.lower() in _META_WORDS:
        console.print("[dim]Type any agentdrive subcommand (e.g. doctor, golden-path verify).[/]")
        console.print("[dim]Tab-complete from the catalog.  exit / quit to leave.[/]")
        return 0

    if stripped.lower().startswith("search "):
        query = stripped[7:].strip()
        if not query:
            console.print("[yellow]Usage: search <query>[/]")
            return 0
        hits = search_catalog(query)
        if not hits:
            console.print(f"[dim]No catalog matches for {query!r}.[/]")
            return 0
        for entry in hits[:12]:
            console.print(f"  [cyan]{entry.command}[/]  [dim]{entry.summary}[/]")
        if len(hits) > 12:
            console.print(f"[dim]… and {len(hits) - 12} more[/]")
        return 0

    try:
        tokens = shlex.split(stripped)
    except ValueError as exc:
        console.print(f"[red]Parse error:[/] {rich_escape(str(exc))}")
        return 1

    if not tokens:
        return None

    try:
        args = parser.parse_args(tokens)
    except SystemExit:
        # argparse already printed usage
        return 1

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    try:
        code = args.func(args)
        return code if code is not None else 0
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/]")
        return 130
    except Exception as exc:
        console.print(f"[red]Error:[/] {rich_escape(str(exc))}")
        return 1


def run_repl(*, parser: argparse.ArgumentParser | None = None) -> int:
    """Interactive operator shell. Returns process exit code."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        console.print(
            "[yellow]REPL requires a TTY.[/] "
            "[dim]Use subcommands directly or set AGENTDRIVE_NO_TUI=1 with a pipe.[/]"
        )
        return 1

    if parser is None:
        # Late import avoids circular dependency at module load.
        from agentdrive.cli import build_parser

        parser = build_parser()

    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import WordCompleter
        from prompt_toolkit.history import FileHistory
    except ImportError:
        console.print(
            "[red]prompt_toolkit is required for the REPL.[/] [dim]pip install prompt_toolkit[/]"
        )
        return 1

    from agentdrive.constants import get_agentdrive_home

    history_path = get_agentdrive_home() / ".agentdrive_repl_history"
    completer = WordCompleter(
        [*_catalog_completions(), "help", "search", "exit", "quit"],
        ignore_case=True,
        sentence=True,
    )
    session: Any = PromptSession(
        history=FileHistory(str(history_path)),
        completer=completer,
        enable_history_search=True,
    )

    console.print()
    console.print("[bold]AgentDrive operator REPL[/]")
    console.print(
        '[dim]Dispatch any subcommand (doctor, golden-path verify, think "…"). '
        "search <query> · help · exit[/]"
    )
    console.print()

    while True:
        try:
            line = session.prompt("agentdrive> ")
        except (EOFError, KeyboardInterrupt):
            console.print()
            break

        code = dispatch_line(line, parser)
        if code is None:
            continue
        if code == -1:
            break

    console.print("[dim]bye[/]")
    return 0


def cmd_repl(_args: argparse.Namespace) -> int:
    """CLI entry: ``agentdrive repl``."""
    return run_repl()
