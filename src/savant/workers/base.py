"""
Base Worker and Agent Adapter interfaces for Savant.

These abstractions allow any capable external or rich agent to be
plugged in as a "worker" that the orchestrator can dispatch work to, and
that can emit instrumented run data usable by Savant Scanners to produce
new or improved Genomes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class WorkerResult:
    """Standardized result from a worker execution."""
    success: bool
    output: Any = None
    artifacts: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    run_id: str | None = None  # Unique identifier for this run (for scanning/provenance)
    error: str | None = None


@dataclass
class WorkerCapabilities:
    """Declarative capabilities of a worker (used by orchestrator for selection)."""
    supports_frameworks: bool = True
    supports_genomes: bool = True
    max_concurrency: int = 1
    supported_domains: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class Worker(ABC):
    """
    Abstract base for a Savant worker.

    Workers execute structured work (frameworks or genome-guided tasks)
    and return rich, scannable results.
    """

    name: str = "base-worker"

    @abstractmethod
    def execute(
        self,
        framework: dict[str, Any] | None = None,
        genome: Any | None = None,  # Genome | str | None
        inputs: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> WorkerResult:
        """Execute a unit of work. Implementations must be robust and return WorkerResult."""
        raise NotImplementedError

    def get_capabilities(self) -> WorkerCapabilities:
        """Return what this worker can do. Override for smarter routing."""
        return WorkerCapabilities()

    def health_check(self) -> bool:
        """Quick liveness / readiness check."""
        return True

    def get_run_data(self, run_id: str) -> Optional[dict[str, Any]]:
        """Optional: retrieve full instrumented run data for a previous execution (for scanners)."""
        return None


class AgentAdapter(Protocol):
    """
    Protocol for adapters that wrap external agents (rich workers or compatible systems)
    so they can be used transparently as Savant Workers and can push their
    execution traces into the Savant genome ecosystem.
    """

    def as_worker(self) -> Worker:
        """Return a Worker view of this agent/adapter."""
        ...

    def contribute_genome(
        self,
        run_data: dict[str, Any] | Path,
        scanner_name: str | None = None,
    ) -> List[Any]:  # List[Genome]
        """Take a run (from this agent) and use Savant scanners to extract candidate Genomes."""
        ...

    def get_name(self) -> str:
        ...


__all__ = ["Worker", "WorkerResult", "WorkerCapabilities", "AgentAdapter"]
