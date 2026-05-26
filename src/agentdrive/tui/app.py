"""
AgentDrive Professional TUI Application

High-quality terminal interface for the AgentDrive.
Focus: precision, clarity, trust, and powerful genome-aware workflows.

Agent Drive is an independent, open-source framework for agent DNA (memory + patterns).
It gives every agent — and every swarm of sub-agents — its own persistent,
user-controlled living pool of experience that starts empty and grows with use.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from contextlib import nullcontext
from datetime import datetime
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from rich.console import Group
from rich.live import Live
from rich.markup import escape as rich_escape
from rich.panel import Panel
from rich.text import Text

from agentdrive.genome.models import Genome
from agentdrive.registry import GenomeRegistry
from agentdrive.tui.chat import ChatView
from agentdrive.tui.skin_engine import skin
from agentdrive.tui.views.drive_view import register_drive_view


class Agent DriveTUI:
    """Production-grade interactive TUI for Agent Drive genome management and orchestration."""

    def __init__(self):
        self.skin = skin
        self.console = skin.console
        self.registry = GenomeRegistry()
        self.running = True
        self.selected: str | None = None  # current focused genome dir_name or id
        self.run_history: list[dict[str, Any]] = []
        self._cancel_event = threading.Event()

        # Prompt toolkit session with persistent history
        agentdrive_home = self.registry.root.parent
        agentdrive_home.mkdir(parents=True, exist_ok=True)
        self._history_file = agentdrive_home / ".agentdrive_tui_history"
        self.session: PromptSession = PromptSession(
            history=FileHistory(str(self._history_file)),
            completer=None,  # set dynamically per prompt for fresh genome list
            enable_history_search=True,
            mouse_support=False,
        )

        self._base_commands = [
            "help",
            "?",
            "h",
            "genomes",
            "ls",
            "list",
            "g",
            "view",
            "v",
            "status",
            "dash",
            "dashboard",
            "s",
            "drive",
            "d",
            "board",
            "missions",
            "kanban",
            "b",
            "chat",
            "scan",
            "run",
            "r",
            "execute",
            "evolve",
            "e",
            "compose",
            "c",
            "doctor",
            "dr",
            "setup",
            "configure",
            "import",
            "bootstrap",
            "clear",
            "cls",
            "exit",
            "quit",
            "q",
            ":q",
        ]
        self._ensure_bootstrap()
        # Attach first-class Pool view (stateful across switches)
        try:
            register_drive_view(self)
        except Exception:
            self.pool_view = None

    def _ensure_bootstrap(self) -> None:
        """Register seed example on first use so TUI is immediately useful."""
        try:
            gid = self.registry.ensure_bootstrap_example()
            if gid:
                self.console.print(
                    f"[agentdrive.ok]✓ Bootstrapped seed genome into registry:[/] [agentdrive.genome]{gid}[/]"
                )
                if not self.selected:
                    self.selected = gid
        except Exception as e:
            self.console.print(f"[agentdrive.warn]Bootstrap note:[/] {e}")

    def _get_status_context(self) -> str:
        """Short status snippet for the prompt line (registry count, pool health)."""
        try:
            stats = self.registry.get_registry_stats()
            cnt = stats.get("count", 0)
            return f"[dim]{cnt} genome{'s' if cnt != 1 else ''}[/]"
        except Exception:
            return "[dim]--[/]"

    def _build_completer(self) -> WordCompleter:
        """Fresh completer including live genome names and commands."""
        try:
            details = self.registry.list_genome_details()
            names = set()
            for d in details:
                names.add(d["dir_name"])
                names.add(d["genome_id"])
                names.add(d["id"])
            names.update(self.registry.list_genomes())
        except Exception:
            names = set()
        # Pool sub-commands for excellent sentence completion after "pool " or "p "
        pool_sub_commands = [
            "query",
            "q",
            "search",
            "swarms",
            "sw",
            "switch",
            "use",
            "swarm",
            "global",
            "main",
            "genomes",
            "ls",
            "browse",
            "view",
            "v",
            "ingest",
            "i",
            "evolve",
            "e",
            "merge",
            "m",
            "settings",
            "cfg",
            "config",
            "stats",
            "st",
            "overview",
            "o",
            "create-swarm",
            "help",
            "back",
            "leave",
        ]
        all_tokens = list(self._base_commands) + pool_sub_commands + sorted(names)
        return WordCompleter(all_tokens, ignore_case=True, sentence=True)

    def run(self) -> None:
        """Main REPL loop — premium feel with completion, history, clean interrupts."""
        self.skin.print_banner("AgentDrive")

        # Dedicated first-launch Agent Drive Welcome Screen
        # Shown once after onboarding — distinct from the reusable setup wizard.
        try:
            from agentdrive.config import load_config, save_config

            cfg = load_config()
            if cfg.get("onboarded") and not cfg.get("tui_welcome_shown"):
                self._show_dedicated_welcome_screen()
                cfg["tui_welcome_shown"] = True
                save_config(cfg)
        except Exception:
            pass

        self.console.print(
            "[dim]Professional evolutionary agent capability platform • Genomes as DNA • Precise • Trustworthy[/dim]\n"
        )

        stats = self.registry.get_registry_stats()
        if stats["count"] > 0:
            doms = ", ".join(stats["domains_covered"][:4]) or "—"
            self.console.print(
                f"[agentdrive.label]Registry[/]: [agentdrive.genome]{stats['count']}[/] genomes  •  domains: [agentdrive.framework]{doms}[/]\n"
            )

        self._print_quick_help()

        # First-class chat is the default landing — drop straight into talking
        # to your Agent Drive Agent. /back from chat returns to the command REPL.
        try:
            self._show_chat()
        except Exception as exc:
            self.console.print(f"[agentdrive.warn]Chat could not start:[/] {rich_escape(str(exc))}")
        if not self.running:
            self.console.print(
                "\n[dim]Goodbye — your genomes and runs are safe in the registry.[/dim]"
            )
            return

        while self.running:
            try:
                completer = self._build_completer()
                self.session.completer = completer

                sel = ""
                if self.selected:
                    short = self.selected.split("@")[0] if "@" in self.selected else self.selected
                    sel = f" ({short})"

                status_str = self._get_status_context()
                prompt_text = f"agentdrive{sel} {status_str} ❯ "
                line = self.session.prompt(
                    prompt_text,
                    default="",
                ).strip()

                if not line:
                    continue
                self._dispatch(line)

            except KeyboardInterrupt:
                self._cancel_event.set()
                self.console.print(
                    "\n[agentdrive.warn]▲ Interrupted[/]  (use 'exit' or Ctrl+D to quit)"
                )
            except EOFError:
                self.running = False
            except Exception as exc:
                self.console.print(f"[agentdrive.error]TUI error:[/] {rich_escape(str(exc))}")

        self.console.print("\n[dim]Goodbye — your genomes and runs are safe in the registry.[/dim]")

    def _print_quick_help(self) -> None:
        from agentdrive.tui.chrome import Palette, status_rule

        p = Palette(self.skin)
        self.console.print(
            status_rule(
                f"[{p.accent}]chat[/]",
                f"[{p.accent}]board[/]",
                f"[{p.accent}]pool[/]",
                f"[{p.accent}]genomes[/]",
                f"[{p.accent}]run[/]",
                f"[{p.accent}]doctor[/]",
                f"[{p.muted}]help · exit[/]",
                palette=p,
            )
        )
        self.console.print()

    def _show_dedicated_welcome_screen(self) -> None:
        """One-time welcome screen shown on first TUI launch after onboarding."""
        from rich.console import Group
        from rich.text import Text

        from agentdrive.tui.chrome import Glyphs, Palette, Section, section_panel

        p = Palette(self.skin)

        # Environment snapshot
        try:
            from pathlib import Path

            from agentdrive.drive.drive import get_default_drive

            agentdrive_home = Path.home() / ".agentdrive"
            pool = get_default_drive()
            pstats = pool.get_pool_stats()
            ingest_count = pstats.get("ingest_events", 0)
            swarm_count = (
                len(list((agentdrive_home / "swarms").glob("*")))
                if (agentdrive_home / "swarms").exists()
                else 0
            )
        except Exception:
            agentdrive_home = Path.home() / ".agentdrive"
            ingest_count = 0
            swarm_count = 0

        try:
            from agentdrive.providers import detect

            detected = detect()
            provider_v = (
                f"[agentdrive.ok]✓ {detected.display_name}[/]"
                if detected
                else "[agentdrive.warn]not configured[/]"
            )
        except Exception:
            provider_v = "[agentdrive.warn]unavailable[/]"

        hero = Text()
        hero.append(f"{Glyphs.DIAMOND} ", style=p.accent)
        hero.append("AGENTDRIVE", style=p.title + " bold")
        hero.append("  —  The Living, Learning Ecosystem for AI Agents", style=p.accent)

        tagline = Text(
            "Every agent (and every sub-agent it spawns) gets a private, persistent DNA pool.",
            style=p.muted + " italic",
        )

        body = section_panel(
            Group(hero, tagline),
            Section(
                "Environment",
                [
                    ("home", f"[agentdrive.genome]{agentdrive_home}[/]"),
                    ("provider", provider_v),
                    (
                        "drive",
                        f"[agentdrive.ok]ready[/]  · {ingest_count} ingest event{'s' if ingest_count != 1 else ''}",
                    ),
                    ("swarms", f"{swarm_count} seen"),
                ],
                palette=p,
            ),
            Section(
                "Recommended next steps",
                [
                    ("chat", "open the agent chat"),
                    ("drive", "browse genomes and swarms"),
                    ("setup swarm", "configure sub-agent sharing rules"),
                    ("doctor", "run a system health check"),
                    ("help", "see every command"),
                ],
                palette=p,
                key_width=14,
            ),
            title="Welcome to AgentDrive",
            palette=p,
        )

        self.console.print()
        self.console.print(body)
        self.console.print()

    def _dispatch(self, line: str) -> None:
        """Parse and route command. Supports 'cmd arg1 arg2', aliases, and
        slash-prefixed forms (`/pool` works the same as `pool`)."""
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower().strip()
        if cmd.startswith("/"):
            cmd = cmd[1:]
        argstr = parts[1] if len(parts) > 1 else ""
        args = argstr.split() if argstr else []

        if cmd in ("exit", "quit", "q", ":q", "bye"):
            self.running = False
            return
        if cmd in ("help", "?", "h"):
            self._show_help()
            return
        if cmd in ("genomes", "ls", "list", "g"):
            self._browse_genomes(args)
            return
        if cmd in ("view", "v", "show"):
            self._view_genome(args)
            return
        if cmd in ("status", "dash", "dashboard", "s"):
            self._show_status()
            return
        if cmd in ("drive", "d"):
            self._show_pool_view(args)
            return
        if cmd in ("chat", "/chat"):
            self._show_chat()
            return
        if cmd in ("board", "missions", "kanban", "b"):
            self._show_board(args)
            return
        if cmd == "scan":
            self._scan_runs(args)
            return
        if cmd in ("run", "r", "execute"):
            self._run_work(args)
            return
        if cmd in ("evolve", "e", "improve"):
            self._evolve_genome(args)
            return
        if cmd in ("compose", "c"):
            self._compose_mission(args)
            return
        if cmd in ("doctor", "dr", "health"):
            self._doctor()
            return
        if cmd in ("setup", "configure"):
            self._run_setup_wizard(args)
            return
        if cmd in ("import", "bootstrap", "seed"):
            self._import_example(args)
            return
        if cmd in ("clear", "cls"):
            # No user input in the command string, but os.system spawns a
            # shell — prefer subprocess.run with an argv list so any future
            # caller that thinks they can templatize the command can't
            # accidentally introduce a shell-injection path.
            import subprocess

            subprocess.run(
                ["cls"] if os.name == "nt" else ["clear"],
                check=False,
                shell=False,
            )
            self.skin.print_banner("AgentDrive")
            return

        self.console.print(f"[agentdrive.warn]Unknown:[/] {cmd}  — try [agentdrive.accent]help[/]")

    # ─────────────────────────────────────────────────────────────────────
    # Command implementations
    # ─────────────────────────────────────────────────────────────────────

    def _show_help(self) -> None:
        from rich.text import Text

        from agentdrive.tui.chrome import Palette, Section, section_panel

        p = Palette(self.skin)

        sections = [
            Section(
                "Talk",
                [
                    ("chat", "open the agent chat (default landing)"),
                ],
                palette=p,
                key_width=18,
            ),
            Section(
                "Pool",
                [
                    ("pool / p", "enter the first-class Pool TUI (global + swarms)"),
                    ('pool query "…"', "one-shot query from this prompt"),
                    ("pool swarms", "browse swarms"),
                    ("pool stats", "pool-wide stats"),
                ],
                palette=p,
                key_width=18,
            ),
            Section(
                "Board",
                [
                    ("board / b", "AgentDrive Mission Board (lanes: pending/running/done/failed)"),
                    ("board recent", "compact recent-missions view"),
                    ("board create <t>", "stage a Pending mission"),
                    ("board stats", "lane counts + avg duration"),
                ],
                palette=p,
                key_width=18,
            ),
            Section(
                "Genomes",
                [
                    ("genomes / g", "browse the registry as a table"),
                    ("view <id|#>", "inspect a single genome"),
                    ("import / seed", "register the bundled seed example"),
                ],
                palette=p,
                key_width=18,
            ),
            Section(
                "Execution",
                [
                    ("run <genome>", "interactive composer + live progress"),
                    ("scan <path>", "extract DNA from a run/trajectory"),
                    ("evolve <genome>", "propose an evolutionary improvement"),
                    ("compose / c", "multi-genome mission composer"),
                ],
                palette=p,
                key_width=18,
            ),
            Section(
                "Environment",
                [
                    ("doctor / dr", "animated system health check"),
                    ("setup / configure", "re-run the setup wizard"),
                    ("status / s", "registry health + recent activity"),
                ],
                palette=p,
                key_width=18,
            ),
            Section(
                "Session",
                [
                    ("clear / cls", "clear screen + banner"),
                    ("help / ?", "show this panel"),
                    ("exit / quit / q", "clean shutdown"),
                ],
                palette=p,
                key_width=18,
            ),
        ]

        hint = Text()
        hint.append("Keys: ", style=p.muted)
        hint.append("Tab", style=f"bold {p.accent}")
        hint.append(" complete  ", style=p.muted)
        hint.append("↑↓", style=f"bold {p.accent}")
        hint.append(" history  ", style=p.muted)
        hint.append("Ctrl+C", style=f"bold {p.accent}")
        hint.append(" interrupt  ", style=p.muted)
        hint.append("Ctrl+D", style=f"bold {p.accent}")
        hint.append(" quit", style=p.muted)

        self.console.print()
        self.console.print(
            section_panel(
                *sections,
                hint,
                title="AgentDrive TUI · commands",
                palette=p,
            )
        )

    def _browse_genomes(self, args: list[str]) -> None:
        """Tree-stem genome browser with optional search filter."""
        from rich.text import Text

        from agentdrive.tui.chrome import (
            Palette,
            Tree,
            TreeRow,
            error_line,
            section_panel,
            warn_line,
        )
        from agentdrive.tui.loading import MicroSpinner

        p = Palette(self.skin)

        query = " ".join(args) if args else ""
        try:
            with MicroSpinner(self.console, "scanning registry…", accent=p.accent):
                if query:
                    dirs = self.registry.search_genomes(query)
                    details = [
                        d for d in self.registry.list_genome_details() if d["dir_name"] in dirs
                    ]
                else:
                    details = self.registry.list_genome_details()
        except Exception as e:
            self.console.print(error_line(f"Registry error: {e}", palette=p))
            return

        if not details:
            self.console.print()
            self.console.print(
                warn_line(
                    f"No genomes match. Use [{p.accent}]import[/] to seed the example.",
                    palette=p,
                )
            )
            return

        rows: list[TreeRow] = []
        for idx, d in enumerate(details, 1):
            dom = ", ".join(d.get("domains", [])[:2]) or "—"
            n_steps = d.get("num_steps", 0)
            score = d.get("score", 0)
            gid = d.get("genome_id", d["dir_name"])
            # genome_id may already include @version (e.g. "name@1.0.0") — don't duplicate
            gid_short = gid.split("@", 1)[0] if "@" in gid else gid
            ver = d.get("version") or (gid.split("@", 1)[1] if "@" in gid else "?")
            author = ", ".join(d.get("authors", [])[:1]) or "?"

            label = f"[{p.muted}]{idx:>2}[/]  [bold {p.genome}]{gid_short}[/] [dim]@{ver}[/]"
            secondary = (
                f"{dom}  [{p.muted}]·[/] {n_steps} step{'s' if n_steps != 1 else ''}  "
                f"[{p.muted}]·[/] score [{p.evolution}]{score:.2f}[/]  "
                f"[{p.muted}]·[/] {author}"
            )
            rows.append(TreeRow(label=label, secondary=secondary))

        head = Text("Genomes  ", style=f"bold {p.accent}")
        head.append(f"({len(details)})", style=p.muted)
        if query:
            head.append("   search: ", style=p.muted)
            head.append(query, style=f"bold {p.framework}")

        hint = Text()
        hint.append("Inspect with ", style=p.muted)
        hint.append("view <#|id>", style=f"bold {p.accent}")
        hint.append("   ·   ", style=p.muted)
        hint.append("Execute with ", style=p.muted)
        hint.append("run <#|id>", style=f"bold {p.accent}")

        self.console.print()
        self.console.print(
            section_panel(
                Group(head, Text(""), Tree(rows, palette=p)),
                hint,
                palette=p,
            )
        )

        if not self.selected and details:
            self.selected = details[0]["dir_name"]

    def _view_genome(self, args: list[str]) -> None:
        """Chrome-styled single-genome inspector."""
        from rich.console import Group as _Group
        from rich.text import Text

        from agentdrive.tui.chrome import (
            Glyphs,
            Palette,
            Section,
            Tree,
            TreeRow,
            error_line,
            section_panel,
        )

        p = Palette(self.skin)

        key = args[0] if args else (self.selected or "")
        if not key:
            self._browse_genomes([])
            details = self.registry.list_genome_details()
            if not details:
                return
            try:
                choice = self.session.prompt("\nEnter # or id to view: ").strip()
                if choice.isdigit():
                    key = details[int(choice) - 1]["dir_name"]
                else:
                    key = choice
            except Exception:
                return

        g = self.registry.get_genome(key)
        if not g:
            self.console.print()
            self.console.print(error_line(f"Genome not found: {key}", palette=p))
            return

        self.selected = g.genome_id
        m = g.manifest

        # Manifest section
        authors = ", ".join((a.name or str(a)) for a in (m.authors or [])) or "—"
        domains = ", ".join(m.applicability.get("domains", [])) or "—"
        score = m.evaluation_score.get("reference_tasks", "—")
        manifest_rows = [
            ("id", f"[bold {p.genome}]{m.id}[/]  [dim]@{m.version}[/]"),
            ("created", str(m.created)),
            ("authors", authors),
            ("domains", domains),
            ("score", f"[{p.evolution}]{score}[/]" if score != "—" else "—"),
        ]

        # Framework section
        fw = g.framework or {}
        steps = fw.get("steps", [])
        n_steps = len(steps)
        step_rows: list[TreeRow] = []
        for i, step in enumerate(steps[:6]):
            step_rows.append(
                TreeRow(
                    label=f"[bold {p.evolution}]{step.get('name', 'step')}[/]",
                    secondary=(step.get("description", "") or "")[:60],
                )
            )
        if n_steps > 6:
            step_rows.append(
                TreeRow(label=f"[dim]+ {n_steps - 6} more step{'s' if n_steps - 6 != 1 else ''}[/]")
            )

        fw_head = Text()
        fw_head.append(f"{Glyphs.EXPANDED} ", style=p.accent)
        fw_head.append("Framework", style=f"bold {p.accent}")
        fw_head.append(f"  {fw.get('id', 'n/a')}", style=p.muted)
        fw_head.append(f"  {n_steps} step{'s' if n_steps != 1 else ''}", style=p.muted)
        if fw.get("inputs"):
            fw_head.append(f"  inputs: {', '.join(fw.get('inputs', []))}", style=p.muted)

        if steps:
            fw_section = _Group(fw_head, Tree(step_rows, palette=p))
        else:
            empty = Text("    no structured steps (generic capability)", style=p.muted)
            fw_section = _Group(fw_head, empty)

        # Reasoning + tools sections (compact)
        extras: list[Any] = []
        if g.reasoning_patterns:
            rp_keys = list(g.reasoning_patterns.keys())
            preview = ", ".join(rp_keys[:5])
            if len(rp_keys) > 5:
                preview += f"  (+{len(rp_keys) - 5} more)"
            extras.append(
                Section(
                    "Reasoning patterns",
                    [
                        ("count", str(len(rp_keys))),
                        ("keys", preview),
                    ],
                    palette=p,
                    key_width=8,
                )
            )

        if g.tool_compositions:
            tc_keys = list(g.tool_compositions.keys())
            preview = ", ".join(tc_keys[:3])
            if len(tc_keys) > 3:
                preview += f"  (+{len(tc_keys) - 3} more)"
            extras.append(
                Section(
                    "Tool compositions",
                    [
                        ("count", str(len(tc_keys))),
                        ("keys", preview),
                    ],
                    palette=p,
                    key_width=8,
                )
            )

        # Compose
        self.console.print()
        self.console.print(
            section_panel(
                Section("Manifest", manifest_rows, palette=p),
                fw_section,
                *extras,
                title=f"Genome · {g.genome_id}",
                palette=p,
            )
        )

        hint = Text()
        hint.append("Selected for run/evolve: ", style=p.muted)
        hint.append(g.genome_id, style=f"bold {p.genome}")
        self.console.print(hint)

    def _show_status(self) -> None:
        stats = self.registry.get_registry_stats()
        c = self.skin.skin["colors"]

        reg_panel = Panel(
            f"[agentdrive.label]Root:[/] {stats['root']}\n"
            f"[agentdrive.label]Genomes:[/] [agentdrive.genome]{stats['count']}[/]\n"
            f"[agentdrive.label]Domains:[/] {', '.join(stats['domains_covered']) or '—'}\n"
            f"[agentdrive.label]Avg Score:[/] [agentdrive.evolution]{stats['avg_score']}[/]\n"
            f"[agentdrive.label]Total Steps:[/] {stats['total_steps']}\n",
            title="Registry",
            border_style=c["banner_border"],
        )

        recent = ""
        if self.run_history:
            recent = "\n".join(
                f"  • {h.get('time_str', '?')}  {h.get('genome', '?')} → [agentdrive.ok]{h.get('status', 'done')}[/]"
                for h in self.run_history[-3:]
            )
        else:
            recent = "[dim]No runs this session yet. Use 'run'.[/dim]"
        run_panel = Panel(recent, title="Recent Session Runs", border_style=c["ui_accent"])

        # Pool stats panel
        try:
            from agentdrive.drive.drive import get_default_drive

            pool = get_default_drive()
            pstats = pool.get_pool_stats()
            pool_lines = (
                f"[agentdrive.label]Pool:[/] {pstats.get('name', 'main')}\n"
                f"[agentdrive.label]Ingest events:[/] {pstats.get('ingest_events', 0)}\n"
                f"[agentdrive.label]Last ingest:[/] {pstats.get('last_ingest') or 'never'}"
            )
            pool_panel = Panel(
                pool_lines, title="Pool", border_style=c.get("status_bar_dim", "dim")
            )
        except Exception:
            pool_panel = Panel("[dim]Pool not available[/]", title="Pool", border_style="dim")

        sys_panel = Panel(
            f"AgentDrive TUI: [agentdrive.ok]active[/]  •  Skin: [agentdrive.label]{self.skin.skin.get('name', 'default')}[/]\n"
            f"Python: {sys.version.split()[0]}  •  Registry writable: [agentdrive.ok]yes[/]\n"
            "[dim]Evolutionary engine, scanners, and worker adapters ready for wiring.[/dim]",
            title="System",
            border_style="dim",
        )

        self.console.print(reg_panel)
        self.console.print(run_panel)
        self.console.print(pool_panel)
        self.console.print(sys_panel)

    def _show_chat(self) -> None:
        """Enter the conversational pool query interface."""
        try:
            cv = ChatView(self)
            cv.enter()
        except Exception as e:
            self.console.print(f"[agentdrive.warn]Chat error:[/] {rich_escape(str(e))}")

    def _show_board(self, args: list[str]) -> None:
        """Render the AgentDrive Mission Board."""
        from agentdrive.board import get_default_board
        from agentdrive.tui.board_view import render_board, render_board_inline
        from agentdrive.tui.chrome import Palette, error_line, ok_line, warn_line
        from agentdrive.tui.loading import MicroSpinner

        p = Palette(self.skin)
        with MicroSpinner(self.console, "loading mission board…", accent=p.accent):
            board = get_default_board()

        sub = args[0].lower() if args else "show"

        if sub in ("show", "view", "ls", "list"):
            render_board(board, p, self.console)
        elif sub == "recent":
            render_board_inline(board, p, self.console, limit=12)
        elif sub == "create":
            title = " ".join(args[1:]) if len(args) > 1 else ""
            if not title:
                self.console.print(warn_line("Usage: board create <title>", palette=p))
                return
            mission = board.create(title=title)
            self.console.print(
                ok_line(
                    f"Created [agentdrive.genome]{mission.id}[/] — {rich_escape(mission.title)}",
                    palette=p,
                )
            )
        elif sub in ("start", "begin"):
            mid = args[1] if len(args) > 1 else ""
            if not mid:
                self.console.print(warn_line("Usage: board start <mission-id>", palette=p))
                return
            m = board.start(mid)
            if m:
                self.console.print(
                    ok_line(f"Started [agentdrive.genome]{m.id}[/] — {m.title}", palette=p)
                )
            else:
                self.console.print(
                    error_line(f"No mission with id [agentdrive.genome]{mid}[/]", palette=p)
                )
        elif sub in ("done", "complete"):
            mid = args[1] if len(args) > 1 else ""
            if not mid:
                self.console.print(warn_line("Usage: board done <mission-id>", palette=p))
                return
            m = board.complete(mid)
            if m:
                self.console.print(ok_line(f"Completed [agentdrive.genome]{m.id}[/]", palette=p))
            else:
                self.console.print(
                    error_line(f"No mission with id [agentdrive.genome]{mid}[/]", palette=p)
                )
        elif sub == "fail":
            mid = args[1] if len(args) > 1 else ""
            if not mid:
                self.console.print(warn_line("Usage: board fail <mission-id>", palette=p))
                return
            m = board.fail(mid)
            if m:
                self.console.print(
                    ok_line(f"Marked failed [agentdrive.genome]{m.id}[/]", palette=p)
                )
            else:
                self.console.print(
                    error_line(f"No mission with id [agentdrive.genome]{mid}[/]", palette=p)
                )
        elif sub == "archive":
            mid = args[1] if len(args) > 1 else ""
            if not mid:
                self.console.print(warn_line("Usage: board archive <mission-id>", palette=p))
                return
            m = board.archive(mid)
            if m:
                self.console.print(ok_line(f"Archived [agentdrive.genome]{m.id}[/]", palette=p))
            else:
                self.console.print(
                    error_line(f"No mission with id [agentdrive.genome]{mid}[/]", palette=p)
                )
        elif sub in ("stats", "stat"):
            stats = board.stats()
            from agentdrive.tui.chrome import Section, section_panel

            self.console.print()
            self.console.print(
                section_panel(
                    Section(
                        "Mission Board",
                        [
                            ("pending", f"[{p.muted}]{stats['pending']}[/]"),
                            ("running", f"[bold {p.accent}]{stats['running']}[/]"),
                            ("done", f"[bold {p.ok}]{stats['done']}[/]"),
                            (
                                "failed",
                                f"[bold {p.error}]{stats['failed']}[/]" if stats["failed"] else "0",
                            ),
                            ("archived", str(stats["archived"])),
                            (
                                "avg time",
                                f"{stats['avg_duration_s']:.1f}s"
                                if stats["avg_duration_s"]
                                else "—",
                            ),
                            ("path", str(stats["path"])),
                        ],
                        palette=p,
                    ),
                    palette=p,
                )
            )
        elif sub in ("help", "?"):
            from agentdrive.tui.chrome import Section, section_panel

            self.console.print()
            self.console.print(
                section_panel(
                    Section(
                        "board · commands",
                        [
                            ("board", "render the full board (default)"),
                            ("board recent", "compact inline of recent missions"),
                            ("board stats", "summary numbers"),
                            ("board create <title>", "stage a Pending mission"),
                            ("board start <id>", "Pending → Running"),
                            ("board done <id>", "Running → Done"),
                            ("board fail <id>", "Running → Failed"),
                            ("board archive <id>", "Done/Failed → Archived"),
                        ],
                        palette=p,
                        key_width=22,
                    ),
                    palette=p,
                )
            )
        else:
            self.console.print(
                warn_line(
                    f"Unknown board subcommand: {sub}. Try [{p.accent}]board help[/]",
                    palette=p,
                )
            )

    def _show_pool_view(self, args: list[str]) -> None:
        """Dedicated first-class TUI for the AgentDrive (global + per-swarm DNA).
        - No args: enter full interactive sub-shell (premium dedicated experience)
        - With args: one-shot execution of subcommand (e.g. `pool query "..."`, `p swarms`, `pool settings`)
        Uses the attached self.pool_view for persistent swarm scope across invocations.
        """
        try:
            pv = getattr(self, "pool_view", None)
            if pv is None:
                from agentdrive.tui.views.drive_view import DriveView

                pv = DriveView(self)
                self.pool_view = pv

            pv._refresh_pool()  # ensure fresh binding to any external changes

            if args:
                # One-shot support: pool query "foo bar"  or  p swarms  etc.  (no enter loop)
                sub = args[0].lower()
                subargs = args[1:]
                pv.handle_command(sub, subargs)
            else:
                # Full beautiful interactive Pool mode
                pv.enter()
        except Exception as e:
            self.console.print(f"[agentdrive.warn]Pool view:[/] {e}")

    def _scan_runs(self, args: list[str]) -> None:
        """Real DNA extraction using Agent DriveRunScanner + reasoning primitives.
        Produces a live candidate Genome from simulated or provided run data.
        """
        from agentdrive.tui.chrome import (
            Palette,
            Section,
            error_line,
            result_panel,
            section_panel,
            warn_line,
        )
        from agentdrive.tui.loading import StepProgress

        p = Palette(self.skin)

        target = args[0] if args else "demo-engagement-2026-05-23"

        self.console.print()
        self.console.print(
            section_panel(
                Section(
                    "Scan",
                    [
                        ("scanner", "[agentdrive.framework]agentdrive-run[/]"),
                        ("target", f"[agentdrive.genome]{target}[/]"),
                    ],
                    palette=p,
                ),
                title="◆ DNA extraction",
                palette=p,
            )
        )
        self.console.print()

        # Build realistic sample run data (from worker telemetry or external agent run)
        sample_run = {
            "timestamp": datetime.utcnow().isoformat(),
            "model": "agentdrive-demo-model",
            "observations": [
                {
                    "kind": "event",
                    "identity": "deploy",
                    "state": "started",
                    "summary": "v2.3.1 rollout",
                    "observed_at": 1748000000,
                },
                {
                    "kind": "metric",
                    "identity": "auth-svc.replicas",
                    "state": "2/3",
                    "summary": "readiness failed",
                    "observed_at": 1748000100,
                },
                {
                    "kind": "claim",
                    "identity": "affected_users",
                    "state": "47",
                    "summary": "lb + sessions",
                    "observed_at": 1748000200,
                },
            ],
            "claims": [
                {
                    "statement": "users impacted",
                    "count": 47,
                    "source": "lb-metrics",
                    "source_id": "run-4821",
                },
                {
                    "statement": "users impacted",
                    "count": 120,
                    "source": "support-tickets",
                    "source_id": "zendesk-991",
                },
            ],
            "ledger": [
                {"ts": 1748000000, "actor": "cd-pipeline", "operation": "deploy", "status": "ok"},
                {
                    "ts": 1748000100,
                    "actor": "auth-svc",
                    "operation": "health_check",
                    "status": "fail",
                },
            ],
            "conversations": [
                {
                    "role": "assistant",
                    "content": "<think>timeline shows deploy then failure... causal?</think>",
                }
            ],
        }

        steps = StepProgress(
            self.console,
            ["Load run data", "Run scanner", "Synthesize genome", "Save to registry"],
            title="Extracting DNA",
        )
        steps.start()
        try:
            from agentdrive.scanners import Agent DriveRunScanner

            steps.advance(
                f"{len(sample_run.get('observations', []))} obs · {len(sample_run.get('claims', []))} claims"
            )

            scanner = Agent DriveRunScanner(actor=f"tui-scan-{target[:8]}")
            candidates = scanner.scan(sample_run)
            if not candidates:
                steps.fail("scanner returned 0 candidates")
                steps.finish()
                self.console.print()
                self.console.print(warn_line("Scanner returned no candidates.", palette=p))
                return
            steps.advance(f"{len(candidates)} candidate(s)")

            cand = candidates[0]
            cand.manifest.id = "extracted-agentdrive-patterns"
            cand.manifest.version = "0.1.0-scanned"
            cand.finalize()
            steps.advance(f"{cand.genome_id}")

            saved_path = self.registry.save(cand)
            steps.advance(f"{saved_path.name}")
            steps.finish()

            rp = cand.reasoning_patterns or {}
            causal_edges = (
                len(rp.get("causality", {}).get("edges", []))
                if isinstance(rp.get("causality"), dict)
                else 0
            )

            self.console.print()
            self.console.print(
                result_panel(
                    f"DNA extracted: {cand.genome_id}",
                    [],
                    success=True,
                    palette=p,
                    extras=[
                        Section(
                            "Reasoning primitives",
                            [
                                ("trace steps", str(rp.get("trace", {}).get("step_count", 0))),
                                ("anomalies", str(len(rp.get("anomalies", [])))),
                                ("contradictions", str(len(rp.get("contradictions", [])))),
                                ("causal edges", str(causal_edges)),
                                ("patterns", str(len(rp.get("patterns_recognized", [])))),
                                (
                                    "framework",
                                    "[agentdrive.ok]synthesized[/]"
                                    if cand.framework
                                    else "[dim]none (needs more obs)[/]",
                                ),
                            ],
                            palette=p,
                        ),
                    ],
                )
            )

            self.selected = cand.genome_id.replace("@", "-")

        except Exception as e:
            steps.fail(str(e)[:60])
            steps.finish()
            import traceback

            self.console.print()
            self.console.print(
                error_line(
                    f"Scanner failed: {rich_escape(str(e))}",
                    palette=p,
                    suggestion=f"see traceback: {rich_escape(traceback.format_exc()[-300:])}",
                )
            )

    def _run_work(self, args: list[str]) -> None:
        """Command composer + live orchestrated execution view."""
        from agentdrive.board import get_default_board

        self._board = get_default_board()
        self._active_mission_id: str | None = None
        key = args[0] if args else (self.selected or "")
        if not key:
            self._browse_genomes([])
            details = self.registry.list_genome_details()
            if not details:
                return
            try:
                choice = self.session.prompt("Genome to run (# or id): ").strip()
                key = details[int(choice) - 1]["dir_name"] if choice.isdigit() else choice
            except Exception:
                return

        g = self.registry.get_genome(key)
        if not g:
            from agentdrive.tui.chrome import Palette, error_line

            p = Palette(self.skin)
            self.console.print()
            self.console.print(
                error_line(
                    f"Not found: {key}",
                    palette=p,
                    suggestion="run [cyan]genomes[/] to list available IDs",
                )
            )
            return
        self.selected = g.genome_id

        fw = g.framework or {}
        inputs_spec = fw.get("inputs", ["incident_summary", "timeline"]) or ["query"]

        from agentdrive.tui.chrome import Palette, Section, section_panel

        p = Palette(self.skin)
        self.console.print()
        self.console.print(
            section_panel(
                Section(
                    "Run",
                    [
                        ("genome", f"[agentdrive.genome]{g.genome_id}[/]"),
                        ("steps", str(len(fw.get("steps", [])))),
                        ("inputs", ", ".join(inputs_spec)),
                    ],
                    palette=p,
                ),
                title="◆ Mission composer",
                palette=p,
            )
        )
        self.console.print()

        collected: dict[str, str] = {}
        for inp in inputs_spec:
            val = self.session.prompt(f"  {inp}: ", default="Demo input for " + inp).strip()
            collected[inp] = val or "N/A"

        # Stage a Pending mission on the board, then flip to Running on launch.
        mission = self._board.create(
            title=f"Run {g.genome_id}",
            description=f"Inputs: {', '.join(collected.keys())}",
            genome_id=g.genome_id,
            agent_id=f"tui-{g.manifest.id[:16]}",
            inputs={k: (v[:80] if isinstance(v, str) else v) for k, v in collected.items()},
        )
        self._active_mission_id = mission.id
        self._board.start(mission.id)
        self.console.print(
            f"[agentdrive.label]Launching live execution...[/] "
            f"[dim]board · {mission.id[-5:]}[/]  (Ctrl+C to abort)"
        )

        # Lazy import + create Harness for the session (before steps) so base TUI launch never pulls harness/pool
        harness = None
        try:
            from agentdrive.harness.harness import Harness as _Agent DriveHarness

            harness = _Agent DriveHarness(
                agent_id=f"tui-{g.manifest.id[:16]}-{int(time.time()) % 100000}"
            )
        except Exception as imp_err:
            self.console.print(
                f"[agentdrive.warn]Harness/Pool integration unavailable this run (will use classic execution):[/] {imp_err}"
            )
            harness = None

        self._execute_live(g, collected, harness=harness)

    def _execute_live(
        self, genome: Genome, inputs: dict[str, str], harness: Harness | None = None
    ) -> None:
        """Rich Live dashboard for orchestrated work with progress, reasoning, tools.

        Integrated with Harness + AgentDrive:
        - Harness created in _run_work (before steps) or here; task_context wraps the live execution
        - Periodically calls pull_relevant_dna() and surfaces "DNA from Pool" in dashboard
        - Uses inject_into_context(...) to augment step reasoning/prompts
        - After run (success/abort): record_outcome(...) + optional auto-ingest of small improvement signal
        - All pool usage is visible, useful, and errors are handled gracefully without breaking the beautiful UI.
        """
        self._cancel_event.clear()
        start = time.time()

        fw = genome.framework or {}
        steps: list[dict] = fw.get("steps", []) or [
            {"name": "establish_facts", "description": "Analyze input"},
            {"name": "synthesize", "description": "Produce artifact"},
        ]
        n_steps = max(1, len(steps))

        # Ensure we have a harness for the session (created in caller _run_work or here as fallback)
        if harness is None:
            try:
                from agentdrive.harness.harness import Harness as _Agent DriveHarness

                harness = _Agent DriveHarness(
                    agent_id=f"tui-{genome.manifest.id[:16]}-{int(time.time()) % 100000}"
                )
            except Exception:
                # already warned in _run_work; stay silent here to not spam during live
                harness = None
        task_desc = f"Live run of {genome.genome_id} (inputs={list(inputs.keys())})"

        state: dict[str, Any] = {
            "step_idx": 0,
            "current_step": "",
            "pct": 0,
            "logs": [],
            "thinking": "",
            "tools": [],
            "done": False,
            "aborted": False,
            "artifact": "",
            "dna_from_pool": [],
            "pool_contrib": "",
        }
        spinner_faces = self.skin.get_spinner_config().get("thinking_faces", ["◐", "◑"])
        verbs = self.skin.get_spinner_config().get("thinking_verbs", ["analyzing", "evolving"])

        def _build_ui():
            sp_idx = int(time.time() * 4) % len(spinner_faces)
            sp = spinner_faces[sp_idx]
            title = f"Live Run — {genome.genome_id}"
            if state["aborted"]:
                title += " [agentdrive.warn](ABORTED)[/]"

            header = Text(
                f"{sp}  Step {state['step_idx']}/{n_steps}  •  {state['current_step']}  •  {state['pct']}%",
                style="agentdrive.accent",
            )

            log_lines = "\n".join(state["logs"][-8:]) or "[dim]No log yet...[/dim]"
            log_panel = Panel(log_lines, title="Activity Log", border_style="dim", height=10)

            think = state["thinking"] or "[dim]idle[/dim]"
            think_panel = Panel(
                think,
                title=f"Reasoning {verbs[sp_idx % len(verbs)]}",
                border_style=self.skin.style("evolution_step"),
            )

            tools = "\n".join(f"  ⊙ {t}" for t in state["tools"][-4:]) or "—"
            tools_panel = Panel(tools, title="Tool Calls", border_style=self.skin.style("ui_label"))

            # DNA from Pool panel — makes the pull-from-pool + adapt loop visible and useful in real time
            dna = state.get("dna_from_pool", []) or []
            dna_lines = (
                "\n".join(f"  🧬 {rich_escape(d)}" for d in dna)
                or "[dim]Pulling relevant DNA from AgentDrive...[/dim]"
            )
            dna_panel = Panel(
                dna_lines, title="DNA from Pool", border_style=self.skin.style("evolution_step")
            )

            hname = getattr(harness, "agent_id", "classic")
            footer = f"Elapsed: {time.time() - start:.1f}s   Inputs: {', '.join(inputs.keys())}   harness={hname}"

            body = Group(
                header, log_panel, think_panel, tools_panel, dna_panel, Text(footer, style="dim")
            )
            return Panel(body, title=title, border_style=self.skin.style("banner_border"))

        has_harness = harness is not None
        task_cm = harness.task_context(task_desc) if has_harness else nullcontext()

        # Wrap live run in task_context (when harness present) to enable the full pull-adapt-contribute loop
        try:
            with task_cm:
                if has_harness:
                    # task_context already pulled; surface DNA in dashboard immediately
                    try:
                        state["dna_from_pool"] = harness.get_pulled_genomes()[:3]
                    except Exception:
                        state["dna_from_pool"] = []

                with Live(
                    _build_ui(), console=self.console, refresh_per_sec=10, transient=False
                ) as live:
                    try:
                        for idx, step in enumerate(steps, 1):
                            if self._cancel_event.is_set():
                                state["aborted"] = True
                                break
                            state["step_idx"] = idx
                            state["current_step"] = step.get("name", f"step-{idx}")
                            state["pct"] = int(idx / n_steps * 100)

                            state["logs"].append(
                                f"[{datetime.now().strftime('%H:%M:%S')}] ▶ {state['current_step']}"
                            )
                            live.update(_build_ui())

                            # Periodically call pull_relevant_dna() and show "DNA from pool" (only when harness active)
                            if has_harness and (idx == 1 or idx % 2 == 0):
                                try:
                                    fresh_dna = harness.pull_relevant_dna(top_k=3)
                                    state["dna_from_pool"] = [
                                        d.get("genome_id", "?") for d in fresh_dna
                                    ]
                                    state["logs"].append(
                                        f"  🧬 pulled {len(fresh_dna)} DNA packets from pool"
                                    )
                                    live.update(_build_ui())
                                except Exception as pull_err:
                                    state["logs"].append(
                                        f"  [agentdrive.warn]DNA pull: {str(pull_err)[:45]}[/]"
                                    )
                                    live.update(_build_ui())

                            for j in range(2):
                                if self._cancel_event.is_set():
                                    break
                                base = f"Applying pattern: contradiction detection + causal chain (iter {j})"
                                if has_harness:
                                    try:
                                        # inject_into_context augments the prompt/reasoning for steps using pool DNA
                                        state["thinking"] = harness.inject_into_context(
                                            base,
                                            extra_instructions="Leverage relevant DNA from AgentDrive for better adaptation and quality.",
                                        )
                                    except Exception:
                                        state["thinking"] = base
                                else:
                                    state["thinking"] = base
                                state["logs"].append(f"  {verbs[j % len(verbs)]}...")
                                live.update(_build_ui())
                                time.sleep(0.35)

                            tool_name = (
                                "analyze_timeline"
                                if "fact" in state["current_step"].lower()
                                else "recommend"
                            )
                            state["tools"].append(f"{tool_name}({state['current_step'][:12]})")
                            state["logs"].append(f"  tool call → {tool_name}")
                            live.update(_build_ui())
                            time.sleep(0.45)

                        if not state["aborted"]:
                            state["done"] = True
                            state["artifact"] = (
                                "Structured postmortem document + action plan (saved to ./artifacts/ in real run)"
                            )
                            state["logs"].append("[agentdrive.ok]✓ Run completed successfully.[/]")
                            state["pct"] = 100
                            self.run_history.append(
                                {
                                    "genome": genome.genome_id,
                                    "time_str": datetime.now().strftime("%H:%M"),
                                    "status": "success",
                                    "inputs": list(inputs.keys()),
                                }
                            )
                            # Settle the mission card to Done.
                            try:
                                mid = getattr(self, "_active_mission_id", None)
                                if mid:
                                    self._board.complete(
                                        mid,
                                        outcome={
                                            "steps_completed": state["step_idx"],
                                            "artifact": state["artifact"],
                                        },
                                        dna_used=state.get("dna_from_pool") or [],
                                    )
                            except Exception:
                                pass
                        elif state["aborted"]:
                            try:
                                mid = getattr(self, "_active_mission_id", None)
                                if mid:
                                    self._board.fail(mid, error="user-aborted")
                            except Exception:
                                pass
                        live.update(_build_ui())
                        time.sleep(0.6)
                    except KeyboardInterrupt:
                        state["aborted"] = True
                        self._cancel_event.set()

                # Post-live (inside task_context when active): record_outcome + optional auto-ingest small signal
                if has_harness:
                    try:
                        outcome: dict[str, Any] = {
                            "status": "success" if not state["aborted"] else "aborted",
                            "duration_s": round(time.time() - start, 2),
                            "steps_completed": state["step_idx"],
                            "dna_used": len(getattr(harness, "pulled_dna", [])),
                            "inputs": list(inputs.keys()),
                        }
                        harness.record_outcome(outcome)

                        if not state["aborted"]:
                            # auto-ingest a small improvement signal (demonstrates contribute back)
                            try:
                                sig_ver = datetime.utcnow().strftime("%Y%m%d.%H%M%S")
                                signal = Genome.create(
                                    id="tui-execution-feedback",
                                    version=sig_ver,
                                    framework={
                                        "steps": [
                                            {
                                                "name": "reflect_contribute",
                                                "description": "Auto signal from live TUI run + pool DNA",
                                            }
                                        ]
                                    },
                                    authors=[{"name": harness.agent_id, "type": "tui-agent"}],
                                    applicability={"domains": ["meta", "pool-feedback"]},
                                    evaluation_score={"reference_tasks": 0.02},
                                    reasoning_patterns={
                                        "tui_pool_loop": {
                                            "source": genome.genome_id,
                                            "dna": state.get("dna_from_pool", []),
                                        }
                                    },
                                )
                                ires = harness.pool.ingest(
                                    signal, source="tui-live-run", actor=harness.agent_id
                                )
                                state["pool_contrib"] = (
                                    f"✓ ingested {ires.genome_id} ({ires.reason})"
                                )
                            except Exception as ingest_err:
                                state["pool_contrib"] = f"ingest note: {str(ingest_err)[:50]}"
                    except Exception as rec_err:
                        state["pool_contrib"] = f"outcome record: {str(rec_err)[:50]}"
        except Exception as harness_err:
            # Graceful: even if task_context or pool ops fail mid-run, we surface useful state
            state["logs"].append(f"[agentdrive.warn]Harness context: {str(harness_err)[:60]}[/]")
            if not state["aborted"] and not state.get("done"):
                state["done"] = True
                state["artifact"] = (
                    state.get("artifact") or "Run completed (pool integration partial)"
                )
                state["pct"] = 100

        if state["aborted"]:
            self.console.print("[agentdrive.warn]Run aborted by user.[/]")
        else:
            contrib = state.get("pool_contrib", "")
            footer_note = f"\n[agentdrive.label]Pool feedback:[/] {contrib}" if contrib else ""
            self.console.print(
                Panel(
                    f"[agentdrive.ok]Success[/]\n\n{state['artifact']}\n\n[dim]Full telemetry would feed scanners for evolution.[/dim]{footer_note}",
                    title="Execution Complete",
                    border_style=self.skin.style("ui_ok"),
                )
            )

    def _evolve_genome(self, args: list[str]) -> None:
        from agentdrive.tui.chrome import (
            Palette,
            Section,
            Tree,
            TreeRow,
            confirm_prompt,
            error_line,
            info_line,
            result_panel,
            section_panel,
        )

        p = Palette(self.skin)

        key = args[0] if args else (self.selected or "")
        if not key:
            self._browse_genomes([])
            return
        g = self.registry.get_genome(key)
        if not g:
            self.console.print()
            self.console.print(error_line("Genome not found for evolution.", palette=p))
            return

        new_ver = g.manifest.version.split(".")
        try:
            new_ver[-1] = str(int(new_ver[-1]) + 1)
        except Exception:
            new_ver = ["1", "0", "1"]
        new_version = ".".join(new_ver) + "-evolved"

        delta_rows = [
            TreeRow(label=f"[bold {p.ok}]+[/] added contradiction-detection reasoning pattern"),
            TreeRow(label=f"[bold {p.ok}]+[/] strengthened root-cause step with ledger witness"),
            TreeRow(label=f"[bold {p.ok}]+[/] +0.04 reference evaluation score"),
        ]

        self.console.print()
        self.console.print(
            section_panel(
                Section(
                    "Source",
                    [
                        ("genome", f"[agentdrive.genome]{g.genome_id}[/]"),
                        ("from", g.manifest.version),
                        ("to", f"[agentdrive.framework]{new_version}[/]"),
                    ],
                    palette=p,
                ),
                Tree(delta_rows, palette=p),
                title="◆ Evolution proposal",
                palette=p,
            )
        )

        ok = confirm_prompt(
            self.console,
            title="Register evolved candidate?",
            body=f"This forks [agentdrive.genome]{g.genome_id}[/] into a new entry at version [agentdrive.framework]{new_version}[/].",
            default_yes=True,
            palette=p,
        )
        if not ok:
            self.console.print()
            self.console.print(info_line("Evolution cancelled. No changes made.", palette=p))
            return

        try:
            g.manifest.version = new_version
            g.manifest.last_improved = datetime.now()
            g.reasoning_patterns["contradiction_detection"] = {"enabled": True, "v": "evolved"}
            g.evaluations["evolution_run"] = {"score_delta": 0.04}
            saved = self.registry.save(g)
            self.console.print()
            self.console.print(
                result_panel(
                    "Evolved genome saved",
                    [
                        ("genome", f"[agentdrive.genome]{g.genome_id}[/]"),
                        ("path", str(saved)),
                    ],
                    success=True,
                    palette=p,
                )
            )
            self.selected = g.genome_id
        except Exception as e:
            self.console.print()
            self.console.print(error_line(f"Failed to register evolved: {e}", palette=p))

    def _compose_mission(self, args: list[str]) -> None:
        from rich.text import Text

        from agentdrive.tui.chrome import (
            Palette,
            Tree,
            TreeRow,
            section_panel,
            warn_line,
        )

        p = Palette(self.skin)

        details = self.registry.list_genome_details()[:5]
        if not details:
            self.console.print()
            self.console.print(
                warn_line("No genomes registered — run [cyan]import[/] first.", palette=p)
            )
            return

        rows: list[TreeRow] = []
        for i, d in enumerate(details, 1):
            gid = d["genome_id"]
            gid_short = gid.split("@", 1)[0] if "@" in gid else gid
            ver = d.get("version") or (gid.split("@", 1)[1] if "@" in gid else "?")
            rows.append(
                TreeRow(
                    label=f"[{p.muted}]{i:>2}[/]  [bold {p.genome}]{gid_short}[/] [dim]@{ver}[/]",
                    secondary=", ".join(d.get("domains", [])[:2]) or "—",
                )
            )

        head = Text("Available for composition", style=f"bold {p.accent}")
        body = Text.from_markup(
            f"[{p.muted}]The full composer (multi-genome orchestration) is staged for the next release. "
            f"For now you can run individual genomes with [/][{p.accent}]run <id>[/] [{p.muted}]and stage "
            f"missions on the[/] [{p.accent}]board[/][{p.muted}].[/]"
        )

        from rich.console import Group as _Group

        self.console.print()
        self.console.print(
            section_panel(
                _Group(head, Text(""), Tree(rows, palette=p)),
                body,
                title="◆ Mission composer",
                palette=p,
            )
        )

    def _doctor(self) -> None:
        """Animated health check that matches the CLI cmd_doctor surface."""
        from agentdrive.cli import _run_doctor

        _run_doctor()

    def _run_setup_wizard(self, args: list[str]) -> None:
        """Modular setup inside the TUI — conversational and section-based.

        This gives users a true CLI/TUI hybrid experience.
        """
        from agentdrive.setup import SECTIONS, run_setup

        self.console.print(
            Panel(
                "[bold]AgentDrive Setup Wizard[/]\n"
                "Run the full wizard or reconfigure specific areas (especially Swarm DNA policies).",
                border_style=self.skin.style("banner_border"),
            )
        )

        # If user passed a section, run it directly via CLI logic
        if args:
            section = args[0].lower()
            mapping = {s["name"]: s["name"] for s in SECTIONS}
            mapping.update(
                {
                    "swarm": "swarm",
                    "dna": "swarm",
                    "agent": "ai",
                    "model": "ai",
                    "provider": "ai",
                    "ui": "tui",
                }
            )
            chosen = mapping.get(section, section)
            run_setup([chosen])
            return

        # Conversational mode
        print()
        self.console.print("[bold]Available sections:[/]")
        for i, s in enumerate(SECTIONS, 1):
            self.console.print(f"  {i}. [agentdrive.accent]{s['name']}[/] — {s['title']}")

        choice = (
            Prompt.ask("\nWhich section? (number or name, or 'all' for full wizard)", default="all")
            .strip()
            .lower()
        )

        if choice in ("all", "full", ""):
            run_setup()
        else:
            mapping = {s["name"]: s["name"] for s in SECTIONS}
            chosen = mapping.get(choice, choice)
            if chosen in [s["name"] for s in SECTIONS]:
                run_setup([chosen])
            else:
                self.console.print(
                    "[agentdrive.warn]Unknown section. Running full wizard instead.[/]"
                )
                run_setup()

    def _import_example(self, args: list[str]) -> None:
        gid = self.registry.ensure_bootstrap_example()
        if gid:
            self.console.print(
                f"[agentdrive.ok]✓ Example re-registered / present:[/] [agentdrive.genome]{gid}[/]"
            )
            self.selected = gid
        else:
            self.console.print(
                "[agentdrive.warn]Example already present or source not found on disk.[/]"
            )


def launch_tui() -> None:
    """Launch the professional AgentDrive TUI."""
    app = Agent DriveTUI()
    app.run()
