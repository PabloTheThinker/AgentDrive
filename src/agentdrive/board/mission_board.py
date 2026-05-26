"""
Mission Board — a persistent, Agent Drive-native lane board for agent missions.

A *Mission* is a piece of work an agent (or a user) commits to. It is more
durable than a chat turn but lighter-weight than a genome — it tracks intent,
state, lineage, and outcome.

Cards flow through these lanes:

    Pending  →  Running  →  Done
                       \\→  Failed
                              \\→  Archived

Storage: JSONL at `$AGENTDRIVE_HOME/board/missions.jsonl`.
Events: `mission`, `transition` records appended on every state change.
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from agentdrive.constants import get_agentdrive_home


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _board_dir() -> Path:
    return get_agentdrive_home() / "board"


def _board_jsonl() -> Path:
    return _board_dir() / "missions.jsonl"


class MissionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    ARCHIVED = "archived"

    @classmethod
    def lanes(cls) -> list[MissionStatus]:
        return [cls.PENDING, cls.RUNNING, cls.DONE, cls.FAILED, cls.ARCHIVED]


@dataclass
class Mission:
    """A single mission card on the board."""

    id: str
    title: str
    status: MissionStatus = MissionStatus.PENDING
    created: str = field(default_factory=_now_iso)
    started: str | None = None
    completed: str | None = None
    duration_s: float = 0.0

    description: str = ""
    agent_id: str = ""
    swarm_id: str = ""
    subagent_id: str = ""

    genome_id: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    outcome: dict[str, Any] = field(default_factory=dict)
    dna_used: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @staticmethod
    def new_id() -> str:
        return datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:5]

    @classmethod
    def create(cls, title: str, **kwargs: Any) -> Mission:
        return cls(id=cls.new_id(), title=title, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Mission:
        d = dict(d)
        d["status"] = MissionStatus(d.get("status", "pending"))
        return cls(**{k: v for k, v in d.items() if k in cls.__annotations__})


class MissionBoard:
    """Append-only mission registry with lane-aware queries."""

    def __init__(self, path: Path | None = None):
        self._path = path or _board_jsonl()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._missions: dict[str, Mission] = {}
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    # ── persistence ─────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._path.exists():
            return
        with self._lock, self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event = rec.get("event")
                if event == "mission":
                    mission = Mission.from_dict(rec.get("data") or {})
                    self._missions[mission.id] = mission
                elif event == "transition":
                    mid = rec.get("mission_id")
                    if mid and mid in self._missions:
                        mission = self._missions[mid]
                        new_status = rec.get("to")
                        if new_status:
                            try:
                                mission.status = MissionStatus(new_status)
                            except ValueError:
                                pass
                        for k in ("started", "completed", "duration_s", "outcome", "dna_used"):
                            if k in rec:
                                setattr(mission, k, rec[k])

    def _append(self, record: dict[str, Any]) -> None:
        record = {"ts": _now_iso(), **record}
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ── core operations ─────────────────────────────────────────────

    def add(self, mission: Mission) -> Mission:
        with self._lock:
            self._missions[mission.id] = mission
            self._append({"event": "mission", "data": mission.to_dict()})
        return mission

    def create(self, title: str, **kwargs: Any) -> Mission:
        return self.add(Mission.create(title, **kwargs))

    def get(self, mid: str) -> Mission | None:
        return self._missions.get(mid)

    def transition(
        self,
        mid: str,
        to: MissionStatus,
        outcome: dict[str, Any] | None = None,
        dna_used: list[str] | None = None,
    ) -> Mission | None:
        with self._lock:
            mission = self._missions.get(mid)
            if not mission:
                return None
            now = _now_iso()
            previous = mission.status
            mission.status = to
            record: dict[str, Any] = {
                "event": "transition",
                "mission_id": mid,
                "from": previous.value,
                "to": to.value,
            }
            if to == MissionStatus.RUNNING and not mission.started:
                mission.started = now
                record["started"] = now
            if to in (MissionStatus.DONE, MissionStatus.FAILED, MissionStatus.ARCHIVED):
                mission.completed = now
                record["completed"] = now
                if mission.started:
                    try:
                        start = datetime.fromisoformat(mission.started)
                        end = datetime.fromisoformat(now)
                        mission.duration_s = (end - start).total_seconds()
                        record["duration_s"] = mission.duration_s
                    except Exception:
                        pass
            if outcome is not None:
                mission.outcome = outcome
                record["outcome"] = outcome
            if dna_used is not None:
                mission.dna_used = list(dna_used)
                record["dna_used"] = mission.dna_used
            self._append(record)
            return mission

    def start(self, mid: str) -> Mission | None:
        return self.transition(mid, MissionStatus.RUNNING)

    def complete(self, mid: str, **kwargs: Any) -> Mission | None:
        return self.transition(mid, MissionStatus.DONE, **kwargs)

    def fail(self, mid: str, error: str = "", **kwargs: Any) -> Mission | None:
        outcome = kwargs.pop("outcome", {}) or {}
        if error:
            outcome["error"] = error
        return self.transition(mid, MissionStatus.FAILED, outcome=outcome, **kwargs)

    def archive(self, mid: str) -> Mission | None:
        return self.transition(mid, MissionStatus.ARCHIVED)

    # ── queries ─────────────────────────────────────────────────────

    def all(self) -> list[Mission]:
        return list(self._missions.values())

    def by_lane(self, status: MissionStatus) -> list[Mission]:
        return [m for m in self._missions.values() if m.status == status]

    def lanes(self) -> dict[MissionStatus, list[Mission]]:
        out: dict[MissionStatus, list[Mission]] = {s: [] for s in MissionStatus.lanes()}
        for m in self._missions.values():
            out[m.status].append(m)
        # Sort each lane: newest first
        for lane in out.values():
            lane.sort(key=lambda m: m.completed or m.started or m.created, reverse=True)
        return out

    def recent(self, limit: int = 20) -> list[Mission]:
        sorted_missions = sorted(
            self._missions.values(),
            key=lambda m: m.completed or m.started or m.created,
            reverse=True,
        )
        return sorted_missions[:limit]

    def stats(self) -> dict[str, Any]:
        lanes = self.lanes()
        total = sum(len(v) for v in lanes.values())
        done = lanes[MissionStatus.DONE]
        avg_duration = sum(m.duration_s for m in done) / len(done) if done else 0.0
        return {
            "total": total,
            "pending": len(lanes[MissionStatus.PENDING]),
            "running": len(lanes[MissionStatus.RUNNING]),
            "done": len(lanes[MissionStatus.DONE]),
            "failed": len(lanes[MissionStatus.FAILED]),
            "archived": len(lanes[MissionStatus.ARCHIVED]),
            "avg_duration_s": round(avg_duration, 2),
            "path": str(self._path),
        }


# ── default board singleton ───────────────────────────────────────────

_DEFAULT_BOARD: MissionBoard | None = None


def get_default_board() -> MissionBoard:
    global _DEFAULT_BOARD
    if _DEFAULT_BOARD is None or _DEFAULT_BOARD.path.parent != _board_dir():
        _DEFAULT_BOARD = MissionBoard()
    return _DEFAULT_BOARD
