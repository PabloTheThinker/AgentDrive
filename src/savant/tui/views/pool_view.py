"""
Savant Pool TUI View

Dedicated, first-class terminal interface for the central Savant Pool and per-swarm DNA.

Features (production-grade):
- Browse global + per-swarm / per-subagent pools
- Live query with relevance explanations
- Ingest, evolve, merge, and inspect Genomes/DNA
- Swarm overview (sub-agent pools, growth metrics)
- User-controlled settings panel (isolation level, sharing policy, auto-ingest rules)
- Full persistence and audit

This makes the Pool visible and controllable exactly as the user owns their experience.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Confirm, Prompt

from prompt_toolkit.completion import WordCompleter

from savant.pool.pool import get_default_pool, SavantPool
from savant.registry import GenomeRegistry
from savant.constants import get_swarms_dir, get_swarm_pool_path
from savant.pool.settings import (
    get_pool_settings_manager,
    PoolSettings,
    IsolationLevel,
    SharingPolicy,
)
from savant.genome.models import Genome


class PoolView:
    """Premium interactive view for the Savant Pool (global + all swarm-isolated DNA pools).

    Supports full sub-REPL when entered via `pool` or `p` from main TUI:
    - Current scope indicator (global or swarm:<id>)
    - Semantic queries with rich "why relevant" explanations from reasoning engine
    - Browse, view, ingest, evolve, merge genomes (scoped to current pool)
    - Live swarm discovery, browser, switcher, and on-the-fly swarm creation
    - Full settings editor for isolation, auto-ingest, sharing policies (persisted)
    - Uses per-swarm GenomeRegistry + SavantPool for true isolation when switched
    """

    def __init__(self, tui: Any):
        self.tui = tui
        self._global_pool: SavantPool = get_default_pool()
        self.pool: SavantPool = self._global_pool
        self.registry: GenomeRegistry = self.pool.registry
        self.current_swarm: Optional[str] = None
        self._pool_completer = WordCompleter(
            [
                "query", "q", "search", "swarms", "sw", "switch", "use", "swarm",
                "global", "main", "genomes", "ls", "browse", "view", "v",
                "ingest", "i", "evolve", "e", "merge", "m",
                "settings", "cfg", "config", "stats", "st", "overview", "o",
                "create-swarm", "help", "?", "back", "leave", "exitpool",
            ],
            ignore_case=True,
            sentence=True,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Scope & Pool Management (global vs per-swarm isolation)
    # ─────────────────────────────────────────────────────────────────────

    def _scope_str(self) -> str:
        if self.current_swarm:
            return f" [swarm:{self.current_swarm}]"
        return " [global]"

    def _get_global_pool(self) -> SavantPool:
        return self._global_pool

    def _get_swarm_pool(self, swarm_id: str) -> SavantPool:
        """Create or return a fully isolated pool for this swarm/sub-agent.
        Genomes live under ~/.savant/swarms/<swarm_id>/genomes/
        Ingest log + metadata under ~/.savant/swarms/<swarm_id>/pool/
        """
        swarm_id = swarm_id.strip()
        if not swarm_id:
            raise ValueError("swarm_id required")
        swarms_root = get_swarms_dir()
        genomes_root = swarms_root / swarm_id / "genomes"
        pool_dir = get_swarm_pool_path(swarm_id)  # supports subagent if we extend id later
        genomes_root.mkdir(parents=True, exist_ok=True)
        pool_dir.mkdir(parents=True, exist_ok=True)

        reg = GenomeRegistry(root=genomes_root)
        return SavantPool(registry=reg, name=f"swarm:{swarm_id}", pool_dir=pool_dir)

    def _refresh_pool(self) -> None:
        if self.current_swarm:
            self.pool = self._get_swarm_pool(self.current_swarm)
        else:
            self.pool = self._get_global_pool()
        self.registry = self.pool.registry

    def switch_to_swarm(self, swarm_id: str) -> None:
        """Live switch: rebind pool + registry to the isolated swarm DNA."""
        if not swarm_id or not swarm_id.strip():
            self.tui.console.print("[savant.warn]Provide a swarm id (from 'swarms' list).[/]")
            return
        self.current_swarm = swarm_id.strip()
        self._refresh_pool()
        self.tui.console.print(
            Panel(
                f"[bold][savant.ok]Switched to isolated swarm pool[/][/]\n"
                f"Swarm: [savant.genome]{self.current_swarm}[/]\n"
                f"Genomes root: {self.registry.root}\n"
                f"Pool dir: {self.pool.pool_dir}\n"
                f"DNA starts empty (or with prior work in this swarm) — fully user-owned.",
                title="Swarm Scope Active",
                border_style=self.tui.skin.style("ui_ok") if hasattr(self.tui, "skin") else "green",
            )
        )
        self.render_overview()

    def switch_to_global(self) -> None:
        """Return to the main shared Savant Pool."""
        self.current_swarm = None
        self._refresh_pool()
        self.tui.console.print("[savant.ok]Switched back to global Savant Pool.[/]")
        self.render_overview()

    def _discover_swarms(self) -> List[Dict[str, Any]]:
        """Discover all swarm directories with optional pool/genome presence + metrics."""
        swarms_dir = get_swarms_dir()
        if not swarms_dir.exists():
            return []
        discovered: List[Dict[str, Any]] = []
        for entry in sorted(swarms_dir.iterdir()):
            if not entry.is_dir():
                continue
            sid = entry.name
            genomes_root = entry / "genomes"
            pdir = entry / "pool"
            ingest_log = pdir / "ingest.jsonl"

            info: Dict[str, Any] = {
                "id": sid,
                "path": str(entry),
                "has_genomes_dir": genomes_root.exists(),
                "has_pool_dir": pdir.exists(),
                "genomes_count": 0,
                "ingest_events": 0,
            }
            if genomes_root.exists():
                try:
                    tmp_reg = GenomeRegistry(root=genomes_root)
                    info["genomes_count"] = len(tmp_reg.list_genomes())
                except Exception:
                    pass
            if ingest_log.exists():
                try:
                    with open(ingest_log, "r", encoding="utf-8") as f:
                        info["ingest_events"] = sum(1 for line in f if line.strip())
                except Exception:
                    pass
            discovered.append(info)
        return discovered

    # ─────────────────────────────────────────────────────────────────────
    # Rendering (premium tables, panels, scope-aware, skin-aligned)
    # ─────────────────────────────────────────────────────────────────────

    def render(self) -> None:
        """Full premium entry render for the Pool view."""
        border = self.tui.skin.style("banner_border") if hasattr(self.tui, "skin") else "magenta"
        title_style = "savant.genome" if hasattr(self.tui, "skin") else "bold magenta"

        self.tui.console.print(
            Panel(
                f"[bold {title_style}]Savant Pool[/] — Living DNA Repository for Agents & Swarms\n"
                "Global pool + isolated per-swarm/per-subagent DNA pools. Starts empty. Grows with your work.\n"
                f"Current scope: [bold]{self._scope_str().strip()}[/]",
                border_style=border,
                padding=(0, 1),
            )
        )

        # Gentle first-time guidance (Apple-grade onboarding)
        if len(self._discover_swarms()) == 0:
            self.tui.console.print(
                "[dim]Tip: Run[/] [savant.accent]PYTHONPATH=src python3 examples/savant_swarm_dna_demo.py[/dim]\n"
                "[dim]then come back and type[/] [savant.accent]swarms[/dim] [dim]to see your first living swarm tree of private DNA pools.[/dim]\n"
            )

        self.render_overview()
        self._show_pool_commands()

    def render_overview(self) -> None:
        """Compact live overview of current pool + summary of all swarms."""
        stats = self.pool.get_pool_stats()
        c = self.tui.skin.skin.get("colors", {}) if hasattr(self.tui, "skin") else {}

        # Current pool card
        pool_table = Table(
            title=f"Current Pool{self._scope_str()}",
            show_header=True,
            header_style=c.get("ui_label", "cyan"),
            border_style=c.get("banner_border", "magenta"),
            expand=True,
        )
        pool_table.add_column("Metric", style="dim")
        pool_table.add_column("Value", style="white")
        pool_table.add_row("Name", stats.get("name", "main"))
        pool_table.add_row("Genomes", str(stats.get("total_genomes", 0)))
        pool_table.add_row("Ingest Events", str(stats.get("ingest_events", 0)))
        pool_table.add_row("Pool Dir", str(stats.get("pool_dir", ""))[:60] + ("..." if len(str(stats.get("pool_dir",""))) > 60 else ""))
        if self.current_swarm:
            pool_table.add_row("Isolation", "swarm-specific (private DNA)")

        self.tui.console.print(pool_table)

        # Swarms summary
        swarms = self._discover_swarms()
        if swarms:
            swarm_table = Table(
                title=f"Discovered Swarms ({len(swarms)})",
                show_header=True,
                header_style=c.get("ui_label", "cyan"),
                border_style=c.get("ui_accent", "#3498DB"),
            )
            swarm_table.add_column("Swarm ID", style="savant.genome")
            swarm_table.add_column("Genomes", justify="right")
            swarm_table.add_column("Ingests", justify="right")
            swarm_table.add_column("Status", style="dim")

            for s in swarms[:8]:  # cap for TUI cleanliness
                status = "active" if (s["genomes_count"] or s["ingest_events"]) else "empty"
                swarm_table.add_row(
                    s["id"],
                    str(s["genomes_count"]),
                    str(s["ingest_events"]),
                    status,
                )
            if len(swarms) > 8:
                swarm_table.add_row("...", f"+{len(swarms)-8} more", "", "")
            self.tui.console.print(swarm_table)
        else:
            self.tui.console.print("[dim]No swarms discovered yet. Use 'create-swarm <id>' or spawn sub-agents with Savant adapters.[/dim]")

        self.tui.console.print(
            f"\n[dim]Tip: 'query \"your task\"' for semantic DNA retrieval with explanations • 'swarms' for live browser • 'settings' for control[/dim]"
        )

    def _show_pool_commands(self) -> None:
        self.tui.console.print(
            "\n[bold]Pool Interactive Commands[/] (in pool mode; also work as `pool <cmd>` from main):\n"
            "  [savant.accent]query <task desc>[/]   Semantic search + relevance explanations\n"
            "  [savant.accent]swarms[/] | [savant.accent]sw[/]              Live swarm browser + metrics\n"
            "  [savant.accent]switch <swarm-id>[/] | [savant.accent]global[/]   Switch DNA scope (isolated or shared)\n"
            "  [savant.accent]genomes[/] | [savant.accent]browse[/]         List genomes in current scope\n"
            "  [savant.accent]view <id|#>[/]            Inspect a genome in detail\n"
            "  [savant.accent]ingest <dir>[/]           Add genome dir to current pool\n"
            "  [savant.accent]evolve <id|#>[/]          Fork + improve a genome\n"
            "  [savant.accent]merge[/]                  Interactive merge of two genomes\n"
            "  [savant.accent]create-swarm <id>[/]      Provision new isolated swarm pool\n"
            "  [savant.accent]settings[/] | [savant.accent]cfg[/]           Edit isolation, auto-ingest, sharing policies\n"
            "  [savant.accent]stats[/]                  Full pool stats + recent ingest history\n"
            "  [savant.accent]help[/] | [savant.accent]back[/]             This help | return to main TUI\n"
        )

    def _render_genomes_table(self, details: List[Dict[str, Any]], title: str = "Genomes in Current Pool") -> None:
        if not details:
            self.tui.console.print(f"[savant.warn]No genomes in current scope.[/] Use ingest or import examples.")
            return
        c = getattr(self.tui.skin, "skin", {}).get("colors", {})
        table = Table(
            title=title,
            show_header=True,
            header_style=c.get("ui_label", "cyan"),
            border_style=c.get("banner_border", "#4A90A4"),
            expand=True,
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("Genome ID", style="savant.genome", no_wrap=True)
        table.add_column("Ver", style="dim", width=7)
        table.add_column("Domains", style="savant.framework")
        table.add_column("Score", justify="right", width=6, style="savant.evolution")
        table.add_column("Steps", justify="right", width=5)

        for idx, d in enumerate(details, 1):
            dom = ", ".join(d.get("domains", [])[:2]) or "—"
            table.add_row(
                str(idx),
                d.get("genome_id", d.get("dir_name", "?")),
                d.get("version", "?"),
                dom,
                f"{d.get('score', 0):.2f}",
                str(d.get("num_steps", 0)),
            )
        self.tui.console.print(table)
        self.tui.console.print(f"[dim]Total: {len(details)} in scope. Use 'view 2' or 'view <id>'.[/dim]")

    # ─────────────────────────────────────────────────────────────────────
    # Core Interactive Features
    # ─────────────────────────────────────────────────────────────────────

    def do_semantic_query(self, task: Optional[str] = None) -> None:
        """Semantic query with full explanations (uses pool.get_dna_for_task + reasoning overlap)."""
        if not task:
            try:
                task = Prompt.ask("Task / intent description for DNA retrieval", console=self.tui.console, default="").strip()
            except Exception:
                task = ""
        if not task:
            self.tui.console.print("[savant.warn]No task provided.[/]")
            return

        self.tui.console.print(f"[savant.label]Semantic query[/] across current pool{self._scope_str()} for: [italic]{task[:80]}[/] ...")
        try:
            packets = self.pool.get_dna_for_task(task, top_k=7)
        except Exception as exc:
            self.tui.console.print(f"[savant.error]Query failed:[/] {exc}")
            return

        if not packets:
            self.tui.console.print("[yellow]No sufficiently relevant DNA found. Broaden task or lower thresholds (via settings).[/]")
            return

        c = getattr(self.tui.skin, "skin", {}).get("colors", {})
        qtable = Table(
            title=f"Top DNA Matches (hybrid relevance via structural + reasoning patterns)",
            show_header=True,
            header_style=c.get("ui_label", "cyan"),
            border_style=c.get("ui_accent", "blue"),
        )
        qtable.add_column("#", width=3)
        qtable.add_column("Genome", style="savant.genome", no_wrap=True)
        qtable.add_column("Rel", justify="right", width=5, style="savant.evolution")
        qtable.add_column("Why Relevant (explanation)", style="dim", max_width=70)

        for i, p in enumerate(packets, 1):
            why = p.get("why_relevant", "")[:120].replace("\n", " ")
            qtable.add_row(
                str(i),
                p.get("genome_id", "?"),
                f"{p.get('relevance_score', 0):.2f}",
                why + ("..." if len(p.get("why_relevant", "")) > 120 else ""),
            )
        self.tui.console.print(qtable)

        self.tui.console.print(
            "\n[dim]Relevance combines domain/signature match + deep Jaccard overlap on reasoning_patterns, framework steps, and patterns_recognized (from savant.reasoning primitives).[/dim]"
        )

        # Offer drill-down
        if Confirm.ask("View full details or use one of these genomes now?", default=False, console=self.tui.console):
            try:
                choice = Prompt.ask("Enter # or genome id", console=self.tui.console, default="1").strip()
                self.do_view_genome(choice)
            except Exception:
                pass

    def browse_current_genomes(self, query: str = "") -> None:
        """Browse genomes in the *current* (global or swarm) registry scope."""
        try:
            if query:
                dirs = self.registry.search_genomes(query)
                details = [d for d in self.registry.list_genome_details() if d["dir_name"] in dirs]
            else:
                details = self.registry.list_genome_details()
        except Exception as e:
            self.tui.console.print(f"[savant.error]Browse error:[/] {e}")
            return
        self._render_genomes_table(details, f"Genomes in Current Pool{self._scope_str()}")

    def do_view_genome(self, key: Optional[str] = None) -> None:
        """Detailed inspection (manifest + framework + reasoning). Mirrors main TUI view but scoped."""
        if not key:
            self.browse_current_genomes()
            try:
                key = Prompt.ask("Enter # or genome id/dir_name to view", console=self.tui.console, default="").strip()
            except Exception:
                return
        if not key:
            return

        # Resolve numeric from current list
        if key.isdigit():
            try:
                details = self.registry.list_genome_details()
                idx = int(key) - 1
                if 0 <= idx < len(details):
                    key = details[idx]["dir_name"]
            except Exception:
                pass

        g = self.registry.get_genome(key)
        if not g:
            self.tui.console.print(f"[savant.error]Genome not found in current scope:[/] {key}")
            return

        m = g.manifest
        c = getattr(self.tui.skin, "skin", {}).get("colors", {})

        lines = [
            f"[savant.label]id:[/] [savant.genome]{m.id}[/]  [savant.label]v:[/] {m.version}",
            f"[savant.label]created:[/] {m.created}   [savant.label]score:[/] {m.evaluation_score}",
            f"[savant.label]domains:[/] {', '.join((m.applicability or {}).get('domains', [])) or '—'}",
        ]
        self.tui.console.print(Panel("\n".join(lines), title="Manifest", border_style=c.get("banner_border", "magenta")))

        fw = g.framework or {}
        steps = fw.get("steps", []) if isinstance(fw, dict) else []
        step_lines = "\n".join(f"  {i+1}. {s.get('name','step')}: {s.get('description','')[:80]}" for i, s in enumerate(steps[:6])) or "[dim]—[/dim]"
        self.tui.console.print(Panel(step_lines, title=f"Framework ({len(steps)} steps)", border_style=c.get("ui_accent", "blue")))

        if g.reasoning_patterns:
            rp = str(g.reasoning_patterns)[:400]
            self.tui.console.print(Panel(rp + "...", title="Reasoning Patterns (DNA)", border_style="dim"))

        self.tui.console.print(f"[dim]Selected in current pool scope. Can evolve/merge from here.[/]")

    def do_ingest(self, source_dir: Optional[str] = None) -> None:
        """Ingest a genome directory into the *current* pool's registry (respects scope)."""
        if not source_dir:
            try:
                source_dir = Prompt.ask("Path to genome directory (e.g. genomes/examples/...) or absolute", console=self.tui.console, default="").strip()
            except Exception:
                return
        if not source_dir:
            return
        p = Path(source_dir).expanduser().resolve()
        if not p.exists() or not p.is_dir():
            self.tui.console.print(f"[savant.error]Directory not found:[/] {p}")
            return
        try:
            g = Genome.load(p)
            result = self.pool.ingest(g, source="tui-ingest", actor=os.environ.get("USER", "tui-user"))
            self.tui.console.print(
                Panel(
                    f"[bold green]Ingest accepted[/]: {result.genome_id}\n"
                    f"Reason: {result.reason}\n"
                    f"Version: {result.new_version or g.manifest.version}\n"
                    f"Current scope: {self._scope_str()}",
                    title="Pool Ingest Success",
                    border_style="green",
                )
            )
            self._refresh_pool()  # pick up new count
        except Exception as exc:
            self.tui.console.print(f"[savant.error]Ingest failed:[/] {exc}")

    def do_evolve(self, key: Optional[str] = None) -> None:
        """Evolve/fork a genome in current scope (simple but real: bump ver + add reasoning + save)."""
        if not key:
            self.browse_current_genomes()
            try:
                key = Prompt.ask("# or id to evolve", console=self.tui.console, default="").strip()
            except Exception:
                return
        if not key:
            return
        if key.isdigit():
            try:
                details = self.registry.list_genome_details()
                key = details[int(key)-1]["dir_name"]
            except Exception:
                pass
        try:
            g = self.registry.get_genome(key)
            if not g:
                self.tui.console.print("[savant.error]Not found.[/]")
                return
            # Use registry fork for proper provenance
            new_ver = g.manifest.version.split(".")
            try:
                new_ver[-1] = str(int(new_ver[-1]) + 1)
            except Exception:
                new_ver = ["1", "0", "1"]
            new_version = ".".join(new_ver) + "-pool-evolved"
            evolved = self.registry.fork(
                source_spec=key,
                new_version=new_version,
                notes="Evolved via Savant Pool TUI — added reasoning depth from query patterns",
            )
            self.tui.console.print(f"[savant.ok]✓ Evolved & saved:[/] [savant.genome]{evolved.genome_id}[/] (v{new_version})")
        except Exception as exc:
            self.tui.console.print(f"[savant.error]Evolve failed:[/] {exc}")

    def do_merge(self) -> None:
        """Interactive merge: pick two genomes, produce a merged descendant via fork + provenance note."""
        self.browse_current_genomes()
        try:
            a = Prompt.ask("First genome (# or id) to merge FROM", console=self.tui.console, default="").strip()
            b = Prompt.ask("Second genome (# or id) to merge concepts FROM", console=self.tui.console, default="").strip()
        except Exception:
            return
        if not a or not b:
            return
        # resolve nums
        details = self.registry.list_genome_details()
        def resolve(k):
            if k.isdigit():
                try:
                    return details[int(k)-1]["dir_name"]
                except: return k
            return k
        a, b = resolve(a), resolve(b)
        try:
            primary = self.registry.get_genome(a)
            if not primary:
                self.tui.console.print(f"[error]Primary not found: {a}[/]")
                return
            # Fork primary, record merge
            new_ver = primary.manifest.version.split(".")
            new_ver[-1] = str(int(new_ver[-1]) + 1) if new_ver[-1].isdigit() else "1"
            merged = self.registry.fork(
                source_spec=a,
                new_version=".".join(new_ver) + "-merged",
                notes=f"Merged concepts from {b} (Pool TUI merge operation)",
            )
            self.tui.console.print(
                Panel(
                    f"Merged genome created: [savant.genome]{merged.genome_id}[/]\n"
                    f"Primary lineage: {a} + influence from {b}\n"
                    f"Provenance recorded. Available for use / further evolution.",
                    title="Merge Complete",
                    border_style="green",
                )
            )
        except Exception as exc:
            self.tui.console.print(f"[savant.error]Merge failed:[/] {exc}")

    def edit_settings(self) -> None:
        """Premium interactive settings editor (global or per-swarm). Persists to config.yaml."""
        mgr = get_pool_settings_manager()
        is_swarm = bool(self.current_swarm)
        if is_swarm:
            settings = mgr.get_for_swarm(self.current_swarm)
        else:
            settings = mgr.get_global()

        self.tui.console.print(
            Panel(
                f"Editing Pool Settings for: [bold]{'swarm:' + self.current_swarm if is_swarm else 'GLOBAL'}[/]\n"
                f"(Changes saved to ~/.savant/config.yaml under pool: section)",
                border_style="cyan",
            )
        )

        data = settings.to_dict()
        s_table = Table(title="Current Effective Settings", show_header=True)
        s_table.add_column("Setting", style="cyan")
        s_table.add_column("Value", style="white")
        for k, v in data.items():
            s_table.add_row(k, str(v))
        self.tui.console.print(s_table)

        if not Confirm.ask("Edit a setting now?", default=True, console=self.tui.console):
            return

        # Simple menu-driven editor
        choices = [
            "1. isolation_level (none / swarm / subagent)",
            "2. auto_ingest_on_success (toggle bool)",
            "3. min_quality_for_ingest (float 0-1)",
            "4. sharing_policy (none / read / selective / full)",
            "5. retention_days (int, 0=forever)",
            "6. allow_upward_proposals (toggle)",
            "7. done",
        ]
        self.tui.console.print("\n".join(choices))
        try:
            choice = Prompt.ask("Choose", console=self.tui.console, default="7").strip()
        except Exception:
            return

        changed = False
        if choice.startswith("1"):
            new_val = Prompt.ask("isolation_level", choices=["none", "swarm", "subagent"], default=settings.isolation_level, console=self.tui.console)
            settings.isolation_level = new_val  # type: ignore
            changed = True
        elif choice.startswith("2"):
            settings.auto_ingest_on_success = not settings.auto_ingest_on_success
            changed = True
        elif choice.startswith("3"):
            try:
                val = float(Prompt.ask("min_quality_for_ingest", default=str(settings.min_quality_for_ingest), console=self.tui.console))
                settings.min_quality_for_ingest = max(0.0, min(1.0, val))
                changed = True
            except Exception:
                pass
        elif choice.startswith("4"):
            newp = Prompt.ask("sharing_policy", choices=["none", "read", "selective", "full"], default=settings.sharing_policy, console=self.tui.console)
            settings.sharing_policy = newp  # type: ignore
            changed = True
        elif choice.startswith("5"):
            try:
                settings.retention_days = int(Prompt.ask("retention_days", default=str(settings.retention_days), console=self.tui.console))
                changed = True
            except Exception:
                pass
        elif choice.startswith("6"):
            settings.allow_upward_proposals = not settings.allow_upward_proposals
            changed = True

        if changed:
            if is_swarm and self.current_swarm:
                mgr.set_for_swarm(self.current_swarm, settings)
            else:
                mgr.set_global(settings)
            self.tui.console.print("[savant.ok]Settings updated and persisted.[/]")
            # Show updated
            self.edit_settings()  # recurse once to confirm
        else:
            self.tui.console.print("[dim]No changes.[/]")

    def show_stats(self) -> None:
        stats = self.pool.get_pool_stats()
        hist = self.pool.get_ingest_history(8)
        panel = Panel(str(stats), title=f"Full Stats for{self._scope_str()}", border_style="blue")
        self.tui.console.print(panel)
        if hist:
            self.tui.console.print("[bold]Recent Ingests (JSONL):[/]")
            for e in hist:
                self.tui.console.print(f"  • {e.get('timestamp')} | {e.get('genome_id')} | {e.get('source')}")

    # ─────────────────────────────────────────────────────────────────────
    # Dispatcher & Interactive Entry Point
    # ─────────────────────────────────────────────────────────────────────

    def handle_command(self, cmd: str, args: List[str]) -> bool:
        """Handle a pool sub-command (works for both one-shot `pool <cmd>` and interactive mode).
        Returns True to continue interactive loop, False to exit sub-mode.
        """
        cmd = (cmd or "").lower().strip()
        if cmd in ("back", "leave", "exitpool", "q", "exit"):
            return False
        if cmd in ("help", "?", "h"):
            self._show_pool_commands()
            self.render_overview()
            return True
        if cmd in ("overview", "o", "status"):
            self.render_overview()
            return True
        if cmd in ("query", "q", "search"):
            task = " ".join(args) if args else None
            self.do_semantic_query(task)
            return True
        if cmd in ("swarms", "sw", "list-swarms"):
            self.show_swarms_browser()
            return True
        if cmd in ("switch", "use", "swarm"):
            sid = args[0] if args else None
            if sid:
                self.switch_to_swarm(sid)
            else:
                self.show_swarms_browser()
                try:
                    sid = Prompt.ask("Swarm id to switch to", console=self.tui.console, default="").strip()
                    if sid:
                        self.switch_to_swarm(sid)
                except Exception:
                    pass
            return True
        if cmd in ("global", "main"):
            self.switch_to_global()
            return True
        if cmd in ("genomes", "ls", "browse", "list"):
            q = " ".join(args) if args else ""
            self.browse_current_genomes(q)
            return True
        if cmd in ("view", "v", "show"):
            key = args[0] if args else None
            self.do_view_genome(key)
            return True
        if cmd in ("ingest", "i"):
            src = args[0] if args else None
            self.do_ingest(src)
            return True
        if cmd in ("evolve", "e"):
            key = args[0] if args else None
            self.do_evolve(key)
            return True
        if cmd in ("merge", "m"):
            self.do_merge()
            return True
        if cmd == "create-swarm":
            sid = args[0] if args else None
            if not sid:
                try:
                    sid = Prompt.ask("New swarm id (e.g. my-research-swarm-01)", console=self.tui.console).strip()
                except Exception:
                    return True
            if sid:
                try:
                    get_swarm_pool_path(sid).mkdir(parents=True, exist_ok=True)
                    (get_swarms_dir() / sid / "genomes").mkdir(parents=True, exist_ok=True)
                    self.tui.console.print(f"[savant.ok]Created swarm structure for[/] [savant.genome]{sid}[/]. Use 'switch {sid}' to enter its pool.")
                except Exception as e:
                    self.tui.console.print(f"[error]Create failed: {e}[/]")
            return True
        if cmd in ("settings", "cfg", "config"):
            self.edit_settings()
            return True
        if cmd in ("stats", "st"):
            self.show_stats()
            return True

        self.tui.console.print(f"[savant.warn]Unknown pool cmd:[/] {cmd}  — try 'help'")
        return True

    def show_swarms_browser(self) -> None:
        """Dedicated live swarm browser with switch shortcut."""
        swarms = self._discover_swarms()
        if not swarms:
            self.tui.console.print(
                Panel(
                    "No swarms found under ~/.savant/swarms/\n\n"
                    "• Swarms are created automatically when using Savant adapters with swarm/subagent ids.\n"
                    "• Or use 'create-swarm my-swarm-1' here.\n"
                    "• Then 'switch my-swarm-1' to browse its private DNA pool.",
                    title="Swarm Browser",
                    border_style="yellow",
                )
            )
            return

        c = getattr(self.tui.skin, "skin", {}).get("colors", {})
        table = Table(title="Live Swarm Browser — Select to switch", show_header=True, border_style=c.get("ui_accent", "blue"))
        table.add_column("#", width=3)
        table.add_column("Swarm ID", style="savant.genome")
        table.add_column("Genomes", justify="right")
        table.add_column("Ingest Events", justify="right")
        table.add_column("Path (truncated)")

        for idx, s in enumerate(swarms, 1):
            shortp = s["path"][-50:] if len(s["path"]) > 50 else s["path"]
            table.add_row(str(idx), s["id"], str(s["genomes_count"]), str(s["ingest_events"]), shortp)

        self.tui.console.print(table)
        self.tui.console.print("[dim]Type 'switch <id>' or 'switch 3' to enter that swarm's private pool.[/]")

    def enter(self) -> None:
        """Enter the first-class interactive Pool sub-shell. Beautiful dedicated experience."""
        self._refresh_pool()
        self.render()

        self.tui.console.print(
            f"\n[bold savant.accent]Entering Savant Pool mode{self._scope_str()}[/]. Type 'help' or 'back' to leave."
        )

        # Temporarily use pool-specific completer for excellent UX
        old_completer = getattr(self.tui.session, "completer", None)
        self.tui.session.completer = self._pool_completer

        try:
            while True:
                try:
                    prompt_text = f"pool{self._scope_str()} ❯ "
                    line = self.tui.session.prompt(prompt_text, default="").strip()
                    if not line:
                        continue

                    parts = line.split(maxsplit=1)
                    cmd = parts[0].lower()
                    argstr = parts[1] if len(parts) > 1 else ""
                    args = argstr.split() if argstr else []

                    if not self.handle_command(cmd, args):
                        break

                except KeyboardInterrupt:
                    self.tui.console.print("\n[savant.warn]Pool interrupted — type 'back' to exit mode.[/]")
                except EOFError:
                    break
                except Exception as exc:
                    self.tui.console.print(f"[savant.error]Pool mode error:[/] {exc}")
        finally:
            self.tui.session.completer = old_completer
            self.tui.console.print("\n[dim]Exited Pool mode — back to main Savant TUI.[/dim]\n")

# Integration hook for main SavantTUI (called from app.py __init__)
def register_pool_view(tui: Any) -> None:
    """Attach a (stateful) PoolView instance to the TUI for dedicated global+swarm DNA management."""
    tui.pool_view = PoolView(tui)
