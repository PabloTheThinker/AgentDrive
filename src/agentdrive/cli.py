"""
Agent Drive CLI - Production-grade command line interface.

Just typing `agentdrive` launches the full interactive TUI experience.

Subcommand structure:
  agentdrive                    # Default: launch the TUI (or REPL with --cli / AGENTDRIVE_NO_TUI=1)
  agentdrive repl               # Operator REPL — same handlers as subcommands
  agentdrive board              # Launch localhost Kanban Mission Board (web) — like `hermes dashboard`
  agentdrive kanban             # Alias for board
  agentdrive mission            # Full real-time Mission Control Tower (loop + fabric + static fire)
  agentdrive mcp serve          # MCP server for Grok /mcp, Claude Code, Cursor, Codex (Experience Graph + DNA)
  agentdrive mcp config         # Print exact config snippets for any AI CLI
  agentdrive setup              # Full interactive setup wizard (strongly recommended first time)
  agentdrive setup swarm        # Only reconfigure Swarm & Sub-Agent DNA policies
  agentdrive tui [--mission ws://<tailscale-magic-dns>/]  # TUI with cross-process MC client (no port needed with tailscale serve)
  agentdrive onboard            # Lightweight first-run consent flow
  agentdrive doctor
  agentdrive drive ...              agentdrive pool ... (alias)
  agentdrive think "question"
  agentdrive learnings log|list|search
  agentdrive harness compose
  agentdrive graph context-pack|record|suggest
  agentdrive eval replay <artifact.json>
  agentdrive commands list|tree|search

First run (or `agentdrive setup`) gives you an interactive wizard that detects
your AI agents, sets up your AgentDrives, and asks for consent on automatic sub-agent
pool attachment — the core of the living swarm DNA system.

Integrates config, logging, registry, workers/adapters, and the persistent AgentDrive.
User sovereignty is absolute.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markup import escape as rich_escape
from rich.panel import Panel
from rich.table import Table


def get_tailscale_ipv4() -> str | None:
    """Return the machine's primary Tailscale IPv4 address if Tailscale is running."""
    try:
        # Best: official tailscale CLI
        out = subprocess.check_output(["tailscale", "ip", "-4"], text=True, timeout=2.0).strip()
        if out:
            return out.splitlines()[0].strip()
    except Exception:
        pass

    try:
        # Fallback: parse `ip addr`
        out = subprocess.check_output(["ip", "-4", "addr", "show", "tailscale0"], text=True, timeout=2.0)
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                return line.split()[1].split("/")[0]
    except Exception:
        pass

    return None


def get_tailscale_dns_name() -> str | None:
    """Return the Tailscale MagicDNS name for this machine (e.g. mymachine.mytailnet.ts.net)."""
    try:
        out = subprocess.check_output(["tailscale", "status", "--json"], text=True, timeout=3.0)
        data = json.loads(out)
        dns = data.get("Self", {}).get("DNSName", "").rstrip(".")
        if dns:
            return dns
    except Exception:
        pass
    return None


from agentdrive import (
    AGENTDRIVE_VERSION,
    GenomeRegistry,
    get_agentdrive_home,
    get_config_value,
    get_logger,
    load_config,
    save_config,
    set_config_value,
    setup_logging,
)
from agentdrive.drive.drive import DriveQuery, get_default_drive

# Genome for direct loading during ingest (pool will persist via registry)
from agentdrive.genome.models import Genome
from agentdrive.cli_repl import cmd_repl
from agentdrive.cli_surface import (
    build_help_epilog,
    cmd_commands,
    cmd_eval,
    cmd_golden_path,
    cmd_graph,
    cmd_harness,
    cmd_learnings,
    cmd_session,
    cmd_skills,
    cmd_think,
)
from agentdrive.setup import cmd_setup
from agentdrive.workers import get_default_adapter

# MCP server (for AI CLI integrations: Grok, Claude Code, Cursor, etc.)
try:
    from agentdrive.adapters.mcp_server import run_mcp_server
except Exception:
    run_mcp_server = None  # type: ignore[assignment]

console = Console()
logger = get_logger("agentdrive.cli")


def _print_banner() -> None:
    from agentdrive.constants import AGENTDRIVE_INSTANCE_NAME

    name = AGENTDRIVE_INSTANCE_NAME
    console.print(
        f"[bold cyan]{name}[/] — AgentDrive\n"
        f"[dim]v{AGENTDRIVE_VERSION}  •  {get_agentdrive_home()}[/]\n"
    )
    # Prominently provide the localhost Kanban / Mission Board on every launch
    # (Hermes-style experience: user gets a real web Kanban immediately)
    console.print(
        "[dim]Mission Kanban Board (localhost):[/] [bold green]http://127.0.0.1:8421/[/]   "
        "[dim](run[/] [cyan]agentdrive board[/] [dim]or[/] [cyan]agentdrive mission[/][dim])[/]"
    )


def cmd_version(args: argparse.Namespace) -> int:
    console.print(f"AgentDrive {AGENTDRIVE_VERSION}")
    return 0


def cmd_cap(args: argparse.Namespace) -> int:
    """Mint or inspect Mission Control capabilities."""
    sub = getattr(args, "cap_subcommand", None)
    if sub == "mint-mission":
        from agentdrive.mission_control.authz import mint_mission_control_cap

        command = getattr(args, "command", "*")
        cap_id = mint_mission_control_cap(command=command)
        console.print(cap_id)
        console.print(
            "[dim]Use this cap for mutating Mission Control commands:[/]\n"
            f"  [cyan]Authorization: Bearer {cap_id}[/]\n"
            f"  or include [cyan]\"cap_id\": \"{cap_id}\"[/] in WS command JSON"
        )
        return 0

    console.print("[red]Unknown cap subcommand.[/] Try: agentdrive cap mint-mission")
    return 1


# Legacy UI layer removed.
# New Mission Control is the unified real-time interface going forward.


def cmd_mission(args: argparse.Namespace) -> int:
    """Launch the new real-time Mission Control for AgentDrive."""
    setup_logging()
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Missing web dependency.[/] Install with: pip install 'agentdrive[web]'")
        return 1

    from agentdrive.mission_control.server import create_mission_control_app

    host = getattr(args, "host", "0.0.0.0")
    port = getattr(args, "port", 8421)

    # Tailnet mode: bind directly to the Tailscale IP when available (Clawdbot-style "tailnet" bind)
    ts_ip = get_tailscale_ipv4()
    bind_host = ts_ip if ts_ip else host

    console.print(f"[bold cyan]Starting AgentDrive Mission Control[/] on http://{bind_host}:{port}")
    if ts_ip:
        console.print(f"[green]Use this on your Tailnet:[/] [bold]http://{ts_ip}:{port}[/]")
    else:
        console.print("[yellow]No Tailscale IP detected — running on localhost only[/]")

    console.print("This is the new unified real-time view of the entire system (loop + fabric + static fire).")
    console.print(f"[green]Mission Kanban Board also available at:[/] [bold]http://{bind_host}:{port}/[/]  (or use [cyan]agentdrive board[/])")
    console.print("[yellow]Local operator control surface[/] (commands like start_static_fire / parent_decision are trusted localhost only; see server.py SECURITY note + AGENTS.md).")

    uvicorn.run(
        create_mission_control_app,
        host=bind_host,
        port=port,
        factory=True,
    )
    return 0


def cmd_board(args: argparse.Namespace) -> int:
    """Launch the localhost Mission Kanban Board (web UI).

    This is the AgentDrive equivalent of `hermes dashboard` Kanban surface.
    Starts the real-time Mission Control server and prints the direct
    Kanban URL. The board shows persistent missions flowing through
    Pending → Running → Done / Failed lanes, integrated with the live
    6-step loop and experience fabric.
    """
    setup_logging()
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Missing web dependency.[/] Install with: pip install 'agentdrive[web]'")
        return 1

    from agentdrive.mission_control.server import create_mission_control_app

    host = getattr(args, "host", "0.0.0.0")
    port = getattr(args, "port", 8421)

    # Tailnet mode: bind directly to the Tailscale IP (Clawdbot-style tailnet bind)
    ts_ip = get_tailscale_ipv4()
    bind_host = ts_ip if ts_ip else host

    kanban_url = f"http://{bind_host}:{port}/#kanban"

    console.print()
    console.print("[bold cyan]AgentDrive Mission Kanban Board[/]")
    console.print(f"  [bold green]{kanban_url}[/]")
    if ts_ip:
        console.print(f"  [green]Use on your Tailnet:[/green] [bold]{kanban_url}[/]")
    console.print()
    console.print("Persistent lanes: Pending → Running → Done | Failed")
    console.print("Real-time integration with the 6-step loop + experience fabric.")
    console.print("Full Mission Control Tower also available at the root URL above.")
    console.print("[dim]Local operator surface — commands and visibility stay on your machine.[/]")
    console.print()

    uvicorn.run(
        create_mission_control_app,
        host=bind_host,
        port=port,
        factory=True,
    )
    return 0


def cmd_tui(args: argparse.Namespace) -> int:
    """Launch the interactive TUI, optionally cross-process wired to a remote Mission Control Tower.

    Supports --mission / --mission-url so a standalone TUI can subscribe to a separate
    `agentdrive mission` process (the Control Tower attached to an
    IntegratedRealTimeEvolutionSystem in the stabilization-wave-20260531 context).
    The `mc` / `mission` command inside the TUI will then render live unified view
    (6-step, fabric, events, commands) with full parity via the resilient client.
    Also honors AGENTDRIVE_MISSION_URL for config-driven discovery.
    """
    setup_logging()
    mission_url = getattr(args, "mission_url", None) or getattr(args, "mission", None)
    if not mission_url:
        import os as _os
        mission_url = _os.environ.get("AGENTDRIVE_MISSION_URL") or _os.environ.get("AGENTDRIVE_MC_URL")
    try:
        from agentdrive.tui.app import launch_tui

        launch_tui(mission_url=mission_url)
    except Exception as e:
        logger.exception("Failed to launch TUI")
        console.print(f"[red]Could not launch TUI:[/] {rich_escape(str(e))}")
        return 1
    return 0


def cmd_genomes(args: argparse.Namespace) -> int:
    setup_logging()
    reg = GenomeRegistry()
    # All logic lives in agentdrive.genomes_api; this function is presentation only.
    from agentdrive import genomes_api

    if args.subcommand == "list" or not args.subcommand:
        from agentdrive.tui.chrome import (
            Palette,
            Tree,
            TreeRow,
            info_line,
            section_panel,
        )
        from agentdrive.tui.skin_engine import skin

        entries = genomes_api.list_genomes(registry=reg)
        p = Palette(skin)

        if not entries:
            console.print()
            console.print(
                info_line(
                    f"No genomes registered yet. Run [agentdrive.genome]agentdrive scan <dir>[/] "
                    f"or drop genomes into [agentdrive.genome]{reg.root}[/].",
                    palette=p,
                )
            )
            return 0

        rows = []
        for e in entries:
            secondary = str(e.path) if e.path else ""
            if e.is_ultimate:
                label = (
                    f"[bold magenta]◆ PROMOTED[/] [bold]{e.dir_name}[/] "
                    f"[dim]{e.ultimate_version or ''}[/]"
                )
            else:
                label = f"[bold]{e.dir_name}[/]"
            rows.append(TreeRow(label=label, secondary=secondary))

        console.print()
        console.print(
            section_panel(
                Tree(rows, palette=p),
                title=f"Registered Genomes  ({len(entries)})",
                palette=p,
            )
        )
        return 0

    if args.subcommand == "info":
        if not args.id:
            console.print("[red]Usage: agentdrive genomes info <genome-id>[/]")
            return 1
        info = genomes_api.get_genome(args.id, registry=reg)
        if info is None:
            console.print(f"[red]Genome not found:[/] {args.id}")
            return 1
        console.print(
            Panel(
                f"[bold]{info.id}[/]\n"
                f"Version: {info.version}\n"
                f"Authors: {len(info.authors)}\n"
                f"Applicability: {info.applicability}\n"
                f"Eval scores: {info.evaluation_score}",
                title=f"Genome: {args.id}",
                border_style="cyan",
            )
        )
        return 0

    if args.subcommand == "search":
        from agentdrive.tui.chrome import (
            Palette,
            Tree,
            TreeRow,
            info_line,
            section_panel,
        )
        from agentdrive.tui.skin_engine import skin

        query = " ".join(getattr(args, "id", None) or []).strip()
        if not query:
            console.print("[red]Usage: agentdrive genomes search <query>[/]")
            return 1

        matches = genomes_api.search_genomes(query)
        p = Palette(skin)

        if not matches:
            console.print()
            console.print(
                info_line(
                    f"No matching genomes for [agentdrive.genome]{query[:80]}[/]. "
                    "Try broadening the description or use "
                    "[agentdrive.genome]agentdrive drive query[/].",
                    palette=p,
                )
            )
            return 0

        rows = []
        for idx, m in enumerate(matches, 1):
            dom = ", ".join(m.domains[:2]) or "—"
            label = f"[dim]{idx:>2}[/]  [bold]{m.genome_id}[/]  [dim]@{m.version}[/]"
            secondary = f"{dom}  · score {m.score:.2f}"
            if m.path:
                secondary += f"  · {m.path}"
            rows.append(TreeRow(label=label, secondary=secondary))

        console.print()
        console.print(
            section_panel(
                Tree(rows, palette=p),
                title=f"Genome Search  ({len(matches)})  ·  {query[:60]}",
                palette=p,
            )
        )
        return 0

    console.print("[red]Unknown genomes subcommand[/]")
    return 1


def cmd_patterns(args: argparse.Namespace) -> int:
    """Fabric-style pattern-as-genome catalog (list / show / apply)."""
    setup_logging()
    from agentdrive.patterns import (
        PatternNotFoundError,
        apply_pattern,
        get_pattern,
        list_patterns,
    )

    subcommand = getattr(args, "patterns_subcommand", None) or "list"

    if subcommand == "list":
        patterns = list_patterns()
        if not patterns:
            console.print("[yellow]No patterns found.[/]")
            console.print(
                "[dim]Bundled patterns live under genomes/patterns/; "
                "user overlays go in ~/.agentdrive/patterns/[/]"
            )
            return 0

        table = Table(title=f"Patterns ({len(patterns)})", show_header=True)
        table.add_column("Name", style="bold cyan")
        table.add_column("Source")
        table.add_column("Version")
        table.add_column("Path", overflow="fold")
        for record in patterns:
            version = record.manifest.version if record.manifest else "-"
            table.add_row(record.name, record.source, version, str(record.path))
        console.print(table)
        return 0

    if subcommand == "show":
        name = getattr(args, "pattern_name", None)
        if not name:
            console.print("[red]Usage: agentdrive patterns show <name>[/]")
            return 1
        try:
            record = get_pattern(name)
        except PatternNotFoundError:
            console.print(f"[red]Pattern not found:[/] {name}")
            return 1

        manifest = record.manifest
        title = manifest.id if manifest else name
        version = manifest.version if manifest else "-"
        description = ""
        if record.framework:
            description = str(record.framework.get("description", "")).strip()
        system_path = record.path / "system.md"
        system_preview = ""
        if system_path.is_file():
            system_preview = system_path.read_text(encoding="utf-8").strip()
            if len(system_preview) > 1200:
                system_preview = system_preview[:1200] + "\n…"

        body = (
            f"[bold]{title}[/]  v{version}\n"
            f"Source: {record.source}\n"
            f"Path: {record.path}\n"
        )
        if description:
            body += f"\n{description}\n"
        if system_preview:
            body += f"\n[dim]system.md preview:[/]\n{system_preview}"
        console.print(Panel(body, title=f"Pattern: {name}", border_style="cyan"))
        return 0

    if subcommand == "apply":
        name = getattr(args, "pattern_name", None)
        if not name:
            console.print("[red]Usage: agentdrive patterns apply <name> [--input TEXT][/]")
            return 1
        input_text = getattr(args, "input", None)
        if input_text is None:
            if not sys.stdin.isatty():
                input_text = sys.stdin.read()
            else:
                input_text = ""
        try:
            prompt = apply_pattern(name, input_text)
        except PatternNotFoundError:
            console.print(f"[red]Pattern not found:[/] {name}")
            return 1
        console.print(prompt)
        return 0

    if subcommand == "import-fabric":
        from agentdrive.patterns.fabric_import import (
            import_fabric_corpus,
            import_fabric_pattern,
            resolve_fabric_root,
        )

        source = getattr(args, "source", None)
        try:
            fabric_root = resolve_fabric_root(source)
        except FileNotFoundError as exc:
            console.print(f"[red]{exc}[/]")
            return 1

        pattern_name = getattr(args, "pattern", None)
        overwrite = bool(getattr(args, "overwrite", False))
        limit = int(getattr(args, "limit", 10) or 10)

        try:
            if pattern_name:
                dest = import_fabric_pattern(
                    fabric_root,
                    pattern_name,
                    get_agentdrive_home() / "patterns",
                    overwrite=overwrite,
                )
                imported = [dest]
            else:
                imported = import_fabric_corpus(
                    fabric_root,
                    limit=limit,
                    overwrite=overwrite,
                )
        except Exception as exc:
            console.print(f"[red]Fabric import failed:[/] {exc}")
            return 1

        if not imported:
            console.print("[yellow]No Fabric patterns imported.[/]")
            console.print(
                "[dim]Use --overwrite to replace existing entries or --pattern NAME for one pattern.[/]"
            )
            return 0

        console.print(
            f"[green]Imported {len(imported)} Fabric pattern(s) from[/] {fabric_root}"
        )
        for path in imported:
            console.print(f"  [cyan]{path.name}[/] → {path}")
        return 0

    console.print("[red]Unknown patterns subcommand[/]")
    return 1


def cmd_sprint(args: argparse.Namespace) -> int:
    """gstack-style sprint chains with STOP gates (ship / ack / status)."""
    setup_logging()
    from agentdrive.sprint import CheckpointPending, CheckpointStore, run_ship_chain

    subcommand = getattr(args, "sprint_subcommand", None) or "status"

    if subcommand == "ship":
        dry_run = bool(getattr(args, "dry_run", False))
        ack_ids: list[str] = []
        ack = getattr(args, "ack", None)
        if ack:
            ack_ids = [ack]
        pytest_path = getattr(args, "pytest_path", "tests") or "tests"
        reset = bool(getattr(args, "reset", False))
        try:
            results = run_ship_chain(
                dry_run=dry_run,
                ack_ids=ack_ids,
                pytest_path=pytest_path,
                reset=reset,
            )
        except CheckpointPending as exc:
            console.print()
            console.print(
                Panel(
                    f"[bold yellow]STOP gate[/] at step [cyan]{exc.step_id}[/]\n\n"
                    f"{rich_escape(exc.message)}\n\n"
                    f"Checkpoint: [bold]{exc.checkpoint_id}[/]\n"
                    f"Resume: [dim]agentdrive sprint ship --ack {exc.checkpoint_id}[/]",
                    title="Sprint paused",
                    border_style="yellow",
                )
            )
            return 2

        console.print()
        table = Table(title="Ship sprint chain", show_header=True)
        table.add_column("Step", style="cyan")
        table.add_column("Status")
        table.add_column("Message", overflow="fold")
        for result in results:
            status = "[green]ok[/]" if result.success else "[red]fail[/]"
            table.add_row(result.step_id, status, result.message)
        console.print(table)
        if dry_run:
            console.print("[dim]Dry-run: pytest and STOP gates bypassed.[/]")
        else:
            console.print("[green]Ship chain complete.[/]")
        return 0 if all(r.success for r in results) else 1

    if subcommand == "ack":
        cp_id = getattr(args, "checkpoint_id", None)
        if not cp_id:
            console.print("[red]Usage: agentdrive sprint ack <checkpoint-id>[/]")
            return 1
        chain_id = getattr(args, "chain_id", "ship") or "ship"
        store = CheckpointStore(chain_id)
        if store.ack(cp_id):
            console.print(f"[green]Acked[/] checkpoint {cp_id} on chain {chain_id}")
            return 0
        console.print(f"[red]Checkpoint not found:[/] {cp_id}")
        return 1

    if subcommand == "status":
        chain_id = getattr(args, "chain_id", "ship") or "ship"
        store = CheckpointStore(chain_id)
        pending = store.list_pending()
        state_path = store.path
        console.print()
        console.print(f"[bold]Sprint chain[/] [cyan]{chain_id}[/]")
        console.print(f"[dim]State: {state_path}[/]")
        if not pending:
            console.print("[green]No pending checkpoints.[/]")
            return 0
        table = Table(title=f"Pending checkpoints ({len(pending)})", show_header=True)
        table.add_column("ID", style="bold")
        table.add_column("Step")
        table.add_column("Message", overflow="fold")
        for cp in pending:
            table.add_row(cp["id"], cp.get("step_id", ""), cp.get("message", ""))
        console.print(table)
        return 0

    console.print("[red]Unknown sprint subcommand[/]")
    return 1


def cmd_scan(args: argparse.Namespace) -> int:
    setup_logging()

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

    console.print(
        "[yellow]Scan is a stub in v0.1. Real scanners + external run ingestion coming in next iteration.[/]"
    )
    console.print(f"Registry location: {reg.root}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    setup_logging()
    return _run_doctor(verbose=getattr(args, "verbose", False))


def cmd_deps_check(args: argparse.Namespace) -> int:
    """Lightweight dependency compatibility report (core of the update framework)."""
    setup_logging()
    from importlib.metadata import PackageNotFoundError, version

    from rich.console import Console
    from rich.table import Table

    console = Console()

    key_packages = [
        ("httpx", "HTTP client (core for providers, web, runtime)"),
        ("fastapi", "Web surface"),
        ("uvicorn", "ASGI server"),
        ("cryptography", "Ed25519 signatures + KDF for grants/trust"),
        ("pydantic", "All data models"),
        ("pytest-asyncio", "Async test support"),
    ]

    table = Table(title="AgentDrive Dependency Compatibility", show_header=True)
    table.add_column("Package", style="bold")
    table.add_column("Installed")
    table.add_column("Declared (pyproject)")
    table.add_column("Notes")

    # Read declared bounds from the installed package metadata / pyproject if possible
    # For v1 we do a best-effort read of the current environment vs common knowledge
    declared = {
        "httpx": ">=0.27 (current framework target: 0.28+)",
        "fastapi": ">=0.115 (current: 0.136+)",
        "uvicorn": ">=0.30 (current: 0.48+)",
        "cryptography": ">=46 (current: 48+)",
        "pydantic": ">=2.13",
        "pytest-asyncio": ">=0.23",
    }

    for pkg, desc in key_packages:
        try:
            inst = version(pkg)
        except PackageNotFoundError:
            inst = "not installed"

        note = declared.get(pkg, "")
        if pkg == "httpx" and "0.28" in inst:
            note += " | StarletteDeprecationWarning on testclient (library-level; tracked)"
        table.add_row(pkg, inst, declared.get(pkg, "?"), desc)

    console.print(table)
    console.print(
        "\nSee [bold]docs/DEPENDENCY_UPDATES.md[/] for the full update framework and process."
    )
    console.print("Run under a fresh venv with proposed pins to validate future bumps.")
    return 0


def _print_doctor_verbose_diagnostics(palette: Any) -> None:
    """Extra subsystem counters surfaced by ``agentdrive doctor --verbose``."""
    from agentdrive.constants import get_default_drive_path
    from agentdrive.tui.chrome import Section, section_panel

    rows: list[tuple[str, str]] = []

    # Reconciliation state
    try:
        from agentdrive.reconciliation import get_default_reconciliation_runner

        rec = get_default_reconciliation_runner()
        state = rec._load_state()
        last_scan = state.get("last_scan_iso", "n/a")
        known_count = len(state.get("known_genome_ids") or [])
        rows.append(("Reconciliation", f"last_scan={last_scan}, known_genomes={known_count}"))
    except Exception as exc:
        rows.append(("Reconciliation", f"unavailable ({exc})"))

    # Knowledge graph edge count
    try:
        edges_path = get_default_drive_path() / "knowledge" / "edges.jsonl"
        if edges_path.is_file():
            kg_lines = sum(1 for line in edges_path.read_text(encoding="utf-8").splitlines() if line.strip())
        else:
            kg_lines = 0
        rows.append(("Knowledge graph", f"{kg_lines} edges.jsonl lines"))
    except Exception as exc:
        rows.append(("Knowledge graph", f"unavailable ({exc})"))

    # Quarantine posture
    try:
        from agentdrive.security import get_security_posture

        posture = get_security_posture()
        rows.append(("Quarantine", f"{posture.quarantined_items} quarantined items"))
    except Exception as exc:
        rows.append(("Quarantine", f"unavailable ({exc})"))

    # Learnings store
    try:
        from agentdrive.learnings import LearningsStore, resolve_learnings_slug

        slug = resolve_learnings_slug()
        learnings_count = LearningsStore(slug=slug).count()
        rows.append(("Learnings", f"{learnings_count} entries (slug={slug})"))
    except ImportError:
        rows.append(("Learnings", "module not installed"))
    except Exception as exc:
        rows.append(("Learnings", f"unavailable ({exc})"))

    # Sprint checkpoints (optional module)
    try:
        from agentdrive.sprint import CheckpointStore

        pending = CheckpointStore("ship").list_pending()
        rows.append(("Sprint checkpoints", f"{len(pending)} pending"))
    except ImportError:
        rows.append(("Sprint checkpoints", "module not installed"))
    except Exception as exc:
        rows.append(("Sprint checkpoints", f"unavailable ({exc})"))

    # Experience layer file counts
    try:
        drive_path = get_default_drive_path()

        def _count_files(rel: str) -> int:
            root = drive_path / rel
            if not root.is_dir():
                return 0
            return sum(1 for p in root.rglob("*") if p.is_file())

        living_count = _count_files("living-experience")
        experience_count = _count_files("experience")
        rows.append(
            (
                "Experience layer",
                f"{living_count} living-experience files, {experience_count} experience files",
            )
        )
    except Exception as exc:
        rows.append(("Experience layer", f"unavailable ({exc})"))

    console.print(
        section_panel(
            Section("Subsystem counters", rows, palette=palette, key_width=18),
            title="Verbose diagnostics",
            palette=palette,
        )
    )


def _run_doctor(verbose: bool = False) -> int:
    """Animated step-by-step health check with a final result panel."""
    from rich.text import Text

    from agentdrive.config import get_instance_name
    from agentdrive.constants import get_agentdrive_home
    from agentdrive.tui.chrome import (
        Palette,
        Section,
        Tree,
        TreeRow,
        result_panel,
        section_panel,
    )
    from agentdrive.tui.loading import StepProgress
    from agentdrive.tui.skin_engine import skin

    p = Palette(skin)
    home = get_agentdrive_home()

    # Pre-flight panel
    instance_name = get_instance_name()
    console.print()
    console.print(
        section_panel(
            Section(
                "Doctor",
                [
                    ("instance", f"[bold]{instance_name}[/]"),
                    ("home", f"[agentdrive.genome]{home}[/]"),
                    ("version", f"v{AGENTDRIVE_VERSION}"),
                ],
                palette=p,
            ),
            title="◆ AgentDrive health check",
            palette=p,
        )
    )
    console.print()

    checks = [
        "Home directory",
        "Config",
        "Registry",
        "Pool",
        "Worker adapter",
        "Core dependencies",
        "MCP bridge",
        "AI provider",
    ]

    steps = StepProgress(console, checks, title="Running checks")
    steps.start()

    results: list[tuple[str, bool, str]] = []  # (check, ok, detail)
    pool = None
    ingests = 0
    total_genomes = 0

    # 1. Home directory (first-run / empty-drive tolerant)
    try:
        from agentdrive.config import ensure_agentdrive_home

        ensure_agentdrive_home()
        missing = []
        for sub in ("genomes", "logs", "cache", "drive", "swarms"):
            sub_path = home / sub
            if not (sub_path.exists() and sub_path.is_dir()):
                missing.append(sub)
        if missing:
            # Still report but actionable for new users; many are auto-created by Drive init.
            steps.advance(f"partial ({', '.join(missing)} auto-created on access)")
            results.append(
                (
                    "Home directory",
                    True,
                    f"ready (missing {', '.join(missing)} will self-heal on first Drive use; run `agentdrive setup` for full init)",
                )
            )
        else:
            steps.advance(f"{home}")
            results.append(("Home directory", True, "all subdirs present"))
    except Exception as e:
        steps.fail(str(e)[:60])
        results.append(
            (
                "Home directory",
                False,
                f"{e} — ensure AGENTDRIVE_HOME is a writable directory (or unset for default ~/.agentdrive)",
            )
        )

    # 2. Config
    try:
        cfg_path = home / "config.yaml"
        present = cfg_path.exists()
        log_level = get_config_value("agentdrive.log_level", "INFO")
        if present:
            steps.advance(f"config.yaml · log {log_level}")
            results.append(("Config", True, f"present · log_level={log_level}"))
        else:
            steps.advance(f"using defaults · log {log_level}")
            results.append(("Config", True, f"defaults · log_level={log_level}"))
    except Exception as e:
        steps.fail(str(e)[:60])
        results.append(("Config", False, str(e)))

    # 3. Pool + registry (use the live drive registry — not a standalone GenomeRegistry)
    try:
        pool = get_default_drive()
        pstats = pool.get_pool_stats()
        ingests = pstats.get("ingest_events", 0)
        total_genomes = pstats.get("total_genomes", 0)
        gcount = total_genomes or len(pool.registry.list_genomes())
        steps.advance(f"{gcount} genome{'s' if gcount != 1 else ''}")
        results.append(
            ("Registry", True, f"{gcount} genome{'s' if gcount != 1 else ''} registered")
        )
        if ingests == 0 and gcount == 0:
            detail = "empty (fresh install) — run `agentdrive reconcile seed-experience-v3` or `agentdrive setup`"
            steps.advance("empty (self-healing ready)")
        else:
            detail = f"{ingests} ingest event{'s' if ingests != 1 else ''}"
            steps.advance(f"{ingests} ingest event{'s' if ingests != 1 else ''}")
        results.append(("Pool", True, detail))
    except Exception as e:
        steps.fail(str(e)[:60])
        results.append(("Registry", False, str(e)))
        results.append(
            (
                "Pool",
                False,
                f"{e} — try `agentdrive doctor` again after `agentdrive setup` or setting a writable AGENTDRIVE_HOME",
            )
        )

    # 5. Worker adapter
    try:
        adapter = get_default_adapter()
        worker = adapter.as_worker()
        healthy = worker.health_check()
        caps = worker.get_capabilities()
        if healthy:
            steps.advance(f"{adapter.get_name()} · {len(caps.supported_domains)} domains")
            results.append(
                (
                    "Worker adapter",
                    True,
                    f"{adapter.get_name()} healthy · {len(caps.supported_domains)} domain(s) · concurrency {caps.max_concurrency}",
                )
            )
        else:
            steps.fail("adapter unhealthy")
            results.append(("Worker adapter", False, "adapter reports unhealthy"))
    except Exception as e:
        steps.fail(str(e)[:60])
        results.append(("Worker adapter", False, str(e)))

    # 6. Core dependencies
    try:
        import pydantic  # noqa
        import yaml  # noqa
        import rich  # noqa
        import httpx  # noqa

        steps.advance("pydantic, yaml, rich, httpx")
        results.append(("Core dependencies", True, "all importable"))
    except Exception as e:
        steps.fail(str(e)[:60])
        results.append(("Core dependencies", False, str(e)))

    # 7. MCP bridge (any-model connectivity)
    try:
        from agentdrive.adapters.mcp_config import resolve_mcp_launcher, run_mcp_doctor

        launcher = resolve_mcp_launcher()
        mcp_report = run_mcp_doctor()
        tool_count = mcp_report.get("tool_count", 0)
        if mcp_report.get("ok"):
            steps.advance(f"{tool_count} tools · {launcher.method}")
            results.append(
                (
                    "MCP bridge",
                    True,
                    f"{tool_count} tools · {launcher.method} → {launcher.command}",
                )
            )
        else:
            steps.fail("mcp not ready")
            results.append(
                (
                    "MCP bridge",
                    False,
                    "run `agentdrive mcp install` (pip install agentdrive[mcp])",
                )
            )
    except Exception as e:
        steps.fail(str(e)[:60])
        results.append(("MCP bridge", False, str(e)))

    # 8. AI provider
    provider_suggestion = ""
    try:
        from agentdrive.providers import get, load_config_provider

        cfg = load_config_provider()
        if cfg and cfg[0]:
            profile = get(cfg[0])
            pname = profile.display_name if profile else cfg[0]
            model = cfg[1] or (profile.default_model if profile else "?")
            if profile and profile.has_key():
                steps.advance(f"{pname} · {model}")
                results.append(("AI provider", True, f"{pname} · {model} · ✓ key set"))
            else:
                steps.advance(f"{pname} (no key)")
                results.append(("AI provider", True, f"{pname} · {model} · no key"))
                provider_suggestion = f"agentdrive provider key {cfg[0]}"
        else:
            steps.skip("not configured")
            results.append(("AI provider", True, "not configured · chat will be disabled"))
            provider_suggestion = "agentdrive provider set <name>"
    except Exception as e:
        steps.fail(str(e)[:60])
        results.append(("AI provider", False, str(e)))

    # 8. Production operational checks (permissions, reconciliation, immune)
    try:
        from agentdrive.utils.safe_paths import safe_join

        home = get_agentdrive_home()

        # Check permissions on sensitive operational files
        sensitive_files = [
            home / "auth.db",
            home / "caps.db",
            home / "dna" / "_ancestry.db",
        ]
        perm_issues = []
        for f in sensitive_files:
            if f.exists():
                mode = oct(f.stat().st_mode)[-3:]
                if mode not in ("600", "700"):
                    perm_issues.append(f"{f.name}={mode}")

        if perm_issues:
            steps.advance(f"permissions: {', '.join(perm_issues)}")
            results.append(("Operational files", False, f"weak perms: {', '.join(perm_issues)}"))
        else:
            steps.advance("sensitive files permissions OK")
            results.append(("Operational files", True, "sensitive DBs have tight permissions"))

        # Quick reconciliation health (first-run tolerant) + first-run recovery guidance
        try:
            from agentdrive.reconciliation import ReconciliationRunner

            rec = ReconciliationRunner()
            status = rec.status() if hasattr(rec, "status") else {"healthy": True}
            if status.get("healthy", True):
                steps.advance("reconciliation healthy")
                results.append(
                    ("Reconciliation", True, "background awareness ready (first-run self-healed)")
                )
            else:
                steps.advance("reconciliation issues")
                results.append(("Reconciliation", False, str(status)))
        except Exception:
            steps.skip("reconciliation ready (first-run)")
            results.append(
                ("Reconciliation", True, "state initialized by self-healing (empty-drive safe)")
            )

    except Exception as e:
        steps.skip(f"ops checks limited: {str(e)[:40]}")
        results.append(("Operational checks", True, "partial (advanced features)"))

    # 9. Security posture (lightweight, production-relevant)
    # Expanded with richer signals from get_security_posture for role-specialized swarms.
    posture = None
    try:
        from agentdrive.security import get_security_posture

        posture = get_security_posture()
        if posture.sensitive_files_ok and not posture.issues:
            steps.advance("keys & auth DBs locked down")
            results.append(("Security posture", True, "sensitive files have tight permissions"))
        else:
            steps.advance(f"security: {len(posture.issues)} issues")
            results.append(
                ("Security posture", False, "; ".join(posture.issues) or "review permissions")
            )
    except Exception:
        steps.skip("security posture (advanced)")

    steps.finish()

    # Build result tree
    failed = [(name, detail) for name, ok, detail in results if not ok]
    needs_attention = [
        (name, detail) for name, ok, detail in results if ok and "no key" in detail.lower()
    ]

    tree_rows = []
    for name, ok, detail in results:
        if ok:
            label = f"[bold {p.ok}]✓[/]  {name}"
        else:
            label = f"[bold {p.error}]✗[/]  {name}"
        tree_rows.append(TreeRow(label=label, secondary=detail))

    console.print()
    if not failed:
        suggestion_extras = []
        if provider_suggestion:
            suggestion_extras.append(Text(""))
            sug = Text()
            sug.append("  next: ", style=p.muted)
            sug.append(provider_suggestion, style=f"bold {p.accent}")
            suggestion_extras.append(sug)

        from agentdrive.config import get_instance_name

        instance = get_instance_name()
        title = (
            f"{instance} — All systems nominal"
            if not needs_attention
            else f"{instance} — Healthy with notes"
        )
        console.print(
            result_panel(
                title,
                [],
                success=True,
                palette=p,
                extras=[
                    Text(""),
                    Tree(tree_rows, palette=p),
                    *suggestion_extras,
                ],
            )
        )
        if verbose:
            _print_doctor_verbose_diagnostics(p)
        # Expanded Security posture subsection (new for this stabilization wave)
        if posture is not None:
            try:
                from rich.text import Text as _Text


                sec_lines = [
                    f"Quarantine: {posture.quarantined_items} items, {posture.recent_quarantine_releases} recent releases",
                    f"Key rotation: {posture.key_rotation_signal or 'n/a'}",
                    f"Recon depth: {posture.reconciliation_last_scan_delta_hours or 'n/a'}h delta, {posture.reconciliation_failure_count} failures (state)",
                    f"Revoked grants: {posture.revoked_grants}",
                    f"Schema sec proposals: {posture.schema_evolution_security_proposals}",
                ]
                console.print(
                    section_panel(
                        "Security posture (role-specialized swarms)",
                        [_Text(" | ".join(sec_lines))],
                        success=True,
                        palette=p,
                    )
                )
            except Exception:
                pass
        if ingests == 0 and total_genomes == 0:
            try:
                from rich.text import Text as _T

                guidance = _T.from_markup(
                    "[bold]Golden path (recommended first-run):[/]\n\n"
                    "  [bold cyan]agentdrive golden-path run[/]\n"
                    "    Walkthrough: doctor → mcp → seed → think → learnings → drive query\n\n"
                    "  [bold cyan]agentdrive golden-path steps[/]\n"
                    "    Show numbered commands (see [dim]docs/GOLDEN_PATH.md[/])\n\n"
                    "[bold]If registry is still empty after auto-seed:[/]\n\n"
                    "  [bold cyan]agentdrive reconcile seed-experience-v3[/]\n"
                    "    Bootstrap experience layer v3 + KG index + living-experience seed genome\n\n"
                    "  [bold cyan]agentdrive doctor[/]   — re-check\n\n"
                    "Auto-seed usually runs on first Drive access. The golden path verifies the full loop."
                )
                console.print(section_panel("First-run guidance", [guidance], palette=p))
            except Exception:
                pass
        return 0
    else:
        console.print(
            result_panel(
                f"{len(failed)} issue{'s' if len(failed) != 1 else ''} found",
                [],
                success=False,
                palette=p,
                extras=[
                    Text(""),
                    Tree(tree_rows, palette=p),
                ],
            )
        )
        if verbose:
            _print_doctor_verbose_diagnostics(p)
        # Expanded Security posture subsection (new for this stabilization wave)
        if posture is not None:
            try:
                from rich.text import Text as _Text

                sec_lines = [
                    f"Quarantine: {posture.quarantined_items} items, {posture.recent_quarantine_releases} recent releases",
                    f"Key rotation: {posture.key_rotation_signal or 'n/a'}",
                    f"Recon depth: {posture.reconciliation_last_scan_delta_hours or 'n/a'}h delta, {posture.reconciliation_failure_count} failures (state)",
                    f"Revoked grants: {posture.revoked_grants}",
                    f"Schema sec proposals: {posture.schema_evolution_security_proposals}",
                ]
                console.print(
                    section_panel(
                        "Security posture (role-specialized swarms)",
                        [_Text(" | ".join(sec_lines))],
                        success=False,
                        palette=p,
                    )
                )
            except Exception:
                pass
        return 1


def cmd_config(args: argparse.Namespace) -> int:
    setup_logging()
    if args.subcommand in (None, "show"):
        from rich.console import Group

        from agentdrive.tui.chrome import Palette, Section, section_panel
        from agentdrive.tui.skin_engine import skin

        cfg = load_config()
        p = Palette(skin)

        def _flatten(d: dict, prefix: str = "") -> list:
            rows: list = []
            for k, v in d.items():
                key = f"{prefix}{k}" if prefix else k
                if isinstance(v, dict):
                    if not v:
                        rows.append((key, "—"))
                    else:
                        rows.extend(_flatten(v, key + "."))
                elif isinstance(v, list):
                    rows.append((key, ", ".join(str(x) for x in v) if v else "—"))
                elif isinstance(v, bool):
                    rows.append((key, "true" if v else "false"))
                elif v is None:
                    rows.append((key, "—"))
                else:
                    rows.append((key, str(v)))
            return rows

        groups: dict = {}
        for key, value in _flatten(cfg):
            top = key.split(".", 1)[0]
            groups.setdefault(top, []).append((key, value))

        order = [
            "agentdrive",
            "registry",
            "scanners",
            "orchestrator",
            "tui",
            "integration",
            "drive",
        ]
        ordered = [k for k in order if k in groups] + [k for k in groups if k not in order]

        # Roll scalar singletons (version, onboarded) into a Meta section.
        meta_rows = []
        for k in list(ordered):
            rows = groups[k]
            if len(rows) == 1 and rows[0][0] == k:
                meta_rows.append(rows[0])
                ordered.remove(k)

        labels = {"tui": "TUI"}
        blocks = [
            Section(labels.get(name, name.capitalize()), groups[name], palette=p)
            for name in ordered
        ]
        if meta_rows:
            blocks.append(Section("Meta", meta_rows, palette=p))

        console.print()
        console.print(
            section_panel(
                Group(*blocks),
                title="Agent Drive Config",
                palette=p,
            )
        )
        console.print(f"  [dim]source: {get_agentdrive_home() / 'config.yaml'}[/]")
        return 0

    if args.subcommand == "get":
        val = get_config_value(args.key, "<not set>")
        console.print(f"{args.key} = {val}")
        return 0

    if args.subcommand == "set":
        if not args.key or args.value is None:
            console.print("[red]Usage: agentdrive config set <key> <value>[/]")
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
        cfg_path = get_agentdrive_home() / "config.yaml"
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
    console.print("[dim]Use agentdrive doctor for deeper integration status.[/]")
    return 0


def cmd_pool(args: argparse.Namespace) -> int:
    """Handler for the `agentdrive drive` subcommand group: status, ingest, query, stats."""
    setup_logging()
    pool = get_default_drive()
    sub = getattr(args, "pool_subcommand", None)

    if sub in (None, "status"):
        from datetime import datetime



        stats = pool.get_pool_stats()
        reg = pool.registry
        try:
            reg_details = reg.get_registry_stats() if hasattr(reg, "get_registry_stats") else {}
        except Exception:
            reg_details = {}

        last_ingest = stats.get("last_ingest")
        if isinstance(last_ingest, (int, float)) and last_ingest > 0:
            last_str = datetime.fromtimestamp(last_ingest, tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
        else:
            last_str = "never"

        domains = ", ".join((reg_details or {}).get("domains_covered", [])[:5]) or "—"

        console.print()
        console.print("[bold cyan]Drive Status[/]")
        console.print(f"  drive: {stats.get('name', 'main')}")
        console.print(f"  genomes: {stats.get('total_genomes', 0)}")
        console.print(f"  events: {stats.get('ingest_events', 0)}")
        console.print(f"  last ingest: {last_str}")
        console.print(f"  domains: {domains}")
        console.print(f"  drive path: {stats.get('drive_path', '')}")
        console.print(f"  schema pack: {stats.get('schema_pack', 'agentdrive-drive')}")
        console.print(
            "  [dim]agentdrive drive stats[/]  full breakdown  ·  "
            '[dim]agentdrive drive query "..."[/]  search'
        )
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
            console.print(
                Panel(
                    f"[bold green]Accepted[/]: {result.genome_id}\n"
                    f"Reason: {result.reason}\n"
                    f"Version: {result.new_version or g.manifest.version}\n"
                    f"Source dir: {gdir}\n"
                    f"Persisted to registry + ingest.jsonl",
                    title="Pool Ingest",
                    border_style="green",
                )
            )
            # Also show updated count
            new_stats = pool.get_pool_stats()
            console.print(
                f"[dim]Pool now has {new_stats['ingest_events']} ingest events, {new_stats['total_genomes']} genomes.[/]"
            )
            return 0
        except Exception as exc:
            console.print(f"[red]Ingest failed:[/] {exc}")
            logger.exception("pool ingest error")
            return 1

    if sub == "query":
        task = args.task or ""
        if not task.strip():
            console.print(
                '[red]Provide a task description: agentdrive drive query "your task here"[/]'
            )
            return 1
        q = DriveQuery(
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
            score = (
                m.evaluation_score.get("reference_tasks", 0.0)
                if isinstance(m.evaluation_score, dict)
                else 0.0
            )
            doms = (
                ", ".join((m.applicability or {}).get("domains", [])[:3])
                if isinstance(m.applicability, dict)
                else ""
            )
            p = pool.registry.get_genome_path(g.genome_id) or ""
            table.add_row(
                g.genome_id,
                str(m.version),
                f"{float(score):.2f}",
                doms,
                str(p),
            )
        console.print(table)
        console.print(
            f"[dim]Returned {len(genomes)} genomes. Use 'agentdrive genomes info <id>' for details.[/]"
        )
        return 0

    if sub == "stats":
        from datetime import datetime

        from rich.console import Group

        # Legacy TUI chrome removed — basic output only.


        stats = pool.get_pool_stats()
        reg_stats = stats.get("registry_stats", {}) or {}
        sources = stats.get("sources", {}) or {}
        top_actors = stats.get("top_actors", {}) or {}

        last_ingest = stats.get("last_ingest")
        if isinstance(last_ingest, (int, float)) and last_ingest > 0:
            last_str = datetime.fromtimestamp(last_ingest, tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
        else:
            last_str = "never"

        domains = ", ".join(reg_stats.get("domains_covered", [])[:6]) or "—"

        console.print()
        console.print("[bold cyan]Drive Stats (simplified for Wave 3 stability)[/]")
        console.print(f"  drive: {stats.get('name', 'main')}")
        console.print(f"  genomes: {stats.get('total_genomes', 0)}")
        console.print(f"  ingest events: {stats.get('ingest_events', 0)}")
        console.print(f"  domains: {domains}")
        if sources:
            console.print("  top sources: " + ", ".join(f"{k}:{v}" for k, v in sorted(sources.items(), key=lambda kv: -kv[1])[:5]))
        if top_actors:
            console.print("  top actors: " + ", ".join(f"{k}:{v}" for k, v in sorted(top_actors.items(), key=lambda kv: -kv[1])[:5]))
        console.print("[dim]Use MC Tower/TUI for rich fabric + loop views.[/]")
        return 0

    console.print("[red]Unknown pool subcommand[/]")
    return 1


def cmd_quarantine(args: argparse.Namespace) -> int:
    """Handler for the `agentdrive quarantine` subcommand group.

    Trust-gated holding area: list / show / validate / approve / reject / hold
    candidate genomes received from sub-agents or peer pools.
    """
    setup_logging()
    from agentdrive.quarantine import (
        QuarantineStatus,
        get_default_quarantine,
    )
    from agentdrive.tui.chrome import (
        Palette,
        Section,
        Tree,
        TreeRow,
        info_line,
        ok_line,
        section_panel,
        warn_line,
    )
    from agentdrive.tui.skin_engine import skin

    p = Palette(skin)
    q = get_default_quarantine()
    sub = getattr(args, "quarantine_subcommand", None) or "list"

    if sub == "list":
        status: QuarantineStatus | None = None
        if getattr(args, "status", None):
            try:
                status = QuarantineStatus(args.status)
            except ValueError:
                console.print(f"[red]Unknown status:[/] {args.status}")
                return 1
        entries = q.list(status=status)
        if not entries:
            console.print()
            console.print(
                info_line(
                    "No quarantine entries"
                    + (f" with status={status.value}" if status else "")
                    + ".",
                    palette=p,
                )
            )
            return 0
        rows: list[TreeRow] = []
        for e in entries:
            label = (
                f"[bold]{e.quarantine_id[:12]}[/] "
                f"[agentdrive.genome]{e.genome_id or '(no id)'}[/]  "
                f"[dim]{e.status.value}[/]"
            )
            rows.append(
                TreeRow(
                    label=label,
                    secondary=f"from {e.source_peer} · {e.received_at}",
                )
            )
        console.print()
        console.print(
            section_panel(
                Tree(rows, palette=p),
                title=f"Quarantine  ({len(entries)})",
                palette=p,
            )
        )
        return 0

    if sub == "show":
        e = q.get(args.quarantine_id)
        if e is None:
            console.print(f"[red]Unknown quarantine_id:[/] {args.quarantine_id}")
            return 1
        section = Section(
            "Entry",
            [
                ("id", e.quarantine_id),
                ("genome", e.genome_id or "—"),
                ("source", e.source_peer),
                ("status", e.status.value),
                ("received", e.received_at),
                ("sha256", e.sha256[:16] + "…"),
                ("dir", str(e.genome_dir)),
                ("reasons", "; ".join(e.reasons) if e.reasons else "—"),
            ],
            palette=p,
        )
        console.print()
        console.print(section_panel(section, title="Quarantine entry", palette=p))
        return 0

    if sub == "validate":
        try:
            results = q.validate(args.quarantine_id)
        except KeyError:
            console.print(f"[red]Unknown quarantine_id:[/] {args.quarantine_id}")
            return 1
        rows = []
        for name, ok, reason in results:
            label = f"[bold green]PASS[/] {name}" if ok else f"[bold red]FAIL[/] {name}"
            rows.append(TreeRow(label=label, secondary=reason if not ok else ""))
        all_passed = all(ok for _n, ok, _r in results)
        title = "Validation: PASS" if all_passed else "Validation: FAIL"
        console.print()
        console.print(
            section_panel(
                Tree(rows, palette=p),
                title=title,
                palette=p,
            )
        )
        return 0 if all_passed else 1

    if sub == "approve":
        pool = get_default_drive()
        try:
            ok = q.approve(args.quarantine_id, pool, note=args.note or "")
        except KeyError:
            console.print(f"[red]Unknown quarantine_id:[/] {args.quarantine_id}")
            return 1
        if ok:
            console.print()
            console.print(
                ok_line(
                    f"Approved [agentdrive.genome]{args.quarantine_id}[/] · released into pool",
                    palette=p,
                )
            )
            return 0
        e = q.get(args.quarantine_id)
        reasons = "; ".join(e.reasons) if e and e.reasons else "validation failed"
        console.print()
        console.print(
            warn_line(
                f"Approval blocked for [agentdrive.genome]{args.quarantine_id}[/]",
                palette=p,
                secondary=reasons,
            )
        )
        return 1

    if sub == "reject":
        try:
            q.reject(args.quarantine_id, args.reason)
        except KeyError:
            console.print(f"[red]Unknown quarantine_id:[/] {args.quarantine_id}")
            return 1
        console.print()
        console.print(
            ok_line(
                f"Rejected [agentdrive.genome]{args.quarantine_id}[/]",
                palette=p,
                secondary=args.reason,
            )
        )
        return 0

    if sub == "hold":
        try:
            q.hold(args.quarantine_id, args.reason)
        except KeyError:
            console.print(f"[red]Unknown quarantine_id:[/] {args.quarantine_id}")
            return 1
        console.print()
        console.print(
            ok_line(
                f"Held [agentdrive.genome]{args.quarantine_id}[/]",
                palette=p,
                secondary=args.reason,
            )
        )
        return 0

    console.print("[red]Unknown quarantine subcommand[/]")
    return 1


def cmd_peers(args: argparse.Namespace) -> int:
    """Handler for the `agentdrive peers` subcommand group.

    Federated peer registry — add / remove / list / set trust / sync.
    Every byte pulled from a peer routes through quarantine; `peers sync`
    never ingests into the live pool directly.
    """
    setup_logging()
    from agentdrive.peers import (
        VALID_TRUST_LEVELS,
        PeerRegistry,
        sync_peer,
    )
    from agentdrive.tui.chrome import (
        Palette,
        Section,
        Tree,
        TreeRow,
        info_line,
        ok_line,
        section_panel,
    )
    from agentdrive.tui.skin_engine import skin

    p = Palette(skin)
    reg = PeerRegistry()
    sub = getattr(args, "peers_subcommand", None) or "list"

    if sub == "list":
        entries = reg.list()
        if not entries:
            console.print()
            console.print(info_line("No peers registered.", palette=p))
            return 0
        rows: list[TreeRow] = []
        for e in entries:
            label = (
                f"[bold]{e.peer_id}[/]  [agentdrive.genome]{e.address}[/]  [dim]{e.trust_level}[/]"
            )
            secondary_bits = []
            if e.last_sync_iso:
                secondary_bits.append(f"last sync {e.last_sync_iso}")
            else:
                secondary_bits.append("never synced")
            if e.notes:
                secondary_bits.append(e.notes)
            rows.append(
                TreeRow(
                    label=label,
                    secondary=" · ".join(secondary_bits),
                )
            )
        console.print()
        console.print(
            section_panel(
                Tree(rows, palette=p),
                title=f"Peers  ({len(entries)})",
                palette=p,
            )
        )
        return 0

    if sub == "add":
        if args.trust not in VALID_TRUST_LEVELS:
            console.print(
                f"[red]Invalid trust level:[/] {args.trust} "
                f"(valid: {', '.join(VALID_TRUST_LEVELS)})"
            )
            return 1
        try:
            entry = reg.add(
                args.peer_id,
                args.address,
                trust_level=args.trust,
                notes=args.notes or "",
            )
        except ValueError as exc:
            console.print(f"[red]Add failed:[/] {exc}")
            return 1
        console.print()
        console.print(
            ok_line(
                f"Added peer [agentdrive.genome]{entry.peer_id}[/] ({entry.trust_level})",
                palette=p,
                secondary=entry.address,
            )
        )
        return 0

    if sub == "remove":
        if reg.remove(args.peer_id):
            console.print()
            console.print(
                ok_line(
                    f"Removed peer [agentdrive.genome]{args.peer_id}[/]",
                    palette=p,
                )
            )
            return 0
        console.print(f"[red]Unknown peer:[/] {args.peer_id}")
        return 1

    if sub == "trust":
        if args.level not in VALID_TRUST_LEVELS:
            console.print(
                f"[red]Invalid trust level:[/] {args.level} "
                f"(valid: {', '.join(VALID_TRUST_LEVELS)})"
            )
            return 1
        ok = reg.set_trust(args.peer_id, args.level)
        if not ok:
            console.print(f"[red]Unknown peer:[/] {args.peer_id}")
            return 1
        console.print()
        console.print(
            ok_line(
                f"Trust level for [agentdrive.genome]{args.peer_id}[/] → {args.level}",
                palette=p,
            )
        )
        return 0

    if sub == "sync":
        pool = get_default_drive()
        result = sync_peer(args.peer_id, target_pool=pool, registry=reg)

        section = Section(
            "Sync result",
            [
                ("peer", result.peer_id),
                ("submitted", str(result.submitted)),
                ("quarantine", ", ".join(qid[:12] for qid in result.quarantine_ids) or "—"),
                ("errors", str(len(result.errors))),
                ("duration_ms", str(result.duration_ms)),
            ],
            palette=p,
        )
        console.print()
        console.print(
            section_panel(
                section,
                title=f"Peer sync · {args.peer_id}",
                palette=p,
            )
        )

        if result.errors:
            rows = [TreeRow(label=err) for err in result.errors]
            console.print(
                section_panel(
                    Tree(rows, palette=p),
                    title="Sync errors",
                    palette=p,
                )
            )
            return 1

        if result.submitted > 0:
            console.print(
                info_line(
                    f"{result.submitted} candidate(s) placed in quarantine — "
                    f"review with 'agentdrive quarantine list'.",
                    palette=p,
                )
            )
        else:
            console.print(
                info_line(
                    "No new genomes from this peer since last sync.",
                    palette=p,
                )
            )
        return 0

    console.print("[red]Unknown peers subcommand[/]")
    return 1


def cmd_models(args: argparse.Namespace) -> int:
    """Handler for the `agentdrive models` subcommand group.

    AgentDrive local LLM backends — list (v1).  Reads
    ``~/.agentdrive/local_models.yaml`` (creating a default scaffold on first
    run), probes each spec in parallel for reachability, and renders the
    result through the existing chrome (matching ``agentdrive peers list``).
    """
    setup_logging()
    from concurrent.futures import ThreadPoolExecutor

    from agentdrive.local_models import (
        get_local_models_path,
        is_available,
        load_specs,
    )
    from agentdrive.tui.chrome import (
        Palette,
        Tree,
        TreeRow,
        info_line,
        section_panel,
    )
    from agentdrive.tui.skin_engine import skin

    p = Palette(skin)
    sub = getattr(args, "models_subcommand", None) or "list"

    if sub == "list":
        path = get_local_models_path()
        specs = load_specs(path)
        if not specs:
            console.print()
            console.print(
                info_line(
                    "No local models configured.",
                    palette=p,
                    secondary=f"edit {path}",
                )
            )
            return 0

        # Probe in parallel — each adapter caps probe time at ~2s, so even
        # an all-unreachable list returns within a couple of seconds.
        with ThreadPoolExecutor(max_workers=min(8, len(specs))) as ex:
            reachable = list(ex.map(is_available, specs))

        rows: list[TreeRow] = []
        for spec, ok in zip(specs, reachable):
            status = "[green]reachable[/]" if ok else "[dim]unreachable[/]"
            label = (
                f"[bold]{spec.display_name()}[/]  [agentdrive.genome]{spec.backend}[/]  {status}"
            )
            secondary_bits = [f"model {spec.model}", f"endpoint {spec.endpoint}"]
            if spec.api_key:
                secondary_bits.append("api-key set")
            rows.append(
                TreeRow(
                    label=label,
                    secondary=" · ".join(secondary_bits),
                )
            )
        console.print()
        console.print(
            section_panel(
                Tree(rows, palette=p),
                title=f"AgentDrive local models  ({len(specs)})",
                palette=p,
            )
        )
        console.print(
            info_line(
                f"config: {path}",
                palette=p,
            )
        )
        return 0

    console.print("[red]Unknown models subcommand[/]")
    return 1


def cmd_grid(args: argparse.Namespace) -> int:
    """Handler for the `agentdrive grid` subcommand group.

    The real-time engine that keeps **AD-Grid** (AgentDrive Grid) alive.

    AD-Grid is the long-lived, persistent intelligence "world" that grows from
    every project and piece of work on your drives — wherever they run.
    It is the always-on counterpart to bounded static fires.

    See docs/AD_GRID_VISION.md for the full philosophy.
    """
    setup_logging()
    from agentdrive.grid.engine import GridConfig, GridEngine

    swarm_id = getattr(args, "swarm_id", None) or "active-grid"
    interval = getattr(args, "interval", 15.0)
    with_tower = getattr(args, "with_tower", False)

    config = GridConfig(
        swarm_id=swarm_id,
        damage_scan_interval_s=interval,
        enable_auto_healing=True,
    )

    engine = GridEngine(config=config)
    console.print(f"[bold cyan]Starting AD-Grid[/] (swarm={swarm_id})")
    console.print("AD-Grid is now the persistent, long-lived intelligence world for this drive.")
    console.print("It will continuously grow from all projects and autonomous work — 24/7.")
    if with_tower:
        console.print("Also starting embedded Mission Control Tower for live Grid view...")

    if with_tower:
        # Start the Tower in the same process for a true long-lived "Grid window"
        import threading

        from agentdrive.mission_control.server import create_mission_control_app

        # Tailnet mode: bind directly to the Tailscale IP (like Clawdbot "bind: tailnet")
        # This makes the Tower reachable at http://<your-tailscale-ip>:8421 from any machine on the tailnet,
        # exactly like localhost but over Tailscale.
        ts_ip = get_tailscale_ipv4()
        bind_host = ts_ip if ts_ip else "127.0.0.1"

        def _run_tower():
            import uvicorn
            uvicorn.run(
                create_mission_control_app,
                host=bind_host,
                port=8421,
                factory=True,
                log_level="warning",
            )

        tower_thread = threading.Thread(target=_run_tower, daemon=True)
        tower_thread.start()

        if ts_ip:
            console.print(f"[green]Tower live at http://{ts_ip}:8421[/]  ← open this from any Tailscale machine")
        else:
            console.print("[green]Tower live at http://127.0.0.1:8421 (localhost only)[/]")

        console.print("[dim]First page load can take 15-30s if there has been heavy recent activity on the drive.[/]")

        # Wire the persistent GridEngine to the MissionControlHub so /api/grid/* and WS
        # serve live AD-Grid state (programs, health, fabric) even with zero active missions.
        # This is the architectural fix for "without a mission everything stops + reconnect spam".
        # Tower becomes the stable always-on window into the living AD-Grid on stabilization-wave-20260531.
        try:
            from agentdrive.mission_control.server import hub as mc_hub
            mc_hub.attach_grid(engine)
            console.print("[dim]Grid attached to Mission Control for persistent observability (quiet mode supported).[/]")
        except Exception as _e:
            console.print(f"[yellow]Grid attach to Tower skipped (non-fatal): {_e}[/]")

    console.print("Press Ctrl+C to stop the Grid.")

    try:
        engine.run_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Grid shutdown requested...[/]")
    finally:
        console.print("[green]Grid stopped cleanly.[/]")

    return 0


def cmd_dream(args: argparse.Namespace) -> int:
    """Phased gbrain-style dream maintenance cycle."""
    setup_logging()
    from agentdrive.dreaming.cycle import (
        DREAM_PHASES,
        DreamCycleLockError,
        DreamCyclePending,
        dream_audit_log_path,
        dream_lock_path,
        get_dream_cycle_status,
        run_dream_cycle,
    )
    from agentdrive.tui.chrome import Palette, Section, info_line, section_panel
    from agentdrive.tui.skin_engine import skin

    p = Palette(skin)
    sub = getattr(args, "dream_subcommand", None) or "status"

    if sub == "phases":
        console.print()
        table = Table(title="Dream cycle phases", show_header=True)
        table.add_column("ID", style="cyan")
        table.add_column("Name")
        table.add_column("STOP gate")
        for spec in DREAM_PHASES:
            gate = "[yellow]yes[/]" if spec.stop_gate else "[dim]no[/]"
            table.add_row(spec.id, spec.name, gate)
        console.print(table)
        return 0

    if sub == "status":
        status = get_dream_cycle_status()
        rows: list[tuple[str, str]] = [
            ("lock", str(status.get("lock_path", ""))),
            ("lock_held", "yes" if status.get("lock_held") else "no"),
            ("audit_log", str(status.get("audit_log", ""))),
            ("phases", str(len(status.get("phases") or []))),
        ]
        last = status.get("last_run")
        if isinstance(last, dict):
            rows.extend(
                [
                    ("last_phase", str(last.get("phase_id", ""))),
                    ("last_success", str(last.get("success", ""))),
                    ("last_run_id", str(last.get("run_id", ""))),
                ]
            )
        console.print()
        console.print(
            section_panel(
                Section("Dream cycle", rows, palette=p),
                title="Dream status",
                palette=p,
            )
        )
        if not last:
            console.print(
                info_line(
                    "No dream cycle runs recorded yet. Try [cyan]agentdrive dream run --dry-run[/].",
                    palette=p,
                )
            )
        return 0

    if sub == "run":
        dry_run = bool(getattr(args, "dry_run", False))
        phase = getattr(args, "phase", None)
        ack_phase = getattr(args, "ack_phase", None)
        phases = [phase] if phase else None
        ack_phases = [ack_phase] if ack_phase else None
        try:
            results = run_dream_cycle(
                dry_run=dry_run,
                phases=phases,
                ack_phases=ack_phases,
            )
        except DreamCycleLockError as exc:
            console.print()
            console.print(
                Panel(
                    f"{rich_escape(str(exc))}\n\n"
                    f"Lock: [agentdrive.genome]{dream_lock_path()}[/]",
                    title="Dream cycle busy",
                    border_style="red",
                )
            )
            return 1
        except DreamCyclePending as exc:
            console.print()
            console.print(
                Panel(
                    f"[bold yellow]STOP gate[/] at phase [cyan]{exc.phase_id}[/]\n\n"
                    f"{rich_escape(exc.message)}\n\n"
                    f"Resume: [dim]agentdrive dream run --ack-phase {exc.phase_id}[/]",
                    title="Dream paused",
                    border_style="yellow",
                )
            )
            return 2

        console.print()
        table = Table(title="Dream cycle", show_header=True)
        table.add_column("Phase", style="cyan")
        table.add_column("Status")
        table.add_column("Duration")
        table.add_column("Message", overflow="fold")
        for result in results:
            status = "[green]ok[/]" if result.success else "[red]fail[/]"
            table.add_row(
                result.phase_id,
                status,
                f"{result.duration_ms} ms",
                result.message,
            )
        console.print(table)
        console.print(f"[dim]Audit: {dream_audit_log_path()}[/]")
        if dry_run:
            console.print("[dim]Dry-run: reconciliation scan and consolidation writes skipped.[/]")
        return 0 if all(r.success for r in results) else 1

    console.print("[red]Unknown dream subcommand[/]")
    return 1


def cmd_reconcile(args: argparse.Namespace) -> int:
    """Handler for the `agentdrive reconcile` subcommand group.

    Runs a one-shot pool reconciliation pass, or shows the persisted state.
    Heavy lifting lives in ``agentdrive.reconciliation``; this surface only
    renders the report through the existing chrome.
    """
    setup_logging()
    from agentdrive.reconciliation import (
        STATE_FILENAME,
        ReconciliationRunner,
    )
    from agentdrive.registry import GenomeRegistry
    from agentdrive.tui.chrome import (
        Palette,
        Section,
        Tree,
        TreeRow,
        info_line,
        section_panel,
    )
    from agentdrive.tui.skin_engine import skin

    p = Palette(skin)
    sub = getattr(args, "reconcile_subcommand", None) or "run"

    if sub == "run":
        try:
            pool = get_default_drive()
            registry = pool.registry if hasattr(pool, "registry") else GenomeRegistry()
        except Exception as exc:
            console.print(f"[red]Failed to acquire pool/registry:[/] {exc}")
            return 1

        runner = ReconciliationRunner(registry=registry, pool=pool)
        report = runner.scan_once()

        rows: list[tuple[str, str]] = [
            ("since", report.since),
            ("until", report.until),
            ("duration", f"{report.duration_ms} ms"),
            ("new", str(len(report.new_genomes))),
            ("updated", str(len(report.updated_genomes))),
            ("ingest", f"{report.new_ingest_events} new event(s)"),
            ("quarantine", f"{report.pending_quarantine} pending"),
        ]
        console.print()
        console.print(
            section_panel(
                Section("Reconciliation", rows, palette=p),
                title="Pool reconciliation",
                palette=p,
            )
        )

        if report.new_genomes or report.updated_genomes:
            delta_rows: list[TreeRow] = []
            for gid in report.new_genomes:
                delta_rows.append(
                    TreeRow(
                        label=f"[bold green]new[/]  [agentdrive.genome]{gid}[/]",
                    )
                )
            for gid in report.updated_genomes:
                delta_rows.append(
                    TreeRow(
                        label=f"[bold yellow]upd[/]  [agentdrive.genome]{gid}[/]",
                    )
                )
            console.print(
                section_panel(
                    Tree(delta_rows, palette=p),
                    title=f"Delta  ({len(delta_rows)})",
                    palette=p,
                )
            )
        else:
            console.print(info_line("No new or updated genomes.", palette=p))
        return 0

    if sub == "status":
        state_path = get_agentdrive_home() / STATE_FILENAME
        if not state_path.is_file():
            console.print()
            console.print(
                info_line(
                    f"No reconciliation state at [agentdrive.genome]{state_path}[/]. "
                    f"Run `agentdrive reconcile run` first.",
                    palette=p,
                )
            )
            return 0
        try:
            import json as _json

            state = _json.loads(state_path.read_text(encoding="utf-8"))
        except Exception as exc:
            console.print(f"[red]Failed to read state:[/] {exc}")
            return 1
        known_ids = list(state.get("known_genome_ids") or [])
        markers = dict(state.get("known_markers") or {})
        ultimates = sum(1 for m in markers.values() if m.get("ultimate"))
        rows = [
            ("state_path", str(state_path)),
            ("last_scan", str(state.get("last_scan_iso") or "(never)")),
            ("known", f"{len(known_ids)} genome(s)"),
            (
                "with_stars",
                f"{sum(1 for m in markers.values() if int(m.get('stars', 0) or 0) > 0)}",
            ),
            ("ultimate", f"{ultimates}"),
        ]
        console.print()
        console.print(
            section_panel(
                Section("Reconciliation state", rows, palette=p),
                title="Reconciliation",
                palette=p,
            )
        )
        return 0

    if sub == "seed-experience-v3":
        # The core lightweight helper exposed by the Self-Healing First-Run &
        # Experience Seed Operator (stabilization swarm component inside AgentDrive).
        # Directly invokes ensure_experience_layer_seed for defensive recovery.
        try:
            pool = get_default_drive()
        except Exception as exc:
            console.print(f"[red]Failed to acquire default drive:[/] {exc}")
            return 1

        try:
            from agentdrive.drive.bootstrap import ensure_experience_layer_seed

            seed_path = ensure_experience_layer_seed(
                pool.drive_path, getattr(pool, "swarm_id", None)
            )

            console.print()
            console.print(
                section_panel(
                    Section(
                        "Seed experience layer v3",
                        [
                            ("drive", str(pool.drive_path)),
                            ("seed_observation", str(seed_path)),
                            ("status", "created / repaired"),
                            (
                                "note",
                                "living-experience page type + genome + KG + recon + trust identity",
                            ),
                        ],
                        palette=p,
                    ),
                    title="First-run recovery complete",
                    palette=p,
                )
            )
            console.print(
                info_line(
                    "New AgentDrive instances for role-swarm self-host users now start coherent. "
                    "Experience layer present from first think. Defensive healing applied for production reliability. "
                    "Run `agentdrive doctor` to verify. Seed artifacts are ingestible.",
                    palette=p,
                )
            )
            return 0
        except Exception as exc:
            console.print(f"[red]seed-experience-v3 failed:[/] {exc}")
            return 1

    console.print("[red]Unknown reconcile subcommand[/]")
    return 1


def cmd_uninstall(args: argparse.Namespace) -> int:
    """Uninstall AgentDrive package and optionally remove user data."""
    from agentdrive.tui.chrome import Palette, confirm_prompt, info_line, ok_line
    from agentdrive.tui.skin_engine import skin

    p = Palette(skin)

    if not args.yes:
        ok = confirm_prompt(
            console,
            title="Uninstall Agent Drive?",
            body=(
                f"This will remove the agentdrive venv at [agentdrive.genome]{get_agentdrive_home() / 'venv'}[/] "
                f"and the [agentdrive.genome]~/.local/bin/agentdrive[/] shim."
            ),
            default_yes=False,
            danger=True,
            palette=p,
        )
        if not ok:
            console.print()
            console.print(info_line("Cancelled. Agent Drive is still installed.", palette=p))
            return 0

    venv_dir = get_agentdrive_home() / "venv"
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
        console.print(ok_line(f"Removed venv at [agentdrive.genome]{venv_dir}[/]", palette=p))

    shim = Path.home() / ".local" / "bin" / "agentdrive"
    if shim.exists():
        shim.unlink()
        console.print(ok_line(f"Removed shim at [agentdrive.genome]{shim}[/]", palette=p))

    if args.yes:
        remove_data = True
    else:
        remove_data = confirm_prompt(
            console,
            title="Also remove all Agent Drive data?",
            body=(
                f"This will delete [agentdrive.genome]{get_agentdrive_home()}[/] "
                f"including all pools, genomes, sessions, and the mission board.\n"
                f"[agentdrive.warn]This cannot be undone.[/]"
            ),
            default_yes=False,
            danger=True,
            palette=p,
        )

    if remove_data:
        home = get_agentdrive_home()
        if home.exists():
            shutil.rmtree(home)
            console.print(ok_line(f"Removed data at [agentdrive.genome]{home}[/]", palette=p))

    console.print()
    console.print(ok_line("Agent Drive uninstalled.", palette=p))
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """Clean AgentDrive cache and data, keeping config intact."""
    from agentdrive.tui.chrome import Palette, confirm_prompt, info_line, ok_line, warn_line
    from agentdrive.tui.skin_engine import skin

    p = Palette(skin)

    home = get_agentdrive_home()
    if not home.exists():
        console.print(warn_line("No Agent Drive data found.", palette=p))
        return 0

    if args.all and not getattr(args, "yes", False):
        ok = confirm_prompt(
            console,
            title="Clean ALL Agent Drive data including genomes?",
            body=(
                f"This will delete cache/, pool/, logs/, reasoning/, "
                f"AND [agentdrive.warn]genomes/[/] under [agentdrive.genome]{home}[/].\n"
                f"Your config + sessions are preserved. [agentdrive.warn]Genome registry will be wiped.[/]"
            ),
            default_yes=False,
            danger=True,
            palette=p,
        )
        if not ok:
            console.print()
            console.print(info_line("Cancelled. Nothing changed.", palette=p))
            return 0

    dirs_to_clean = ["cache", "drive", "logs", "reasoning"]
    for name in dirs_to_clean:
        target = home / name
        if target.exists():
            shutil.rmtree(target)
            console.print(ok_line(f"Cleaned [agentdrive.genome]{target}[/]", palette=p))

    if args.all:
        genomes_dir = home / "genomes"
        if genomes_dir.exists():
            shutil.rmtree(genomes_dir)
            console.print(ok_line(f"Cleaned [agentdrive.genome]{genomes_dir}[/]", palette=p))

    console.print()
    console.print(ok_line("Agent Drive data cleaned.", palette=p))
    return 0


# Canonical source for self-update / reinstall. Overridable via env for forks
# or mirrors. Defaults kept factual to the live GitHub repo for functionality.
_REPO_OWNER = os.environ.get("AGENTDRIVE_REPO_OWNER", "PabloTheThinker")
_REPO_NAME = os.environ.get("AGENTDRIVE_REPO_NAME", "agentdrive")
_REPO_HTTPS = f"https://github.com/{_REPO_OWNER}/{_REPO_NAME}.git"


def _fetch_remote_head_sha(branch: str = "main") -> str | None:
    """Return the remote HEAD short SHA for the given branch, or None on failure."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", _REPO_HTTPS, f"refs/heads/{branch}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        full_sha = result.stdout.strip().split()[0]
        return full_sha[:7]
    except Exception:
        return None


def _fetch_recent_commits(branch: str = "main", limit: int = 5) -> list[dict]:
    """Fetch the most recent commits from the GitHub REST API (no auth required)."""
    try:
        import httpx

        url = f"https://api.github.com/repos/{_REPO_OWNER}/{_REPO_NAME}/commits"
        resp = httpx.get(url, params={"sha": branch, "per_page": limit}, timeout=8)
        resp.raise_for_status()
        out = []
        for c in resp.json():
            out.append(
                {
                    "sha": c.get("sha", "")[:7],
                    "message": (c.get("commit", {}).get("message", "") or "").split("\n", 1)[0],
                    "author": c.get("commit", {}).get("author", {}).get("name", ""),
                    "date": c.get("commit", {}).get("author", {}).get("date", ""),
                }
            )
        return out
    except Exception:
        return []


def _verify_installed_version(venv_pip: Path) -> str | None:
    """Return the version of agentdrive installed in the venv."""
    try:
        out = subprocess.run(
            [str(venv_pip), "show", "agentdrive"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        for line in out.stdout.splitlines():
            if line.lower().startswith("version:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        return None
    return None


def cmd_reinstall(args: argparse.Namespace) -> int:
    """Reinstall Agent Drive from the same source into the venv.

    Same flow as ``cmd_update`` but skips the up-to-date short-circuit so it
    always force-reinstalls — used after corruption or to recover from a bad
    state.
    """
    return _run_update_flow(args, force=True)


# ---------------------------------------------------------------------------
# MCP integration commands (for Claude Code, Grok, Cursor, Codex, etc.)
# ---------------------------------------------------------------------------


def cmd_mcp_serve(args: argparse.Namespace) -> int:
    """Start the AgentDrive MCP server (stdio by default).

    This is the bridge that lets Claude Code, Grok CLI, Cursor, Windsurf,
    and other MCP-capable AI clients use the Experience Graph, DNA pools,
    and structural reasoning surfaces directly.
    """
    if run_mcp_server is None:
        console.print("[red]MCP server not available.[/] Install with: pip install 'mcp'")
        return 1

    transport = getattr(args, "transport", "stdio")
    port = getattr(args, "port", 9876)
    verbose = getattr(args, "verbose", False)

    console.print(f"[bold cyan]Starting AgentDrive MCP server[/] (transport={transport})")
    if transport != "stdio":
        console.print(f"  Listening on http://127.0.0.1:{port}")

    console.print("[dim]Press Ctrl-C to stop. Use this with your AI CLI's MCP config.[/]")
    console.print()

    try:
        run_mcp_server(transport=transport, port=port, verbose=verbose)
    except KeyboardInterrupt:
        console.print("\n[dim]MCP server stopped.[/]")
    return 0


def cmd_mcp_config(args: argparse.Namespace) -> int:
    """Print ready-to-paste MCP configuration for popular AI CLIs."""
    import json as _json

    from agentdrive.adapters.mcp_config import (
        client_config_paths,
        export_client_bundle,
        get_grok_toml_snippet,
        resolve_mcp_launcher,
        write_client_config,
    )

    prefer_uvx = bool(getattr(args, "uvx", False))
    as_json = bool(getattr(args, "json", False))
    client = getattr(args, "client", None)
    do_write = bool(getattr(args, "write", False))

    bundle = export_client_bundle(prefer_uvx=prefer_uvx)
    launcher = resolve_mcp_launcher(prefer_uvx=prefer_uvx)

    if as_json:
        console.print(_json.dumps(bundle, indent=2))
        return 0

    if do_write:
        targets = [client] if client else ["grok", "cursor", "claude", "continue"]
        for cid in targets:
            result = write_client_config(cid, prefer_uvx=prefer_uvx, dry_run=False)  # type: ignore[arg-type]
            if result.get("written"):
                console.print(f"[green]✓[/] wrote {cid} → {result.get('path')}")
            else:
                console.print(f"[yellow]⚠[/] skipped {cid} (no target path)")
        return 0

    if client:
        block = bundle["mcpServers"]
        if client == "grok":
            console.print(get_grok_toml_snippet(prefer_uvx=prefer_uvx), highlight=False)
        else:
            console.print(_json.dumps({"mcpServers": block}, indent=2), highlight=False)
        paths = client_config_paths().get(client, [])  # type: ignore[arg-type]
        if paths:
            console.print(f"\n[dim]Config path:[/] {paths[0]}")
        return 0

    console.print(Panel.fit(
        "[bold cyan]AgentDrive MCP — connect any AI model[/]\n\n"
        f"Resolved launcher: [green]{launcher.method}[/] → {launcher.command}\n"
        f"[dim]{launcher.notes}[/]",
        title="agentdrive mcp config",
        border_style="cyan",
    ))

    console.print("\n[bold]Quick connect[/]\n")
    console.print("  [green]agentdrive mcp install[/]           # pip install [mcp] + write client configs")
    console.print("  [green]agentdrive mcp doctor[/]           # verify tools + launcher")
    console.print("  [green]agentdrive mcp config --write[/]   # merge into Grok/Cursor/Claude/Continue configs")
    console.print("  [green]agentdrive mcp config --json[/]     # machine-readable bundle")

    console.print("\n[bold]1. Grok[/]\n")
    console.print(f"  [green]{bundle['grok_cli']}[/]")
    console.print("\n[dim]" + bundle["grok_toml"].strip() + "[/dim]", highlight=False)

    console.print("\n[bold]2. Claude / Continue / Cursor[/]\n")
    console.print(_json.dumps({"mcpServers": bundle["mcpServers"]}, indent=2), highlight=False)
    console.print("\n[dim]Cursor path: ~/.cursor/mcp.json · Claude: ~/.config/claude/claude_desktop_config.json[/]")

    console.print("\n[bold]3. Clone / editable install fallback[/]\n")
    console.print(
        f"  command: [green]{launcher.command}[/]\n"
        f"  args: [green]{' '.join(launcher.args)}[/]"
    )

    console.print("\n[dim]Onboarding for models: docs/FOR_AI_MODELS.md · Full guide: docs/MCP.md[/]\n")
    return 0


def cmd_mcp_doctor(args: argparse.Namespace) -> int:
    """Verify MCP package, launcher resolution, and tool registration."""
    from agentdrive.adapters.mcp_config import run_mcp_doctor

    report = run_mcp_doctor(prefer_uvx=bool(getattr(args, "uvx", False)))
    console.print(Panel.fit("[bold]AgentDrive MCP doctor[/]", border_style="cyan"))
    for check in report.get("checks", []):
        mark = "[green]✓[/]" if check.get("ok") else "[red]✗[/]"
        console.print(f"  {mark} {check.get('name')}: {check.get('detail')}")
    launcher = report.get("launcher", {})
    console.print(
        f"\n[dim]Launcher[/] {launcher.get('method')} → {launcher.get('command')} "
        f"{' '.join(launcher.get('args') or [])}"
    )
    if report.get("ok"):
        console.print(f"\n[green]MCP ready[/] — {report.get('tool_count', 0)} tools for your AI client")
        return 0
    console.print("\n[red]MCP not ready[/] — run: [green]agentdrive mcp install[/]")
    return 1


def cmd_mcp_install(args: argparse.Namespace) -> int:
    """Install MCP extra and optionally write client configuration files."""
    from agentdrive.adapters.mcp_config import (
        install_mcp_extra,
        run_mcp_doctor,
        try_grok_mcp_add,
        write_client_config,
    )

    if not getattr(args, "skip_pip", False):
        console.print("[cyan]Installing agentdrive[mcp]…[/]")
        pip_result = install_mcp_extra()
        if pip_result.get("ok"):
            console.print("[green]✓[/] mcp extra installed")
        else:
            console.print("[yellow]⚠[/] pip install reported issues (may already be installed)")
            if pip_result.get("stderr"):
                console.print(f"[dim]{pip_result['stderr'][-300:]}[/]")

    if getattr(args, "write", True):
        for client in ("grok", "cursor", "claude", "continue"):
            result = write_client_config(client, dry_run=False)  # type: ignore[arg-type]
            if result.get("written"):
                console.print(f"[green]✓[/] merged MCP config for {client} → {result.get('path')}")

    grok = try_grok_mcp_add()
    if grok.get("ok"):
        console.print("[green]✓[/] registered via grok mcp add")
    elif shutil.which("grok"):
        console.print(f"[dim]grok mcp add: {grok.get('stderr') or grok.get('reason', '')}[/]")

    report = run_mcp_doctor()
    if report.get("ok"):
        console.print(f"\n[green]MCP connection ready[/] — {report.get('tool_count')} tools")
        console.print("[dim]Restart your AI client, then call experience_graph_get_context_pack[/]")
        return 0
    return cmd_mcp_doctor(args)


def cmd_mcp_tools(args: argparse.Namespace) -> int:
    """List MCP tools exposed by the AgentDrive server."""
    from agentdrive.adapters.mcp_config import list_mcp_tool_names

    tools = list_mcp_tool_names()
    if getattr(args, "json", False):
        import json as _json

        console.print(_json.dumps({"count": len(tools), "tools": tools}, indent=2))
        return 0
    console.print(f"[bold]{len(tools)} MCP tools[/]\n")
    for name in tools:
        console.print(f"  • {name}")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    """Update AgentDrive to the latest version from GitHub."""
    return _run_update_flow(args, force=False)


def _run_update_flow(args: argparse.Namespace, force: bool) -> int:
    """Polished, animated update flow with version check, changelog, and verification."""
    from rich.console import Group
    from rich.text import Text

    from agentdrive.tui.loading import StepProgress

    branch = getattr(args, "branch", "main") or "main"
    venv_dir = get_agentdrive_home() / "venv"
    venv_pip = venv_dir / "bin" / "pip"
    use_uv_fallback = shutil.which("uv") is not None and not venv_pip.exists()

    if not venv_dir.exists():
        console.print("[red]AgentDrive virtual environment not found. Re-run the installer.[/]")
        return 1
    if not venv_pip.exists() and not use_uv_fallback:
        console.print("[red]No pip or uv found in the AgentDrive venv.[/]")
        return 1

    # ─── Pre-flight panel ────────────────────────────────────────────
    current_version = (
        _verify_installed_version(venv_pip) if venv_pip.exists() else AGENTDRIVE_VERSION
    )
    pre = Group(
        Text.from_markup("[bold cyan]◆ Agent Drive update[/]"),
        Text.from_markup(f"  [dim]source[/]  {_REPO_HTTPS}"),
        Text.from_markup(f"  [dim]branch[/]  {branch}"),
        Text.from_markup(f"  [dim]current[/] v{current_version or '?'}"),
    )
    console.print()
    console.print(Panel(pre, border_style="cyan", padding=(1, 2)))
    console.print()

    # ─── Stepped flow ─────────────────────────────────────────────────
    steps = StepProgress(
        console,
        labels=[
            "Inspect current install",
            "Fetch latest from GitHub",
            "Plan upgrade",
            "Install upgrade",
            "Verify installation",
        ],
        title="Updating Agent Drive",
    )
    steps.start()

    # Step 1: inspect current install
    steps.advance(f"v{current_version or '?'}")

    # Step 2: fetch remote head + recent commits in parallel via thread
    remote_sha = _fetch_remote_head_sha(branch)
    if remote_sha is None:
        steps.fail("could not reach GitHub")
        steps.finish()
        console.print()
        console.print("[red]Update aborted:[/] failed to fetch remote HEAD. Check your network.")
        return 1
    recent = _fetch_recent_commits(branch=branch, limit=5)
    steps.advance(f"remote @{remote_sha}")

    # Step 3: plan
    up_to_date = (
        current_version is not None
        and remote_sha
        and _is_same_revision(current_version, remote_sha)
    )
    if up_to_date and not force:
        steps.skip("already up to date")
        # Skip remaining
        steps.skip("nothing to install")
        steps.skip("nothing to verify")
        steps.finish()

        console.print()
        already = Group(
            Text.from_markup("[bold green]✓ Already up to date[/]"),
            Text.from_markup(f"  [dim]current[/]  v{current_version}"),
            Text.from_markup(f"  [dim]remote[/]   @{remote_sha}"),
            Text.from_markup(
                "  [dim]nothing to do — run with[/] [cyan]--force[/] [dim]to reinstall anyway[/]"
            ),
        )
        console.print(Panel(already, border_style="green", padding=(1, 2)))
        return 0

    plan_detail = "force reinstall" if force else f"upgrade to @{remote_sha}"
    steps.advance(plan_detail)

    # Step 4: install
    spec = f"git+{_REPO_HTTPS}@{branch}"
    steps.detail(f"pip install {spec[:48]}…")
    if venv_pip.exists():
        proc = subprocess.run(
            [str(venv_pip), "install", "--upgrade", "--force-reinstall", spec],
            capture_output=True,
            text=True,
        )
    else:
        proc = subprocess.run(
            ["uv", "pip", "install", "--force-reinstall", spec],
            capture_output=True,
            text=True,
            env={**os.environ, "VIRTUAL_ENV": str(venv_dir)},
        )

    if proc.returncode != 0:
        last_err = (proc.stderr.strip().splitlines() or [""])[-1][:80]
        steps.fail(last_err)
        steps.skip("install failed — verification skipped")
        steps.finish()
        console.print()
        console.print("[red]Update failed:[/]")
        console.print(rich_escape((proc.stderr or proc.stdout or "").strip())[:1200])
        return 1

    steps.advance("installed")

    # Step 5: verify
    new_version = _verify_installed_version(venv_pip) if venv_pip.exists() else current_version
    if new_version is None:
        steps.fail("verify failed")
    else:
        steps.advance(f"v{new_version}")
    steps.finish()

    # ─── Result panel ─────────────────────────────────────────────────
    console.print()
    rows = [
        Text.from_markup("[bold green]✓ Update complete[/]"),
        Text.from_markup(f"  [dim]from[/]    v{current_version or '?'}"),
        Text.from_markup(f"  [dim]to[/]      v{new_version or '?'} [dim]@{remote_sha}[/]"),
    ]
    if recent:
        rows.append(Text(""))
        rows.append(Text.from_markup("[bold cyan]Recent commits[/]"))
        for i, c in enumerate(recent):
            is_last = i == len(recent) - 1
            stem = "└─" if is_last else "├─"
            msg = (c["message"][:62] + "…") if len(c["message"]) > 62 else c["message"]
            rows.append(
                Text.from_markup(
                    f"  [grey50]{stem}[/] [bold green]{c['sha']}[/] {rich_escape(msg)}"
                )
            )

    rows.append(Text(""))
    rows.append(
        Text.from_markup(
            "  [dim]restart any open[/] [cyan]agentdrive[/] [dim]TUI for changes to take effect[/]"
        )
    )
    console.print(Panel(Group(*rows), border_style="green", padding=(1, 2)))
    return 0


def _is_same_revision(current_version: str, remote_sha: str) -> bool:
    """Heuristic: if AGENTDRIVE_VERSION embeds the remote SHA, treat as up-to-date.

    Until we wire commit-tagged dev versions, this is conservative:
    just compare the trimmed SHA against the version trailer.
    """
    return current_version.endswith(remote_sha) if current_version and remote_sha else False


def cmd_provider(args: argparse.Namespace) -> int:
    """List and manage AI model providers."""
    from agentdrive.providers import (
        get,
        list_all,
        save_config_provider,
        write_env_var,
    )

    sub = getattr(args, "provider_subcommand", "list")

    if sub == "list":
        from agentdrive.tui.loading import MicroSpinner

        with MicroSpinner(console, "scanning provider profiles…", style="braille"):
            providers = list(list_all())

        console.print()
        console.print("[bold cyan]Available AI Providers[/]")
        for i, p in enumerate(providers):
            is_last = i == len(providers) - 1
            stem = "└─" if is_last else "├─"
            mark = "[green]✓[/]" if p.has_key() else "[grey50]·[/]"
            console.print(
                f"  [grey50]{stem}[/] {mark} [bold cyan]{p.name:<12}[/] [dim]{p.description[:48]}[/]"
            )
            if p.default_model:
                pre = "│" if not is_last else " "
                console.print(
                    f"  [grey50]{pre}[/]     [dim]default model:[/] [agentdrive.genome]{p.default_model}[/]"
                )
        console.print("\n[dim]Configure with[/] [cyan]agentdrive provider set <name>[/]")
        return 0

    if sub == "set":
        pname = args.provider_name or ""
        if not pname:
            console.print("[red]Usage: agentdrive provider set <name>[/]")
            return 1

        profile = get(pname)
        if not profile:
            console.print(f"[red]Unknown provider: {pname}[/]")
            console.print(f"Available: {', '.join(p.name for p in list_all())}")
            return 1

        if profile.requires_key:
            env_var = profile.env_var
            existing = profile.get_api_key()
            if existing:
                console.print(f"[green]✓[/] {profile.display_name} already has a key configured.")
                from rich.prompt import Confirm

                if not Confirm.ask("Replace it?"):
                    save_config_provider(profile.name, args.model or "")
                    if args.model:
                        console.print(f"[green]✓[/] Model set to {args.model}")
                    else:
                        console.print(f"[green]✓[/] Provider set to {profile.name}")
                    return 0

            from rich.prompt import Confirm, Prompt

            console.print(f"\n[bold]Configure {profile.display_name}[/]")
            console.print(f"Get your API key at: [cyan]{profile.signup_url}[/]")
            console.print(
                f"It will be stored in: [dim]{get_agentdrive_home() / '.env'}[/] (permissions 600)\n"
            )
            key = Prompt.ask("API key", password=True).strip()
            if key and key not in ("", "*", "changeme"):
                write_env_var(env_var, key)
                console.print(f"[green]✓[/] API key saved for {profile.display_name}")
            else:
                console.print(
                    "[yellow]No key entered. Provider will not be usable until a key is set.[/]"
                )

        save_config_provider(profile.name, args.model or "")
        if args.model:
            console.print(f"[green]✓[/] Model set to {args.model}")
        else:
            console.print(f"[green]✓[/] Active provider set to {profile.name}")
        return 0

    if sub == "key":
        pname = args.provider_name or ""
        if not pname:
            console.print("[red]Usage: agentdrive provider key <name>[/]")
            return 1
        profile = get(pname)
        if not profile:
            console.print(f"[red]Unknown provider: {pname}[/]")
            return 1
        if not profile.env_var:
            console.print(f"[yellow]{profile.display_name} does not require an API key.[/]")
            return 0

        from rich.prompt import Prompt

        console.print(f"\nSet API key for [bold]{profile.display_name}[/]")
        console.print(f"Env var: [cyan]{profile.env_var}[/]")
        console.print(f"Get a key at: [cyan]{profile.signup_url}[/]\n")
        key = Prompt.ask("API key", password=True).strip()
        if key:
            write_env_var(profile.env_var, key)
            console.print(f"[green]✓[/] Key saved to {get_agentdrive_home() / '.env'}")
        return 0

    console.print("[red]Unknown provider subcommand[/]")
    return 1


def cmd_model(args: argparse.Namespace) -> int:
    """List or switch the active model for your configured provider."""
    from agentdrive.providers import get, load_config_provider, save_config_provider

    sub = getattr(args, "model_subcommand", "list")

    cfg = load_config_provider()
    current_provider = cfg[0] if cfg else None
    current_model = cfg[1] if cfg else ""

    if sub == "list":
        profile = None
        if current_provider:
            profile = get(current_provider)

        console.print("[bold]Active Model Configuration[/]\n")
        if profile:
            console.print(
                f"  Provider: [cyan]{profile.display_name}[/]  {'[green]✓[/]' if profile.has_key() else '[yellow]no key[/]'}"
            )
            console.print(
                f"  Model:    [agentdrive.genome]{current_model or profile.default_model or 'not set'}[/]"
            )

            models = profile.fallback_models
            if models:
                console.print(f"\n[bold]Available models for {profile.display_name}:[/]")
                for m in models:
                    mark = (
                        "[agentdrive.accent]→ active[/]"
                        if m == (current_model or profile.default_model)
                        else ""
                    )
                    console.print(f"  • [agentdrive.genome]{m}[/] {mark}")
        else:
            console.print("  [yellow]No provider configured.[/]")
            console.print("  Use [cyan]agentdrive provider set <name>[/] to configure one.")

        console.print("\n[dim]Use 'agentdrive model set <model>' to switch.[/]")
        return 0

    if sub == "set":
        model = args.model_name or ""
        if not model:
            console.print("[red]Usage: agentdrive model set <model-id>[/]")
            console.print("  List available models with: [cyan]agentdrive model list[/]")
            return 1

        if current_provider:
            save_config_provider(current_provider, model)
            console.print(f"[green]✓[/] Active model set to [agentdrive.genome]{model}[/]")
        else:
            console.print("[yellow]No provider configured. Set a provider first:[/]")
            console.print("  [cyan]agentdrive provider set openai[/]")
        return 0

    console.print("[red]Unknown model subcommand[/]")
    return 1


def _run_onboarding() -> None:
    from agentdrive.onboarding import run_onboarding

    run_onboarding()


def cmd_ops(args: argparse.Namespace) -> int:
    """Contract-first operations registry (list / describe / run)."""
    from agentdrive.operations import (
        describe_operation,
        export_operations_json,
        get_operation,
        list_operations,
        parse_operation_kwargs,
        run_operation,
    )

    sub = getattr(args, "ops_subcommand", None) or "list"

    if sub == "list":
        ops = list_operations()
        table = Table(title=f"Operations ({len(ops)})", show_header=True)
        table.add_column("Name", style="bold cyan")
        table.add_column("Category")
        table.add_column("Read-only")
        table.add_column("CLI", overflow="fold")
        table.add_column("MCP", overflow="fold")
        for op in ops:
            table.add_row(
                op.name,
                op.category,
                "yes" if op.read_only else "no",
                op.cli_command or "—",
                op.mcp_tool or "—",
            )
        console.print(table)
        return 0

    if sub == "describe":
        name = getattr(args, "operation_name", None)
        if not name:
            console.print("[red]Usage: agentdrive ops describe <name>[/]")
            return 1
        try:
            detail = describe_operation(name)
        except KeyError:
            console.print(f"[red]Unknown operation:[/] {name}")
            return 1
        console.print(json.dumps(detail, indent=2))
        return 0

    if sub == "export":
        console.print(export_operations_json())
        return 0

    if sub == "run":
        name = getattr(args, "operation_name", None)
        if not name:
            console.print("[red]Usage: agentdrive ops run <name> [--dry-run] [--json] [key=value ...][/]")
            return 1
        if get_operation(name) is None:
            console.print(f"[red]Unknown operation:[/] {name}")
            return 1

        kwargs = parse_operation_kwargs(getattr(args, "ops_kwargs", []) or [])
        if getattr(args, "dry_run", False):
            kwargs["dry_run"] = True

        result = run_operation(name, **kwargs)
        if getattr(args, "json_output", False):
            console.print(json.dumps(result, indent=2, default=str))
        else:
            success = result.get("success", False)
            style = "green" if success else "red"
            console.print(f"[{style}]{name}[/] → success={success}")
            if result.get("dry_run"):
                console.print("[dim]dry-run mode[/]")
            if result.get("error"):
                console.print(f"[red]error:[/] {result['error']}")
            elif getattr(args, "json_output", False) is False:
                preview = json.dumps(result, indent=2, default=str)
                if len(preview) > 2400:
                    preview = preview[:2400] + "\n…"
                console.print(preview)
        return 0 if result.get("success", False) else 1

    console.print("[red]Unknown ops subcommand[/]")
    return 1


def cmd_demo_swarm(args: argparse.Namespace) -> int:
    """Scripted 10-second demo of the live SubagentTree renderer.

    Spawns four sub-agents on the default event bus, drives a believable
    progression of tool / token / done events, and renders the tree
    inside a ``rich.live.Live`` at 8 Hz. Used as the visual proof for
    UX Pattern 4 before real multi-agent dispatch lands.
    """
    import random
    import threading
    import time as _time

    from rich.live import Live

    from agentdrive.events import (
        SubagentDone,
        SubagentSpawn,
        SubagentTokens,
        SubagentTool,
        default_bus,
    )
    from agentdrive.tui.chrome import Palette
    from agentdrive.tui.skin_engine import skin
    from agentdrive.tui.subagent_tree import SubagentTree

    setup_logging()

    palette = Palette(skin)
    tree = SubagentTree(root_id="orchestrator", root_label="agentdrive orchestrator")

    # Subscribe the tree to the default bus so any emission updates state.
    token = default_bus.subscribe(tree.apply)

    # Scripted swarm: (id, label, lifetime_s, tools, final_ok)
    script = [
        ("ingest-1", "ingest-1", 3.5, ["bash(rg)", "read_file(genomes/*)", "embed"], True),
        ("trace-2", "trace-2", 9.0, ["bash(strace)", "parse", "summarize"], True),
        ("scorer-1", "scorer-1", 2.2, ["score", "rank"], False),  # fails early
        ("author-1", "author-1", 7.0, ["draft", "review", "write_file(out.md)"], True),
    ]

    rng = random.Random(7)
    start = _time.monotonic()

    def _drive(sid: str, label: str, lifetime: float, tools: list[str], ok: bool) -> None:
        # Stagger the spawn so the tree visibly grows.
        delay = rng.uniform(0.1, 1.0)
        _time.sleep(delay)
        default_bus.emit(
            SubagentSpawn(
                subagent_id=sid,
                parent_id="orchestrator",
                label=label,
            )
        )

        spawned_at = _time.monotonic()
        # Emit a few tool transitions + token bursts across the lifetime.
        steps = max(len(tools), 3)
        step_dt = lifetime / (steps + 1)
        cum_tokens = 0
        cum_cost = 0.0
        for i in range(steps):
            _time.sleep(step_dt)
            tool = tools[i % len(tools)]
            default_bus.emit(SubagentTool(subagent_id=sid, tool=tool))
            burst = rng.randint(400, 1800)
            cost = burst * rng.uniform(0.000015, 0.00004)
            cum_tokens += burst
            cum_cost += cost
            default_bus.emit(
                SubagentTokens(
                    subagent_id=sid,
                    tokens=burst,
                    cost_usd=cost,
                )
            )

        _time.sleep(step_dt)
        duration = _time.monotonic() - spawned_at
        default_bus.emit(
            SubagentDone(
                subagent_id=sid,
                ok=ok,
                duration_s=duration,
            )
        )

    threads = [threading.Thread(target=_drive, args=row, daemon=True) for row in script]

    try:
        with Live(
            tree.render(palette),
            console=console,
            refresh_per_second=8,
            transient=False,
        ) as live:
            for t in threads:
                t.start()

            # Hard cap so a demo never wedges the terminal.
            deadline = start + 14.0
            while _time.monotonic() < deadline:
                live.update(tree.render(palette))
                # Once every worker finishes, mark the root done and exit.
                worker_done = all(
                    (n := tree.get(sid)) is not None and n.is_terminal for sid, *_ in script
                )
                if worker_done:
                    default_bus.emit(
                        SubagentDone(
                            subagent_id="orchestrator",
                            ok=True,
                            duration_s=_time.monotonic() - start,
                        )
                    )
                    live.update(tree.render(palette))
                    break
                _time.sleep(1 / 8)

            for t in threads:
                t.join(timeout=0.5)

        # Final static snapshot after Live exits.
        console.print()
        console.print(tree.render(palette))
        console.print()
        elapsed = _time.monotonic() - start
        console.print(f"[dim]demo-swarm complete · {elapsed:.1f}s · {len(tree.nodes())} nodes[/]")
        # The simulation deliberately fails one sub-agent (scorer-1) to
        # exercise the ✗ render path. Surface that intent so new users
        # don't read the red ✗ as a broken demo.
        console.print(
            "[dim]note: scorer-1 fails intentionally — the demo exercises "
            "both the success and failure render paths.[/]"
        )
        return 0
    finally:
        default_bus.unsubscribe(token)


def _register_drive_parsers(
    subparsers: argparse._SubParsersAction,
    *,
    names: tuple[str, ...] = ("drive",),
    help_text: str = "AgentDrive: status, ingest genomes, query by task, detailed stats",
) -> None:
    """Register drive (and optional pool alias) with identical subcommands."""
    for name in names:
        p = subparsers.add_parser(name, help=help_text)
        pool_subs = p.add_subparsers(dest="pool_subcommand")
        ps = pool_subs.add_parser(
            "status", help="Show Drive status, integration with registry, recent activity"
        )
        ps.set_defaults(func=cmd_pool)
        pi = pool_subs.add_parser(
            "ingest", help="Ingest a genome directory (manifest + files) into this Drive"
        )
        pi.add_argument(
            "genome_dir",
            help="Filesystem path to a genome directory (e.g. genomes/examples/xxx-v1)",
        )
        pi.set_defaults(func=cmd_pool)
        pq = pool_subs.add_parser(
            "query", help="Semantic query of the Drive for genomes relevant to a task description"
        )
        pq.add_argument(
            "task",
            help='Natural language task description (e.g. "security incident postmortem")',
        )
        pq.add_argument("--limit", type=int, default=5, help="Maximum number of results (default 5)")
        pq.add_argument("--min-score", type=float, default=0.0, help="Minimum evaluation score filter")
        pq.set_defaults(func=cmd_pool)
        pst = pool_subs.add_parser(
            "stats", help="Full pool statistics (ingest counts, sources, actors, registry metrics)"
        )
        pst.set_defaults(func=cmd_pool)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentdrive",
        description="AgentDrive — local-first Drive for AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=build_help_epilog(),
    )
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Skip default TUI; launch operator REPL when no subcommand is given",
    )
    subparsers = parser.add_subparsers(dest="command")

    # repl — operator shell (Pattern 5)
    p = subparsers.add_parser(
        "repl",
        help="Operator REPL — dispatch any subcommand interactively (no TUI)",
    )
    p.set_defaults(func=cmd_repl)

    # Mission Control — the new unified real-time interface (recommended)
    p = subparsers.add_parser(
        "mission",
        help="Launch Mission Control — real-time view of the entire AgentDrive system (loop + fabric + static fire)",
    )
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8421)
    p.set_defaults(func=cmd_mission)

    # Board / Kanban — the prominent localhost Kanban experience (Hermes dashboard equivalent)
    for name, help_text in [
        ("board", "Launch the Mission Kanban Board (web) — persistent lanes with live updates"),
        ("kanban", "Alias for board (Kanban Mission Board on localhost)"),
    ]:
        p = subparsers.add_parser(name, help=help_text)
        p.add_argument("--host", default="0.0.0.0")
        p.add_argument("--port", type=int, default=8421)
        p.set_defaults(func=cmd_board)

    # TUI (explicit entry; supports cross-process Mission Control client --mission flag for Wave 3)
    p = subparsers.add_parser(
        "tui",
        help="Launch the professional AgentDrive TUI (genome registry, chat, pool, mc view). Use --mission for separate-process live MC Tower.",
    )
    p.add_argument(
        "--mission",
        "--mc",
        dest="mission_url",
        default=None,
        metavar="WS_URL",
        help="Cross-process: connect TUI 'mc' view to remote Mission Control at ws://host:port (e.g. ws://127.0.0.1:8421 from `agentdrive mission`). Falls back to /state + WS if websocket-client installed. Env: AGENTDRIVE_MISSION_URL.",
    )
    p.set_defaults(func=cmd_tui)

    # grid — the real-time active engine that keeps the AgentDrive Grid alive
    p = subparsers.add_parser(
        "grid",
        help="Run AD-Grid (the long-lived persistent intelligence substrate that grows from all projects)",
    )
    p.add_argument("--swarm-id", default="active-grid", help="Swarm to bind the Grid to")
    p.add_argument("--interval", type=float, default=15.0, help="Damage scan interval in seconds")
    p.add_argument(
        "--with-tower",
        action="store_true",
        help="Also start the Mission Control Tower on :8421 for live Grid observability (the persistent 'window into the Grid')",
    )
    p.set_defaults(func=cmd_grid)

    # setup wizard (modular experience)
    p = subparsers.add_parser("setup", help="Interactive setup wizard")
    p.add_argument("section", nargs="?", help="Optional section: home, pool, swarm, ai, tui")
    p.set_defaults(func=cmd_setup)

    # explicit onboarding (lightweight first-run flow)
    p = subparsers.add_parser(
        "onboard", help="Run the guided first-time consent flow (lighter than full setup)"
    )
    p.set_defaults(func=lambda args: _run_onboarding())

    # genomes
    p = subparsers.add_parser("genomes", help="Genome registry operations")
    p.add_argument("subcommand", nargs="?", choices=["list", "info", "search"], default="list")
    p.add_argument("id", nargs="*", help="Genome ID for 'info' or query words for 'search'")
    p.set_defaults(func=cmd_genomes)

    # patterns — Fabric-style pattern-as-genome catalog
    p = subparsers.add_parser(
        "patterns",
        help="Fabric-style pattern catalog (bundled genomes/patterns + ~/.agentdrive/patterns overlay)",
    )
    pat_subs = p.add_subparsers(dest="patterns_subcommand")

    pat_list = pat_subs.add_parser("list", help="List available patterns")
    pat_list.set_defaults(func=cmd_patterns)

    pat_show = pat_subs.add_parser("show", help="Show pattern metadata and system.md preview")
    pat_show.add_argument("pattern_name", help="Pattern directory name (e.g. morning-brief-v1)")
    pat_show.set_defaults(func=cmd_patterns)

    pat_apply = pat_subs.add_parser(
        "apply", help="Compose system+user prompt with {{input}} replaced"
    )
    pat_apply.add_argument("pattern_name", help="Pattern directory name (e.g. morning-brief-v1)")
    pat_apply.add_argument(
        "--input",
        default=None,
        help="Input text for {{input}} (reads stdin when omitted and not a TTY)",
    )
    pat_apply.set_defaults(func=cmd_patterns)

    pat_import = pat_subs.add_parser(
        "import-fabric",
        help="Import Fabric data/patterns into ~/.agentdrive/patterns overlay",
    )
    pat_import.add_argument(
        "--source",
        default=None,
        help="Fabric repository root (default: FABRIC_PATTERNS_ROOT or walk-up discovery)",
    )
    pat_import.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum patterns to import when --pattern is omitted (default: 10)",
    )
    pat_import.add_argument(
        "--pattern",
        default=None,
        help="Import a single Fabric pattern by source folder name",
    )
    pat_import.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing imported pattern genomes",
    )
    pat_import.set_defaults(func=cmd_patterns)

    # default behavior when no subcommand is given: list
    p.set_defaults(func=cmd_patterns, patterns_subcommand="list")

    # scan
    p = subparsers.add_parser("scan", help="Scan runs / trajectories and extract candidate Genomes")
    p.add_argument("path", nargs="?", help="Optional path to run data or genome source dir")
    p.set_defaults(func=cmd_scan)

    # doctor
    p = subparsers.add_parser(
        "doctor", help="Diagnose AgentDrive installation, config, workers, and registry"
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="After the main result panel, print extra subsystem diagnostics",
    )
    p.set_defaults(func=cmd_doctor)

    # MCP — first-class integration for Claude Code, Grok, Cursor, Codex, etc.
    p = subparsers.add_parser(
        "mcp",
        help="MCP server for AI CLI sessions (Grok /mcp, Claude Code, Cursor, etc.)",
    )
    p.set_defaults(func=cmd_mcp_config)  # bare `agentdrive mcp` shows config + instructions
    mcp_subs = p.add_subparsers(dest="mcp_subcommand")

    # agentdrive mcp serve
    p_serve = mcp_subs.add_parser(
        "serve", help="Start the AgentDrive MCP server (stdio for local AI CLIs)"
    )
    p_serve.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="Transport (stdio is what Grok, Claude Code, Cursor expect)",
    )
    p_serve.add_argument("--port", type=int, default=9876)
    p_serve.add_argument("-v", "--verbose", action="store_true")
    p_serve.set_defaults(func=cmd_mcp_serve)

    # agentdrive mcp config
    p_config = mcp_subs.add_parser(
        "config", help="Print ready-to-paste MCP config snippets for Grok, Claude, Cursor..."
    )
    p_config.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable config bundle (paths, launcher, mcpServers block)",
    )
    p_config.add_argument(
        "--client",
        choices=["grok", "claude", "cursor", "continue", "vscode", "windsurf", "generic"],
        help="Show config for one client only",
    )
    p_config.add_argument(
        "--write",
        action="store_true",
        help="Merge AgentDrive MCP entry into client config files",
    )
    p_config.add_argument(
        "--uvx",
        action="store_true",
        help="Use uvx launcher in generated configs (zero-install)",
    )
    p_config.set_defaults(func=cmd_mcp_config)

    p_doctor = mcp_subs.add_parser("doctor", help="Verify MCP package, launcher, and tool registration")
    p_doctor.add_argument("--uvx", action="store_true", help="Test uvx launcher resolution")
    p_doctor.set_defaults(func=cmd_mcp_doctor)

    p_install = mcp_subs.add_parser(
        "install",
        help="pip install [mcp] and write client configs (Grok, Cursor, Claude, Continue)",
    )
    p_install.add_argument(
        "--no-write",
        dest="write",
        action="store_false",
        help="Skip writing client config files",
    )
    p_install.add_argument(
        "--skip-pip",
        action="store_true",
        help="Skip pip install (config write + doctor only)",
    )
    p_install.set_defaults(func=cmd_mcp_install, write=True)

    p_tools = mcp_subs.add_parser("tools", help="List MCP tools exposed by the server")
    p_tools.add_argument("--json", action="store_true", help="JSON tool list")
    p_tools.set_defaults(func=cmd_mcp_tools)

    # deps — part of the Dependency Updates Framework (see docs/DEPENDENCY_UPDATES.md)
    p = subparsers.add_parser(
        "deps",
        help="Dependency management, compatibility checks, and update support (see docs/DEPENDENCY_UPDATES.md)",
    )
    deps_subs = p.add_subparsers(dest="deps_subcommand")
    dc = deps_subs.add_parser(
        "check", help="Report declared vs installed key dependencies + known compatibility notes"
    )
    dc.set_defaults(func=cmd_deps_check)

    # cap — Mission Control capability minting
    p = subparsers.add_parser("cap", help="Capability management (Mission Control command caps)")
    cap_subs = p.add_subparsers(dest="cap_subcommand")
    p_cap_mint = cap_subs.add_parser(
        "mint-mission",
        help="Mint a capability for Mission Control mutating commands",
    )
    p_cap_mint.add_argument(
        "--command",
        default="*",
        help="Specific command name (e.g. start_static_fire) or * for all mutating commands",
    )
    p_cap_mint.set_defaults(func=cmd_cap)

    # config
    p = subparsers.add_parser("config", help="View and modify AgentDrive configuration")
    p.add_argument("subcommand", nargs="?", choices=["show", "get", "set", "edit"], default="show")
    p.add_argument("key", nargs="?", help="config key for get/set (dot notation supported)")
    p.add_argument("value", nargs="?", help="value for 'set'")
    p.set_defaults(func=cmd_config)

    # workers
    p = subparsers.add_parser("workers", help="List and inspect worker adapters (external etc.)")
    p.add_argument("subcommand", nargs="?", default="list")
    p.set_defaults(func=cmd_workers)

    # drive / pool — first-class queryable persistent pool service
    _register_drive_parsers(
        subparsers,
        names=("drive",),
        help_text="AgentDrive: status, ingest genomes, query by task, detailed stats (persistent JSONL + registry)",
    )
    _register_drive_parsers(
        subparsers,
        names=("pool",),
        help_text="Alias for drive (same subcommands: status, ingest, query, stats)",
    )

    # think — cited synthesis with mandatory gaps
    p = subparsers.add_parser(
        "think",
        help="Cited Drive.think synthesis with mandatory gap analysis",
    )
    p.add_argument("question", help="Question or task to synthesize against the Drive")
    p.add_argument(
        "--no-experience-layer",
        action="store_true",
        help="Skip preferring the experience layer during synthesis",
    )
    p.add_argument("--dry-run", action="store_true", help="Plan without calling synthesis")
    p.add_argument("--json", dest="json_output", action="store_true", help="Emit full JSON result")
    p.set_defaults(func=cmd_think)

    # learnings — gstack-style operational memory
    p = subparsers.add_parser(
        "learnings",
        help="Operational learnings JSONL (log / list / search)",
    )
    learn_subs = p.add_subparsers(dest="learnings_subcommand")

    lr_list = learn_subs.add_parser("list", help="List recent learnings for current project slug")
    lr_list.add_argument("--slug", help="Override project slug (default: git repo basename)")
    lr_list.add_argument("--limit", type=int, default=20)
    lr_list.add_argument("--json", dest="json_output", action="store_true")
    lr_list.set_defaults(func=cmd_learnings)

    lr_log = learn_subs.add_parser("log", help="Append one learning entry")
    lr_log.add_argument("--key", required=True, help="Stable key (alphanumeric, hyphens, underscores)")
    lr_log.add_argument("--insight", required=True, help="Learning insight text")
    lr_log.add_argument(
        "--type",
        default="pattern",
        choices=["pattern", "pitfall", "preference", "architecture", "tool", "operational", "investigation"],
    )
    lr_log.add_argument("--confidence", type=int, default=5, help="1-10 confidence (default 5)")
    lr_log.add_argument(
        "--source",
        default="observed",
        choices=["observed", "user-stated", "inferred", "cross-model"],
    )
    lr_log.add_argument("--skill", default="harness")
    lr_log.add_argument("--slug", help="Override project slug")
    lr_log.add_argument("--dry-run", action="store_true")
    lr_log.add_argument("--json", dest="json_output", action="store_true")
    lr_log.set_defaults(func=cmd_learnings)

    lr_search = learn_subs.add_parser("search", help="Token search over key/insight/files")
    lr_search.add_argument("query", help="Search query (space-separated tokens)")
    lr_search.add_argument("--slug", help="Override project slug")
    lr_search.add_argument("--limit", type=int, default=10)
    lr_search.add_argument("--json", dest="json_output", action="store_true")
    lr_search.set_defaults(func=cmd_learnings)

    p.set_defaults(func=cmd_learnings, learnings_subcommand="list")

    # session — typed event stream inspect / replay (Pattern 1)
    p = subparsers.add_parser(
        "session",
        help="Per-session typed event stream (events.jsonl inspect / replay)",
    )
    session_subs = p.add_subparsers(dest="session_subcommand")

    se_events = session_subs.add_parser(
        "events",
        help="List one-line summaries of recorded session events",
    )
    se_events.add_argument("session_id", help="Session id (full or suffix from /sessions)")
    se_events.add_argument(
        "--agent-id",
        dest="agent_id",
        default="agentdrive-agent",
        help="Agent id (default: agentdrive-agent)",
    )
    se_events.add_argument(
        "--type",
        dest="event_type",
        metavar="EVENT_TYPE",
        help="Filter to one event type (e.g. PoolMatch, MessageDelta)",
    )
    se_events.add_argument("--json", dest="json_output", action="store_true")
    se_events.set_defaults(func=cmd_session)

    se_replay = session_subs.add_parser(
        "replay",
        help="Replay session events as a numbered timeline",
    )
    se_replay.add_argument("session_id", help="Session id (full or suffix from /sessions)")
    se_replay.add_argument(
        "--agent-id",
        dest="agent_id",
        default="agentdrive-agent",
        help="Agent id (default: agentdrive-agent)",
    )
    se_replay.add_argument(
        "--type",
        dest="event_type",
        metavar="EVENT_TYPE",
        help="Filter to one event type (e.g. PoolMatch, MessageDelta)",
    )
    se_replay.add_argument("--json", dest="json_output", action="store_true")
    se_replay.set_defaults(func=cmd_session)

    se_panel = session_subs.add_parser(
        "panel",
        help="Rich replay panel with type histogram and timeline",
    )
    se_panel.add_argument("session_id", help="Session id (full or suffix from /sessions)")
    se_panel.add_argument(
        "--agent-id",
        dest="agent_id",
        default="agentdrive-agent",
        help="Agent id (default: agentdrive-agent)",
    )
    se_panel.add_argument(
        "--type",
        dest="event_type",
        metavar="EVENT_TYPE",
        help="Filter to one event type (e.g. PoolMatch, MessageDelta)",
    )
    se_panel.set_defaults(func=cmd_session)

    p.set_defaults(func=cmd_session, session_subcommand="events")

    # skills — SKILL.md registry (Pattern 5)
    p = subparsers.add_parser(
        "skills",
        help="SKILL.md capabilities — list, show, run (shared with /skill in chat)",
    )
    skills_subs = p.add_subparsers(dest="skills_subcommand")

    sk_list = skills_subs.add_parser("list", help="List discovered skills")
    sk_list.add_argument(
        "--harness",
        dest="skills_harness",
        metavar="NAME",
        choices=["agentdrive", "universal", "grok", "claude", "codex"],
        help="Filter to one harness tier (default: show all tiers)",
    )
    sk_list.add_argument("--json", dest="json_output", action="store_true")
    sk_list.set_defaults(func=cmd_skills)

    sk_show = skills_subs.add_parser("show", help="Show one skill metadata and body")
    sk_show.add_argument("skill_name", help="Skill name from frontmatter")
    sk_show.add_argument("--json", dest="json_output", action="store_true")
    sk_show.set_defaults(func=cmd_skills)

    sk_run = skills_subs.add_parser("run", help="Run a skill by name")
    sk_run.add_argument("skill_name", help="Skill name")
    sk_run.add_argument(
        "skill_arg",
        nargs="*",
        default="",
        help="Arguments passed to the skill operation",
    )
    sk_run.add_argument("--json", dest="json_output", action="store_true")
    sk_run.set_defaults(func=cmd_skills)

    sk_review = skills_subs.add_parser(
        "review",
        help="Review inherited skills using match/run evidence",
    )
    sk_review.add_argument(
        "--include-promoted",
        action="store_true",
        help="Include already-promoted inherited skills",
    )
    sk_review.add_argument("--json", dest="json_output", action="store_true")
    sk_review.set_defaults(func=cmd_skills)

    sk_promote = skills_subs.add_parser(
        "promote",
        help="Promote an inherited skill into the parent bench",
    )
    sk_promote.add_argument("skill_name", help="Inherited skill name")
    sk_promote.add_argument("--json", dest="json_output", action="store_true")
    sk_promote.set_defaults(func=cmd_skills)

    sk_prune = skills_subs.add_parser(
        "prune",
        help="Disable a weak inherited skill without deleting its file",
    )
    sk_prune.add_argument("skill_name", help="Inherited skill name")
    sk_prune.add_argument(
        "--reason",
        default="",
        help="Reason stored in the skill frontmatter",
    )
    sk_prune.add_argument("--json", dest="json_output", action="store_true")
    sk_prune.set_defaults(func=cmd_skills)

    sk_dna = skills_subs.add_parser(
        "dna",
        help="Ingest an inherited/promoted skill into the DNA pool",
    )
    sk_dna.add_argument("skill_name", help="Inherited or promoted skill name")
    sk_dna.add_argument("--json", dest="json_output", action="store_true")
    sk_dna.set_defaults(func=cmd_skills)

    sk_init = skills_subs.add_parser(
        "init",
        help="Scaffold ~/.agentdrive/skills/<name>/SKILL.md",
    )
    sk_init.add_argument("skill_name", help="Skill name (becomes directory slug)")
    sk_init.add_argument(
        "--description",
        dest="skill_description",
        default="",
        help="Frontmatter description (default: generated)",
    )
    sk_init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing SKILL.md",
    )
    sk_init.add_argument("--json", dest="json_output", action="store_true")
    sk_init.set_defaults(func=cmd_skills)

    p.set_defaults(func=cmd_skills, skills_subcommand="list")

    # harness — prompt composition
    p = subparsers.add_parser(
        "harness",
        help="Compose harness prompts (DNA + learnings + optional Fabric layers)",
    )
    harness_subs = p.add_subparsers(dest="harness_subcommand")
    hc = harness_subs.add_parser("compose", help="Compose a full harness context prompt")
    hc.add_argument("--task", help="Current task description")
    hc.add_argument("--prompt", help="Base system prompt (default: generic agent)")
    hc.add_argument("--slug", help="Learnings slug override")
    hc.add_argument("--pattern", help="Fabric pattern name")
    hc.add_argument("--strategy", help="Fabric strategy layer name")
    hc.add_argument("--context", help="Fabric context layer name")
    hc.add_argument("--session-id", dest="session_id", help="Session layer id")
    hc.add_argument("--input-text", dest="input_text", help="Pattern {{input}} substitution")
    hc.add_argument("--agent-id", dest="agent_id", default="cli-harness")
    hc.add_argument("--dry-run", action="store_true")
    hc.add_argument("--json", dest="json_output", action="store_true")
    hc.set_defaults(func=cmd_harness)
    p.set_defaults(func=cmd_harness, harness_subcommand="compose")

    def _register_graph_parsers(names: tuple[str, ...], help_text: str) -> None:
        for gname in names:
            gp = subparsers.add_parser(gname, help=help_text)
            graph_subs = gp.add_subparsers(dest="graph_subcommand")

            gcp = graph_subs.add_parser(
                "context-pack", help="Dense Experience Graph context pack for briefings"
            )
            gcp.add_argument("--swarm-id", dest="swarm_id", help="Swarm id override")
            gcp.add_argument(
                "--reasoning-style",
                dest="reasoning_style",
                default="balanced",
                choices=[
                    "balanced",
                    "high_lift_patterns_only",
                    "weak_links_focus",
                    "structural_analogies",
                    "continuations_only",
                ],
            )
            gcp.add_argument("--lookback-days", type=int, default=7)
            gcp.add_argument("--max-tokens", type=int, default=1800)
            gcp.add_argument("--dry-run", action="store_true")
            gcp.add_argument("--json", dest="json_output", action="store_true")
            gcp.set_defaults(func=cmd_graph)

            gs = graph_subs.add_parser(
                "suggest", help="Schema and examples for authoring reasoning traces"
            )
            gs.add_argument("--swarm-id", dest="swarm_id")
            gs.add_argument("--dry-run", action="store_true")
            gs.add_argument("--json", dest="json_output", action="store_true")
            gs.set_defaults(func=cmd_graph)

            gr = graph_subs.add_parser("record", help="Record structural reasoning into the graph")
            gr.add_argument("--swarm-id", dest="swarm_id")
            gr.add_argument("--cycle-id", dest="cycle_id")
            gr.add_argument("--summary", help="Short reasoning summary")
            gr.add_argument("--reasoning-file", dest="reasoning_file", help="JSON reasoning object file")
            gr.add_argument("--dry-run", action="store_true")
            gr.add_argument("--json", dest="json_output", action="store_true")
            gr.set_defaults(func=cmd_graph)

            gp.set_defaults(func=cmd_graph, graph_subcommand="context-pack")

    _register_graph_parsers(
        ("graph",),
        "Experience Graph: context-pack, record reasoning, suggest structure",
    )
    _register_graph_parsers(
        ("experience",),
        "Alias for graph (Experience Graph commands)",
    )

    # eval — artifact replay
    p = subparsers.add_parser("eval", help="Evaluation utilities (harness replay)")
    eval_subs = p.add_subparsers(dest="eval_subcommand")
    er = eval_subs.add_parser("replay", help="Re-score a stored research artifact JSON")
    er.add_argument("artifact", help="Path to genome/research artifact JSON")
    er.add_argument("--tolerance", type=float, default=0.05, help="Goodness score tolerance")
    er.add_argument("--json", dest="json_output", action="store_true")
    er.set_defaults(func=cmd_eval)
    p.set_defaults(func=cmd_eval, eval_subcommand="replay")

    # golden-path — canonical first-run walkthrough
    p = subparsers.add_parser(
        "golden-path",
        help="First-run golden path: install → doctor → mcp → think → learnings → query",
    )
    gp_subs = p.add_subparsers(dest="golden_subcommand")

    gp_steps = gp_subs.add_parser("steps", help="Show numbered golden-path commands")
    gp_steps.add_argument("--json", dest="json_output", action="store_true")
    gp_steps.set_defaults(func=cmd_golden_path)

    gp_verify = gp_subs.add_parser("verify", help="Verify golden-path step completion")
    gp_verify.add_argument("--step", help="Verify one step (install, doctor, mcp, seed, think, learnings, query)")
    gp_verify.add_argument("--skip-optional", action="store_true", help="Skip optional seed check")
    gp_verify.add_argument("--json", dest="json_output", action="store_true")
    gp_verify.set_defaults(func=cmd_golden_path)

    gp_run = gp_subs.add_parser("run", help="Execute golden-path operations")
    gp_run.add_argument("--dry-run", action="store_true", help="Plan mutating steps without writes")
    gp_run.add_argument(
        "--require-provider",
        action="store_true",
        help="Fail think step when no AI provider is configured (default: skip with hint)",
    )
    gp_run.add_argument("--continue-on-fail", action="store_true", help="Keep going after a failed step")
    gp_run.add_argument("--json", dest="json_output", action="store_true")
    gp_run.set_defaults(func=cmd_golden_path)

    p.set_defaults(func=cmd_golden_path, golden_subcommand="steps")

    # commands — CLI discovery
    p = subparsers.add_parser(
        "commands",
        help="Discover all CLI commands (list / tree / search)",
    )
    cmd_subs = p.add_subparsers(dest="commands_subcommand")
    cl = cmd_subs.add_parser("list", help="All commands grouped by category")
    cl.set_defaults(func=cmd_commands)
    ct = cmd_subs.add_parser("tree", help="Indented command tree")
    ct.set_defaults(func=cmd_commands)
    cs = cmd_subs.add_parser("search", help="Search commands by keyword")
    cs.add_argument("query", help="Search terms")
    cs.set_defaults(func=cmd_commands)
    p.set_defaults(func=cmd_commands, commands_subcommand="list")

    # provider
    p = subparsers.add_parser("provider", help="List and manage AI model providers")
    provider_subs = p.add_subparsers(dest="provider_subcommand")
    ps_list = provider_subs.add_parser("list", help="List all available providers")
    ps_list.set_defaults(func=cmd_provider)
    ps_set = provider_subs.add_parser("set", help="Configure a provider (API key + model)")
    ps_set.add_argument("provider_name", help="Provider name (e.g. openai, anthropic, openrouter)")
    ps_set.add_argument("--model", "-m", help="Default model ID")
    ps_set.set_defaults(func=cmd_provider)
    ps_key = provider_subs.add_parser(
        "key", help="Set API key for a provider without changing config"
    )
    ps_key.add_argument("provider_name", help="Provider name")
    ps_key.set_defaults(func=cmd_provider)

    # model
    p = subparsers.add_parser("model", help="List or switch the active model")
    model_subs = p.add_subparsers(dest="model_subcommand")
    pm_list = model_subs.add_parser(
        "list", help="Show active model configuration and available models"
    )
    pm_list.set_defaults(func=cmd_model)
    pm_set = model_subs.add_parser("set", help="Switch to a different model")
    pm_set.add_argument("model_name", help="Model ID (e.g. gpt-4o, claude-sonnet-4.6)")
    pm_set.set_defaults(func=cmd_model)

    # self-management
    p = subparsers.add_parser("uninstall", help="Uninstall AgentDrive package")
    p.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")
    p.set_defaults(func=cmd_uninstall)

    p = subparsers.add_parser("clean", help="Clean AgentDrive cache and data (keeps config)")
    p.add_argument("--all", "-a", action="store_true", help="Also remove genomes")
    p.set_defaults(func=cmd_clean)

    p = subparsers.add_parser("reinstall", help="Reinstall AgentDrive from GitHub")
    p.add_argument("--branch", default="main", help="Branch to install from (default: main)")
    p.set_defaults(func=cmd_reinstall)

    p = subparsers.add_parser("update", help="Update AgentDrive to the latest version")
    p.add_argument("--branch", default="main", help="Branch to update from (default: main)")
    p.set_defaults(func=cmd_update)

    # quarantine — trust-gated holding area for externally-sourced DNA
    p = subparsers.add_parser(
        "quarantine",
        help="Trust-gated quarantine: list / show / validate / approve / reject / hold candidate genomes",
    )
    q_subs = p.add_subparsers(dest="quarantine_subcommand")

    q_list = q_subs.add_parser("list", help="List quarantine entries")
    q_list.add_argument(
        "--status",
        choices=["pending", "approved", "rejected", "quarantined"],
        help="Filter by status",
    )
    q_list.set_defaults(func=cmd_quarantine)

    q_show = q_subs.add_parser("show", help="Show one quarantine entry")
    q_show.add_argument("quarantine_id")
    q_show.set_defaults(func=cmd_quarantine)

    q_val = q_subs.add_parser("validate", help="Run validation rules against a quarantine entry")
    q_val.add_argument("quarantine_id")
    q_val.set_defaults(func=cmd_quarantine)

    q_app = q_subs.add_parser("approve", help="Approve an entry and release it into the Drive")
    q_app.add_argument("quarantine_id")
    q_app.add_argument("--note", default="", help="Optional approval note")
    q_app.set_defaults(func=cmd_quarantine)

    q_rej = q_subs.add_parser("reject", help="Reject an entry permanently")
    q_rej.add_argument("quarantine_id")
    q_rej.add_argument("--reason", required=True, help="Rejection reason")
    q_rej.set_defaults(func=cmd_quarantine)

    q_hold = q_subs.add_parser("hold", help="Move an entry to indefinite hold")
    q_hold.add_argument("quarantine_id")
    q_hold.add_argument("--reason", required=True, help="Hold reason")
    q_hold.set_defaults(func=cmd_quarantine)

    # default behavior when no subcommand is given: list
    p.set_defaults(func=cmd_quarantine, quarantine_subcommand="list")

    # peers — federated peer registry
    p = subparsers.add_parser(
        "peers",
        help="Federated peer registry: list / add / remove / trust / sync",
    )
    pe_subs = p.add_subparsers(dest="peers_subcommand")

    pe_list = pe_subs.add_parser("list", help="List registered peers")
    pe_list.set_defaults(func=cmd_peers)

    pe_add = pe_subs.add_parser("add", help="Register a peer")
    pe_add.add_argument("peer_id")
    pe_add.add_argument("address", help="file:///path, https://..., or agentdrive://host")
    pe_add.add_argument(
        "--trust",
        default="untrusted",
        choices=["untrusted", "review", "trusted"],
        help="Initial trust level (default: untrusted)",
    )
    pe_add.add_argument("--notes", default="", help="Free-form operator notes")
    pe_add.set_defaults(func=cmd_peers)

    pe_rm = pe_subs.add_parser("remove", help="Unregister a peer")
    pe_rm.add_argument("peer_id")
    pe_rm.set_defaults(func=cmd_peers)

    pe_tr = pe_subs.add_parser("trust", help="Change a peer's trust level")
    pe_tr.add_argument("peer_id")
    pe_tr.add_argument("level", choices=["untrusted", "review", "trusted"])
    pe_tr.set_defaults(func=cmd_peers)

    pe_sy = pe_subs.add_parser(
        "sync",
        help="Pull new genomes from a peer into quarantine (never directly into the Drive)",
    )
    pe_sy.add_argument("peer_id")
    pe_sy.set_defaults(func=cmd_peers)

    # default behavior when no subcommand is given: list
    p.set_defaults(func=cmd_peers, peers_subcommand="list")

    # models — AgentDrive local LLM backends
    p = subparsers.add_parser(
        "models",
        help="AgentDrive local LLM backends: list configured local models",
    )
    md_subs = p.add_subparsers(dest="models_subcommand")

    md_list = md_subs.add_parser(
        "list",
        help="List configured local models with reachability status",
    )
    md_list.set_defaults(func=cmd_models)

    # default behavior when no subcommand is given: list
    p.set_defaults(func=cmd_models, models_subcommand="list")

    # reconcile — periodic pool reconciliation routine
    p = subparsers.add_parser(
        "reconcile",
        help="Drive reconciliation: scan the local Drive for new/updated DNA and emit a report",
    )
    rc_subs = p.add_subparsers(dest="reconcile_subcommand")

    rc_run = rc_subs.add_parser("run", help="Run a single synchronous reconciliation pass")
    rc_run.set_defaults(func=cmd_reconcile)

    rc_st = rc_subs.add_parser("status", help="Show persisted reconciliation state")
    rc_st.set_defaults(func=cmd_reconcile)

    # seed-experience-v3: lightweight first-run recovery helper (Stabilization Swarm)
    # Bootstraps experience layer v3 seed for role-swarm self-host users so new
    # AgentDrive instances start coherent with experience layer present from first think.
    rc_seed = rc_subs.add_parser(
        "seed-experience-v3",
        help="First-run recovery: ensure experience layer v3 seed genome/observation (living-experience page type), KG index bootstrap, reconciliation state, trust self-identity, and directory structure. Defensive healing for empty/partial drives.",
    )
    rc_seed.set_defaults(func=cmd_reconcile)

    # default behavior when no subcommand is given: run
    p.set_defaults(func=cmd_reconcile, reconcile_subcommand="run")

    # sprint — gstack-style ship chain with STOP gates
    p = subparsers.add_parser(
        "sprint",
        help="Sprint chains with human STOP gates (gstack /ship workflow)",
    )
    sprint_subs = p.add_subparsers(dest="sprint_subcommand")

    sprint_ship = sprint_subs.add_parser(
        "ship",
        help="Run reconcile → test → think_gaps → changelog_check ship chain",
    )
    sprint_ship.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip pytest subprocess and STOP gate pauses",
    )
    sprint_ship.add_argument(
        "--ack",
        metavar="ID",
        help="Acknowledge a checkpoint and resume the chain",
    )
    sprint_ship.add_argument(
        "--pytest-path",
        default="tests",
        help="Pytest path for the test step (default: tests)",
    )
    sprint_ship.add_argument(
        "--reset",
        action="store_true",
        help="Clear persisted chain progress before running",
    )
    sprint_ship.set_defaults(func=cmd_sprint)

    sprint_ack = sprint_subs.add_parser("ack", help="Acknowledge a sprint checkpoint")
    sprint_ack.add_argument("checkpoint_id", help="Checkpoint id (cp-...)")
    sprint_ack.add_argument(
        "--chain",
        dest="chain_id",
        default="ship",
        help="Chain id (default: ship)",
    )
    sprint_ack.set_defaults(func=cmd_sprint)

    sprint_status = sprint_subs.add_parser("status", help="List pending sprint checkpoints")
    sprint_status.add_argument(
        "--chain",
        dest="chain_id",
        default="ship",
        help="Chain id (default: ship)",
    )
    sprint_status.set_defaults(func=cmd_sprint)

    p.set_defaults(func=cmd_sprint, sprint_subcommand="status")

    # dream — phased gbrain-style maintenance cycle
    p = subparsers.add_parser(
        "dream",
        help="Phased dream cycle: reconcile, extract links, consolidate, grade confidence, purge stale",
    )
    dream_subs = p.add_subparsers(dest="dream_subcommand")

    dream_run = dream_subs.add_parser("run", help="Run the dream cycle (all phases or one phase)")
    dream_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip heavy writes; reconciliation uses status only",
    )
    from agentdrive.dreaming.cycle import DREAM_PHASES as _dream_phase_specs

    dream_run.add_argument(
        "--phase",
        metavar="NAME",
        choices=[spec.id for spec in _dream_phase_specs],
        help="Run a single phase instead of the full cycle",
    )
    dream_run.add_argument(
        "--ack-phase",
        metavar="NAME",
        help="Acknowledge a STOP gate and continue past the given phase",
    )
    dream_run.set_defaults(func=cmd_dream)

    dream_status = dream_subs.add_parser("status", help="Show dream lock and last audit entry")
    dream_status.set_defaults(func=cmd_dream)

    dream_phases = dream_subs.add_parser("phases", help="List dream cycle phases")
    dream_phases.set_defaults(func=cmd_dream)

    p.set_defaults(func=cmd_dream, dream_subcommand="status")

    # demo-swarm — live SubagentTree proof-of-concept (UX Pattern 4)
    p = subparsers.add_parser(
        "demo-swarm",
        help="Scripted 10s demo of the live sub-agent tree renderer",
    )
    p.set_defaults(func=cmd_demo_swarm)

    # ops — contract-first operations registry (gbrain operations.ts pattern)
    p = subparsers.add_parser(
        "ops",
        help="Contract-first operations registry (list / describe / run / export)",
    )
    ops_subs = p.add_subparsers(dest="ops_subcommand")

    ops_list = ops_subs.add_parser("list", help="Table of registered operations")
    ops_list.set_defaults(func=cmd_ops)

    ops_describe = ops_subs.add_parser("describe", help="JSON detail for one operation")
    ops_describe.add_argument("operation_name", help="Operation name (e.g. doctor, pool_status)")
    ops_describe.set_defaults(func=cmd_ops)

    ops_export = ops_subs.add_parser(
        "export", help="Export full operations manifest as JSON (tools-json)"
    )
    ops_export.set_defaults(func=cmd_ops)

    ops_run = ops_subs.add_parser(
        "run",
        help="Execute an operation with key=value kwargs or minimal defaults",
    )
    ops_run.add_argument("operation_name", help="Operation name (e.g. doctor, pool_status)")
    ops_run.add_argument(
        "ops_kwargs",
        nargs="*",
        help="Optional handler kwargs as key=value pairs or bare text",
    )
    ops_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan execution without mutating state where supported",
    )
    ops_run.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Emit full JSON result",
    )
    ops_run.set_defaults(func=cmd_ops)

    p.set_defaults(func=cmd_ops, ops_subcommand="list")

    return parser


def main() -> None:
    # Very early defensive setup (robust CLI bootstrap)
    if "--version" in sys.argv:
        print(f"AgentDrive {AGENTDRIVE_VERSION}")
        sys.exit(0)

    parser = build_parser()
    args = parser.parse_args()

    # Initialize logging & config as early as possible for all paths
    try:
        setup_logging()
    except Exception:
        pass

    # First-run experience: if no provider is configured yet AND we're on a real
    # TTY, run the guided onboarding flow. We check provider state — not just
    # config file existence — because logging/setup writes a stub config.yaml
    # before the user has chosen a provider. In non-interactive contexts (CI,
    # pipes, IDE shells, automation), silently materialize a minimal config.
    tried_onboarding = False
    try:
        home = get_agentdrive_home()
        config_exists = (home / "config.yaml").exists()
        provider_configured = False
        if config_exists:
            try:
                from agentdrive.providers import load_config_provider

                cfg = load_config_provider()
                provider_configured = bool(cfg and cfg[0])
            except Exception:
                provider_configured = False

        if not provider_configured:
            if sys.stdin.isatty() and sys.stdout.isatty():
                from agentdrive.onboarding import run_onboarding

                print()
                tried_onboarding = run_onboarding()
            elif not config_exists:
                from agentdrive.onboarding import init_minimal_config

                init_minimal_config()
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
            logger.exception("Unhandled error in AgentDrive CLI")
            console.print(f"[red]Error:[/] {exc}")
            sys.exit(1)
    else:
        # No subcommand — TUI by default; REPL when --cli or AGENTDRIVE_NO_TUI=1.
        no_tui = getattr(args, "cli", False) or os.environ.get("AGENTDRIVE_NO_TUI", "").lower() in (
            "1",
            "true",
            "yes",
        )
        if no_tui:
            from agentdrive.cli_repl import run_repl

            sys.exit(run_repl(parser=parser))

        # Default: launch the TUI experience
        # (also covers bare `agentdrive tui` before explicit subparser was registered)
        if not tried_onboarding:
            try:
                from agentdrive.tui.app import launch_tui

                mission_url = getattr(args, "mission_url", None)
                if not mission_url:
                    mission_url = os.environ.get("AGENTDRIVE_MISSION_URL") or os.environ.get(
                        "AGENTDRIVE_MC_URL"
                    )
                launch_tui(mission_url=mission_url)
            except Exception as e:
                logger.exception("Failed to launch TUI")
                console.print(f"[red]Could not launch TUI:[/] {rich_escape(str(e))}")
                console.print(
                    "[dim]Falling back to help. Try 'agentdrive repl' or 'agentdrive --cli'.[/]"
                )
                parser.print_help()
                sys.exit(1)


if __name__ == "__main__":
    main()
