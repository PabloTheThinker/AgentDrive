"""
Savant Workers and Agent Adapters.

Provides the Worker interface and pluggable adapters so that external agents
(custom agents, rich workers, ACP/MCP agents) can act as execution workers for the
Savant orchestrator and can contribute high-quality runs for genome extraction.
"""

from .base import Worker, WorkerResult, WorkerCapabilities
from .adapters import ExternalAgentAdapter, HermesAdapter, get_default_adapter
from .rich_agent_adapter import RichAgentAdapter

# Preferred clean names for rich external workers
ExternalWorkerAdapter = RichAgentAdapter

# Back-compat alias (deprecated; will be removed)
HermesStyleWorker = RichAgentAdapter

__all__ = [
    "Worker",
    "WorkerResult",
    "WorkerCapabilities",
    "ExternalAgentAdapter",
    "HermesAdapter",
    "get_default_adapter",
    "ExternalWorkerAdapter",
    "RichAgentAdapter",
    "HermesStyleWorker",
]
