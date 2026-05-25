"""
AgentDrive Settings & User Control

This module gives the user (and any AI the user instructs) full control over how their AgentDrive(s) behave.

All settings are persisted in `~/.agentdrive/config.yaml` (or AGENTDRIVE_HOME equivalent) under the `pool:` section.

The user is always sovereign: the Drive starts empty, and every policy can be changed by the owner at any time — including by telling Grok, Claude, Codex, etc. "Use these Savant pool settings for this swarm."

"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from agentdrive.config import load_config, save_config

IsolationLevel = Literal["none", "swarm", "subagent"]
SharingPolicy = Literal["none", "read", "selective", "full"]


@dataclass
class DriveSettings:
    # How isolated sub-agent pools are from each other and the parent
    isolation_level: IsolationLevel = "subagent"

    # Automatically ingest high-quality outcomes into the Drive?
    auto_ingest_on_success: bool = True
    min_quality_for_ingest: float = 0.75

    # What other pools in the same swarm/family can do with this pool's DNA
    sharing_policy: SharingPolicy = "selective"

    # How long to keep old genomes (0 = forever)
    retention_days: int = 0

    # Whether the Drive is allowed to propose improvements back to parent swarms
    allow_upward_proposals: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DriveSettings:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class DriveSettingsManager:
    """User-controlled settings for AgentDrives (global + per-swarm overrides)."""

    def __init__(self, savant_home: Path | None = None):
        # load_config uses current AGENTDRIVE_HOME (respects overrides); savant_home param kept for future
        if savant_home is not None:
            from agentdrive.constants import (
                reset_agentdrive_home_override,
                set_agentdrive_home_override,
            )

            tok = set_agentdrive_home_override(savant_home)
            try:
                self.config = load_config()
            finally:
                reset_agentdrive_home_override(tok)
        else:
            self.config = load_config()
        self._pool_section = self.config.setdefault("pool", {})

    def get_global(self) -> DriveSettings:
        data = self._pool_section.get("global", {})
        return DriveSettings.from_dict(data)

    def set_global(self, settings: DriveSettings) -> None:
        self._pool_section["global"] = settings.to_dict()
        self._save()

    def get_for_swarm(self, swarm_id: str) -> DriveSettings:
        """Get settings for a specific swarm (falls back to global)."""
        swarm_data = self._pool_section.get("swarms", {}).get(swarm_id, {})
        global_settings = self.get_global()
        if not swarm_data:
            return global_settings
        # Merge: swarm overrides global
        merged = {**global_settings.to_dict(), **swarm_data}
        return DriveSettings.from_dict(merged)

    def set_for_swarm(self, swarm_id: str, settings: DriveSettings) -> None:
        if "swarms" not in self._pool_section:
            self._pool_section["swarms"] = {}
        self._pool_section["swarms"][swarm_id] = settings.to_dict()
        self._save()

    def get_effective_settings(
        self, swarm_id: str | None = None, subagent_id: str | None = None
    ) -> DriveSettings:
        """Final settings that apply to a specific sub-agent (isolation/sharing etc control user sovereignty)."""
        if swarm_id:
            base = self.get_for_swarm(swarm_id)
        else:
            base = self.get_global()
        # Future: support per-subagent overrides under pool.subagents["<swarm_id>:<subagent_id>"]
        if subagent_id and swarm_id:
            sub_key = f"{swarm_id}:{subagent_id}"
            sub_over = self._pool_section.get("subagents", {}).get(sub_key, {})
            if sub_over:
                merged = {**base.to_dict(), **sub_over}
                base = DriveSettings.from_dict(merged)
        return base

    def _save(self) -> None:
        save_config(self.config)

    def as_user_instructions(self) -> str:
        """Helpful text any AI can be given so the user can control the Drive via natural language."""
        return (
            "You are using the AgentDrive system. The user owns all settings. "
            "Current effective pool rules are stored in the user's config. "
            "If the user tells you to change isolation, auto-ingest, sharing policy, etc., "
            "you must update the Savant pool settings on their behalf using the provided API or CLI."
        )


# Convenience singleton
_settings_manager: DriveSettingsManager | None = None


def get_drive_settings_manager() -> DriveSettingsManager:
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = DriveSettingsManager()
    return _settings_manager


def get_effective_drive_settings(
    swarm_id: str | None = None, subagent_id: str | None = None
) -> DriveSettings:
    """Get the effective (merged global+swarm+sub) settings controlling isolation and sharing."""
    return get_drive_settings_manager().get_effective_settings(swarm_id, subagent_id)
