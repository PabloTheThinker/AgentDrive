"""Agent runtime adapter registry and config helpers."""

from __future__ import annotations

from agentdrive.runtime.base import (
    AgentRuntimeAdapter,
    build,
    is_registered,
    register,
    registered_kinds,
)
from agentdrive.runtime.config import (
    load_runtime_config,
    resolve_adapter,
    runtime_config_path,
    write_runtime_config,
)
from agentdrive.runtime.http_sse import HTTPSSEAdapter
from agentdrive.runtime.model import ModelAdapter

register("http_sse", lambda agent_id, config: HTTPSSEAdapter(agent_id, config))
register("model", lambda agent_id, config: ModelAdapter(agent_id, config))

__all__ = [
    "AgentRuntimeAdapter",
    "HTTPSSEAdapter",
    "ModelAdapter",
    "build",
    "is_registered",
    "load_runtime_config",
    "register",
    "registered_kinds",
    "resolve_adapter",
    "runtime_config_path",
    "write_runtime_config",
]
