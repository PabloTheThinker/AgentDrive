"""
AgentDrive TUI View — chrome-styled

Dedicated, first-class terminal interface for the central AgentDrive and
per-swarm DNA. Renders entirely against the unified chrome primitives so the
pool sub-shell feels like the same product as chat, doctor, and onboarding.

Features:
- Browse global + per-swarm / per-subagent pools (sections + tree stems)
- Live semantic query with relevance explanations (spinner + tree cards)
- Ingest, evolve, merge, and inspect Genomes/DNA (result panels + sections)
- Swarm overview and live browser (status rules + tree stems)
- User-controlled settings panel (select_prompt / confirm_prompt)
- Full persistence and audit
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from prompt_toolkit.completion import WordCompleter
from rich.console import Group
from rich.markup import escape as rich_escape
from rich.text import Text

from agentdrive.constants import get_swarm_drive_path, get_swarms_dir
from agentdrive.drive.drive import AgentDrive, get_default_drive
from agentdrive.drive.settings import (
    get_drive_settings_manager,
)
from agentdrive.genome.models import Genome
from agentdrive.registry import GenomeRegistry
from agentdrive.tui.chrome import (
    Glyphs,
    Palette,
    Section,
    Tree,
    TreeRow,
    confirm_prompt,
    error_line,
    info_line,
    ok_line,
    result_panel,
    section_panel,
    select_prompt,
    status_rule,
    warn_line,
)
from agentdrive.tui.loading import MicroSpinner

POOL_HELP_SECTIONS = [
    (
        "Browse",
        [
            ("genomes", "list genomes in current scope"),
            ("view <#|id>", "inspect a genome (manifest / framework / reasoning)"),
            ("stats", "full pool stats + recent ingests"),
            ("overview", "current scope + swarm summary"),
        ],
    ),
    (
        "Scope",
        [
            ("swarms", "live swarm browser + metrics"),
            ("switch <id>", "enter an isolated swarm pool"),
            ("global", "return to the shared global pool"),
            ("create-swarm <id>", "provision a new isolated swarm pool"),
        ],
    ),
    (
        "Pool ops",
        [
            ("query <task>", "semantic search with 'why relevant'"),
            ("ingest <dir>", "add a genome directory to current pool"),
            ("evolve <#|id>", "fork + improve a genome"),
            ("merge", "merge two genomes into a descendant"),
            ("settings", "edit isolation, auto-ingest, sharing"),
        ],
    ),
    (
        "Exit",
        [
            ("help", "show this panel"),
            ("back", "return to the main TUI"),
        ],
    ),
]


class DriveView:
    """Premium interactive view for the AgentDrive (global + swarm-isolated DNA).

    Renders against the chrome primitives. Public surface kept stable:
        DriveView(tui)
        DriveView.enter()
        DriveView.handle_command(cmd, args)        — primary dispatcher
        DriveView._handle_subcommand(args)         — back-compat alias
        register_drive_view(tui)
    """

    def __init__(self, tui: Any):
        self.tui = tui
        self.console = tui.console
        self.skin = getattr(tui, "skin", None)
        self.palette = Palette(self.skin)

        self._global_pool: AgentDrive = get_default_drive()
        self.pool: AgentDrive = self._global_pool
        self.registry: GenomeRegistry = self.pool.registry
        self.current_swarm: str | None = None

        self._pool_completer = WordCompleter(
            [
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
                "?",
                "back",
                "leave",
                "exitpool",
            ],
            ignore_case=True,
            sentence=True,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Scope helpers
    # ─────────────────────────────────────────────────────────────────────

    def _scope_label(self) -> str:
        """Short label used inline and in status rules."""
        return f"swarm:{self.current_swarm}" if self.current_swarm else "global"

    def _scope_str(self) -> str:
        """Legacy bracketed form kept for downstream calls/messages."""
        if self.current_swarm:
            return f" [swarm:{self.current_swarm}]"
        return " [global]"

    def _get_global_pool(self) -> AgentDrive:
        return self._global_pool

    def _get_swarm_pool(self, swarm_id: str) -> AgentDrive:
        """Create or return a fully isolated pool for this swarm/sub-agent."""
        swarm_id = swarm_id.strip()
        if not swarm_id:
            raise ValueError("swarm_id required")
        swarms_root = get_swarms_dir()
        genomes_root = swarms_root / swarm_id / "genomes"
        drive_path = get_swarm_drive_path(swarm_id)
        genomes_root.mkdir(parents=True, exist_ok=True)
        drive_path.mkdir(parents=True, exist_ok=True)

        reg = GenomeRegistry(root=genomes_root)
        return AgentDrive(registry=reg, name=f"swarm:{swarm_id}", drive_path=drive_path)

    def _refresh_pool(self) -> None:
        if self.current_swarm:
            self.pool = self._get_swarm_pool(self.current_swarm)
        else:
            self.pool = self._get_global_pool()
        self.registry = self.pool.registry

    def _print_status_rule(self) -> None:
        """Single-line `─ scope ─ N genomes ─ M ingests ─` rule."""
        p = self.palette

        scope_seg = f"[{p.accent}]{self._scope_label()}[/]"

        try:
            stats = self.pool.get_pool_stats()
            n_g = stats.get("total_genomes") or stats.get("registry_stats", {}).get("count", 0)
            n_i = stats.get("ingest_events", 0)
        except Exception:
            n_g = 0
            n_i = 0

        genomes_seg = f"{n_g} genome{'s' if n_g != 1 else ''}"

        try:
            swarms = self._discover_swarms()
            swarms_seg = f"{len(swarms)} swarm{'s' if len(swarms) != 1 else ''}"
        except Exception:
            swarms_seg = ""

        ingests_seg = f"{n_i} ingest{'s' if n_i != 1 else ''}"

        help_seg = f"[{p.muted}]help · back[/]"

        self.console.print(
            status_rule(
                scope_seg,
                genomes_seg,
                swarms_seg,
                ingests_seg,
                help_seg,
                palette=p,
            )
        )

    # ─────────────────────────────────────────────────────────────────────
    # Switching
    # ─────────────────────────────────────────────────────────────────────

    def switch_to_swarm(self, swarm_id: str) -> None:
        """Live switch: rebind pool + registry to the isolated swarm DNA."""
        p = self.palette
        if not swarm_id or not swarm_id.strip():
            self.console.print()
            self.console.print(
                warn_line(
                    "Provide a swarm id (from 'swarms' list).",
                    palette=p,
                )
            )
            return

        target = swarm_id.strip()

        # If we already have a current swarm, treat the switch as user-confirmed
        # context move so it doesn't surprise them. Only ask once they've done
        # work in the swarm; otherwise just go.
        if self.current_swarm and self.current_swarm != target:
            ok = confirm_prompt(
                self.console,
                title="Switch swarm context?",
                body=(
                    f"Current: [{p.genome}]{self.current_swarm}[/]\n"
                    f"Target:  [{p.genome}]{target}[/]"
                ),
                default_yes=True,
                palette=p,
            )
            if not ok:
                self.console.print(info_line("Switch canceled.", palette=p))
                return

        self.current_swarm = target
        self._refresh_pool()

        rows = [
            ("scope", f"[{p.genome}]{self.current_swarm}[/]"),
            ("genomes dir", str(self.registry.root)),
            ("pool dir", str(self.pool.drive_path)),
            ("isolation", "private DNA (user-owned)"),
        ]
        self.console.print()
        self.console.print(
            section_panel(
                Section("Swarm scope active", rows, palette=p, key_width=12),
                palette=p,
            )
        )
        self._print_status_rule()

    def switch_to_global(self) -> None:
        """Return to the main shared AgentDrive."""
        p = self.palette
        self.current_swarm = None
        self._refresh_pool()
        self.console.print()
        self.console.print(
            ok_line(
                "Switched back to global AgentDrive.",
                palette=p,
            )
        )
        self._print_status_rule()

    # ─────────────────────────────────────────────────────────────────────
    # Discovery
    # ─────────────────────────────────────────────────────────────────────

    def _discover_swarms(self) -> list[dict[str, Any]]:
        """Discover all swarm directories with optional pool/genome presence + metrics."""
        swarms_dir = get_swarms_dir()
        if not swarms_dir.exists():
            return []
        discovered: list[dict[str, Any]] = []
        for entry in sorted(swarms_dir.iterdir()):
            if not entry.is_dir():
                continue
            sid = entry.name
            genomes_root = entry / "genomes"
            pdir = entry / "drive"
            ingest_log = pdir / "ingest.jsonl"

            info: dict[str, Any] = {
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
                    with open(ingest_log, encoding="utf-8") as f:
                        info["ingest_events"] = sum(1 for line in f if line.strip())
                except Exception:
                    pass
            discovered.append(info)
        return discovered

    # ─────────────────────────────────────────────────────────────────────
    # Welcome + overview
    # ─────────────────────────────────────────────────────────────────────

    def render(self) -> None:
        """Full chrome-styled entry render for the Pool view."""
        p = self.palette

        try:
            stats = self.pool.get_pool_stats()
            rs = stats.get("registry_stats", {}) or {}
        except Exception:
            stats = {}
            rs = {}

        scope_rows = [
            ("scope", f"[{p.genome}]{self._scope_label()}[/]"),
            (
                "isolation",
                "[agentdrive.framework]private DNA[/]"
                if self.current_swarm
                else "[agentdrive.framework]shared[/]",
            ),
        ]
        pool_rows = [
            ("name", stats.get("name", "main")),
            ("genomes", f"[{p.genome}]{stats.get('total_genomes', rs.get('count', 0))}[/]"),
            ("ingests", str(stats.get("ingest_events", 0))),
            ("avg score", f"{rs.get('avg_score', 0):.2f}"),
        ]

        hint = Text.from_markup(
            f"[{p.muted}]Type[/] [{p.accent}]help[/] [{p.muted}]for commands · "
            f"[{p.accent}]back[/{p.accent}] [{p.muted}]to leave[/]"
        )

        self.console.print()
        self.console.print(
            section_panel(
                Section("Scope", scope_rows, palette=p, key_width=10),
                Section("Pool", pool_rows, palette=p, key_width=10),
                hint,
                title="AgentDrive",
                palette=p,
            )
        )

        # Onboarding nudge when nothing has been provisioned yet.
        if not self._discover_swarms():
            self.console.print()
            self.console.print(
                info_line(
                    f"Tip: run [{p.accent}]PYTHONPATH=src python3 examples/savant_swarm_dna_demo.py[/]"
                    f" then [{p.accent}]swarms[/] to see your first swarm.",
                    palette=p,
                )
            )

        self._print_status_rule()

    def render_overview(self) -> None:
        """Compact pool + swarms overview, rendered as sections."""
        p = self.palette
        try:
            stats = self.pool.get_pool_stats()
        except Exception:
            stats = {}

        drive_path = str(stats.get("drive_path", "") or "")
        if len(drive_path) > 60:
            drive_path = "…" + drive_path[-58:]

        pool_rows = [
            ("name", stats.get("name", "main")),
            ("genomes", str(stats.get("total_genomes", 0))),
            ("ingests", str(stats.get("ingest_events", 0))),
            ("pool dir", drive_path or "—"),
        ]
        if self.current_swarm:
            pool_rows.append(("isolation", "[agentdrive.framework]swarm-specific (private DNA)[/]"))

        sections: list[Any] = [
            Section(f"Current Pool · {self._scope_label()}", pool_rows, palette=p, key_width=10),
        ]

        # Swarms section (as a tree)
        swarms = self._discover_swarms()
        if swarms:
            head = Text("Discovered Swarms  ", style=f"bold {p.accent}")
            head.append(f"({len(swarms)})", style=p.muted)

            rows: list[TreeRow] = []
            for s in swarms[:8]:
                active = bool(s["genomes_count"] or s["ingest_events"])
                status = "active" if active else "empty"
                status_style = p.ok if active else p.muted
                label = f"[bold {p.genome}]{s['id']}[/]"
                secondary = (
                    f"{s['genomes_count']} genome{'s' if s['genomes_count'] != 1 else ''}  "
                    f"[{p.muted}]·[/] {s['ingest_events']} ingest{'s' if s['ingest_events'] != 1 else ''}  "
                    f"[{p.muted}]·[/] [{status_style}]{status}[/]"
                )
                rows.append(TreeRow(label=label, secondary=secondary))
            if len(swarms) > 8:
                rows.append(
                    TreeRow(
                        label=f"[{p.muted}]+ {len(swarms) - 8} more[/]",
                    )
                )

            sections.append(Group(head, Text(""), Tree(rows, palette=p)))
        else:
            empty = Text.from_markup(
                f"[{p.muted}]No swarms discovered. Use[/] [{p.accent}]create-swarm <id>[/]"
                f" [{p.muted}]or spawn sub-agents with Savant adapters.[/]"
            )
            sections.append(empty)

        hint = Text.from_markup(
            f'[{p.muted}]Use[/] [{p.accent}]query "task"[/] [{p.muted}]for semantic retrieval · '
            f"[{p.accent}]swarms[/] [{p.muted}]for live browser · "
            f"[{p.accent}]settings[/] [{p.muted}]to tune isolation[/]"
        )
        sections.append(hint)

        self.console.print()
        self.console.print(section_panel(*sections, palette=p))

    def show_help(self) -> None:
        """Chrome-styled help panel matching chat /help."""
        p = self.palette
        section_groups: list[Any] = []
        for title, rows in POOL_HELP_SECTIONS:
            section_groups.append(Section(title, rows, palette=p, key_width=18))
        self.console.print()
        self.console.print(
            section_panel(
                *section_groups,
                title="AgentDrive · commands",
                palette=p,
            )
        )
        self._print_status_rule()

    # ─────────────────────────────────────────────────────────────────────
    # Genome listing / viewing
    # ─────────────────────────────────────────────────────────────────────

    def _render_genomes_tree(
        self,
        details: list[dict[str, Any]],
        title_label: str | None = None,
    ) -> None:
        p = self.palette
        if not details:
            self.console.print()
            self.console.print(
                warn_line(
                    "No genomes in current scope.",
                    palette=p,
                    secondary=f"use [{p.accent}]ingest <dir>[/] or import an example",
                )
            )
            return

        rows: list[TreeRow] = []
        for idx, d in enumerate(details, 1):
            gid = d.get("genome_id", d.get("dir_name", "?"))
            gid_short = gid.split("@", 1)[0] if "@" in gid else gid
            ver = d.get("version") or (gid.split("@", 1)[1] if "@" in gid else "?")
            dom = ", ".join(d.get("domains", [])[:2]) or "—"
            n_steps = d.get("num_steps", 0)
            score = d.get("score", 0)

            label = f"[{p.muted}]{idx:>2}[/]  [bold {p.genome}]{gid_short}[/] [dim]@{ver}[/]"
            secondary = (
                f"{dom}  [{p.muted}]·[/] {n_steps} step{'s' if n_steps != 1 else ''}  "
                f"[{p.muted}]·[/] score [{p.evolution}]{score:.2f}[/]"
            )
            rows.append(TreeRow(label=label, secondary=secondary))

        head = Text(title_label or f"Genomes · {self._scope_label()}  ", style=f"bold {p.accent}")
        head.append(f"({len(details)})", style=p.muted)

        hint = Text()
        hint.append("Inspect with ", style=p.muted)
        hint.append("view <#|id>", style=f"bold {p.accent}")
        hint.append("   ·   ", style=p.muted)
        hint.append("Evolve with ", style=p.muted)
        hint.append("evolve <#|id>", style=f"bold {p.accent}")

        self.console.print()
        self.console.print(
            section_panel(
                Group(head, Text(""), Tree(rows, palette=p)),
                hint,
                palette=p,
            )
        )

    def browse_current_genomes(self, query: str = "") -> None:
        """Browse genomes in the *current* (global or swarm) registry scope."""
        p = self.palette
        try:
            with MicroSpinner(self.console, "loading genomes…", accent=p.accent):
                if query:
                    dirs = self.registry.search_genomes(query)
                    details = [
                        d for d in self.registry.list_genome_details() if d["dir_name"] in dirs
                    ]
                else:
                    details = self.registry.list_genome_details()
        except Exception as e:
            self.console.print()
            self.console.print(error_line(f"Browse error: {rich_escape(str(e))}", palette=p))
            return

        title_label = None
        if query:
            title_label = f"Genomes · {self._scope_label()} · search: {query}  "
        self._render_genomes_tree(details, title_label=title_label)
        self._print_status_rule()

    def do_view_genome(self, key: str | None = None) -> None:
        """Manifest / Framework / Reasoning composed sections."""
        p = self.palette

        if not key:
            self.browse_current_genomes()
            try:
                key = self.tui.session.prompt("\nEnter # or id to view: ").strip()
            except Exception:
                return
        if not key:
            return

        if key.isdigit():
            try:
                details = self.registry.list_genome_details()
                idx = int(key) - 1
                if 0 <= idx < len(details):
                    key = details[idx]["dir_name"]
            except Exception:
                pass

        try:
            g = self.registry.get_genome(key)
        except Exception as e:
            self.console.print()
            self.console.print(error_line(f"Lookup failed: {rich_escape(str(e))}", palette=p))
            return

        if not g:
            self.console.print()
            self.console.print(
                error_line(
                    f"Genome not found in current scope: [bold]{rich_escape(str(key))}[/]",
                    palette=p,
                    suggestion=f"run [{p.accent}]genomes[/] to list available ids",
                )
            )
            return

        m = g.manifest

        authors = ", ".join((a.name or str(a)) for a in (m.authors or [])) or "—"
        domains = ", ".join((m.applicability or {}).get("domains", [])) or "—"
        try:
            score = m.evaluation_score.get("reference_tasks", "—")
        except Exception:
            score = m.evaluation_score
        manifest_rows = [
            ("id", f"[bold {p.genome}]{m.id}[/]  [dim]@{m.version}[/]"),
            ("created", str(m.created)),
            ("authors", authors),
            ("domains", domains),
            ("score", f"[{p.evolution}]{score}[/]" if score != "—" else "—"),
        ]

        # Framework section
        fw = g.framework or {}
        steps = fw.get("steps", []) if isinstance(fw, dict) else []
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
                TreeRow(
                    label=f"[dim]+ {n_steps - 6} more step{'s' if n_steps - 6 != 1 else ''}[/]",
                )
            )

        fw_head = Text()
        fw_head.append(f"{Glyphs.EXPANDED} ", style=p.accent)
        fw_head.append("Framework", style=f"bold {p.accent}")
        fw_head.append(f"  {fw.get('id', 'n/a')}", style=p.muted)
        fw_head.append(f"  {n_steps} step{'s' if n_steps != 1 else ''}", style=p.muted)
        if isinstance(fw, dict) and fw.get("inputs"):
            fw_head.append(f"  inputs: {', '.join(fw.get('inputs', []))}", style=p.muted)

        if step_rows:
            fw_section = Group(fw_head, Tree(step_rows, palette=p))
        else:
            fw_section = Group(
                fw_head, Text("    no structured steps (generic capability)", style=p.muted)
            )

        # Reasoning + tools
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

        if getattr(g, "tool_compositions", None):
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

        self.console.print()
        self.console.print(
            section_panel(
                Section("Manifest", manifest_rows, palette=p),
                fw_section,
                *extras,
                title=f"Genome · {g.genome_id}  ·  {self._scope_label()}",
                palette=p,
            )
        )

        hint = Text()
        hint.append("Selected for evolve/merge: ", style=p.muted)
        hint.append(g.genome_id, style=f"bold {p.genome}")
        self.console.print(hint)
        self._print_status_rule()

    # ─────────────────────────────────────────────────────────────────────
    # Query
    # ─────────────────────────────────────────────────────────────────────

    def do_semantic_query(self, task: str | None = None) -> None:
        """Semantic query with chrome-styled result tree."""
        p = self.palette

        if not task:
            try:
                task = self.tui.session.prompt(
                    f"\n{Glyphs.USER} task / intent: ",
                ).strip()
            except Exception:
                task = ""
        if not task:
            self.console.print()
            self.console.print(warn_line("No task provided.", palette=p))
            return

        try:
            with MicroSpinner(
                self.console, f"querying pool · {self._scope_label()}…", accent=p.accent
            ):
                packets = self.pool.get_dna_for_task(task, top_k=7)
        except Exception as exc:
            self.console.print()
            self.console.print(
                error_line(
                    f"Query failed: {rich_escape(str(exc))}",
                    palette=p,
                )
            )
            return

        if not packets:
            self.console.print()
            self.console.print(
                warn_line(
                    "No sufficiently relevant DNA found.",
                    palette=p,
                    secondary="broaden the task or lower thresholds via 'settings'",
                )
            )
            self._print_status_rule()
            return

        rows: list[TreeRow] = []
        for i, pkt in enumerate(packets, 1):
            gid = pkt.get("genome_id", "?")
            score = pkt.get("relevance_score") or pkt.get("score") or 0.0
            why_full = (pkt.get("why_relevant") or "").strip()
            why = why_full.split("\n")[0][:80]
            reasons = pkt.get("top_reasoning") or []

            children: list[TreeRow] = []
            if reasons:
                children.append(
                    TreeRow(
                        label=f"[{p.muted}]patterns:[/] [italic]{', '.join(reasons[:3])}[/]",
                    )
                )
            if why_full and len(why_full) > 80:
                children.append(
                    TreeRow(
                        label=f"[{p.muted}]more:[/] [italic]{rich_escape(why_full[80:200])}…[/]",
                    )
                )

            label = f"[{p.muted}]{i:>2}[/]  [bold {p.genome}]{gid}[/]"
            secondary = f"score [{p.evolution}]{score:.2f}[/]"
            if why:
                secondary += f"  [{p.muted}]·[/] {rich_escape(why)}"
            rows.append(TreeRow(label=label, secondary=secondary, children=children))

        head = Text(f"DNA matches · {self._scope_label()}  ", style=f"bold {p.accent}")
        head.append(f"({len(packets)})", style=p.muted)
        head.append("   task: ", style=p.muted)
        head.append(task[:60], style=f"bold {p.framework}")

        footnote = Text.from_markup(
            f"[{p.muted}]Relevance blends domain/signature match + Jaccard overlap "
            f"on reasoning_patterns and framework steps.[/]"
        )

        self.console.print()
        self.console.print(
            section_panel(
                Group(head, Text(""), Tree(rows, palette=p)),
                footnote,
                palette=p,
            )
        )
        self._print_status_rule()

        # Optional drill-down
        try:
            if confirm_prompt(
                self.console,
                title="View one of these genomes in detail?",
                body=f"Enter the [#] from the list. ([{p.accent}]No[/] to skip.)",
                default_yes=False,
                palette=p,
            ):
                choice = self.tui.session.prompt("\nEnter # or genome id: ").strip()
                if choice:
                    self.do_view_genome(choice)
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────
    # Ingest / evolve / merge
    # ─────────────────────────────────────────────────────────────────────

    def do_ingest(self, source_dir: str | None = None) -> None:
        """Ingest a genome directory into the current pool."""
        p = self.palette
        if not source_dir:
            try:
                source_dir = self.tui.session.prompt(
                    "\nPath to genome directory: ",
                ).strip()
            except Exception:
                return
        if not source_dir:
            return

        path = Path(source_dir).expanduser().resolve()
        if not path.exists() or not path.is_dir():
            self.console.print()
            self.console.print(
                error_line(
                    f"Directory not found: [bold]{rich_escape(str(path))}[/]",
                    palette=p,
                    suggestion="check the path or pass an absolute one",
                )
            )
            return

        try:
            with MicroSpinner(self.console, f"ingesting {path.name}…", accent=p.accent):
                g = Genome.load(path)
                result = self.pool.ingest(
                    g,
                    source="tui-ingest",
                    actor=os.environ.get("USER", "tui-user"),
                )
            self._refresh_pool()
        except Exception as exc:
            self.console.print()
            self.console.print(
                error_line(
                    f"Ingest failed: {rich_escape(str(exc))}",
                    palette=p,
                )
            )
            return

        rows = [
            ("genome", f"[{p.genome}]{result.genome_id}[/]"),
            ("version", str(result.new_version or g.manifest.version)),
            ("scope", self._scope_label()),
            ("reason", rich_escape(result.reason or "—")),
        ]
        self.console.print()
        self.console.print(
            result_panel(
                "Ingest accepted",
                rows,
                success=True,
                palette=p,
            )
        )
        self._print_status_rule()

    def do_evolve(self, key: str | None = None) -> None:
        """Evolve/fork a genome in current scope."""
        p = self.palette
        if not key:
            self.browse_current_genomes()
            try:
                key = self.tui.session.prompt("\n# or id to evolve: ").strip()
            except Exception:
                return
        if not key:
            return
        if key.isdigit():
            try:
                details = self.registry.list_genome_details()
                key = details[int(key) - 1]["dir_name"]
            except Exception:
                pass

        try:
            with MicroSpinner(self.console, f"evolving {key}…", accent=p.accent):
                g = self.registry.get_genome(key)
                if not g:
                    raise RuntimeError(f"Genome not found: {key}")

                new_ver = g.manifest.version.split(".")
                try:
                    new_ver[-1] = str(int(new_ver[-1]) + 1)
                except Exception:
                    new_ver = ["1", "0", "1"]
                new_version = ".".join(new_ver) + "-pool-evolved"
                evolved = self.registry.fork(
                    source_spec=key,
                    new_version=new_version,
                    notes="Evolved via AgentDrive TUI — added reasoning depth from query patterns",
                )
        except Exception as exc:
            self.console.print()
            self.console.print(
                error_line(
                    f"Evolve failed: {rich_escape(str(exc))}",
                    palette=p,
                )
            )
            return

        rows = [
            ("source", f"[{p.genome}]{key}[/]"),
            ("descendant", f"[{p.genome}]{evolved.genome_id}[/]"),
            ("version", new_version),
            ("scope", self._scope_label()),
        ]
        self.console.print()
        self.console.print(
            result_panel(
                "Evolved",
                rows,
                success=True,
                palette=p,
            )
        )
        self._print_status_rule()

    def do_merge(self) -> None:
        """Interactive merge: pick two genomes, produce a merged descendant."""
        p = self.palette
        self.browse_current_genomes()

        try:
            a = self.tui.session.prompt("\nFirst genome (# or id) — merge FROM: ").strip()
            b = self.tui.session.prompt("Second genome (# or id) — concepts FROM: ").strip()
        except Exception:
            return
        if not a or not b:
            self.console.print()
            self.console.print(warn_line("Two genome references required.", palette=p))
            return

        details = self.registry.list_genome_details()

        def resolve(k: str) -> str:
            if k.isdigit():
                try:
                    return details[int(k) - 1]["dir_name"]
                except Exception:
                    return k
            return k

        a_id, b_id = resolve(a), resolve(b)

        if not confirm_prompt(
            self.console,
            title="Merge these genomes?",
            body=(
                f"Primary: [{p.genome}]{a_id}[/]\n"
                f"Influence: [{p.genome}]{b_id}[/]\n"
                f"Scope: [{p.accent}]{self._scope_label()}[/]"
            ),
            default_yes=True,
            palette=p,
        ):
            self.console.print(info_line("Merge canceled.", palette=p))
            return

        try:
            with MicroSpinner(self.console, "merging genomes…", accent=p.accent):
                primary = self.registry.get_genome(a_id)
                if not primary:
                    raise RuntimeError(f"Primary not found: {a_id}")
                new_ver = primary.manifest.version.split(".")
                new_ver[-1] = str(int(new_ver[-1]) + 1) if new_ver[-1].isdigit() else "1"
                merged = self.registry.fork(
                    source_spec=a_id,
                    new_version=".".join(new_ver) + "-merged",
                    notes=f"Merged concepts from {b_id} (Pool TUI merge operation)",
                )
        except Exception as exc:
            self.console.print()
            self.console.print(
                error_line(
                    f"Merge failed: {rich_escape(str(exc))}",
                    palette=p,
                )
            )
            return

        rows = [
            ("primary", f"[{p.genome}]{a_id}[/]"),
            ("influence", f"[{p.genome}]{b_id}[/]"),
            ("descendant", f"[{p.genome}]{merged.genome_id}[/]"),
            ("scope", self._scope_label()),
        ]
        self.console.print()
        self.console.print(
            result_panel(
                "Merge complete",
                rows,
                success=True,
                palette=p,
            )
        )
        self._print_status_rule()

    # ─────────────────────────────────────────────────────────────────────
    # Settings
    # ─────────────────────────────────────────────────────────────────────

    def edit_settings(self) -> None:
        """Chrome-styled settings editor."""
        p = self.palette
        mgr = get_drive_settings_manager()
        is_swarm = bool(self.current_swarm)
        settings = (
            mgr.get_for_swarm(self.current_swarm)
            if is_swarm and self.current_swarm
            else mgr.get_global()
        )

        # Render current effective settings
        data = settings.to_dict()
        rows = [(k, rich_escape(str(v))) for k, v in data.items()]
        scope_label = f"swarm:{self.current_swarm}" if is_swarm and self.current_swarm else "GLOBAL"

        self.console.print()
        self.console.print(
            section_panel(
                Section(f"Pool settings · {scope_label}", rows, palette=p, key_width=22),
                Text.from_markup(
                    f"[{p.muted}]Persisted to[/] [{p.accent}]~/.agentdrive/config.yaml[/] "
                    f"[{p.muted}]under the Drive: key.[/]"
                ),
                palette=p,
            )
        )

        # Editor menu
        choices = [
            "isolation_level (none / swarm / subagent)",
            "auto_ingest_on_success (toggle)",
            "min_quality_for_ingest (0.0 – 1.0)",
            "sharing_policy (none / read / selective / full)",
            "retention_days (integer, 0 = forever)",
            "allow_upward_proposals (toggle)",
            "done",
        ]
        idx = select_prompt(
            self.console,
            "Edit which setting?",
            choices,
            default_idx=len(choices) - 1,
            palette=p,
        )
        if idx is None or idx == len(choices) - 1:
            self.console.print(info_line("No changes.", palette=p))
            self._print_status_rule()
            return

        changed = False
        if idx == 0:
            opts = ["none", "swarm", "subagent"]
            cur = settings.isolation_level if settings.isolation_level in opts else "none"
            sel = select_prompt(
                self.console,
                "isolation_level",
                opts,
                default_idx=opts.index(cur),
                palette=p,
            )
            if sel is not None:
                settings.isolation_level = opts[sel]  # type: ignore
                changed = True
        elif idx == 1:
            settings.auto_ingest_on_success = not settings.auto_ingest_on_success
            changed = True
        elif idx == 2:
            try:
                raw = self.tui.session.prompt(
                    f"\nmin_quality_for_ingest [{settings.min_quality_for_ingest}]: ",
                ).strip()
                if raw:
                    val = float(raw)
                    settings.min_quality_for_ingest = max(0.0, min(1.0, val))
                    changed = True
            except Exception:
                self.console.print(warn_line("Invalid float — unchanged.", palette=p))
        elif idx == 3:
            opts = ["none", "read", "selective", "full"]
            cur = settings.sharing_policy if settings.sharing_policy in opts else "none"
            sel = select_prompt(
                self.console,
                "sharing_policy",
                opts,
                default_idx=opts.index(cur),
                palette=p,
            )
            if sel is not None:
                settings.sharing_policy = opts[sel]  # type: ignore
                changed = True
        elif idx == 4:
            try:
                raw = self.tui.session.prompt(
                    f"\nretention_days [{settings.retention_days}]: ",
                ).strip()
                if raw:
                    settings.retention_days = int(raw)
                    changed = True
            except Exception:
                self.console.print(warn_line("Invalid integer — unchanged.", palette=p))
        elif idx == 5:
            settings.allow_upward_proposals = not settings.allow_upward_proposals
            changed = True

        if changed:
            if is_swarm and self.current_swarm:
                mgr.set_for_swarm(self.current_swarm, settings)
            else:
                mgr.set_global(settings)
            self.console.print()
            self.console.print(
                ok_line(
                    "Settings updated and persisted.",
                    palette=p,
                    secondary=f"scope: {scope_label}",
                )
            )
            self._print_status_rule()
        else:
            self.console.print(info_line("No changes.", palette=p))
            self._print_status_rule()

    # ─────────────────────────────────────────────────────────────────────
    # Stats / swarm browser
    # ─────────────────────────────────────────────────────────────────────

    def show_stats(self) -> None:
        """Full pool stats + recent ingest history, as sections."""
        p = self.palette

        try:
            with MicroSpinner(self.console, "loading pool stats…", accent=p.accent):
                stats = self.pool.get_pool_stats() or {}
                hist = self.pool.get_ingest_history(8) or []
        except Exception as e:
            self.console.print()
            self.console.print(error_line(f"Pool unavailable: {rich_escape(str(e))}", palette=p))
            return

        rs = stats.get("registry_stats", {}) or {}

        pool_rows = [
            ("name", stats.get("name", "main")),
            ("genomes", f"[{p.genome}]{stats.get('total_genomes', rs.get('count', 0))}[/]"),
            ("ingests", str(stats.get("ingest_events", 0))),
            ("last", str(stats.get("last_ingest") or "never")),
            ("pool dir", str(stats.get("drive_path", "") or "—")[:60]),
        ]
        registry_rows = [
            ("count", str(rs.get("count", 0))),
            ("domains", ", ".join(rs.get("domains_covered", [])[:6]) or "—"),
            ("avg score", f"{rs.get('avg_score', 0):.2f}"),
            ("steps", str(rs.get("total_steps", 0))),
        ]

        sections: list[Any] = [
            Section(f"Pool · {self._scope_label()}", pool_rows, palette=p, key_width=10),
            Section("Registry", registry_rows, palette=p, key_width=10),
        ]

        if hist:
            head = Text("Recent ingests  ", style=f"bold {p.accent}")
            head.append(f"({len(hist)})", style=p.muted)
            rows: list[TreeRow] = []
            for e in hist:
                ts = (e.get("timestamp") or "")[:19].replace("T", " ")
                rows.append(
                    TreeRow(
                        label=f"[bold {p.genome}]{e.get('genome_id', '?')}[/]",
                        secondary=f"{ts}  [{p.muted}]·[/] {e.get('source', '?')}",
                    )
                )
            sections.append(Group(head, Text(""), Tree(rows, palette=p)))

        self.console.print()
        self.console.print(section_panel(*sections, palette=p))
        self._print_status_rule()

    def show_swarms_browser(self) -> None:
        """Live swarm browser rendered as a tree."""
        p = self.palette

        try:
            with MicroSpinner(self.console, "scanning swarms…", accent=p.accent):
                swarms = self._discover_swarms()
        except Exception as e:
            self.console.print()
            self.console.print(error_line(f"Swarm scan failed: {rich_escape(str(e))}", palette=p))
            return

        if not swarms:
            self.console.print()
            self.console.print(
                section_panel(
                    warn_line(
                        "No swarms found under ~/.agentdrive/swarms/",
                        palette=p,
                    ),
                    Text.from_markup(
                        f"  [{p.muted}]Swarms are created when using Savant adapters with swarm ids,[/]\n"
                        f"  [{p.muted}]or via[/] [{p.accent}]create-swarm <id>[/]\n"
                        f"  [{p.muted}]then[/] [{p.accent}]switch <id>[/] [{p.muted}]to enter the private pool.[/]"
                    ),
                    title="Swarm browser",
                    palette=p,
                )
            )
            self._print_status_rule()
            return

        rows: list[TreeRow] = []
        for idx, s in enumerate(swarms, 1):
            shortp = s["path"][-50:] if len(s["path"]) > 50 else s["path"]
            active = bool(s["genomes_count"] or s["ingest_events"])
            status_style = p.ok if active else p.muted
            status = "active" if active else "empty"

            label = f"[{p.muted}]{idx:>2}[/]  [bold {p.genome}]{s['id']}[/]"
            secondary = (
                f"{s['genomes_count']} genome{'s' if s['genomes_count'] != 1 else ''}  "
                f"[{p.muted}]·[/] {s['ingest_events']} ingest{'s' if s['ingest_events'] != 1 else ''}  "
                f"[{p.muted}]·[/] [{status_style}]{status}[/]  "
                f"[{p.muted}]·[/] [{p.muted}]{shortp}[/]"
            )
            rows.append(TreeRow(label=label, secondary=secondary))

        head = Text("Swarms  ", style=f"bold {p.accent}")
        head.append(f"({len(swarms)})", style=p.muted)

        hint = Text()
        hint.append("Switch with ", style=p.muted)
        hint.append("switch <id|#>", style=f"bold {p.accent}")
        hint.append("   ·   ", style=p.muted)
        hint.append("Create with ", style=p.muted)
        hint.append("create-swarm <id>", style=f"bold {p.accent}")

        self.console.print()
        self.console.print(
            section_panel(
                Group(head, Text(""), Tree(rows, palette=p)),
                hint,
                palette=p,
            )
        )
        self._print_status_rule()

    # ─────────────────────────────────────────────────────────────────────
    # Dispatcher
    # ─────────────────────────────────────────────────────────────────────

    def handle_command(self, cmd: str, args: list[str]) -> bool:
        """Handle one pool sub-command. Returns True to keep the loop running."""
        p = self.palette
        cmd = (cmd or "").lower().strip()

        if cmd in ("back", "leave", "exitpool", "q", "exit"):
            return False
        if cmd in ("help", "?", "h"):
            self.show_help()
            return True
        if cmd in ("overview", "o", "status"):
            self.render_overview()
            self._print_status_rule()
            return True
        if cmd in ("query", "q", "search"):
            task = " ".join(args) if args else None
            self.do_semantic_query(task)
            return True
        if cmd in ("swarms", "sw", "list-swarms"):
            self.show_swarms_browser()
            return True
        if cmd in ("switch", "use", "swarm"):
            sid = args[0] if args else ""
            if not sid:
                self.show_swarms_browser()
                try:
                    sid = self.tui.session.prompt(
                        f"\n{Glyphs.USER} swarm id (or #): ",
                    ).strip()
                except Exception:
                    return True
            if sid:
                # Resolve numeric to id from current discovery
                if sid.isdigit():
                    swarms = self._discover_swarms()
                    try:
                        sid = swarms[int(sid) - 1]["id"]
                    except Exception:
                        pass
                self.switch_to_swarm(sid)
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
            sid = args[0] if args else ""
            if not sid:
                try:
                    sid = self.tui.session.prompt(
                        "\nNew swarm id (e.g. my-research-swarm-01): ",
                    ).strip()
                except Exception:
                    return True
            if sid:
                try:
                    get_swarm_drive_path(sid).mkdir(parents=True, exist_ok=True)
                    (get_swarms_dir() / sid / "genomes").mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    self.console.print()
                    self.console.print(
                        error_line(
                            f"Create failed: {rich_escape(str(e))}",
                            palette=p,
                        )
                    )
                    return True
                self.console.print()
                self.console.print(
                    ok_line(
                        f"Created swarm structure for [{p.genome}]{sid}[/]",
                        palette=p,
                        secondary=f"use [bold {p.accent}]switch {sid}[/] to enter",
                    )
                )
                self._print_status_rule()
            return True
        if cmd in ("settings", "cfg", "config"):
            self.edit_settings()
            return True
        if cmd in ("stats", "st"):
            self.show_stats()
            return True

        self.console.print()
        self.console.print(
            warn_line(
                f"Unknown pool command: [bold]{rich_escape(cmd)}[/]  — try [{p.accent}]help[/]",
                palette=p,
            )
        )
        return True

    # Back-compat alias — some callers may use the older underscore-prefixed name.
    def _handle_subcommand(self, args: list[str]) -> bool:
        if not args:
            return True
        cmd = args[0]
        rest = args[1:]
        return self.handle_command(cmd, rest)

    # ─────────────────────────────────────────────────────────────────────
    # Interactive entry point
    # ─────────────────────────────────────────────────────────────────────

    def enter(self) -> None:
        """Enter the chrome-styled interactive Pool sub-shell."""
        p = self.palette
        self._refresh_pool()
        self.render()

        self.console.print()
        self.console.print(
            info_line(
                f"Entering AgentDrive mode · [{p.accent}]{self._scope_label()}[/] — "
                f"type [{p.accent}]help[/] or [{p.accent}]back[/].",
                palette=p,
            )
        )

        old_completer = getattr(self.tui.session, "completer", None)
        self.tui.session.completer = self._pool_completer

        try:
            while True:
                try:
                    prompt_text = f"\npool · {self._scope_label()}  {Glyphs.USER} "
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
                    self.console.print()
                    self.console.print(
                        warn_line(
                            f"Pool interrupted — type [{p.accent}]back[/] to exit mode.",
                            palette=p,
                        )
                    )
                except EOFError:
                    break
                except Exception as exc:
                    self.console.print()
                    self.console.print(
                        error_line(
                            f"Pool mode error: {rich_escape(str(exc))}",
                            palette=p,
                        )
                    )
        finally:
            self.tui.session.completer = old_completer
            self.console.print()
            self.console.print(
                info_line(
                    "Exited Pool mode — back to the main Savant TUI.",
                    palette=p,
                )
            )
            self.console.print()


# Integration hook for main SavantTUI (called from app.py __init__)
def register_drive_view(tui: Any) -> None:
    """Attach a (stateful) DriveView instance to the TUI for dedicated global+swarm DNA management."""
    tui.pool_view = DriveView(tui)
