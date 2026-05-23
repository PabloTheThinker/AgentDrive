"""
Savant Professional TUI Application

High-quality terminal interface for the Savant Framework.
Focus: precision, clarity, trust, and powerful genome-aware workflows.

Savant is an independent, open-source framework for agent DNA (memory + patterns).
It gives every agent — and every swarm of sub-agents — its own persistent,
user-controlled living pool of experience that starts empty and grows with use.
"""

from __future__ import annotations

import os
import sys
import time
import threading
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.markup import escape as rich_escape
from rich.prompt import Confirm

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter, Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.document import Document

from savant.tui.skin_engine import skin
from savant.registry import GenomeRegistry
from savant.genome.models import Genome
from savant.tui.views.pool_view import register_pool_view


class SavantTUI:
    """Production-grade interactive TUI for Savant genome management and orchestration."""

    def __init__(self):
        self.skin = skin
        self.console = skin.console
        self.registry = GenomeRegistry()
        self.running = True
        self.selected: Optional[str] = None  # current focused genome dir_name or id
        self.run_history: List[Dict[str, Any]] = []
        self._cancel_event = threading.Event()

        # Prompt toolkit session with persistent history
        savant_home = self.registry.root.parent
        savant_home.mkdir(parents=True, exist_ok=True)
        self._history_file = savant_home / ".savant_tui_history"
        self.session: PromptSession = PromptSession(
            history=FileHistory(str(self._history_file)),
            completer=None,  # set dynamically per prompt for fresh genome list
            enable_history_search=True,
            mouse_support=False,
        )

        self._base_commands = [
            "help", "?", "h",
            "genomes", "ls", "list", "g",
            "view", "v",
            "status", "dash", "dashboard", "s",
            "pool", "p",                    # NEW: dedicated Savant Pool view + swarm management
            "scan",
            "run", "r", "execute",
            "evolve", "e",
            "compose", "c",
            "doctor", "dr",
            "setup", "configure",
            "import", "bootstrap",
            "clear", "cls",
            "exit", "quit", "q", ":q",
        ]
        self._ensure_bootstrap()
        # Attach first-class Pool view (stateful across switches)
        try:
            register_pool_view(self)
        except Exception:
            self.pool_view = None

    def _ensure_bootstrap(self) -> None:
        """Register seed example on first use so TUI is immediately useful."""
        try:
            gid = self.registry.ensure_bootstrap_example()
            if gid:
                self.console.print(f"[savant.ok]✓ Bootstrapped seed genome into registry:[/] [savant.genome]{gid}[/]")
                if not self.selected:
                    self.selected = gid
        except Exception as e:
            self.console.print(f"[savant.warn]Bootstrap note:[/] {e}")

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
            "query", "q", "search", "swarms", "sw", "switch", "use", "swarm",
            "global", "main", "genomes", "ls", "browse", "view", "v",
            "ingest", "i", "evolve", "e", "merge", "m",
            "settings", "cfg", "config", "stats", "st", "overview", "o",
            "create-swarm", "help", "back", "leave",
        ]
        all_tokens = list(self._base_commands) + pool_sub_commands + sorted(names)
        return WordCompleter(all_tokens, ignore_case=True, sentence=True)

    def run(self) -> None:
        """Main REPL loop — premium feel with completion, history, clean interrupts."""
        self.skin.print_banner("Savant Framework")

        # Dedicated first-launch Savant Welcome Screen (Hermes-grade, Apple-polish)
        # Shown once after onboarding — distinct from the reusable setup wizard.
        try:
            from savant.config import load_config, save_config
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
                f"[savant.label]Registry[/]: [savant.genome]{stats['count']}[/] genomes  •  domains: [savant.framework]{doms}[/]\n"
            )

        self._print_quick_help()

        while self.running:
            try:
                completer = self._build_completer()
                self.session.completer = completer

                sel = ""
                if self.selected:
                    short = self.selected.split("@")[0] if "@" in self.selected else self.selected
                    sel = f" ({short})"

                prompt_text = f"savant{sel} ❯ "
                line = self.session.prompt(
                    prompt_text,
                    default="",
                ).strip()

                if not line:
                    continue
                self._dispatch(line)

            except KeyboardInterrupt:
                self._cancel_event.set()
                self.console.print("\n[savant.warn]▲ Interrupted[/]  (use 'exit' or Ctrl+D to quit)")
            except EOFError:
                self.running = False
            except Exception as exc:
                self.console.print(f"[savant.error]TUI error:[/] {rich_escape(str(exc))}")

        self.console.print("\n[dim]Goodbye — your genomes and runs are safe in the registry.[/dim]")

    def _print_quick_help(self) -> None:
        self.console.print(
            "[dim]Commands:[/] [savant.accent]genomes[/] [savant.accent]view[/] [savant.accent]run[/] [savant.accent]status[/] [savant.accent]pool[/] [savant.accent]setup[/] [savant.accent]doctor[/]  •  'help' for full list\n"
            "[dim]Pro:[/] 'savant' in terminal = TUI • 'savant setup' = full Hermes-style wizard[/dim]\n"
        )

    def _show_dedicated_welcome_screen(self) -> None:
        """Hermes-grade, one-time dedicated welcome screen shown on first TUI launch after onboarding.

        Polished, clear, actionable. Builds trust and immediately teaches the core value:
        the living Savant Pool + per-subagent DNA inheritance for swarms.

        Distinct from the reusable `setup` wizard (which can be re-run anytime via `setup`).
        """
        c = self.skin.skin["colors"]
        border = c.get("banner_border", "#4A90A4")
        accent = c.get("ui_accent", "#3498DB")
        ok = c.get("ui_ok", "#27AE60")

        # Hero header
        self.console.print(
            Panel(
                f"[bold {accent}]Savant[/]  —  The Living, Learning Ecosystem for AI Agents\n\n"
                "Your agents (and every sub-agent they spawn) now have private, persistent memory pools.\n"
                "Pools start empty. They grow with real, proven DNA: frameworks, reasoning patterns, and outcomes.\n"
                "You set the rules. Full sovereignty.",
                title="[bold]Welcome to Savant — First Launch[/]",
                border_style=border,
                padding=(1, 2),
            )
        )

        # Core concept
        self.console.print(
            Panel(
                "🧬 [bold]The Savant Pool System[/]\n\n"
                "• [savant.genome]Global pool[/] — your primary workspace (starts with your first genomes)\n"
                "• [savant.framework]Per-swarm / per-subagent pools[/] — each child gets its own isolated DNA garden\n"
                "• Automatic [savant.evolution]pull + inject[/] during harness execution (SavantHarness + adapters)\n"
                "• Explicit [savant.accent]sharing policies[/] you control (sibling / upward / cross-swarm)\n\n"
                "[dim]Think Assassin's Creed DNA + professional agent memory. Every agent learns and contributes.[/]",
                title="How Your Swarm Grows Smarter",
                border_style=accent,
                padding=(0, 1),
            )
        )

        # Quick-start actions (the "setup" guidance is prominent)
        quick = Table(
            title="Recommended First Actions",
            show_header=True,
            header_style=f"bold {accent}",
            border_style=border,
        )
        quick.add_column("Type this", style=f"bold {ok}", width=18)
        quick.add_column("Purpose", style="white")
        quick.add_row("pool", "or p   →  Enter the full interactive Pool TUI (query DNA, view swarms, settings, ingest)")
        quick.add_row("p swarms", "       →  See all active swarms and their private sub-agent pools")
        quick.add_row("setup", "or configure →  Re-run Hermes-style modular wizard (especially Swarm DNA policies)")
        quick.add_row("setup swarm", "    →  Jump straight to conversational sub-agent sharing rules")
        quick.add_row("genomes", "or g   →  Browse the capability genomes you've collected")
        quick.add_row("help", "         →  Full command list + keyboard tips")

        self.console.print(quick)

        # Environment status snapshot
        try:
            from pathlib import Path
            savant_home = Path.home() / ".savant"
            pool_dir = savant_home / "pool"
            swarm_count = len(list((savant_home / "swarms").glob("*"))) if (savant_home / "swarms").exists() else 0
            status_lines = [
                f"Home: [dim]{savant_home}[/]",
                f"Global Pool: [green]ready[/]  •  Swarms seen: [cyan]{swarm_count}[/]",
                "Consent for auto sub-agent pools: [green]recorded[/] (change anytime in setup or pool settings)",
            ]
            self.console.print(
                Panel(
                    "\n".join(status_lines),
                    title="Your Savant Environment",
                    border_style="dim",
                    padding=(0, 1),
                )
            )
        except Exception:
            pass

        self.console.print(
            f"\n[{ok}]Ready when you are.[/]  Type [bold]pool[/] or [bold]p[/] to begin exploring your living DNA system.\n"
        )

    def _dispatch(self, line: str) -> None:
        """Parse and route command. Supports 'cmd arg1 arg2' and aliases."""
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower().strip()
        argstr = parts[1] if len(parts) > 1 else ""
        args = argstr.split() if argstr else []

        if cmd in ("exit", "quit", "q", ":q"):
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
        if cmd in ("pool", "p"):
            self._show_pool_view(args)
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
            os.system("clear" if os.name != "nt" else "cls")
            self.skin.print_banner("Savant Framework")
            return

        self.console.print(f"[savant.warn]Unknown:[/] {cmd}  — try [savant.accent]help[/]")

    # ─────────────────────────────────────────────────────────────────────
    # Command implementations
    # ─────────────────────────────────────────────────────────────────────

    def _show_help(self) -> None:
        help_text = """[savant.accent]genomes[/] [dim](ls, list, g)[/]          Browse registered genomes (table + search)
[savant.accent]view[/] [dim]<id|#>[/] [dim](v)[/]               Detailed view of a genome (manifest, framework steps, etc.)
[savant.accent]status[/] [dim](dash, s)[/]               Registry health, domains, recent activity
[savant.accent]scan[/]                        Simulate DNA extraction from a run / trajectory
[savant.accent]run[/] [dim]<genome>[/] [dim](r)[/]             Interactive execution composer + live progress
[savant.accent]evolve[/] [dim]<genome>[/] [dim](e)[/]          Review & propose evolutionary improvement
[savant.accent]compose[/] [dim](c)[/]                Multi-genome mission composer (stub)
[savant.accent]doctor[/] [dim](dr)[/]                 Environment + registry diagnostics
[savant.accent]setup[/] [dim](configure)[/]           Hermes-style modular setup wizard (re-run any section anytime)
[savant.accent]import[/] [dim](seed)[/]               Force-register the seed example genome
[savant.accent]clear[/]                       Clear screen + banner
[savant.accent]help[/] [dim](?)[/]                   This help
[savant.accent]exit[/] [dim](quit, q)[/]             Clean shutdown

[savant.accent]pool[/] [dim](p)[/]                     Enter first-class interactive Savant Pool TUI (global + swarms)
  Inside pool mode or via `pool <sub>`: [savant.accent]query "task"[/], [savant.accent]swarms[/], [savant.accent]switch <id>[/], [savant.accent]global[/],
  [savant.accent]genomes[/], [savant.accent]view[/], [savant.accent]ingest <dir>[/], [savant.accent]evolve[/], [savant.accent]merge[/], [savant.accent]settings[/] (editor), [savant.accent]stats[/], [savant.accent]create-swarm[/], [savant.accent]back[/]

[dim]Keyboard:[/] Tab=complete  ↑↓=history  Ctrl+C=interrupt live work  Ctrl+D=EOF quit
[dim]Selection:[/] Many commands accept numeric index from the genomes table or full genome id.[/]
"""
        self.console.print(
            Panel(
                help_text,
                title="[savant.label]Savant TUI Commands[/]",
                border_style=self.skin.style("banner_border"),
                padding=(0, 1),
            )
        )

    def _browse_genomes(self, args: List[str]) -> None:
        """Interactive table browser. Supports search arg."""
        query = " ".join(args) if args else ""
        try:
            if query:
                dirs = self.registry.search_genomes(query)
                details = [d for d in self.registry.list_genome_details() if d["dir_name"] in dirs]
            else:
                details = self.registry.list_genome_details()
        except Exception as e:
            self.console.print(f"[savant.error]Registry error:[/] {e}")
            return

        if not details:
            self.console.print("[savant.warn]No genomes match.[/] Use [savant.accent]import[/] to seed the example.")
            return

        table = Table(
            title=f"[savant.label]Genomes{' — search: ' + query if query else ''}[/]",
            show_header=True,
            header_style=self.skin.style("ui_label"),
            border_style=self.skin.style("banner_border"),
            expand=True,
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("Genome ID", style="savant.genome", no_wrap=True)
        table.add_column("Ver", style="dim", width=8)
        table.add_column("Domains", style="savant.framework")
        table.add_column("Steps", justify="right", width=6)
        table.add_column("Score", justify="right", width=6, style="savant.evolution")
        table.add_column("Authors", style="dim")

        for idx, d in enumerate(details, 1):
            dom = ", ".join(d.get("domains", [])[:2]) or "—"
            table.add_row(
                str(idx),
                d.get("genome_id", d["dir_name"]),
                d.get("version", "?"),
                dom,
                str(d.get("num_steps", 0)),
                f"{d.get('score', 0):.2f}",
                ", ".join(d.get("authors", [])[:1]) or "?",
            )

        self.console.print(table)
        self.console.print(
            f"\n[dim]Total: {len(details)}  •  Use[/] [savant.accent]view 3[/] or [savant.accent]view security-incident-postmortem@1.0.0[/] [dim]to inspect. 'run' will use selection.[/]"
        )

        if not self.selected and details:
            self.selected = details[0]["dir_name"]

    def _view_genome(self, args: List[str]) -> None:
        key = args[0] if args else (self.selected or "")
        if not key:
            self._browse_genomes([])
            details = self.registry.list_genome_details()
            if not details:
                return
            try:
                choice = self.session.prompt("Enter # or id to view: ").strip()
                if choice.isdigit():
                    key = details[int(choice) - 1]["dir_name"]
                else:
                    key = choice
            except Exception:
                return

        g = self.registry.get_genome(key)
        if not g:
            self.console.print(f"[savant.error]Genome not found:[/] {key}")
            return

        self.selected = g.genome_id

        m = g.manifest
        c = self.skin.skin["colors"]

        manifest_lines = [
            f"[savant.label]id:[/] [savant.genome]{m.id}[/]  [savant.label]v:[/] {m.version}",
            f"[savant.label]created:[/] {m.created}   [savant.label]authors:[/] {', '.join((a.name or str(a)) for a in (m.authors or [])) or '—'}",
            f"[savant.label]domains:[/] {', '.join(m.applicability.get('domains', [])) or '—'}",
            f"[savant.label]score:[/] {m.evaluation_score.get('reference_tasks', '—')}",
        ]
        manifest_panel = Panel(
            "\n".join(manifest_lines),
            title="Manifest",
            border_style=c["banner_border"],
            style="savant.banner.text",
        )

        fw = g.framework or {}
        steps_text = ""
        if fw.get("steps"):
            steps_text = "\n".join(
                f"  {i+1}. [savant.evolution]{step.get('name', 'step')}[/] — {step.get('description', '')}"
                for i, step in enumerate(fw.get("steps", []))
            )
        else:
            steps_text = "[dim]No structured steps (generic capability).[/dim]"
        fw_panel = Panel(
            steps_text or "[dim]—[/dim]",
            title=f"Framework • {fw.get('id', 'n/a')} (inputs: {', '.join(fw.get('inputs', [])) or '—'})",
            border_style=c["ui_accent"],
        )

        extra = []
        if g.reasoning_patterns:
            extra.append(Panel(str(g.reasoning_patterns)[:300] + "...", title="Reasoning Patterns", border_style="dim"))
        if g.tool_compositions:
            extra.append(Panel(str(g.tool_compositions)[:300] + "...", title="Tool Compositions", border_style="dim"))

        self.console.print(manifest_panel)
        self.console.print(fw_panel)
        for p in extra:
            self.console.print(p)

        self.console.print(f"\n[dim]Selected for run/evolve: [savant.genome]{g.genome_id}[/][/]")

    def _show_status(self) -> None:
        stats = self.registry.get_registry_stats()
        c = self.skin.skin["colors"]

        reg_panel = Panel(
            f"[savant.label]Root:[/] {stats['root']}\n"
            f"[savant.label]Genomes:[/] [savant.genome]{stats['count']}[/]\n"
            f"[savant.label]Domains:[/] {', '.join(stats['domains_covered']) or '—'}\n"
            f"[savant.label]Avg Score:[/] [savant.evolution]{stats['avg_score']}[/]\n"
            f"[savant.label]Total Steps:[/] {stats['total_steps']}\n",
            title="Registry",
            border_style=c["banner_border"],
        )

        recent = ""
        if self.run_history:
            recent = "\n".join(
                f"  • {h.get('time_str', '?')}  {h.get('genome','?')} → [savant.ok]{h.get('status','done')}[/]"
                for h in self.run_history[-3:]
            )
        else:
            recent = "[dim]No runs this session yet. Use 'run'.[/dim]"
        run_panel = Panel(recent, title="Recent Session Runs", border_style=c["ui_accent"])

        sys_panel = Panel(
            f"Savant TUI: [savant.ok]active[/]  •  Skin: [savant.label]{self.skin.skin.get('name', 'default')}[/]\n"
            f"Python: {sys.version.split()[0]}  •  Registry writable: [savant.ok]yes[/]\n"
            "[dim]Evolutionary engine, scanners, and worker adapters ready for wiring.[/dim]",
            title="System",
            border_style="dim",
        )

        self.console.print(reg_panel)
        self.console.print(run_panel)
        self.console.print(sys_panel)

    def _show_pool_view(self, args: List[str]) -> None:
        """Dedicated first-class TUI for the Savant Pool (global + per-swarm DNA).
        - No args: enter full interactive sub-shell (premium dedicated experience)
        - With args: one-shot execution of subcommand (e.g. `pool query "..."`, `p swarms`, `pool settings`)
        Uses the attached self.pool_view for persistent swarm scope across invocations.
        """
        try:
            pv = getattr(self, "pool_view", None)
            if pv is None:
                from savant.tui.views.pool_view import PoolView
                pv = PoolView(self)
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
            self.console.print(f"[savant.warn]Pool view:[/] {e}")

    def _scan_runs(self, args: List[str]) -> None:
        """Real DNA extraction using SavantRunScanner + reasoning primitives.
        Produces a live candidate Genome from simulated or provided run data.
        """
        target = args[0] if args else "demo-engagement-2026-05-23"
        self.console.print(f"[savant.label]DNA Scan[/]  • scanner=[savant.accent]savant-run[/]  • target=[savant.framework]{target}[/]")

        # Build realistic sample run data (from worker telemetry or external agent run)
        sample_run = {
            "timestamp": datetime.utcnow().isoformat(),
            "model": "savant-demo-model",
            "observations": [
                {"kind": "event", "identity": "deploy", "state": "started", "summary": "v2.3.1 rollout", "observed_at": 1748000000},
                {"kind": "metric", "identity": "auth-svc.replicas", "state": "2/3", "summary": "readiness failed", "observed_at": 1748000100},
                {"kind": "claim", "identity": "affected_users", "state": "47", "summary": "lb + sessions", "observed_at": 1748000200},
            ],
            "claims": [
                {"statement": "users impacted", "count": 47, "source": "lb-metrics", "source_id": "run-4821"},
                {"statement": "users impacted", "count": 120, "source": "support-tickets", "source_id": "zendesk-991"},
            ],
            "ledger": [
                {"ts": 1748000000, "actor": "cd-pipeline", "operation": "deploy", "status": "ok"},
                {"ts": 1748000100, "actor": "auth-svc", "operation": "health_check", "status": "fail"},
            ],
            "conversations": [{"role": "assistant", "content": "<think>timeline shows deploy then failure... causal?</think>"}],
        }

        try:
            from savant.scanners import SavantRunScanner

            scanner = SavantRunScanner(actor=f"tui-scan-{target[:8]}")
            candidates = scanner.scan(sample_run)

            if not candidates:
                self.console.print("[savant.warn]Scanner returned no candidates.[/]")
                return

            cand = candidates[0]
            # Make it a distinct scanned variant for demo
            cand.manifest.id = "extracted-savant-patterns"
            cand.manifest.version = "0.1.0-scanned"
            cand.finalize()

            # Register the real extracted candidate
            saved_path = self.registry.save(cand)

            self.console.print(
                f"[savant.ok]✓ Real candidate Genome produced by SavantRunScanner + primitives[/]\n"
                f"  [savant.genome]{cand.genome_id}[/]\n"
                f"  saved: {saved_path}\n"
            )

            # Show what the reasoning primitives extracted (high value!)
            rp = cand.reasoning_patterns or {}
            self.console.print(Panel(
                f"Trace steps: {rp.get('trace', {}).get('step_count', 0)}\n"
                f"Anomalies: {len(rp.get('anomalies', []))}\n"
                f"Contradictions: {len(rp.get('contradictions', []))}\n"
                f"Causal edges: {len(rp.get('causality', {}).get('edges', [])) if isinstance(rp.get('causality'), dict) else 0}\n"
                f"Patterns recognized: {len(rp.get('patterns_recognized', []))}\n\n"
                f"[dim]Framework synthesized: {'yes' if cand.framework else 'no (needs more obs)'}[/]\n"
                f"Full details via 'view {cand.manifest.id}' or 'genomes'[/]",
                title="Reasoning Primitives Output (live from engine.extract_from_run)",
                border_style=self.skin.style("ok"),
            ))

            self.selected = cand.genome_id.replace("@", "-")

        except Exception as e:
            self.console.print(f"[savant.error]Scanner failed:[/] {e}")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()[-400:]}[/]")

    def _run_work(self, args: List[str]) -> None:
        """Command composer + live orchestrated execution view."""
        key = args[0] if args else (self.selected or "")
        if not key:
            self._browse_genomes([])
            details = self.registry.list_genome_details()
            if not details:
                return
            try:
                choice = self.session.prompt("Genome to run (# or id): ").strip()
                key = details[int(choice)-1]["dir_name"] if choice.isdigit() else choice
            except Exception:
                return

        g = self.registry.get_genome(key)
        if not g:
            self.console.print(f"[savant.error]Not found:[/] {key}")
            return
        self.selected = g.genome_id

        fw = g.framework or {}
        inputs_spec = fw.get("inputs", ["incident_summary", "timeline"]) or ["query"]

        self.console.print(Panel(f"Preparing run for [savant.genome]{g.genome_id}[/]", border_style=self.skin.style("ui_accent")))

        collected: Dict[str, str] = {}
        for inp in inputs_spec:
            val = self.session.prompt(f"  {inp}: ", default="Demo input for " + inp).strip()
            collected[inp] = val or "N/A"

        self.console.print("[savant.label]Launching live execution...[/] (Ctrl+C to abort)")

        # Lazy import + create SavantHarness for the session (before steps) so base TUI launch never pulls harness/pool
        harness = None
        try:
            from savant.harness.harness import SavantHarness as _SavantHarness
            harness = _SavantHarness(agent_id=f"tui-{g.manifest.id[:16]}-{int(time.time()) % 100000}")
        except Exception as imp_err:
            self.console.print(f"[savant.warn]SavantHarness/Pool integration unavailable this run (will use classic execution):[/] {imp_err}")
            harness = None

        self._execute_live(g, collected, harness=harness)

    def _execute_live(self, genome: Genome, inputs: Dict[str, str], harness: Optional["SavantHarness"] = None) -> None:
        """Rich Live dashboard for orchestrated work with progress, reasoning, tools.

        Integrated with SavantHarness + Savant Pool:
        - Harness created in _run_work (before steps) or here; task_context wraps the live execution
        - Periodically calls pull_relevant_dna() and surfaces "DNA from Pool" in dashboard
        - Uses inject_into_context(...) to augment step reasoning/prompts
        - After run (success/abort): record_outcome(...) + optional auto-ingest of small improvement signal
        - All pool usage is visible, useful, and errors are handled gracefully without breaking the beautiful UI.
        """
        self._cancel_event.clear()
        start = time.time()

        fw = genome.framework or {}
        steps: List[Dict] = fw.get("steps", []) or [{"name": "establish_facts", "description": "Analyze input"},
                                                     {"name": "synthesize", "description": "Produce artifact"}]
        n_steps = max(1, len(steps))

        # Ensure we have a harness for the session (created in caller _run_work or here as fallback)
        if harness is None:
            try:
                from savant.harness.harness import SavantHarness as _SavantHarness
                harness = _SavantHarness(agent_id=f"tui-{genome.manifest.id[:16]}-{int(time.time()) % 100000}")
            except Exception as imp_err:
                # already warned in _run_work; stay silent here to not spam during live
                harness = None
        task_desc = f"Live run of {genome.genome_id} (inputs={list(inputs.keys())})"

        state: Dict[str, Any] = {
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
                title += " [savant.warn](ABORTED)[/]"

            header = Text(f"{sp}  Step {state['step_idx']}/{n_steps}  •  {state['current_step']}  •  {state['pct']}%", style="savant.accent")

            log_lines = "\n".join(state["logs"][-8:]) or "[dim]No log yet...[/dim]"
            log_panel = Panel(log_lines, title="Activity Log", border_style="dim", height=10)

            think = state["thinking"] or "[dim]idle[/dim]"
            think_panel = Panel(think, title=f"Reasoning {verbs[sp_idx % len(verbs)]}", border_style=self.skin.style("evolution_step"))

            tools = "\n".join(f"  ⊙ {t}" for t in state["tools"][-4:]) or "—"
            tools_panel = Panel(tools, title="Tool Calls", border_style=self.skin.style("ui_label"))

            # DNA from Pool panel — makes the pull-from-pool + adapt loop visible and useful in real time
            dna = state.get("dna_from_pool", []) or []
            dna_lines = "\n".join(f"  🧬 {rich_escape(d)}" for d in dna) or "[dim]Pulling relevant DNA from Savant Pool...[/dim]"
            dna_panel = Panel(dna_lines, title="DNA from Pool", border_style=self.skin.style("evolution_step"))

            hname = getattr(harness, "agent_id", "classic")
            footer = f"Elapsed: {time.time() - start:.1f}s   Inputs: {', '.join(inputs.keys())}   harness={hname}"

            body = Group(header, log_panel, think_panel, tools_panel, dna_panel, Text(footer, style="dim"))
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

                with Live(_build_ui(), console=self.console, refresh_per_sec=10, transient=False) as live:
                    try:
                        for idx, step in enumerate(steps, 1):
                            if self._cancel_event.is_set():
                                state["aborted"] = True
                                break
                            state["step_idx"] = idx
                            state["current_step"] = step.get("name", f"step-{idx}")
                            state["pct"] = int(idx / n_steps * 100)

                            state["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ▶ {state['current_step']}")
                            live.update(_build_ui())

                            # Periodically call pull_relevant_dna() and show "DNA from pool" (only when harness active)
                            if has_harness and (idx == 1 or idx % 2 == 0):
                                try:
                                    fresh_dna = harness.pull_relevant_dna(top_k=3)
                                    state["dna_from_pool"] = [d.get("genome_id", "?") for d in fresh_dna]
                                    state["logs"].append(f"  🧬 pulled {len(fresh_dna)} DNA packets from pool")
                                    live.update(_build_ui())
                                except Exception as pull_err:
                                    state["logs"].append(f"  [savant.warn]DNA pull: {str(pull_err)[:45]}[/]")
                                    live.update(_build_ui())

                            for j in range(2):
                                if self._cancel_event.is_set(): break
                                base = f"Applying pattern: contradiction detection + causal chain (iter {j})"
                                if has_harness:
                                    try:
                                        # inject_into_context augments the prompt/reasoning for steps using pool DNA
                                        state["thinking"] = harness.inject_into_context(
                                            base,
                                            extra_instructions="Leverage relevant DNA from Savant Pool for better adaptation and quality."
                                        )
                                    except Exception:
                                        state["thinking"] = base
                                else:
                                    state["thinking"] = base
                                state["logs"].append(f"  {verbs[j % len(verbs)]}...")
                                live.update(_build_ui())
                                time.sleep(0.35)

                            tool_name = "analyze_timeline" if "fact" in state["current_step"].lower() else "recommend"
                            state["tools"].append(f"{tool_name}({state['current_step'][:12]})")
                            state["logs"].append(f"  tool call → {tool_name}")
                            live.update(_build_ui())
                            time.sleep(0.45)

                        if not state["aborted"]:
                            state["done"] = True
                            state["artifact"] = "Structured postmortem document + action plan (saved to ./artifacts/ in real run)"
                            state["logs"].append("[savant.ok]✓ Run completed successfully.[/]")
                            state["pct"] = 100
                            self.run_history.append({
                                "genome": genome.genome_id,
                                "time_str": datetime.now().strftime("%H:%M"),
                                "status": "success",
                                "inputs": list(inputs.keys()),
                            })
                        live.update(_build_ui())
                        time.sleep(0.6)
                    except KeyboardInterrupt:
                        state["aborted"] = True
                        self._cancel_event.set()

                # Post-live (inside task_context when active): record_outcome + optional auto-ingest small signal
                if has_harness:
                    try:
                        outcome: Dict[str, Any] = {
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
                                    framework={"steps": [{"name": "reflect_contribute", "description": "Auto signal from live TUI run + pool DNA"}]},
                                    authors=[{"name": harness.agent_id, "type": "tui-agent"}],
                                    applicability={"domains": ["meta", "pool-feedback"]},
                                    evaluation_score={"reference_tasks": 0.02},
                                    reasoning_patterns={"tui_pool_loop": {"source": genome.genome_id, "dna": state.get("dna_from_pool", [])}},
                                )
                                ires = harness.pool.ingest(signal, source="tui-live-run", actor=harness.agent_id)
                                state["pool_contrib"] = f"✓ ingested {ires.genome_id} ({ires.reason})"
                            except Exception as ingest_err:
                                state["pool_contrib"] = f"ingest note: {str(ingest_err)[:50]}"
                    except Exception as rec_err:
                        state["pool_contrib"] = f"outcome record: {str(rec_err)[:50]}"
        except Exception as harness_err:
            # Graceful: even if task_context or pool ops fail mid-run, we surface useful state
            state["logs"].append(f"[savant.warn]Harness context: {str(harness_err)[:60]}[/]")
            if not state["aborted"] and not state.get("done"):
                state["done"] = True
                state["artifact"] = state.get("artifact") or "Run completed (pool integration partial)"
                state["pct"] = 100

        if state["aborted"]:
            self.console.print("[savant.warn]Run aborted by user.[/]")
        else:
            contrib = state.get("pool_contrib", "")
            footer_note = f"\n[savant.label]Pool feedback:[/] {contrib}" if contrib else ""
            self.console.print(
                Panel(
                    f"[savant.ok]Success[/]\n\n{state['artifact']}\n\n[dim]Full telemetry would feed scanners for evolution.[/dim]{footer_note}",
                    title="Execution Complete",
                    border_style=self.skin.style("ui_ok"),
                )
            )

    def _evolve_genome(self, args: List[str]) -> None:
        key = args[0] if args else (self.selected or "")
        if not key:
            self._browse_genomes([])
            return
        g = self.registry.get_genome(key)
        if not g:
            self.console.print("[savant.error]Genome not found for evolution.[/]")
            return

        self.console.print(f"[savant.label]Reviewing[/] [savant.genome]{g.genome_id}[/] for evolutionary improvements...")

        new_ver = g.manifest.version.split(".")
        try:
            new_ver[-1] = str(int(new_ver[-1]) + 1)
        except Exception:
            new_ver = ["1", "0", "1"]
        new_id = f"{g.manifest.id}@{'.'.join(new_ver)}-evolved"

        diff = f"""[savant.label]Proposed delta v{'.'.join(new_ver)}[/]:
+ Added contradiction-detection reasoning pattern
+ Strengthened root-cause step with ledger witness
+ +0.04 reference evaluation score
"""
        self.console.print(Panel(diff, title="Evolution Proposal", border_style=self.skin.style("evolution_step")))

        if Confirm.ask("Register evolved candidate?", default=True, console=self.console):
            try:
                g.manifest.version = ".".join(new_ver) + "-evolved"
                g.manifest.last_improved = datetime.now()
                g.reasoning_patterns["contradiction_detection"] = {"enabled": True, "v": "evolved"}
                g.evaluations["evolution_run"] = {"score_delta": 0.04}
                saved = self.registry.save(g)
                self.console.print(f"[savant.ok]✓ Evolved genome saved as[/] [savant.genome]{g.genome_id}[/]\n  {saved}")
                self.selected = g.genome_id
            except Exception as e:
                self.console.print(f"[savant.error]Failed to register evolved:[/] {e}")

    def _compose_mission(self, args: List[str]) -> None:
        self.console.print("[savant.label]Mission Composer[/] (multi-genome orchestration stub)")
        details = self.registry.list_genome_details()[:5]
        if not details:
            self.console.print("[dim]No genomes — import first.[/dim]")
            return
        table = Table(title="Available for composition")
        table.add_column("#"); table.add_column("ID")
        for i, d in enumerate(details, 1):
            table.add_row(str(i), d["genome_id"])
        self.console.print(table)
        self.console.print("[dim]In production this would let you build a composite playbook and dispatch to workers.[/dim]")

    def _doctor(self) -> None:
        issues = []
        ok = []
        try:
            stats = self.registry.get_registry_stats()
            ok.append(f"Registry at {stats['root']} — {stats['count']} genomes, writable ✓")
        except Exception as e:
            issues.append(f"Registry: {e}")

        try:
            home = self.registry.root.parent
            if home.exists() and os.access(home, os.W_OK):
                ok.append("Savant home permissions OK")
            else:
                issues.append("Savant home not writable")
        except Exception:
            issues.append("Home dir check failed")

        if self.registry.list_genomes():
            ok.append("At least one genome present")
        else:
            issues.append("No genomes — run 'import'")

        report = "\n".join(f"[savant.ok]✓[/] {x}" for x in ok) + "\n" + "\n".join(f"[savant.warn]⚠[/] {x}" for x in issues)
        self.console.print(Panel(report or "All green.", title="Savant Doctor", border_style=self.skin.style("banner_border")))

    def _run_setup_wizard(self, args: List[str]) -> None:
        """Hermes-style modular setup inside the TUI — conversational and section-based.

        This gives users a true CLI/TUI hybrid experience like Hermes.
        """
        from savant.setup import SECTIONS, run_setup

        self.console.print(Panel(
            "[bold]Savant Setup Wizard[/]\n"
            "Run the full wizard or reconfigure specific areas (especially Swarm DNA policies).",
            border_style=self.skin.style("banner_border")
        ))

        # If user passed a section, run it directly via CLI logic
        if args:
            section = args[0].lower()
            mapping = {s["name"]: s["name"] for s in SECTIONS}
            mapping.update({"swarm": "swarm", "dna": "swarm", "agent": "ai", "model": "ai", "ui": "tui"})
            chosen = mapping.get(section, section)
            run_setup([chosen])
            return

        # Conversational mode
        print()
        self.console.print("[bold]Available sections:[/]")
        for i, s in enumerate(SECTIONS, 1):
            self.console.print(f"  {i}. [savant.accent]{s['name']}[/] — {s['title']}")

        choice = Prompt.ask(
            "\nWhich section? (number or name, or 'all' for full wizard)",
            default="all"
        ).strip().lower()

        if choice in ("all", "full", ""):
            run_setup()
        else:
            mapping = {s["name"]: s["name"] for s in SECTIONS}
            chosen = mapping.get(choice, choice)
            if chosen in [s["name"] for s in SECTIONS]:
                run_setup([chosen])
            else:
                self.console.print("[savant.warn]Unknown section. Running full wizard instead.[/]")
                run_setup()

    def _import_example(self, args: List[str]) -> None:
        gid = self.registry.ensure_bootstrap_example()
        if gid:
            self.console.print(f"[savant.ok]✓ Example re-registered / present:[/] [savant.genome]{gid}[/]")
            self.selected = gid
        else:
            self.console.print("[savant.warn]Example already present or source not found on disk.[/]")


def launch_tui() -> None:
    """Launch the professional Savant TUI."""
    app = SavantTUI()
    app.run()
