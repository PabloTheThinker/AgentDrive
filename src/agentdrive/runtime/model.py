"""Bare-model fallback runtime adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from agentdrive.providers.agent_providers import resolve_agent_default
from agentdrive.providers.base import get as get_provider
from agentdrive.runtime.base import AgentRuntimeAdapter

# The streaming chat client still lives in agentdrive.web.chat (only the
# legacy web *UI* — templates + app routes — was removed; the LLM client layer
# survives). Import defensively so a future relocation of the chat layer keeps
# this adapter importable.
try:
    from agentdrive.web.chat import DEFAULT_MODEL, LLMStreamClient
except ImportError:
    DEFAULT_MODEL = "qwen3:14b"
    LLMStreamClient = None  # type: ignore[assignment]


class ModelAdapter(AgentRuntimeAdapter):
    """Adapter for agents that are still raw LLM wrappers."""

    kind = "model"

    def __init__(
        self,
        agent_id: str,
        config: dict[str, Any],
        *,
        stream_client: LLMStreamClient | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.config = dict(config)
        self.provider_name, self.model = self._resolve_provider_model()
        self.profile = get_provider(self.provider_name) if self.provider_name else None
        self.client = stream_client or (LLMStreamClient(self.profile) if self.profile else None)

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        if self.client is None or self.profile is None:
            yield f"[runtime {self.agent_id} error: no available model provider]"
            return
        async for piece in self.client.stream_chat(self.model, messages):
            yield piece

    async def health(self) -> dict[str, Any]:
        if self.profile is None:
            return {
                "kind": self.kind,
                "healthy": False,
                "detail": "no available model provider",
            }
        return {
            "kind": self.kind,
            "healthy": True,
            "detail": f"{self.profile.name} / {self.model}",
            "provider": self.profile.name,
            "model": self.model,
        }

    def _resolve_provider_model(self) -> tuple[str, str]:
        provider_name = str(self.config.get("provider") or "")
        model = str(self.config.get("model") or "")
        if provider_name:
            profile = get_provider(provider_name)
            return provider_name, model or (profile.default_model if profile else DEFAULT_MODEL)

        default = resolve_agent_default(self.agent_id)
        if default:
            default_provider, default_model = default
            return default_provider, model or default_model
        return "", model or DEFAULT_MODEL
