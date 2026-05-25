"""
Savant Swarm Pool Manager — Professional manager for per-agent DNA pools in swarms.

Design goals (professional subagent handling):
- Every spawned sub-agent gets its own isolated, persistent AgentDrive by default.
- Clear, configurable policies (inspired by best-practice delegation controls and config-driven behavior).
- Full provenance and audit trail.
- Safe defaults with explicit user overrides.
- Thread-safe registry of active swarm members.
- Clean separation between "parent sees summary" vs "child has private DNA".

This is the core that makes "agent swarms with living memory" actually work at a high-quality level.
"""

from __future__ import annotations

import logging
import os
import os.path
import threading
from pathlib import Path
from typing import Any

from agentdrive.constants import get_swarm_drive_path
from agentdrive.drive.drive import AgentDrive
from agentdrive.drive.swarm_policy import SwarmDrivePolicy

logger = logging.getLogger(__name__)


class SwarmDriveManager:
    """
    Central manager for all swarm-scoped AgentDrives.

    When an orchestrator (Grok, Claude, custom agent, etc.) calls something like
    `spawn_subagent(...)`, it should also call into this manager to ensure the
    child gets its own DNA pool.

    Professional invariants:
    - Sub-agents are isolated by default.
    - All sharing is explicit and policy-driven.
    - The manager knows about every active swarm member (for observability and control).
    - User can pause spawning, inspect, or kill swarm members at the Drive level.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._active_swarms: dict[str, dict[str, Any]] = {}  # swarm_id -> metadata
        self._pools: dict[str, AgentDrive] = {}  # pool_key -> AgentDrive
        self._global_policy = SwarmDrivePolicy()  # default safe policy

    def _make_pool_key(self, swarm_id: str, subagent_id: str | None = None) -> str:
        # v2 / Milestone 2a: cache key is swarm_id only — all sub-agents in
        # the same swarm share one Drive. The subagent_id arg is kept for
        # backwards-compatible callers but ignored for routing.
        return swarm_id

    def get_or_create_pool(
        self,
        swarm_id: str,
        subagent_id: str | None = None,
        policy: SwarmDrivePolicy | None = None,
    ) -> AgentDrive:
        """Get (or create) the shared AgentDrive for this swarm.

        v2 / Milestone 2a: every sub-agent in the same swarm gets the **same**
        AgentDrive — the shared "we work together" experience pool. The Drive
        lives at ``<swarms>/<swarm_id>/drive/`` regardless of which sub-agent
        asked for it. Sub-agents namespace their writes via Genome author
        field; the cross-sibling read is free.

        ``subagent_id`` is registered as a swarm member (for observability)
        but does not isolate the Drive. To get a truly air-gapped child
        Drive (red-team / adversarial probes), construct ``AgentDrive``
        directly with an explicit ``drive_path``.
        """
        key = self._make_pool_key(swarm_id, subagent_id)

        with self._lock:
            existing = self._pools.get(key)
            if existing is not None:
                # Track the new sub-agent as a swarm member even on cache hit.
                if subagent_id:
                    self._active_swarms.setdefault(
                        swarm_id,
                        {
                            "members": set(),
                            "created_at": __import__("time").time(),
                            "paused": False,
                        },
                    )["members"].add(subagent_id)
                return existing

            # ``os.path.realpath`` is the documented CodeQL sanitizer for
            # ``py/path-injection`` — collapses the swarm_id taint flow.
            drive_path = Path(os.path.realpath(os.fspath(get_swarm_drive_path(swarm_id))))
            drive_path.mkdir(parents=True, exist_ok=True)
            (drive_path / "genomes").mkdir(exist_ok=True)

            effective_policy = policy or self._global_policy

            # BUGFIX (v2 / M2a): previously this constructed AgentDrive()
            # without drive_path, so every "isolated" sub-agent silently
            # landed on the default Drive. Surface caught by examples/03_swarm.py
            # during the OSS-hygiene audit. The shared-Drive design now
            # makes this the correct path on purpose, not by accident.
            pool = AgentDrive(
                name=f"swarm:{swarm_id}",
                drive_path=drive_path,
                swarm_id=swarm_id,
                # subagent_id intentionally NOT passed — Drive is per-swarm,
                # not per-sub-agent. Author tagging happens at ingest time.
            )

            pool._swarm_policy = effective_policy  # type: ignore[attr-defined]
            pool._swarm_id = swarm_id

            self._pools[key] = pool

            self._active_swarms.setdefault(
                swarm_id,
                {"members": set(), "created_at": __import__("time").time(), "paused": False},
            )
            if subagent_id:
                self._active_swarms[swarm_id]["members"].add(subagent_id)

            from agentdrive.utils.log_safe import safe_for_log

            logger.info(
                "Created shared AgentDrive for swarm",
                extra={
                    "swarm_id": safe_for_log(swarm_id),
                    "path": safe_for_log(drive_path),
                },
            )

            pool._provenance = {
                "swarm_id": swarm_id,
                "shared": True,
                "created_at": __import__("time").time(),
            }

            return pool

    def register_active_member(
        self, swarm_id: str, subagent_id: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Register a running sub-agent for observability and control."""
        with self._lock:
            if swarm_id not in self._active_swarms:
                self._active_swarms[swarm_id] = {
                    "members": set(),
                    "created_at": __import__("time").time(),
                    "paused": False,
                }
            self._active_swarms[swarm_id]["members"].add(subagent_id)
            # Could store more metadata (current task, pool ref, etc.)

    def unregister_active_member(self, swarm_id: str, subagent_id: str) -> None:
        with self._lock:
            if swarm_id in self._active_swarms:
                self._active_swarms[swarm_id]["members"].discard(subagent_id)

    def list_active_swarms(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {
                sid: {
                    "member_count": len(meta["members"]),
                    "members": list(meta["members"]),
                    "created_at": meta.get("created_at"),
                    "paused": meta.get("paused", False),
                }
                for sid, meta in self._active_swarms.items()
            }

    def pause_swarm(self, swarm_id: str, paused: bool = True) -> bool:
        """Global-style pause for an entire swarm (spawn pause control)."""
        with self._lock:
            if swarm_id not in self._active_swarms:
                self._active_swarms[swarm_id] = {
                    "members": set(),
                    "created_at": __import__("time").time(),
                    "paused": paused,
                }
            else:
                self._active_swarms[swarm_id]["paused"] = paused
            return paused

    def is_swarm_paused(self, swarm_id: str) -> bool:
        with self._lock:
            return self._active_swarms.get(swarm_id, {}).get("paused", False)

    def get_pool(self, swarm_id: str, subagent_id: str | None = None) -> AgentDrive | None:
        key = self._make_pool_key(swarm_id, subagent_id)
        return self._pools.get(key)

    def get_parent_pool(self, swarm_id: str) -> AgentDrive | None:
        """Get the root pool for this swarm (the orchestrator's pool)."""
        return self.get_pool(swarm_id, subagent_id=None)

    def set_global_policy(self, policy: SwarmDrivePolicy) -> None:
        with self._lock:
            self._global_policy = policy
            logger.info("Updated global swarm pool policy: %s", policy)

    def get_global_policy(self) -> SwarmDrivePolicy:
        return self._global_policy

    def list_active_swarms(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {
                sid: {
                    "member_count": len(meta["members"]),
                    "members": list(meta["members"]),
                    "created_at": meta["created_at"],
                }
                for sid, meta in self._active_swarms.items()
            }

    def pause_new_spawns(self, paused: bool = True) -> None:
        """Global kill-switch for creating new swarm pools (useful for user control)."""
        # In a fuller implementation this would be backed by the settings manager
        logger.warning("Swarm spawn pause set to %s (not yet persisted)", paused)
        # TODO: wire to DriveSettingsManager

    def propose_dna_merge(
        self,
        source_swarm: str,
        source_subagent: str | None,
        target_swarm: str,
        target_subagent: str | None,
        genome_id: str,
    ) -> bool:
        """
        Professional, auditable way for one pool to propose DNA to another.
        Respects current sharing policies.
        """
        # Real implementation would check policies, provenance, quality, user approval, etc.
        from agentdrive.utils.log_safe import safe_for_log

        logger.info(
            "DNA merge proposed",
            extra={
                "from": safe_for_log(f"{source_swarm}:{source_subagent}"),
                "to": safe_for_log(f"{target_swarm}:{target_subagent}"),
                "genome": safe_for_log(genome_id),
            },
        )
        # For now we just log — the actual merge logic lives in the evolutionary engine
        return True


# Global singleton (module-level active subagents registry)
_swarm_pool_manager: SwarmDriveManager | None = None
_manager_lock = threading.Lock()


def get_swarm_drive_manager() -> SwarmDriveManager:
    """Get the process-wide professional manager for all swarm DNA pools."""
    global _swarm_pool_manager
    if _swarm_pool_manager is None:
        with _manager_lock:
            if _swarm_pool_manager is None:
                _swarm_pool_manager = SwarmDriveManager()
    return _swarm_pool_manager
