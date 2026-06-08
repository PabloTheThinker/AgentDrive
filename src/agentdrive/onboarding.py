"""
AgentDrive Onboarding — polished first-run experience.

When a user types `agentdrive` for the first time, they get a guided,
step-by-step flow that explains Agent Drive, detects their environment,
sets up their pool, and gets them to the TUI.

Renders against the unified chrome primitives so it feels like part of
the same product as chat, doctor, and the rest.
"""

from __future__ import annotations

import os
from typing import Any

from rich.console import Group
from rich.text import Text

from agentdrive.config import ensure_agentdrive_home, get_agentdrive_home, load_config, save_config
from agentdrive.constants import AGENTDRIVE_VERSION
from agentdrive.drive.drive import get_default_drive
from agentdrive.tui.chrome import (
    Glyphs,
    Palette,
    Section,
    Tree,
    TreeRow,
    confirm_prompt,
    info_line,
    ok_line,
    result_panel,
    section_panel,
    warn_line,
)
from agentdrive.tui.skin_engine import skin

console = skin.console
PALETTE = Palette(skin)


def _detect_environment() -> dict[str, Any]:
    env: dict[str, Any] = {
        "grok_build": False,
        "ollama": False,
        "openai_key": False,
        "anthropic_key": False,
        "claude_cli": False,
    }

    if any(k.startswith("GROK_") or k.startswith("XAI_") for k in os.environ):
        env["grok_build"] = True
    if os.path.exists("/usr/local/bin/ollama") or os.path.exists(os.path.expanduser("~/.ollama")):
        env["ollama"] = True
    if os.getenv("OPENAI_API_KEY"):
        env["openai_key"] = True
    if os.getenv("ANTHROPIC_API_KEY"):
        env["anthropic_key"] = True
    if os.path.exists("/usr/local/bin/claude") or os.path.exists(os.path.expanduser("~/.claude")):
        env["claude_cli"] = True

    try:
        from agentdrive.providers import list_available

        avail = list_available()
        if avail:
            env["agentdrive_providers"] = [p.display_name for p in avail]
    except Exception:
        pass

    return env


def _env_rows(env: dict[str, Any]) -> list[TreeRow]:
    items = []
    if env.get("grok_build"):
        items.append(("Grok Build", True))
    if env.get("ollama"):
        items.append(("Ollama (local models)", True))
    if env.get("openai_key"):
        items.append(("OpenAI API key", True))
    if env.get("anthropic_key"):
        items.append(("Anthropic API key", True))
    if env.get("claude_cli"):
        items.append(("Claude CLI", True))
    for p in env.get("agentdrive_providers") or []:
        items.append((f"{p} (Agent Drive)", True))

    if not items:
        return [
            TreeRow(
                label="[dim]nothing detected[/]",
                secondary="run [bold]agentdrive provider set <name>[/] later",
            )
        ]

    rows: list[TreeRow] = []
    for name, present in items:
        mark = f"[bold {PALETTE.ok}]✓[/] " if present else f"[{PALETTE.muted}]·[/] "
        rows.append(TreeRow(label=f"{mark}{name}"))
    return rows


def _print_step(current: int, total: int, title: str, description: str = "") -> None:
    head = Text()
    head.append(f"  Step {current}/{total}  ", style=f"bold {PALETTE.accent}")
    head.append(title, style="bold")
    console.print()
    console.print(head)
    if description:
        desc = Text("    ")
        desc.append(description, style=PALETTE.muted)
        console.print(desc)
    console.print()


def run_onboarding() -> bool:
    """Run the first-time Agent Drive onboarding experience.

    Returns True if onboarding completed successfully.
    """
    home = get_agentdrive_home()
    config_path = home / "config.yaml"

    # Skip if already onboarded
    if config_path.exists():
        try:
            cfg = load_config()
            if cfg.get("onboarded", False):
                return True
        except Exception:
            pass

    TOTAL_STEPS = 4

    # ── Welcome panel ────────────────────────────────────────────────
    hero = Text()
    hero.append(f"{Glyphs.DIAMOND} ", style=PALETTE.accent)
    hero.append("AGENTDRIVE", style=PALETTE.title + " bold")
    hero.append(f"  v{AGENTDRIVE_VERSION}", style=PALETTE.muted)

    tagline = Text(
        "The Living, Learning Ecosystem for AI Agents",
        style=PALETTE.muted + " italic",
    )

    body_text = Text.from_markup(
        "This is now your personal AgentDrive.\n\n"
        "Every agent you run — and every sub-agent it spawns — gets its own private,\n"
        "persistent pool of DNA: frameworks, reasoning patterns, and real outcomes.\n\n"
        "It starts empty. It grows only with experience you choose to keep.\n"
        "You own the rules. Complete sovereignty."
    )

    console.print()
    console.print(
        section_panel(
            Group(hero, tagline),
            body_text,
            title="Welcome to your AgentDrive",
            palette=PALETTE,
        )
    )

    proceed = confirm_prompt(
        console,
        title="Set up Agent Drive now?",
        body=f"This takes ~30 seconds. You can re-run setup any time with [{PALETTE.accent}]agentdrive setup[/].",
        default_yes=True,
        palette=PALETTE,
    )
    if not proceed:
        console.print()
        console.print(
            info_line(
                f"Onboarding skipped. Run [{PALETTE.accent}]agentdrive setup[/] anytime.",
                palette=PALETTE,
            )
        )
        return False

    # ── Apple-level: Name your AgentDrive (instance identity) ─────────
    from agentdrive.config import get_instance_name, set_instance_name

    current_name = get_instance_name()
    if current_name == "AgentDrive":
        console.print()
        name_hero = Text()
        name_hero.append("This is ", style=PALETTE.muted)
        name_hero.append("yours", style=f"bold {PALETTE.title}")
        name_hero.append(".", style=PALETTE.muted)

        console.print(
            section_panel(
                name_hero,
                Text.from_markup(
                    "Give your AgentDrive a name that feels like home.\n"
                    "Examples:  [bold]My Research Drive[/],  [bold]Vektra Core[/],  [bold]Team Orion[/]"
                ),
                title="Name this AgentDrive",
                palette=PALETTE,
            )
        )

        try:
            from prompt_toolkit import PromptSession

            session = PromptSession()
            suggested = os.environ.get("USER", "My") + " AgentDrive"
            user_name = session.prompt(
                f"[{PALETTE.accent}]Name[/] (Enter for default): ",
                default=suggested,
            ).strip()
            if user_name:
                set_instance_name(user_name)
                console.print()
                console.print(
                    result_panel(
                        "Your AgentDrive is ready",
                        [f"Named: [bold]{user_name}[/]"],
                        success=True,
                        palette=PALETTE,
                    )
                )
        except Exception:
            # Fallback to simple input
            user_name = input("Name (or press Enter): ").strip()
            if user_name:
                set_instance_name(user_name)

    # ── Step 1: Home directory ────────────────────────────────────────
    _print_step(
        1, TOTAL_STEPS, "Home directory", "Agent Drive stores your data, config, and DNA here."
    )
    ensure_agentdrive_home()
    # Expanded first-run self-healing for role-swarm self-host users.
    # Ensures experience layer v3 seed etc. even during interactive onboarding
    # so new instances start coherent and experience layer is present from first think.
    try:
        from agentdrive.constants import get_default_drive_path
        from agentdrive.drive.bootstrap import ensure_experience_layer_seed

        ensure_experience_layer_seed(get_default_drive_path())
    except Exception:
        pass
    console.print(
        ok_line(
            f"Ready at [agentdrive.genome]{home}[/]",
            palette=PALETTE,
        )
    )

    # ── Step 2: Environment detection ─────────────────────────────────
    _print_step(
        2,
        TOTAL_STEPS,
        "Environment scan",
        "Detecting AI tools and API keys already on this machine.",
    )
    env = _detect_environment()
    console.print(Tree(_env_rows(env), palette=PALETTE))

    # ── Step 3: Swarm Pool consent ────────────────────────────────────
    _print_step(
        3,
        TOTAL_STEPS,
        "Swarm DNA pools",
        "Automatic isolated memory for every sub-agent you spawn.",
    )
    console.print(
        section_panel(
            Text.from_markup(
                "When you (or an AI) spawn sub-agents, each one can automatically get\n"
                "its own private, persistent AgentDrive. Children grow individual\n"
                "DNA; the swarm compounds intelligence under [bold]your[/] sharing rules."
            ),
            palette=PALETTE,
        )
    )

    consent = confirm_prompt(
        console,
        title="Allow automatic private pools for sub-agents?",
        body=f"Sharing rules are off by default. You change them in [{PALETTE.accent}]agentdrive setup swarm[/].",
        default_yes=True,
        palette=PALETTE,
    )

    # ── Step 4: Create pool & finalize ────────────────────────────────
    _print_step(
        4, TOTAL_STEPS, "Create your pool", "Your first DNA pool — starts empty, grows with use."
    )

    cfg = load_config()
    cfg["onboarded"] = True
    cfg["onboarding_consent_swarm_pools"] = consent
    cfg.setdefault("pool", {})
    cfg["pool"].setdefault("global", {})
    cfg["pool"]["global"]["isolation_level"] = "subagent" if consent else "none"
    cfg["pool"]["global"]["auto_ingest_on_success"] = True
    save_config(cfg)

    try:
        pool = get_default_drive()
        console.print(
            ok_line(
                f"Global pool ready at [agentdrive.genome]{pool.drive_path}[/]",
                palette=PALETTE,
            )
        )
    except Exception as e:
        console.print(warn_line(f"Pool initialization: {e}", palette=PALETTE))

    # ── Done — result panel ───────────────────────────────────────────
    console.print()
    console.print(
        result_panel(
            "Onboarding complete",
            [],
            success=True,
            palette=PALETTE,
            extras=[
                Text(""),
                Section(
                    "Golden path (do this next)",
                    [
                        ("agentdrive golden-path steps", "numbered first-run commands"),
                        ("agentdrive mcp install", "wire Grok/Cursor/Claude MCP"),
                        ("agentdrive golden-path run", "doctor → think → learnings → query"),
                        ("agentdrive think", "cited synthesis + gap analysis"),
                        ("agentdrive drive query", "semantic genome search"),
                    ],
                    palette=PALETTE,
                    key_width=28,
                ),
                Section(
                    "Also useful",
                    [
                        ("agentdrive provider set", "connect an AI model"),
                        ("agentdrive doctor", "full system health check"),
                        ("agentdrive setup", "re-run any setup section"),
                    ],
                    palette=PALETTE,
                    key_width=28,
                ),
            ],
        )
    )

    return True


def ensure_onboarding() -> None:
    """Call early in CLI flows. Runs onboarding only on first use."""
    home = get_agentdrive_home()
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


def init_minimal_config() -> None:
    """Materialize a minimal config + home layout for non-interactive use.

    Called when there's no TTY (CI, pipes, IDE shells) so commands like
    `agentdrive doctor` or `agentdrive pool status` can run cleanly without firing
    the onboarding flow on every invocation.

    Leaves `onboarded: false` so `agentdrive doctor` still nudges the user
    toward `agentdrive setup` when they next sit down at a real terminal.

    Respects live AGENTDRIVE_INSTANCE_NAME from env on first-run.

    Now also triggers first-run self-healing bootstrap so even non-interactive
    fresh AgentDrive instances (role-swarm self-host) start with coherent
    experience layer v3 seed etc.
    """
    ensure_agentdrive_home()
    from agentdrive.config import get_instance_name

    inst = get_instance_name()
    cfg = {
        "onboarded": False,
        "agentdrive": {
            "log_level": "INFO",
            "instance_name": inst if inst != "AgentDrive" else None,
        },
        "pool": {"global": {"isolation_level": "subagent"}},
    }
    save_config(cfg)
    # Defensive healing for production reliability on headless first-run
    try:
        from agentdrive.constants import get_default_drive_path
        from agentdrive.drive.bootstrap import ensure_experience_layer_seed

        ensure_experience_layer_seed(get_default_drive_path())
    except Exception:
        pass
