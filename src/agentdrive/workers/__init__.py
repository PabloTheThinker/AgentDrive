"""
Agent Drive Workers and Agent Adapters.

Provides the Worker interface and pluggable adapters so that external agents
(custom agents, rich workers, ACP/MCP agents) can act as execution workers for the
Agent Drive orchestrator and can contribute high-quality runs for genome extraction.
"""

from .adapters import ExternalAgentAdapter, get_default_adapter
from .base import Worker, WorkerCapabilities, WorkerResult
from .rich_agent_adapter import RichAgentAdapter

# Preferred clean names for rich external workers
ExternalWorkerAdapter = RichAgentAdapter

__all__ = [
    "Worker",
    "WorkerResult",
    "WorkerCapabilities",
    "ExternalAgentAdapter",
    "get_default_adapter",
    "ExternalWorkerAdapter",
    "RichAgentAdapter",
]
