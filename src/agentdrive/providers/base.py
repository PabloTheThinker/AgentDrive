"""
Provider profile base — typed connection metadata for any LLM provider.
Each provider defines how to connect, which env vars hold keys, and
what models are available.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

import httpx

from agentdrive.constants import get_agentdrive_env_path

logger = logging.getLogger(__name__)


@dataclass
class ProviderProfile:
    """Declarative profile for an AI model provider."""

    name: str
    display_name: str
    description: str
    api_mode: str = "chat_completions"
    env_var: str = ""
    alt_env_vars: tuple[str, ...] = ()
    base_url: str = ""
    models_url: str = ""
    fallback_models: list[str] = field(default_factory=list)
    default_model: str = ""
    requires_key: bool = True
    signup_url: str = ""

    def get_env_var(self) -> str:
        return self.env_var

    def get_all_env_vars(self) -> tuple[str, ...]:
        return (self.env_var,) + self.alt_env_vars if self.env_var else self.alt_env_vars

    def get_api_key(self) -> str | None:
        for var in self.get_all_env_vars():
            val = _read_env_value(var)
            if val and val not in ("", "*", "changeme", "your_api_key"):
                return val
        return None

    def has_key(self) -> bool:
        if not self.requires_key:
            return True
        return self.get_api_key() is not None

    def fetch_models(self) -> list[str]:
        if not self.models_url:
            return self.fallback_models
        try:
            headers = {}
            key = self.get_api_key()
            if key:
                headers["Authorization"] = f"Bearer {key}"
            resp = httpx.get(self.models_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                models = []
                for m in data.get("data", []):
                    mid = m.get("id", "")
                    if mid:
                        models.append(mid)
                for m in data.get("models", []):
                    mid = m.get("name", "") or m.get("model", "") or m.get("id", "")
                    if mid:
                        models.append(mid)
                return models[:50] if models else self.fallback_models
            return self.fallback_models
        except Exception:
            return self.fallback_models


def _read_env_value(var: str) -> str | None:
    val = os.environ.get(var, "")
    if val:
        return val
    env_path = get_agentdrive_env_path()
    if env_path.exists():
        try:
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith(f"{var}="):
                    return line.split("=", 1)[1].strip().strip("\"'")
                if line.startswith("export ") and f"{var}=" in line:
                    return line.split("=", 1)[1].strip().strip("\"'")
        except Exception:
            pass
    return None


def write_env_var(var: str, value: str) -> None:
    env_path = get_agentdrive_env_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    found = False
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith(f"{var}=") or line.startswith(f"export {var}="):
                lines.append(f"{var}={value}")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"{var}={value}")
    env_path.write_text("\n".join(lines) + "\n")
    env_path.chmod(0o600)


# ── Registry ──────────────────────────────────────────────────────────────

_registry: dict[str, ProviderProfile] = {}
_alias_map: dict[str, str] = {}


def register(profile: ProviderProfile) -> None:
    _registry[profile.name] = profile
    _alias_map[profile.name.lower()] = profile.name
    if profile.display_name:
        _alias_map[profile.display_name.lower()] = profile.name


def get(name: str) -> ProviderProfile | None:
    key = name.lower()
    if key in _alias_map:
        return _registry.get(_alias_map[key])
    return _registry.get(name)


def list_all() -> list[ProviderProfile]:
    return list(_registry.values())


def list_available() -> list[ProviderProfile]:
    return [p for p in _registry.values() if p.has_key()]


def detect() -> ProviderProfile | None:
    for p in _registry.values():
        if p.has_key():
            return p
    return None


def load_config_provider() -> tuple[str, str] | None:
    from agentdrive.config import load_config

    cfg = load_config()
    provider_cfg = cfg.get("provider", {})
    pname = provider_cfg.get("default", "")
    model = provider_cfg.get("model", "")
    if pname:
        return pname, model
    return None


def save_config_provider(provider_name: str, model: str = "") -> None:
    from agentdrive.config import load_config, save_config

    cfg = load_config()
    cfg.setdefault("provider", {})
    cfg["provider"]["default"] = provider_name
    if model:
        cfg["provider"]["model"] = model
    save_config(cfg)
