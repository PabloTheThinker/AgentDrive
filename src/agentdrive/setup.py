"""
AgentDrive Setup Wizard — interactive CLI configuration.

Rendered against the unified chrome primitives so it feels like part of
the same product as chat, doctor, and onboarding.

Sections (each can be run independently via `agentdrive setup <section>`):

  1. Home & Persistence
  2. AgentDrive (default)
  3. Swarm & Sub-Agent DNA
  4. AI Model Provider
  5. TUI Preferences
"""

from __future__ import annotations

from typing import Any

from rich.console import Group
from rich.prompt import Prompt
from rich.text import Text

from agentdrive.config import ensure_agentdrive_home, get_agentdrive_home, load_config, save_config
from agentdrive.constants import AGENTDRIVE_VERSION
from agentdrive.drive.settings import get_drive_settings_manager
from agentdrive.drive.swarm_manager import get_swarm_drive_manager
from agentdrive.tui.chrome import (
    Glyphs,
    Palette,
    Section,
    confirm_prompt,
    error_line,
    info_line,
    ok_line,
    result_panel,
    section_panel,
    select_prompt,
    warn_line,
)
from agentdrive.tui.skin_engine import skin

console = skin.console
PALETTE = Palette(skin)


# ── Step header ───────────────────────────────────────────────────────────


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


def _text_input(question: str, default: str = "", password: bool = False) -> str:
    """Plain text prompt — chrome doesn't ship a text-input primitive yet."""
    head = Text()
    head.append("ask ", style=f"bold {PALETTE.accent}")
    head.append(question)
    console.print()
    console.print(head)
    try:
        return Prompt.ask(
            "  ", default=default, password=password, show_default=not password
        ).strip()
    except (KeyboardInterrupt, EOFError):
        console.print()
        raise


# ── Sections ───────────────────────────────────────────────────────────────


def section_home() -> bool:
    home = get_agentdrive_home()

    console.print()
    console.print(
        section_panel(
            Section(
                "Home Directory",
                [
                    ("location", f"[{PALETTE.genome}]{home}[/]"),
                    ("stores", "config, pools, genomes, sessions"),
                ],
                palette=PALETTE,
                key_width=10,
            ),
            title="Home & Persistence",
            palette=PALETTE,
        )
    )

    proceed = confirm_prompt(
        console,
        title="Create this directory?",
        body=f"Agent Drive will set up [{PALETTE.accent}]{home}[/] with the right permissions.",
        default_yes=True,
        palette=PALETTE,
    )
    if not proceed:
        console.print()
        console.print(
            warn_line(
                "Setup cannot continue without a home directory.",
                palette=PALETTE,
            )
        )
        return False

    ensure_agentdrive_home()
    console.print()
    console.print(ok_line(f"Ready at [{PALETTE.genome}]{home}[/]", palette=PALETTE))

    cfg = load_config()
    cfg["agentdrive_home"] = str(home)
    save_config(cfg)
    return True


def section_global_pool() -> bool:
    console.print()
    console.print(
        section_panel(
            Section(
                "AgentDrive (default)",
                [
                    ("purpose", "main DNA repository — shared across all agents"),
                    ("contents", "frameworks, reasoning patterns, outcomes"),
                ],
                palette=PALETTE,
                key_width=10,
            ),
            title="AgentDrive (default)",
            palette=PALETTE,
        )
    )

    proceed = confirm_prompt(
        console,
        title="Create your global AgentDrive?",
        body="Every Agent Drive installation has one. Starts empty, grows with use.",
        default_yes=True,
        palette=PALETTE,
    )
    if not proceed:
        console.print()
        console.print(
            info_line("Skipped. Run [bold]agentdrive setup pool[/] anytime.", palette=PALETTE)
        )
        return True

    try:
        pool = get_swarm_drive_manager().get_or_create_pool("global")
        console.print()
        console.print(
            ok_line(
                f"Default Drive ready at [{PALETTE.genome}]{pool.drive_path}[/]",
                palette=PALETTE,
            )
        )
    except Exception as e:
        console.print()
        console.print(error_line(f"Could not create global pool: {e}", palette=PALETTE))
        return False

    return True


def section_swarm_dna() -> bool:
    console.print()
    console.print(
        section_panel(
            Section(
                "Swarm & Sub-Agent DNA",
                [
                    ("the feature", "automatic private pools for sub-agents"),
                    ("how", "each sub-agent grows its own DNA"),
                    ("flow", "valuable patterns can return to you"),
                ],
                palette=PALETTE,
                key_width=12,
            ),
            title="Swarm & Sub-Agent DNA",
            palette=PALETTE,
        )
    )

    styles = [
        "High Security / Isolated  — recommended for most people",
        "Collaborative Research    — good sharing between agents",
        "Personal Assistant Swarm  — balanced",
        "Custom                    — you choose the details",
    ]

    choice = select_prompt(
        console,
        "Choose your default swarm style:",
        styles,
        default_idx=0,
        palette=PALETTE,
    )
    if choice is None:
        choice = 0

    settings_mgr = get_drive_settings_manager()
    current = settings_mgr.get_global()

    if choice == 0:
        current.isolation_level = "subagent"
        current.sharing_policy = "selective"
        current.auto_ingest_on_success = True
        current.min_quality_for_sharing = 0.85
        preset = "High Security"
    elif choice == 1:
        current.isolation_level = "swarm"
        current.sharing_policy = "full"
        current.auto_ingest_on_success = True
        current.min_quality_for_sharing = 0.6
        preset = "Collaborative"
    elif choice == 2:
        current.isolation_level = "subagent"
        current.sharing_policy = "selective"
        current.auto_ingest_on_success = True
        current.min_quality_for_sharing = 0.75
        preset = "Balanced"
    else:
        consent = confirm_prompt(
            console,
            title="Automatically give private pools to sub-agents?",
            body="Off = no isolation, no automatic ingest.",
            default_yes=True,
            palette=PALETTE,
        )
        current.isolation_level = "subagent" if consent else "none"
        current.auto_ingest_on_success = consent

        if consent:
            share = confirm_prompt(
                console,
                title="Allow valuable DNA to flow back from sub-agents?",
                body="Selective = high-quality patterns only. Read = no outbound flow.",
                default_yes=True,
                palette=PALETTE,
            )
            current.sharing_policy = "selective" if share else "read"
        else:
            current.sharing_policy = "none"
        preset = "Custom"

    settings_mgr.set_global(current)

    console.print()
    console.print(ok_line(f"{preset} preset applied", palette=PALETTE))
    console.print(ok_line("Swarm DNA policies saved", palette=PALETTE))

    return True


def section_ai_integration() -> bool:
    from agentdrive.providers import (
        list_all,
        list_available,
        save_config_provider,
        write_env_var,
    )

    detected = list_available()
    all_providers = list_all()

    rows = [
        ("purpose", "powers chat, pool queries, genome analysis"),
        ("storage", f"keys in [{PALETTE.muted}]{get_agentdrive_home() / '.env'}[/] (chmod 600)"),
    ]
    if detected:
        rows.append(
            (
                "detected",
                ", ".join(f"[{PALETTE.ok}]{p.display_name}[/]" for p in detected),
            )
        )

    console.print()
    console.print(
        section_panel(
            Section(
                "AI Model Provider",
                rows,
                palette=PALETTE,
                key_width=10,
            ),
            title="AI Model Provider",
            palette=PALETTE,
        )
    )

    options: list[str] = []
    for p in all_providers:
        mark = f"  [{PALETTE.ok}]✓[/]" if p.has_key() else ""
        options.append(f"{p.display_name:<22}  {p.description}{mark}")
    options.append("Skip — configure later")

    choice = select_prompt(
        console,
        "Available providers:",
        options,
        default_idx=0,
        palette=PALETTE,
    )
    if choice is None:
        choice = len(options) - 1  # Skip on cancel

    if 0 <= choice < len(all_providers):
        profile = all_providers[choice]

        if profile.requires_key and not profile.has_key():
            console.print()
            console.print(
                info_line(
                    f"Get your [bold]{profile.display_name}[/] API key:",
                    palette=PALETTE,
                    secondary=profile.signup_url,
                )
            )
            try:
                key = _text_input(f"API key for {profile.display_name}", password=True)
            except (KeyboardInterrupt, EOFError):
                return False
            if key and key not in ("", "*", "changeme"):
                write_env_var(profile.env_var, key)
                console.print()
                console.print(
                    ok_line(
                        f"API key saved for {profile.display_name}",
                        palette=PALETTE,
                    )
                )
            else:
                console.print()
                console.print(
                    warn_line(
                        "No key entered. Set one later with: [bold]agentdrive provider key <name>[/]",
                        palette=PALETTE,
                    )
                )
        elif not profile.requires_key:
            console.print()
            console.print(
                ok_line(
                    f"{profile.display_name} doesn't need an API key.",
                    palette=PALETTE,
                )
            )

        models = profile.fallback_models
        if models:
            model_options = [f"[bold {PALETTE.genome}]{m}[/]" for m in models]
            model_options.append("Enter custom model ID")

            model_choice = select_prompt(
                console,
                f"Select default model for {profile.display_name}:",
                model_options,
                default_idx=0,
                palette=PALETTE,
            )
            if model_choice is None:
                model_choice = 0

            if 0 <= model_choice < len(models):
                chosen_model = models[model_choice]
            else:
                try:
                    chosen_model = _text_input("Enter model ID", default=profile.default_model)
                except (KeyboardInterrupt, EOFError):
                    chosen_model = profile.default_model
                if not chosen_model:
                    chosen_model = profile.default_model
        else:
            try:
                chosen_model = _text_input("Enter model ID", default=profile.default_model)
            except (KeyboardInterrupt, EOFError):
                chosen_model = profile.default_model
            if not chosen_model:
                chosen_model = profile.default_model

        save_config_provider(profile.name, chosen_model)
        console.print()
        console.print(
            ok_line(
                f"Provider set to [bold]{profile.display_name}[/] · model [{PALETTE.genome}]{chosen_model}[/]",
                palette=PALETTE,
            )
        )
    else:
        console.print()
        console.print(
            info_line(
                f"Skipped. Run [{PALETTE.accent}]agentdrive provider set <name>[/] later.",
                palette=PALETTE,
            )
        )

    use_rich = confirm_prompt(
        console,
        title="Enable the rich external agent adapter for demos?",
        body="The adapter exposes a polished demo surface for external agents.",
        default_yes=True,
        palette=PALETTE,
    )

    cfg = load_config()
    cfg.setdefault("adapters", {})
    cfg["adapters"]["rich_enabled"] = use_rich
    save_config(cfg)

    if use_rich:
        console.print()
        console.print(ok_line("Rich agent adapter enabled.", palette=PALETTE))

    return True


def section_tui() -> bool:
    console.print()
    console.print(
        section_panel(
            Section(
                "TUI Preferences",
                [
                    ("the surface", "primary way most people use Agent Drive"),
                    ("skin", "controls glyphs, palette, panel borders"),
                ],
                palette=PALETTE,
                key_width=12,
            ),
            title="TUI Preferences",
            palette=PALETTE,
        )
    )

    skin_default = confirm_prompt(
        console,
        title="Use the default professional skin?",
        body="You can switch skins later with [bold]agentdrive tui skin <name>[/].",
        default_yes=True,
        palette=PALETTE,
    )

    cfg = load_config()
    cfg.setdefault("tui", {})
    cfg["tui"]["skin"] = "default" if skin_default else "custom"
    save_config(cfg)

    console.print()
    console.print(
        ok_line(
            f"TUI preferences saved · skin [{PALETTE.genome}]{cfg['tui']['skin']}[/]",
            palette=PALETTE,
        )
    )

    return True


# ── Section registry ───────────────────────────────────────────────────────

SECTIONS: list[dict[str, Any]] = [
    {"name": "home", "title": "Home & Persistence", "func": section_home},
    {"name": "pool", "title": "AgentDrive (default)", "func": section_global_pool},
    {"name": "swarm", "title": "Swarm & Sub-Agent DNA", "func": section_swarm_dna},
    {"name": "ai", "title": "AI Model Provider", "func": section_ai_integration},
    {"name": "tui", "title": "TUI Preferences", "func": section_tui},
]

TOTAL_SECTIONS = len(SECTIONS)


def _welcome_panel(running_subset: bool, names: list[str]) -> None:
    hero = Text()
    hero.append(f"{Glyphs.DIAMOND} ", style=PALETTE.accent)
    hero.append("AGENTDRIVE SETUP", style=PALETTE.title + " bold")
    hero.append(f"  v{AGENTDRIVE_VERSION}", style=PALETTE.muted)

    if running_subset:
        body_text = Text.from_markup(
            f"Reconfiguring [bold]{len(names)}[/] section"
            f"{'s' if len(names) != 1 else ''}: "
            + ", ".join(f"[{PALETTE.accent}]{n}[/]" for n in names)
        )
    else:
        body_text = Text.from_markup(
            "Configure your pools, swarm policies, AI provider, and TUI.\n"
            "Every value is persisted to [bold]~/.agentdrive/config.yaml[/]."
        )

    console.print()
    console.print(
        section_panel(
            Group(hero),
            body_text,
            title=None,
            palette=PALETTE,
        )
    )


def run_setup(sections: list[str] | None = None) -> bool:
    """
    Run the Agent Drive setup wizard.

    If `sections` is provided, only run those specific sections (by short name).
    """
    if sections is None:
        target_names = [s["name"] for s in SECTIONS]
        running_subset = False
    else:
        target_names = list(sections)
        running_subset = True

    _welcome_panel(running_subset, target_names)

    success = True
    completed: list[str] = []
    skipped: list[str] = []

    # Track step position only across sections we'll actually run.
    to_run = [s for s in SECTIONS if s["name"] in target_names]
    total = len(to_run) or 1

    for i, sec in enumerate(to_run, 1):
        _print_step(i, total, sec["title"])
        try:
            result = sec["func"]()
            if result:
                completed.append(sec["title"])
            else:
                success = False
                skipped.append(sec["title"])
                console.print()
                console.print(
                    warn_line(
                        f"Section '{sec['title']}' had issues.",
                        palette=PALETTE,
                    )
                )
        except KeyboardInterrupt:
            console.print()
            console.print(warn_line("Setup interrupted.", palette=PALETTE))
            return False
        except Exception as e:
            console.print()
            console.print(
                error_line(
                    f"Section '{sec['title']}' error: {e}",
                    palette=PALETTE,
                )
            )
            success = False
            skipped.append(sec["title"])

    # ── Result panel ──────────────────────────────────────────────────────
    console.print()
    rows = []
    for title in completed:
        rows.append((title, f"[{PALETTE.ok}]configured[/]"))
    for title in skipped:
        rows.append((title, f"[{PALETTE.muted}]skipped[/]"))
    if not running_subset:
        for sec in SECTIONS:
            if sec["title"] not in completed and sec["title"] not in skipped:
                rows.append((sec["title"], f"[{PALETTE.muted}]not run[/]"))

    console.print(
        result_panel(
            "Setup complete" if success else "Setup finished with issues",
            rows,
            success=success and bool(completed),
            palette=PALETTE,
            extras=[
                Text(""),
                Section(
                    "Try next",
                    [
                        ("agentdrive setup swarm", "tweak sub-agent pool policies"),
                        ("agentdrive setup ai", "change AI provider or API key"),
                        ("agentdrive provider set", "switch AI provider from CLI"),
                        ("agentdrive model set", "switch model from CLI"),
                        ("agentdrive", "launch the agent chat"),
                    ],
                    palette=PALETTE,
                    key_width=22,
                ),
            ],
        )
    )
    console.print()

    if success and completed and not running_subset:
        try:
            cfg = load_config()
            cfg["onboarded"] = True
            cfg.setdefault("onboarding_consent_swarm_pools", True)
            save_config(cfg)
        except Exception:
            pass

    return success


def cmd_setup(args) -> int:
    """Entry point for `agentdrive setup` and `agentdrive setup <section>`."""
    sections = None
    if hasattr(args, "section") and args.section:
        mapping = {s["name"]: s["name"] for s in SECTIONS}
        mapping.update(
            {
                "swarm": "swarm",
                "dna": "swarm",
                "agent": "ai",
                "model": "ai",
                "provider": "ai",
                "key": "ai",
                "ui": "tui",
            }
        )
        sections = [mapping.get(args.section.lower(), args.section.lower())]
        console.print()
        console.print(
            info_line(
                f"Running section: [bold]{sections[0]}[/]",
                palette=PALETTE,
            )
        )

    try:
        run_setup(sections)
    except KeyboardInterrupt:
        console.print()
        console.print(warn_line("Setup interrupted.", palette=PALETTE))
        return 1
    return 0
