"""
Savant Pool Settings & User Control

This module gives the user (and any AI the user instructs) full control over how their Savant Pool(s) behave.

All settings are persisted in `~/.savant/config.yaml` (or SAVANT_HOME equivalent) under the `pool:` section.

The user is always sovereign: the pool starts empty, and every policy can be changed by the owner at any time — including by telling Grok, Claude, Codex, etc. "Use these Savant pool settings for this swarm."

"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Literal

from savant.config import load_config, save_config

IsolationLevel = Literal["none", "swarm", "subagent"]
SharingPolicy = Literal["none", "read", "selective", "full"]


@dataclass
class PoolSettings:
    # How isolated sub-agent pools are from each other and the parent
    isolation_level: IsolationLevel = "subagent"

    # Automatically ingest high-quality outcomes into the pool?
    auto_ingest_on_success: bool = True
    min_quality_for_ingest: float = 0.75

    # What other pools in the same swarm/family can do with this pool's DNA
    sharing_policy: SharingPolicy = "selective"

    # How long to keep old genomes (0 = forever)
    retention_days: int = 0

    # Whether the pool is allowed to propose improvements back to parent swarms
    allow_upward_proposals: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PoolSettings":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class PoolSettingsManager:
    """User-controlled settings for Savant Pools (global + per-swarm overrides)."""

    def __init__(self, savant_home: Path | None = None):
        # load_config uses current SAVANT_HOME (respects overrides); savant_home param kept for future
        if savant_home is not None:
            from savant.constants import set_savant_home_override, reset_savant_home_override
            tok = set_savant_home_override(savant_home)
            try:
                self.config = load_config()
            finally:
                reset_savant_home_override(tok)
        else:
            self.config = load_config()
        self._pool_section = self.config.setdefault("pool", {})

    def get_global(self) -> PoolSettings:
        data = self._pool_section.get("global", {})
        return PoolSettings.from_dict(data)

    def set_global(self, settings: PoolSettings) -> None:
        self._pool_section["global"] = settings.to_dict()
        self._save()

    def get_for_swarm(self, swarm_id: str) -> PoolSettings:
        """Get settings for a specific swarm (falls back to global)."""
        swarm_data = self._pool_section.get("swarms", {}).get(swarm_id, {})
        global_settings = self.get_global()
        if not swarm_data:
            return global_settings
        # Merge: swarm overrides global
        merged = {**global_settings.to_dict(), **swarm_data}
        return PoolSettings.from_dict(merged)

    def set_for_swarm(self, swarm_id: str, settings: PoolSettings) -> None:
        if "swarms" not in self._pool_section:
            self._pool_section["swarms"] = {}
        self._pool_section["swarms"][swarm_id] = settings.to_dict()
        self._save()

    def get_effective_settings(self, swarm_id: str | None = None, subagent_id: str | None = None) -> PoolSettings:
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
                base = PoolSettings.from_dict(merged)
        return base

    def _save(self) -> None:
        save_config(self.config)

    def as_user_instructions(self) -> str:
        """Helpful text any AI can be given so the user can control the pool via natural language."""
        return (
            "You are using the Savant Pool system. The user owns all settings. "
            "Current effective pool rules are stored in the user's config. "
            "If the user tells you to change isolation, auto-ingest, sharing policy, etc., "
            "you must update the Savant pool settings on their behalf using the provided API or CLI."
        )


# Convenience singleton
_settings_manager: PoolSettingsManager | None = None

def get_pool_settings_manager() -> PoolSettingsManager:
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = PoolSettingsManager()
    return _settings_manager


def get_effective_pool_settings(swarm_id: str | None = None, subagent_id: str | None = None) -> PoolSettings:
    """Get the effective (merged global+swarm+sub) settings controlling isolation and sharing."""
    return get_pool_settings_manager().get_effective_settings(swarm_id, subagent_id)