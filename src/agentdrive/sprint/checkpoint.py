"""gstack-style sprint STOP gates — human ack checkpoints per chain.

Checkpoints persist at::

    ~/.agentdrive/checkpoints/<chain_id>.json

Each chain file tracks completed steps and pending/acked checkpoints so
``agentdrive sprint ship`` can pause for operator review between phases.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentdrive.constants import get_agentdrive_home

_CHAIN_ID_RE = __import__("re").compile(r"^[a-zA-Z0-9._-]+$")


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_checkpoint_id() -> str:
    return f"cp-{secrets.token_hex(6)}"


class CheckpointPending(Exception):
    """Raised when a STOP gate requires operator acknowledgment."""

    def __init__(self, step_id: str, checkpoint_id: str, message: str) -> None:
        self.step_id = step_id
        self.checkpoint_id = checkpoint_id
        self.message = message
        super().__init__(message)


@dataclass
class CheckpointRecord:
    id: str
    step_id: str
    message: str
    created_at: str
    acked: bool = False
    acked_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "step_id": self.step_id,
            "message": self.message,
            "created_at": self.created_at,
            "acked": self.acked,
            "acked_at": self.acked_at,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CheckpointRecord:
        return cls(
            id=str(raw.get("id") or ""),
            step_id=str(raw.get("step_id") or ""),
            message=str(raw.get("message") or ""),
            created_at=str(raw.get("created_at") or ""),
            acked=bool(raw.get("acked")),
            acked_at=raw.get("acked_at"),
        )


class CheckpointStore:
    """JSON-backed checkpoint store — one file per sprint chain."""

    def __init__(self, chain_id: str = "ship", *, root: Path | None = None) -> None:
        cleaned = (chain_id or "ship").strip() or "ship"
        if not _CHAIN_ID_RE.match(cleaned):
            raise ValueError(f"invalid chain_id: {chain_id!r}")
        self.chain_id = cleaned
        if root is None:
            root = get_agentdrive_home() / "checkpoints"
        self.root = Path(root)
        self.path = self.root / f"{self.chain_id}.json"

    def _default_state(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "completed_steps": [],
            "checkpoints": [],
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return self._default_state()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return self._default_state()
        if not isinstance(raw, dict):
            return self._default_state()
        raw.setdefault("chain_id", self.chain_id)
        raw.setdefault("completed_steps", [])
        raw.setdefault("checkpoints", [])
        return raw

    def _save(self, state: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def _checkpoints(self, state: dict[str, Any]) -> list[CheckpointRecord]:
        raw_list = state.get("checkpoints") or []
        out: list[CheckpointRecord] = []
        if not isinstance(raw_list, list):
            return out
        for item in raw_list:
            if isinstance(item, dict) and item.get("id"):
                out.append(CheckpointRecord.from_dict(item))
        return out

    def create(self, step_id: str, message: str) -> str:
        """Create a pending checkpoint for *step_id* and return its id."""
        state = self._load()
        cp_id = _new_checkpoint_id()
        record = CheckpointRecord(
            id=cp_id,
            step_id=step_id,
            message=message,
            created_at=_utc_now_iso(),
            acked=False,
        )
        cps = self._checkpoints(state)
        cps.append(record)
        state["checkpoints"] = [cp.to_dict() for cp in cps]
        self._save(state)
        return cp_id

    def is_acked(self, checkpoint_id: str) -> bool:
        for cp in self._checkpoints(self._load()):
            if cp.id == checkpoint_id:
                return cp.acked
        return False

    def ack(self, checkpoint_id: str) -> bool:
        """Mark a checkpoint acked. Returns False when id is unknown."""
        state = self._load()
        cps = self._checkpoints(state)
        found = False
        for cp in cps:
            if cp.id == checkpoint_id:
                cp.acked = True
                cp.acked_at = _utc_now_iso()
                found = True
                break
        if not found:
            return False
        state["checkpoints"] = [cp.to_dict() for cp in cps]
        self._save(state)
        return True

    def list_pending(self) -> list[dict[str, Any]]:
        """Return unacked checkpoints (newest last)."""
        return [cp.to_dict() for cp in self._checkpoints(self._load()) if not cp.acked]

    def mark_step_completed(self, step_id: str) -> None:
        state = self._load()
        completed = list(state.get("completed_steps") or [])
        if step_id not in completed:
            completed.append(step_id)
        state["completed_steps"] = completed
        self._save(state)

    def is_step_completed(self, step_id: str) -> bool:
        completed = self._load().get("completed_steps") or []
        return step_id in completed

    def reset_chain(self) -> None:
        """Clear completed steps and checkpoints for a fresh ship run."""
        self._save(self._default_state())
