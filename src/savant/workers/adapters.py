"""
Concrete Agent Adapters.

ExternalAgentAdapter (with legacy 'hermes' key support) is the reference
implementation that lets external agents act as Savant workers and
contribute genomes to the ecosystem.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional

from .base import AgentAdapter, Worker, WorkerResult, WorkerCapabilities

logger = logging.getLogger(__name__)


class ExternalAgentAdapter(AgentAdapter):
    """
    Adapter that wraps external agents (rich workers or compatible systems) for use inside Savant.

    - as_worker(): returns a Worker that can dispatch framework execution to the external agent
      (via subprocess, ACP, local import if co-located, etc.)
    - contribute_genome(): accepts a run artifact (trajectory, log dir, or
      structured dict) and feeds it through Savant scanners to produce candidate Genomes.

    This is intentionally lightweight in v0.1 — real integrations use agent
    tool surfaces, run export, or direct hooks. The legacy name 'hermes' is
    supported in config for transition.
    """

    def __init__(self, external_home: Path | str | None = None, **connection_kwargs: Any):
        self.external_home = Path(external_home) if external_home else None
        self.connection_kwargs = connection_kwargs
        self._worker: Optional[Worker] = None
        logger.info("ExternalAgentAdapter initialized (stub)")

    def get_name(self) -> str:
        return "external"

    def as_worker(self) -> Worker:
        if self._worker is None:
            self._worker = _ExternalWorker(self)
        return self._worker

    def contribute_genome(
        self,
        run_data: dict[str, Any] | Path,
        scanner_name: str | None = None,
    ) -> List[Any]:
        """
        Extract genomes from an external agent run.

        In a full implementation this would:
        - Normalize trajectory format into scanner input
        - Select appropriate scanners (e.g. "framework-extractor", "reasoning-patterns")
        - Register resulting genomes via GenomeRegistry
        """
        from savant.scanners.base import BaseScanner

        # Stub: for now just log and return empty. Real scanners will be registered later.
        logger.info(f"ExternalAgentAdapter.contribute_genome called with {type(run_data)} (scanner={scanner_name})")
        # Example future:
        # scanners = registry.get_scanners(scanner_name or "default")
        # genomes = []
        # for s in scanners:
        #     genomes.extend(s.scan(run_data))
        # return genomes
        return []

    def health(self) -> bool:
        # In real impl: check if external agent gateway/process is reachable
        return True


class _ExternalWorker(Worker):
    """Internal Worker implementation backed by ExternalAgentAdapter."""

    name = "external-worker"

    def __init__(self, adapter: ExternalAgentAdapter):
        self.adapter = adapter

    def execute(
        self,
        framework: dict[str, Any] | None = None,
        genome: Any | None = None,
        inputs: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> WorkerResult:
        logger.info("ExternalWorker executing (stub implementation)")
        # Real: call out to external agent (CLI invoke, API, or in-proc), capture full trace.
        # For now return a successful stub result so orchestrator can be wired later.
        return WorkerResult(
            success=True,
            output={"message": "Executed via ExternalAgentAdapter (stub)", "framework": framework},
            run_id=f"external-stub-{id(self)}",
            metrics={"stub": 1.0},
        )

    def get_capabilities(self) -> WorkerCapabilities:
        return WorkerCapabilities(
            supports_frameworks=True,
            supports_genomes=True,
            max_concurrency=4,
            supported_domains=["general", "security", "code", "analysis"],
            metadata={"agent": "external", "adapter_version": "0.1"},
        )

    def health_check(self) -> bool:
        return self.adapter.health()


def get_default_adapter() -> AgentAdapter:
    """Return the default adapter (external for now; future: registry of adapters)."""
    return ExternalAgentAdapter()


# Legacy alias for transition (config keys and old imports may still reference 'hermes')
HermesAdapter = ExternalAgentAdapter


__all__ = ["ExternalAgentAdapter", "HermesAdapter", "get_default_adapter"]
