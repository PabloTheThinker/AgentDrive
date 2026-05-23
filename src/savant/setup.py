"""
Savant Setup Wizard — Hermes-grade interactive CLI experience.

This is the official way to configure Savant the first time and to reconfigure specific areas later.

Sections (can be run independently via `savant setup <section>`):

1. Home & Persistence
2. Global Savant Pool
3. Swarm & Sub-Agent DNA (the heart of the system)
4. AI Integration & Adapters (Grok, local models, Claude, etc.)
5. TUI Preferences

The wizard is designed to feel premium, clear, and respectful of user sovereignty — exactly like Hermes setup, but tuned for Savant's Swarm DNA Pool vision.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from savant.config import (
    get_savant_home,
    ensure_savant_home,
    load_config,
    save_config,
)
from savant.pool.settings import (
    PoolSettings,
    get_pool_settings_manager,
)
from savant.pool.swarm_manager import get_swarm_pool_manager
from savant.constants import SAVANT_VERSION

console = Console()


# ---------------------------------------------------------------------------
# Helpers (inspired by Hermes prompt utilities)
# ---------------------------------------------------------------------------

def print_header(title: str):
    console.print()
    console.print(f"[bold cyan]◆ {title}[/]")


def print_success(msg: str):
    console.print(f"[green]✓[/] {msg}")


def print_info(msg: str):
    console.print(f"[dim]{msg}[/]")


def print_warning(msg: str):
    console.print(f"[yellow]! {msg}[/]")


def prompt_yes_no(question: str, default: bool = True) -> bool:
    default_str = "Y/n" if default else "y/N"
    while True:
        try:
            ans = Prompt.ask(f"{question} [{default_str}]", default="y" if default else "n").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(1)

        if not ans:
            return default
        if ans in {"y", "yes"}:
            return True
        if ans in {"n", "no"}:
            return False
        print_warning("Please answer y or n.")


# ---------------------------------------------------------------------------
# Setup Sections
# ---------------------------------------------------------------------------

def section_home() -> bool:
    """Section 1: Home directory & basic persistence."""
    print_header("Home Directory & Persistence")

    home = get_savant_home()
    print_info(f"Savant will store all data under: [cyan]{home}[/]")

    if not prompt_yes_no("Create / use this directory?", default=True):
        print_warning("Setup cannot continue without a home directory.")
        return False

    ensure_savant_home()
    print_success(f"Home directory ready: {home}")

    cfg = load_config()
    cfg["savant_home"] = str(home)
    save_config(cfg)
    return True


def section_global_pool() -> bool:
    """Section 2: Global (root) Savant Pool."""
    print_header("Global Savant Pool")

    print_info(
        "Every Savant installation has one global pool. This is where your main agent (and any shared DNA) lives."
    )

    if not prompt_yes_no("Create your global Savant Pool now?", default=True):
        return True

    try:
        pool = get_swarm_pool_manager().get_or_create_pool("global")
        print_success(f"Global pool ready at [cyan]{pool.pool_dir}[/]")
    except Exception as e:
        print_warning(f"Could not create global pool: {e}")
        return False

    return True


def section_swarm_dna() -> bool:
    """Section 3: The heart — Swarm & Sub-Agent DNA pools (most important section)."""
    print_header("Swarm & Sub-Agent DNA Pools — The Core of Savant")

    print_info(
        "This is what makes Savant special.\n\n"
        "When you (or Grok, Claude, etc.) spawn sub-agents, each one gets its own private, persistent Savant Pool.\n"
        "Their DNA (memory + patterns) grows independently. High-value patterns can optionally flow back to you."
    )

    print()
    console.print("[bold]Choose your default swarm style:[/]")
    console.print("  1. High Security / Isolated (recommended for most people)")
    console.print("  2. Collaborative Research (good sharing between agents)")
    console.print("  3. Personal Assistant Swarm (balanced)")
    console.print("  4. Custom (I'll ask you the details)")

    try:
        choice = int(Prompt.ask("Select style [1-4]", default="1"))
    except Exception:
        choice = 1

    settings_mgr = get_pool_settings_manager()
    current = settings_mgr.get_global()

    if choice == 1:
        current.isolation_level = "subagent"
        current.sharing_policy = "selective"
        current.auto_ingest_on_success = True
        current.min_quality_for_sharing = 0.85
        print_success("High Security preset applied.")
    elif choice == 2:
        current.isolation_level = "swarm"
        current.sharing_policy = "full"
        current.auto_ingest_on_success = True
        current.min_quality_for_sharing = 0.6
        print_success("Collaborative preset applied.")
    elif choice == 3:
        current.isolation_level = "subagent"
        current.sharing_policy = "selective"
        current.auto_ingest_on_success = True
        current.min_quality_for_sharing = 0.75
        print_success("Balanced preset applied.")
    else:
        # Custom
        consent = prompt_yes_no("Automatically give private pools to sub-agents you spawn?", default=True)
        current.isolation_level = "subagent" if consent else "none"
        current.auto_ingest_on_success = consent

        if consent:
            share = prompt_yes_no("Allow valuable DNA to flow back from sub-agents to you?", default=True)
            current.sharing_policy = "selective" if share else "read"
        else:
            current.sharing_policy = "none"

    settings_mgr.set_global(current)
    print_success("Swarm DNA policies configured and saved.")

    return True


def section_ai_integration() -> bool:
    """Section 4: Detect and integrate with AI agents / models."""
    print_header("AI Agent & Model Integration")

    print_info("Savant works best when it knows which agents and models you use.")

    # Very lightweight detection for now (can be expanded)
    detected = []

    if any(k for k in ["GROK", "XAI"] if k in __import__("os").environ):
        detected.append("Grok Build TUI (this environment)")

    if __import__("os").path.exists(__import__("os").path.expanduser("~/.ollama")):
        detected.append("Ollama (local models)")

    if __import__("os").getenv("OPENAI_API_KEY"):
        detected.append("OpenAI-compatible models")

    if __import__("os").getenv("ANTHROPIC_API_KEY"):
        detected.append("Anthropic / Claude")

    if detected:
        print_info("Detected in your environment:")
        for d in detected:
            print(f"  • {d}")
    else:
        print_info("No major AI environments detected yet — you can add them later via adapters.")

    # Ask if they want to enable the rich external agent adapter by default
    use_rich = prompt_yes_no(
        "Enable the built-in rich external agent adapter for demos and examples?",
        default=True,
    )

    cfg = load_config()
    cfg.setdefault("adapters", {})
    cfg["adapters"]["rich_enabled"] = use_rich
    save_config(cfg)

    if use_rich:
        print_success("Rich agent adapter enabled.")

    return True


def section_tui() -> bool:
    """Section 5: TUI preferences."""
    print_header("TUI Experience")

    print_info("Savant TUI is the main way most people interact with their pools and swarms.")

    skin_choice = prompt_yes_no("Use the default professional skin?", default=True)

    cfg = load_config()
    cfg.setdefault("tui", {})
    cfg["tui"]["skin"] = "default" if skin_choice else "custom"
    save_config(cfg)

    print_success("TUI preferences saved. You can change skins later with 'savant tui'.")

    return True


# Registry of sections
SECTIONS: List[Dict[str, Any]] = [
    {"name": "home", "title": "Home & Persistence", "func": section_home},
    {"name": "pool", "title": "Global Savant Pool", "func": section_global_pool},
    {"name": "swarm", "title": "Swarm & Sub-Agent DNA (Core Feature)", "func": section_swarm_dna},
    {"name": "ai", "title": "AI Agent Integration", "func": section_ai_integration},
    {"name": "tui", "title": "TUI Preferences", "func": section_tui},
]


def run_setup(sections: Optional[List[str]] = None) -> bool:
    """
    Run the Savant setup wizard.

    If `sections` is provided, only run those specific sections (by short name).
    """
    print()
    console.print(Panel(f"[bold cyan]Savant Setup Wizard[/] v{SAVANT_VERSION}", border_style="cyan"))

    if sections is None:
        sections = [s["name"] for s in SECTIONS]

    success = True
    for sec in SECTIONS:
        if sec["name"] in sections:
            if not sec["func"]():
                success = False
                print_warning(f"Section '{sec['title']}' had issues.")

    if success:
        print()
        console.print("[bold green]Setup complete.[/] You can re-run specific sections with:")
        console.print("  [cyan]savant setup swarm[/]     — tweak sub-agent pool policies")
        console.print("  [cyan]savant setup ai[/]        — re-detect models and adapters")
        console.print("  [cyan]savant setup tui[/]       — change TUI skin")
        console.print()
        console.print("Launch the experience with [bold]savant[/] (no arguments).")

        # Mark as onboarded so the TUI dedicated welcome screen can trigger on first launch
        try:
            cfg = load_config()
            cfg["onboarded"] = True
            cfg.setdefault("onboarding_consent_swarm_pools", True)
            save_config(cfg)
        except Exception:
            pass

    return success


# ---------------------------------------------------------------------------
# CLI entry points
# ---------------------------------------------------------------------------

def cmd_setup(args) -> int:
    """Entry point for `savant setup` and `savant setup <section>`."""
    from savant.cli import console as cli_console

    sections = None
    if hasattr(args, "section") and args.section:
        # Map friendly names
        mapping = {s["name"]: s["name"] for s in SECTIONS}
        mapping.update({
            "swarm": "swarm",
            "dna": "swarm",
            "agent": "ai",
            "model": "ai",
            "ui": "tui",
        })
        sections = [mapping.get(args.section.lower(), args.section.lower())]

    run_setup(sections)
    return 0
