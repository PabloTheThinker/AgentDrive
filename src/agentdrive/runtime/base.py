"""Runtime adapter registry for agent chat transports."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class AgentRuntimeAdapter:
    """Base class for agent runtime transports."""

    agent_id: str
    kind: str
    config: dict[str, Any]

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Yield plain text chunks from the target runtime."""
        raise NotImplementedError

    async def health(self) -> dict[str, Any]:
        """Return display-safe health metadata for the target runtime."""
        raise NotImplementedError


class AdapterFactory(Protocol):
    def __call__(self, agent_id: str, config: dict[str, Any]) -> AgentRuntimeAdapter: ...


_REGISTRY: dict[str, AdapterFactory] = {}


def register(kind: str, factory: AdapterFactory) -> None:
    cleaned = kind.strip().lower()
    if not cleaned:
        raise ValueError("runtime kind is required")
    _REGISTRY[cleaned] = factory


def registered_kinds() -> set[str]:
    return set(_REGISTRY)


def is_registered(kind: str) -> bool:
    return kind.strip().lower() in _REGISTRY


def build(agent_id: str, config: dict[str, Any]) -> AgentRuntimeAdapter:
    kind = str(config.get("kind") or "").strip().lower()
    if not kind:
        kind = "model"
        config = {**config, "kind": kind}
    factory = _REGISTRY.get(kind)
    if factory is None:
        raise ValueError(f"unknown agent runtime kind: {kind}")
    return factory(agent_id, config)
