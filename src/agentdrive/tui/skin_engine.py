"""
AgentDrive TUI Skin / Theme Engine

A professional, data-driven theming system for the Agent Drive terminal experience.
Skins are defined in YAML and allow full visual customization without code changes.

Designed for a precise, analytical, high-trust aesthetic appropriate for
framework orchestration, genome management, and evolutionary agent work.
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.theme import Theme

DEFAULT_SKIN = {
    "name": "default",
    "description": "Professional analytical theme for Agent Drive (precise, trustworthy, low-distraction)",
    "colors": {
        "banner_border": "#4A90A4",
        "banner_title": "#5DADE2",
        "banner_accent": "#3498DB",
        "banner_dim": "#5D6D7E",
        "banner_text": "#D5D8DC",
        "ui_accent": "#3498DB",
        "ui_label": "#5DADE2",
        "ui_ok": "#27AE60",
        "ui_error": "#E74C3C",
        "ui_warn": "#F39C12",
        "prompt": "#EBF5FB",
        "input_rule": "#4A90A4",
        "response_border": "#5DADE2",
        "status_bar_bg": "#1C2833",
        "status_bar_text": "#AEB6BF",
        "status_bar_strong": "#5DADE2",
        "status_bar_dim": "#5D6D7E",
        "status_bar_good": "#27AE60",
        "status_bar_warn": "#F39C12",
        "status_bar_bad": "#E67E22",
        "status_bar_critical": "#C0392B",
        "genome_id": "#58D68D",
        "framework_name": "#5DADE2",
        "evolution_step": "#AF7AC5",
    },
    "spinner": {
        "waiting_faces": ["⟐", "⟑", "⟒", "⟓"],
        "thinking_faces": ["◐", "◓", "◑", "◒"],
        "thinking_verbs": ["analyzing", "composing", "evolving", "scanning", "synthesizing"],
    },
}


class SkinEngine:
    """Manages visual theming for the AgentDrive TUI."""

    def __init__(self, skin_name: str | None = None):
        self.skin = self._load_skin(skin_name or "default")
        self.console = Console(theme=self._build_rich_theme())

    def _load_skin(self, name: str) -> dict[str, Any]:
        """Load a skin, falling back to default."""
        # Future: load from ~/.agentdrive/skins/ or built-in presets
        if name == "default":
            return DEFAULT_SKIN
        # TODO: implement real skin loading
        return DEFAULT_SKIN

    def _build_rich_theme(self) -> Theme:
        c = self.skin["colors"]
        styles = {
            "agentdrive.banner.border": f"bold {c['banner_border']}",
            "agentdrive.banner.title": f"bold {c['banner_title']}",
            "agentdrive.accent": c["ui_accent"],
            "agentdrive.label": c["ui_label"],
            "agentdrive.ok": c["ui_ok"],
            "agentdrive.error": c["ui_error"],
            "agentdrive.warn": c["ui_warn"],
            "agentdrive.genome": c.get("genome_id", c["ui_accent"]),
            "agentdrive.framework": c.get("framework_name", c["ui_label"]),
            "agentdrive.evolution": c.get("evolution_step", "#AF7AC5"),
        }
        return Theme(styles)

    def get_spinner_config(self) -> dict[str, Any]:
        return self.skin.get("spinner", DEFAULT_SKIN["spinner"])

    def style(self, key: str) -> str:
        """Return the Rich style string for a semantic key."""
        return self.skin["colors"].get(key, "white")

    def print_banner(self, title: str) -> None:
        """Render a professional Agent Drive banner."""
        c = self.skin["colors"]
        self.console.print(
            f"[{c['banner_border']}]╭{'─' * (len(title) + 4)}╮[/{c['banner_border']}]"
        )
        self.console.print(
            f"[{c['banner_border']}]│[/]  [{c['banner_title']}]{title}[/]  [{c['banner_border']}]│[/]"
        )
        self.console.print(
            f"[{c['banner_border']}]╰{'─' * (len(title) + 4)}╯[/{c['banner_border']}]"
        )


# Global instance for convenience during early development
skin = SkinEngine()
