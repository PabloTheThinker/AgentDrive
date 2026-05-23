"""
Savant Onboarding Experience — Apple-grade, simple, and powerful.

Goals:
- When a user types `savant` for the first time, they get a delightful, guided experience.
- Detect available AI agents and local models in their environment.
- Explain the Savant Swarm DNA Pool vision clearly and briefly.
- Ask for explicit user consent (especially for automatic pool attachment when spawning sub-agents).
- Set up the user's Savant home with sensible defaults.
- Feel premium and respectful of the user's sovereignty.

This is heavily inspired by the quality of OpenClaw `onboard`, Hermes `setup.py`, and modern Grok Build TUI flows.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from savant.config import load_config, save_config, get_savant_home, ensure_savant_home
from savant.constants import SAVANT_VERSION
from savant.pool.pool import get_default_pool

console = Console()


def _detect_environment() -> Dict[str, Any]:
    """Detect what AI agents / models are available in the user's environment."""
    env: Dict[str, Any] = {
        "grok_build": False,
        "ollama": False,
        "openai_key": False,
        "anthropic_key": False,
        "claude_cli": False,
        "other": [],
    }

    # Detect Grok Build TUI context
    if any(k.startswith("GROK_") or k.startswith("XAI_") for k in os.environ):
        env["grok_build"] = True

    # Ollama
    if os.path.exists("/usr/local/bin/ollama") or os.path.exists(os.path.expanduser("~/.ollama")):
        env["ollama"] = True

    # API keys
    if os.getenv("OPENAI_API_KEY"):
        env["openai_key"] = True
    if os.getenv("ANTHROPIC_API_KEY"):
        env["anthropic_key"] = True

    # Claude CLI
    if os.path.exists("/usr/local/bin/claude") or os.path.exists(os.path.expanduser("~/.claude")):
        env["claude_cli"] = True

    return env


def run_onboarding() -> bool:
    """
    Run the first-time Savant onboarding experience.
    Returns True if onboarding completed successfully.
    """
    home = get_savant_home()
    config_path = home / "config.yaml"

    # If config already exists and has the onboarded flag, skip
    if config_path.exists():
        try:
            cfg = load_config()
            if cfg.get("onboarded", False):
                return True
        except Exception:
            pass

    console.print(
        Panel(
            f"[bold cyan]Welcome to Savant[/] v{SAVANT_VERSION}\n\n"
            "Savant gives your AI agents (and every sub-agent they spawn) a living, private, "
            "persistent memory system called a **Savant Pool**.\n\n"
            "Each pool starts empty and grows with real experience — DNA made of successful "
            "frameworks, reasoning patterns, and outcomes.\n\n"
            "You stay in full control. Your pools are yours.",
            title="Savant Onboarding",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    if not Confirm.ask("\n[bold]Would you like to set up Savant now?[/]", default=True):
        console.print("[yellow]Onboarding skipped. You can run it later with 'savant doctor'.[/]")
        return False

    # Detect environment
    env = _detect_environment()
    detected = []
    if env["grok_build"]:
        detected.append("Grok Build TUI (this environment)")
    if env["ollama"]:
        detected.append("Ollama (local models)")
    if env["openai_key"]:
        detected.append("OpenAI")
    if env["anthropic_key"]:
        detected.append("Anthropic / Claude")
    if env["claude_cli"]:
        detected.append("Claude CLI")

    if detected:
        console.print("\n[green]Detected in your environment:[/]")
        for d in detected:
            console.print(f"  • {d}")
    else:
        console.print("\n[dim]No major AI CLIs or keys detected yet — that's fine. You can add them later.[/]")

    # Core consent for the killer feature (swarm pools)
    console.print("\n[bold]The most powerful part of Savant[/]:")
    console.print(
        "When you (or an AI) spawn sub-agents, each one can automatically get its own private Savant Pool.\n"
        "This lets sub-agents grow their own intelligence while the whole swarm can still share high-value patterns under your rules."
    )

    consent = Confirm.ask(
        "\n[bold cyan]Allow Savant to automatically create and attach private pools when you or your agents spawn sub-agents?[/]",
        default=True,
    )

    # Create home + initial config
    ensure_savant_home()
    cfg = load_config()

    cfg["onboarded"] = True
    cfg["onboarding_consent_swarm_pools"] = consent
    cfg.setdefault("pool", {})
    cfg["pool"].setdefault("global", {})
    cfg["pool"]["global"]["isolation_level"] = "subagent" if consent else "none"
    cfg["pool"]["global"]["auto_ingest_on_success"] = True

    save_config(cfg)

    # Create the user's first global pool so it's immediately useful
    try:
        pool = get_default_pool()
        console.print(f"\n[green]✓[/] Created your first Savant Pool at [cyan]{pool.pool_dir}[/]. It starts empty and will grow with use.")
    except Exception as e:
        console.print(f"[yellow]Pool initialization note:[/] {e}")

    console.print(
        "\n[bold green]Onboarding complete.[/]\n"
        "You can always change these settings later with [cyan]savant pool settings[/] or in the TUI.\n"
    )

    if Confirm.ask("Launch the Savant TUI now?", default=True):
        from savant.tui.app import launch_tui
        launch_tui()

    return True


def ensure_onboarding() -> None:
    """Call this early in CLI flows. Runs onboarding only on first use."""
    home = get_savant_home()
    config_path = home / "config.yaml"

    needs_onboarding = True
    if config_path.exists():
        try:
            cfg = load_config()
            if cfg.get("onboarded"):
                needs_onboarding = False
        except Exception:
            pass

    if needs_onboarding:
        run_onboarding()
