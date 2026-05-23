"""
Savant Swarm Pool Manager — Professional manager for per-agent DNA pools in swarms.

Design goals (professional subagent handling):
- Every spawned sub-agent gets its own isolated, persistent SavantPool by default.
- Clear, configurable policies (inspired by best-practice delegation controls and config-driven behavior).
- Full provenance and audit trail.
- Safe defaults with explicit user overrides.
- Thread-safe registry of active swarm members.
- Clean separation between "parent sees summary" vs "child has private DNA".

This is the core that makes "agent swarms with living memory" actually work at a high-quality level.
"""

from __future__ import annotations

import logging
import threading
import uuid
from pathlib import Path
from typing import Dict, Optional, Any

from savant.pool.pool import SavantPool, get_default_pool
from savant.pool.swarm_policy import SwarmPoolPolicy
from savant.constants import get_swarm_pool_path, get_savant_home

logger = logging.getLogger(__name__)


class SavantSwarmPoolManager:
    """
    Central manager for all swarm-scoped Savant Pools.

    When an orchestrator (Grok, Claude, custom agent, etc.) calls something like
    `spawn_subagent(...)`, it should also call into this manager to ensure the
    child gets its own DNA pool.

    Professional invariants:
    - Sub-agents are isolated by default.
    - All sharing is explicit and policy-driven.
    - The manager knows about every active swarm member (for observability and control).
    - User can pause spawning, inspect, or kill swarm members at the pool level.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._active_swarms: Dict[str, Dict[str, Any]] = {}   # swarm_id -> metadata
        self._pools: Dict[str, SavantPool] = {}               # pool_key -> SavantPool
        self._global_policy = SwarmPoolPolicy()               # default safe policy

    def _make_pool_key(self, swarm_id: str, subagent_id: Optional[str] = None) -> str:
        return f"{swarm_id}:{subagent_id or 'root'}"

    def get_or_create_pool(
        self,
        swarm_id: str,
        subagent_id: Optional[str] = None,
        policy: Optional[SwarmPoolPolicy] = None,
    ) -> SavantPool:
        """
        Get (or create) an isolated SavantPool for this swarm member.

        This is the key method called when spawning a new sub-agent.
        """
        key = self._make_pool_key(swarm_id, subagent_id)

        with self._lock:
            if key in self._pools:
                return self._pools[key]

            pool_dir = get_swarm_pool_path(swarm_id, subagent_id)
            pool_dir.mkdir(parents=True, exist_ok=True)

            # Each swarm member gets its own registry root under the pool dir
            registry_root = pool_dir / "genomes"
            registry_root.mkdir(exist_ok=True)

            effective_policy = policy or self._global_policy

            pool = SavantPool(
                name=f"swarm:{swarm_id}:{subagent_id or 'root'}",
                # We will later pass a custom registry that lives under pool_dir
            )

            # Store policy with the pool for later reference
            pool._swarm_policy = effective_policy  # type: ignore[attr-defined]
            pool._swarm_id = swarm_id
            pool._subagent_id = subagent_id

            self._pools[key] = pool

            # Register in active swarms (observable registry)
            if swarm_id not in self._active_swarms:
                self._active_swarms[swarm_id] = {
                    "members": set(),
                    "created_at": __import__("time").time(),
                    "paused": False,
                }
            self._active_swarms[swarm_id]["members"].add(subagent_id or "root")

            logger.info(
                "Created isolated Savant Pool for swarm member",
                extra={"swarm_id": swarm_id, "subagent_id": subagent_id, "path": str(pool_dir)},
            )

            # Record provenance on the pool itself
            pool._provenance = {
                "swarm_id": swarm_id,
                "subagent_id": subagent_id,
                "parent_pool": "root" if subagent_id is None else f"{swarm_id}:root",
                "created_at": __import__("time").time(),
            }

            return pool

    def register_active_member(self, swarm_id: str, subagent_id: str, metadata: Dict[str, Any] | None = None) -> None:
        """Register a running sub-agent for observability and control."""
        with self._lock:
            if swarm_id not in self._active_swarms:
                self._active_swarms[swarm_id] = {"members": set(), "created_at": __import__("time").time(), "paused": False}
            self._active_swarms[swarm_id]["members"].add(subagent_id)
            # Could store more metadata (current task, pool ref, etc.)

    def unregister_active_member(self, swarm_id: str, subagent_id: str) -> None:
        with self._lock:
            if swarm_id in self._active_swarms:
                self._active_swarms[swarm_id]["members"].discard(subagent_id)

    def list_active_swarms(self) -> Dict[str, Dict[str, Any]]:
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
                self._active_swarms[swarm_id] = {"members": set(), "created_at": __import__("time").time(), "paused": paused}
            else:
                self._active_swarms[swarm_id]["paused"] = paused
            return paused

    def is_swarm_paused(self, swarm_id: str) -> bool:
        with self._lock:
            return self._active_swarms.get(swarm_id, {}).get("paused", False)

    def get_pool(self, swarm_id: str, subagent_id: Optional[str] = None) -> Optional[SavantPool]:
        key = self._make_pool_key(swarm_id, subagent_id)
        return self._pools.get(key)

    def get_parent_pool(self, swarm_id: str) -> Optional[SavantPool]:
        """Get the root pool for this swarm (the orchestrator's pool)."""
        return self.get_pool(swarm_id, subagent_id=None)

    def set_global_policy(self, policy: SwarmPoolPolicy) -> None:
        with self._lock:
            self._global_policy = policy
            logger.info("Updated global swarm pool policy: %s", policy)

    def get_global_policy(self) -> SwarmPoolPolicy:
        return self._global_policy

    def list_active_swarms(self) -> Dict[str, Dict[str, Any]]:
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
        # TODO: wire to PoolSettingsManager

    def propose_dna_merge(
        self,
        source_swarm: str,
        source_subagent: Optional[str],
        target_swarm: str,
        target_subagent: Optional[str],
        genome_id: str,
    ) -> bool:
        """
        Professional, auditable way for one pool to propose DNA to another.
        Respects current sharing policies.
        """
        # Real implementation would check policies, provenance, quality, user approval, etc.
        logger.info(
            "DNA merge proposed",
            extra={
                "from": f"{source_swarm}:{source_subagent}",
                "to": f"{target_swarm}:{target_subagent}",
                "genome": genome_id,
            },
        )
        # For now we just log — the actual merge logic lives in the evolutionary engine
        return True


# Global singleton (module-level active subagents registry)
_swarm_pool_manager: Optional[SavantSwarmPoolManager] = None
_manager_lock = threading.Lock()


def get_swarm_pool_manager() -> SavantSwarmPoolManager:
    """Get the process-wide professional manager for all swarm DNA pools."""
    global _swarm_pool_manager
    if _swarm_pool_manager is None:
        with _manager_lock:
            if _swarm_pool_manager is None:
                _swarm_pool_manager = SavantSwarmPoolManager()
    return _swarm_pool_manager
