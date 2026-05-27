"""
AgentSession — JSONL conversation persistence.

Each session is one JSONL file at ~/.agentdrive/agents/<agent_id>/sessions/<session_id>.jsonl.
Lines are events: meta, user, assistant, tool, error.
Resume = read prior lines, rebuild history.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentdrive.constants import get_agentdrive_home
from agentdrive.utils.safe_paths import safe_name


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _agents_root() -> Path:
    return get_agentdrive_home() / "agents"


def _session_dir(agent_id: str) -> Path:
    safe_id = safe_name(agent_id)
    return _agents_root() / safe_id / "sessions"


@dataclass
class Turn:
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    timestamp: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_message(self) -> dict[str, str]:
        """Format for LLM API message history."""
        return {"role": self.role, "content": self.content}


class AgentSession:
    """A single conversation with the Agent Drive Agent. Persists to JSONL."""

    def __init__(
        self,
        agent_id: str,
        session_id: str | None = None,
        title: str | None = None,
    ):
        self.agent_id = agent_id
        self.session_id = session_id or self._new_session_id()
        self.title = title or "Untitled"
        self.created = _now_iso()
        self.turns: list[Turn] = []
        self._path = _session_dir(agent_id) / f"{self.session_id}.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._write_meta_if_new()

    @staticmethod
    def _new_session_id() -> str:
        return datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]

    def _write_meta_if_new(self) -> None:
        if self._path.exists() and self._path.stat().st_size > 0:
            return
        meta = {
            "event": "meta",
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "title": self.title,
            "created": self.created,
        }
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(meta) + "\n")

    def append(self, turn: Turn) -> None:
        self.turns.append(turn)
        record = {"event": "turn", **asdict(turn)}
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def history_for_llm(self, max_turns: int = 30) -> list[dict[str, str]]:
        """Format the recent N turns as LLM API messages (user/assistant only)."""
        relevant = [t for t in self.turns if t.role in ("user", "assistant")]
        return [t.to_message() for t in relevant[-max_turns:]]

    def clear(self) -> None:
        """Wipe in-memory turns and start a new session file."""
        self.session_id = self._new_session_id()
        self._path = _session_dir(self.agent_id) / f"{self.session_id}.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self.turns = []
        self.created = _now_iso()
        self._write_meta_if_new()

    @classmethod
    def load(cls, agent_id: str, session_id: str) -> AgentSession:
        safe_session = safe_name(session_id)  # also protect the filename component
        path = _session_dir(agent_id) / f"{safe_session}.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"No session {session_id} for agent {agent_id}")

        session = cls.__new__(cls)
        session.agent_id = agent_id
        session.session_id = session_id
        session.title = "Untitled"
        session.created = _now_iso()
        session.turns = []
        session._path = path

        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("event") == "meta":
                    session.title = rec.get("title", "Untitled")
                    session.created = rec.get("created", _now_iso())
                elif rec.get("event") == "turn":
                    session.turns.append(
                        Turn(
                            role=rec.get("role", "user"),
                            content=rec.get("content", ""),
                            timestamp=rec.get("timestamp", _now_iso()),
                            metadata=rec.get("metadata", {}),
                        )
                    )
        return session

    @classmethod
    def list_sessions(cls, agent_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Return the most recent N sessions for an agent."""
        d = _session_dir(agent_id)
        if not d.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
            sid = path.stem
            title = sid
            created = ""
            n_turns = 0
            try:
                with path.open("r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            rec = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if rec.get("event") == "meta":
                            title = rec.get("title", title)
                            created = rec.get("created", "")
                        elif rec.get("event") == "turn":
                            n_turns += 1
            except OSError:
                continue
            rows.append(
                {
                    "session_id": sid,
                    "title": title,
                    "created": created,
                    "turns": n_turns,
                    "path": str(path),
                }
            )
            if len(rows) >= limit:
                break
        return rows

    @classmethod
    def latest_for_agent(cls, agent_id: str) -> AgentSession | None:
        listing = cls.list_sessions(agent_id, limit=1)
        if not listing:
            return None
        return cls.load(agent_id, listing[0]["session_id"])

    @property
    def path(self) -> Path:
        return self._path
