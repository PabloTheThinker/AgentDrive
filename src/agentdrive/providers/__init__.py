"""
Agent Drive Provider System — connect any AI model to your AgentDrive.

Provides:
- Provider profiles (OpenAI, Anthropic, OpenRouter, local models, etc.)
- API key management via ~/.agentdrive/.env
- Model selection and switching
- A simple LLM client for chat completions
"""

from agentdrive.providers.base import (
    ProviderProfile,
    detect,
    get,
    list_all,
    list_available,
    load_config_provider,
    register,
    save_config_provider,
    write_env_var,
)
from agentdrive.providers.builtins import *  # noqa — registers all built-in providers

__all__ = [
    "ProviderProfile",
    "register",
    "get",
    "list_all",
    "list_available",
    "detect",
    "write_env_var",
    "load_config_provider",
    "save_config_provider",
]
