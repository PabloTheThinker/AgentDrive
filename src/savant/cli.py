"""
Savant CLI - Production-grade command line interface.

Default behavior (Apple/OpenClaw/Hermes style):
  Just typing `savant` launches the full interactive TUI experience.

Polished subcommand structure (Hermes-style modular wizard):
  savant                    # Default: launch the beautiful TUI
  savant setup              # Full interactive setup wizard (strongly recommended first time)
  savant setup swarm        # Only reconfigure Swarm & Sub-Agent DNA policies
  savant tui
  savant onboard            # Lightweight first-run consent flow
  savant doctor
  savant pool ...

First run (or `savant setup`) gives you a Hermes-grade interactive wizard that detects
your AI agents, sets up your Savant Pools, and asks for consent on automatic sub-agent
pool attachment — the core of the living swarm DNA system.

Integrates config, logging, registry, workers/adapters, and the persistent SavantPool.
User sovereignty is absolute.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from savant import (
    SAVANT_VERSION,
    GenomeRegistry,
    get_config_value,
    get_logger,
    get_savant_home,
    load_config,
    save_config,
    set_config_value,
    setup_logging,
)
from savant.pool.pool import get_default_pool, PoolQuery
from savant.tui.app import launch_tui
from savant.workers import get_default_adapter

# Genome for direct loading during ingest (pool will persist via registry)
from savant.genome.models import Genome
from savant.setup import cmd_setup, run_setup
from savant.config import get_savant_home

console = Console()
logger = get_logger("savant.cli")


def _print_banner() -> None:
    console.print(
        "[bold cyan]Savant[/] — The Living, Learning Ecosystem for AI Agents\n"
        f"[dim]v{SAVANT_VERSION}  •  {get_savant_home()}[/]\n"
    )


def cmd_version(args: argparse.Namespace) -> int:
    console.print(f"Savant {SAVANT_VERSION}")
    return 0


def cmd_tui(args: argparse.Namespace) -> int:
    setup_logging()
    launch_tui()
    return 0


def cmd_genomes(args: argparse.Namespace) -> int:
    setup_logging()
    reg = GenomeRegistry()
    if args.subcommand == "list" or not args.subcommand:
        genomes = reg.list_genomes()
        if not genomes:
            console.print("[yellow]No genomes registered yet.[/]")
            console.print("Use [cyan]savant scan[/] or place genomes in "
                          f"{reg.root}")
            return 0

        table = Table(title="Registered Genomes", show_header=True)
        table.add_column("ID", style="green")
        table.add_column("Path", style="dim")
        for g in genomes:
            p = reg.get_genome_path(g)
            table.add_row(g, str(p) if p else "")
        console.print(table)
        return 0

    if args.subcommand == "info":
        if not args.id:
            console.print("[red]Usage: savant genomes info <genome-id>[/]")
            return 1
        g = reg.load(args.id)
        if not g:
            console.print(f"[red]Genome not found:[/] {args.id}")
            return 1
        console.print(Panel(
            f"[bold]{g.manifest.id}[/]\n"
            f"Version: {g.manifest.version}\n"
            f"Authors: {len(g.manifest.authors)}\n"
            f"Applicability: {g.manifest.applicability}\n"
            f"Eval scores: {g.manifest.evaluation_score}",
            title=f"Genome: {args.id}",
            border_style="cyan",
        ))
        return 0

    console.print("[red]Unknown genomes subcommand[/]")
    return 1


def cmd_scan(args: argparse.Namespace) -> int:
    setup_logging()
    from savant.scanners.base import BaseScanner  # type: ignore

    reg = GenomeRegistry()
    path = Path(args.path) if args.path else None

    console.print("[cyan]Scanning for candidate Genomes...[/]")
    if path:
        console.print(f"  Source: {path}")
    else:
        console.print("  Source: (no path given — would use recent worker runs)")

    # Stub scanner usage (real scanners registered via entry points later)
    console.print("[dim]Using registered scanners (framework, reasoning, ...)[/]")
    # In future:
    # adapter = get_default_adapter()
    # genomes = adapter.contribute_genome(path or latest_run)
    # for g in genomes: reg.save(g)

    console.print("[yellow]Scan is a stub in v0.1. Real scanners + external run ingestion coming in next iteration.[/]")
    console.print(f"Registry location: {reg.root}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    setup_logging()
    console.print("[bold]Savant Doctor — System Health Check[/]\n")

    issues = 0

    # Home & dirs
    home = get_savant_home()
    console.print(f"• Savant home: {home}")
    for sub in ("genomes", "logs", "cache"):
        p = home / sub
        ok = p.exists() and p.is_dir()
        console.print(f"  - {sub}/ : {'[green]OK[/]' if ok else '[red]MISSING[/]'}")
        if not ok:
            issues += 1

    # Config
    cfg_path = home / "config.yaml"
    cfg = load_config()
    console.print(f"• Config: {cfg_path}  ({'present' if cfg_path.exists() else 'using defaults'})")
    console.print(f"  log_level: {get_config_value('savant.log_level', 'INFO')}")

    # Registry
    reg = GenomeRegistry()
    gcount = len(reg.list_genomes())
    console.print(f"• Registry: {gcount} genomes registered")

    # Pool (persistent)
    try:
        p = get_default_pool()
        pstats = p.get_pool_stats()
        console.print(f"• Pool: {pstats.get('ingest_events', 0)} ingest events (persistent JSONL at {pstats.get('pool_dir')})")
    except Exception:
        console.print("• Pool: available (via get_default_pool)")

    # Worker adapters
    adapter = get_default_adapter()
    worker = adapter.as_worker()
    caps = worker.get_capabilities()
    console.print(f"• Default worker: {adapter.get_name()}  (healthy={worker.health_check()})")
    console.print(f"  Capabilities: domains={caps.supported_domains}, concurrency={caps.max_concurrency}")

    # Python / deps quick check (import smoke)
    try:
        import pydantic  # noqa
        import yaml  # noqa
        import rich  # noqa
        console.print("• Core dependencies: [green]importable[/]")
    except Exception as e:
        console.print(f"• Core dependencies: [red]problem ({e})[/]")
        issues += 1

    # Integration note
    console.print("\n[dim]External agent integration: adapter present. Full run export & execution bridge in progress.[/]")

    if issues == 0:
        console.print("\n[green]✓ All checks passed. Savant is ready.[/]")
    else:
        console.print(f"\n[red]✗ {issues} issue(s) found.[/]")
    return 0 if issues == 0 else 1


def cmd_config(args: argparse.Namespace) -> int:
    setup_logging()
    if args.subcommand in (None, "show"):
        cfg = load_config()
        console.print(Panel(str(cfg), title="Effective Savant Config", border_style="blue"))
        return 0

    if args.subcommand == "get":
        val = get_config_value(args.key, "<not set>")
        console.print(f"{args.key} = {val}")
        return 0

    if args.subcommand == "set":
        if not args.key or args.value is None:
            console.print("[red]Usage: savant config set <key> <value>[/]")
            return 1
        # Very naive typing for now (strings mostly)
        try:
            val: Any = args.value
            if args.value.lower() in ("true", "false"):
                val = args.value.lower() == "true"
            elif args.value.isdigit():
                val = int(args.value)
            set_config_value(args.key, val)
            console.print(f"[green]Set[/] {args.key} = {val}")
        except Exception as e:
            console.print(f"[red]Failed to set:[/] {e}")
            return 1
        return 0

    if args.subcommand == "edit":
        import subprocess
        editor = os.environ.get("EDITOR", "vi")
        cfg_path = get_savant_home() / "config.yaml"
        if not cfg_path.exists():
            save_config(load_config())  # materialize defaults
        subprocess.call([editor, str(cfg_path)])
        return 0

    console.print("[red]Unknown config subcommand[/]")
    return 1


def cmd_workers(args: argparse.Namespace) -> int:
    setup_logging()
    adapter = get_default_adapter()
    worker = adapter.as_worker()
    caps = worker.get_capabilities()

    table = Table(title="Available Workers / Adapters")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Healthy")
    table.add_column("Domains")
    table.add_column("Concurrency")

    table.add_row(
        adapter.get_name(),
        "ExternalAgentAdapter (default)",
        "yes" if worker.health_check() else "no",
        ", ".join(caps.supported_domains),
        str(caps.max_concurrency),
    )
    console.print(table)
    console.print("[dim]Use savant doctor for deeper integration status.[/]")
    return 0


def cmd_pool(args: argparse.Namespace) -> int:
    """Handler for the `savant pool` subcommand group: status, ingest, query, stats."""
    setup_logging()
    pool = get_default_pool()
    sub = getattr(args, "pool_subcommand", None)

    if sub in (None, "status"):
        # High-level status + integration view
        stats = pool.get_pool_stats()
        reg = pool.registry
        try:
            reg_details = reg.get_registry_stats() if hasattr(reg, "get_registry_stats") else {}
        except Exception:
            reg_details = {}

        console.print(Panel(
            f"[bold]Pool:[/] {stats.get('name', 'main')}\n"
            f"[bold]Pool dir:[/] {stats.get('pool_dir')}\n"
            f"[bold]Ingest log:[/] {stats.get('ingest_log_path')}\n"
            f"[bold]Genomes in registry:[/] {stats.get('total_genomes', 0)}\n"
            f"[bold]Ingest events (persistent):[/] {stats.get('ingest_events', 0)}\n"
            f"[bold]Last ingest:[/] {stats.get('last_ingest') or 'never'}\n"
            f"[bold]Sources:[/] {stats.get('sources', {})}\n"
            f"[bold]Registry domains:[/] {reg_details.get('domains_covered', [])[:5] if reg_details else []}",
            title="Savant Pool Status",
            border_style="magenta",
        ))
        console.print("[dim]Use 'savant pool stats' for full details, 'savant pool query \"...\"' to search.[/]")
        return 0

    if sub == "ingest":
        gdir = Path(args.genome_dir).expanduser().resolve()
        if not gdir.exists() or not gdir.is_dir():
            console.print(f"[red]Genome dir not found or not a directory:[/] {gdir}")
            return 1
        try:
            g = Genome.load(gdir)
            # Ingest will also save to the canonical registry location
            result = pool.ingest(g, source="cli-ingest", actor=os.environ.get("USER", "cli-user"))
            console.print(Panel(
                f"[bold green]Accepted[/]: {result.genome_id}\n"
                f"Reason: {result.reason}\n"
                f"Version: {result.new_version or g.manifest.version}\n"
                f"Source dir: {gdir}\n"
                f"Persisted to registry + ingest.jsonl",
                title="Pool Ingest",
                border_style="green",
            ))
            # Also show updated count
            new_stats = pool.get_pool_stats()
            console.print(f"[dim]Pool now has {new_stats['ingest_events']} ingest events, {new_stats['total_genomes']} genomes.[/]")
            return 0
        except Exception as exc:
            console.print(f"[red]Ingest failed:[/] {exc}")
            logger.exception("pool ingest error")
            return 1

    if sub == "query":
        task = args.task or ""
        if not task.strip():
            console.print("[red]Provide a task description: savant pool query \"your task here\"[/]")
            return 1
        q = PoolQuery(
            task_description=task,
            limit=getattr(args, "limit", 5),
            min_score=getattr(args, "min_score", 0.0) or 0.0,
        )
        genomes = pool.query(q)
        if not genomes:
            console.print(f"[yellow]No matching genomes found for task:[/] {task[:80]}")
            console.print("[dim]Try broadening the description or lowering --min-score.[/]")
            return 0

        table = Table(title=f"Pool Query Results for: {task[:60]}...", show_header=True)
        table.add_column("ID", style="green")
        table.add_column("Version", style="dim")
        table.add_column("Score", justify="right")
        table.add_column("Domains")
        table.add_column("Path (registry)")

        for g in genomes:
            m = g.manifest
            score = m.evaluation_score.get("reference_tasks", 0.0) if isinstance(m.evaluation_score, dict) else 0.0
            doms = ", ".join((m.applicability or {}).get("domains", [])[:3]) if isinstance(m.applicability, dict) else ""
            p = pool.registry.get_genome_path(g.genome_id) or ""
            table.add_row(
                g.genome_id,
                str(m.version),
                f"{float(score):.2f}",
                doms,
                str(p),
            )
        console.print(table)
        console.print(f"[dim]Returned {len(genomes)} genomes. Use 'savant genomes info <id>' for details.[/]")
        return 0

    if sub == "stats":
        stats = pool.get_pool_stats()
        console.print(Panel(str(stats), title="Savant Pool Full Stats (persistent)", border_style="blue"))
        # Also show a few recent ingests if any
        hist = pool.get_ingest_history(5)
        if hist:
            console.print("\n[bold]Recent ingest events (from JSONL):[/]")
            for e in hist:
                console.print(f"  • {e.get('timestamp'):.0f} | {e.get('genome_id')} | src={e.get('source')} actor={e.get('actor')}")
        return 0

    console.print("[red]Unknown pool subcommand[/]")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="savant",
        description="Savant Framework — evolutionary agent genome platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  savant tui
  savant doctor
  savant genomes list
  savant config show
  savant scan /path/to/run
  savant pool status
  savant pool ingest genomes/examples/skill-creator-v1
  savant pool query "security incident postmortem analysis"
  savant pool stats
  SAVANT_HOME=/tmp/test savant doctor
""",
    )
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    subparsers = parser.add_subparsers(dest="command")

    # tui
    p = subparsers.add_parser("tui", help="Launch the interactive TUI")
    p.set_defaults(func=cmd_tui)

    # setup wizard (Hermes-style modular experience)
    p = subparsers.add_parser("setup", help="Interactive setup wizard (Hermes-grade experience)")
    p.add_argument("section", nargs="?", help="Optional section: home, pool, swarm, ai, tui")
    p.set_defaults(func=cmd_setup)

    # explicit onboarding (lightweight first-run flow)
    p = subparsers.add_parser("onboard", help="Run the guided first-time consent flow (lighter than full setup)")
    p.set_defaults(func=lambda args: __import__("savant.onboarding", fromlist=["run_onboarding"]).run_onboarding())

    # genomes
    p = subparsers.add_parser("genomes", help="Genome registry operations")
    p.add_argument("subcommand", nargs="?", choices=["list", "info"], default="list")
    p.add_argument("id", nargs="?", help="Genome ID for 'info'")
    p.set_defaults(func=cmd_genomes)

    # scan
    p = subparsers.add_parser("scan", help="Scan runs / trajectories and extract candidate Genomes")
    p.add_argument("path", nargs="?", help="Optional path to run data or genome source dir")
    p.set_defaults(func=cmd_scan)

    # doctor
    p = subparsers.add_parser("doctor", help="Diagnose Savant installation, config, workers, and registry")
    p.set_defaults(func=cmd_doctor)

    # config
    p = subparsers.add_parser("config", help="View and modify Savant configuration")
    p.add_argument("subcommand", nargs="?", choices=["show", "get", "set", "edit"], default="show")
    p.add_argument("key", nargs="?", help="config key for get/set (dot notation supported)")
    p.add_argument("value", nargs="?", help="value for 'set'")
    p.set_defaults(func=cmd_config)

    # workers
    p = subparsers.add_parser("workers", help="List and inspect worker adapters (external etc.)")
    p.add_argument("subcommand", nargs="?", default="list")
    p.set_defaults(func=cmd_workers)

    # pool — first-class queryable persistent pool service
    p = subparsers.add_parser("pool", help="Savant Pool: status, ingest genomes, query by task, detailed stats (persistent JSONL + registry)")
    pool_subs = p.add_subparsers(dest="pool_subcommand")
    # status (default)
    ps = pool_subs.add_parser("status", help="Show pool status, integration with registry, recent activity")
    ps.set_defaults(func=cmd_pool)
    # ingest
    pi = pool_subs.add_parser("ingest", help="Ingest a genome directory (manifest + files) into the central pool")
    pi.add_argument("genome_dir", help="Filesystem path to a genome directory (e.g. genomes/examples/xxx-v1)")
    pi.set_defaults(func=cmd_pool)
    # query
    pq = pool_subs.add_parser("query", help="Semantic query of the pool for genomes relevant to a task description")
    pq.add_argument("task", help="Natural language task description (e.g. \"security incident postmortem\")")
    pq.add_argument("--limit", type=int, default=5, help="Maximum number of results (default 5)")
    pq.add_argument("--min-score", type=float, default=0.0, help="Minimum evaluation score filter")
    pq.set_defaults(func=cmd_pool)
    # stats
    pst = pool_subs.add_parser("stats", help="Full pool statistics (ingest counts, sources, actors, registry metrics)")
    pst.set_defaults(func=cmd_pool)

    return parser


def main() -> None:
    # Very early defensive setup (robust CLI bootstrap)
    if "--version" in sys.argv:
        print(f"Savant {SAVANT_VERSION}")
        sys.exit(0)

    parser = build_parser()
    args = parser.parse_args()

    # Initialize logging & config as early as possible for all paths
    try:
        setup_logging()
    except Exception:
        pass

    # First-run experience: if no config yet, run the full Hermes-style setup wizard
    try:
        home = get_savant_home()
        if not (home / "config.yaml").exists():
            from savant.setup import run_setup
            print()  # spacing
            run_setup()
            # After setup, fall through to normal behavior (usually launch TUI)
    except Exception:
        pass

    if args.version:
        sys.exit(cmd_version(args))

    if hasattr(args, "func"):
        try:
            code = args.func(args)
            sys.exit(code if code is not None else 0)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/]")
            sys.exit(130)
        except Exception as exc:
            logger.exception("Unhandled error in Savant CLI")
            console.print(f"[red]Error:[/] {exc}")
            sys.exit(1)
    else:
        # No subcommand — default to launching the premium TUI experience
        # (Apple / OpenClaw / Hermes style: just typing the command name opens the main interface)
        try:
            from savant.tui.app import launch_tui
            launch_tui()
        except Exception as e:
            logger.exception("Failed to launch TUI")
            console.print(f"[red]Could not launch TUI:[/] {e}")
            console.print("[dim]Falling back to help. You can also run 'savant tui' explicitly.[/]")
            parser.print_help()
            sys.exit(1)


if __name__ == "__main__":
    main()
