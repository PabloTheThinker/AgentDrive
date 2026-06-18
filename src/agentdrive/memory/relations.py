"""
Memory relation graph — time-bounded facts linked to Memory Bank entries.

Stores subject–predicate–object records with optional validity windows.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentdrive.drive.drive import get_swarm_drive_path


def _graph_path(swarm_id: str) -> Path:
    root = get_swarm_drive_path(swarm_id) / "memory_bank"
    root.mkdir(parents=True, exist_ok=True)
    return root / "relations.sqlite3"


@dataclass
class RelationRecord:
    relation_id: str
    subject: str
    predicate: str
    object: str
    valid_from: str | None = None
    valid_to: str | None = None
    memory_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "memory_id": self.memory_id,
        }


class MemoryRelationGraph:
    """Per-swarm SQLite relation store."""

    def __init__(self, swarm_id: str) -> None:
        self.swarm_id = swarm_id
        self.path = _graph_path(swarm_id)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS relations (
                    relation_id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    valid_from TEXT,
                    valid_to TEXT,
                    memory_id TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rel_subject ON relations(subject)")
            conn.commit()

    def record(
        self,
        subject: str,
        predicate: str,
        obj: str,
        *,
        valid_from: str | None = None,
        valid_to: str | None = None,
        memory_id: str | None = None,
    ) -> RelationRecord:
        relation_id = f"rel-{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO relations (
                    relation_id, subject, predicate, object,
                    valid_from, valid_to, memory_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relation_id,
                    subject.strip(),
                    predicate.strip(),
                    obj.strip(),
                    valid_from,
                    valid_to,
                    memory_id,
                    now,
                ),
            )
            conn.commit()
        return RelationRecord(
            relation_id=relation_id,
            subject=subject,
            predicate=predicate,
            object=obj,
            valid_from=valid_from,
            valid_to=valid_to,
            memory_id=memory_id,
        )

    def expire(
        self,
        subject: str,
        predicate: str,
        obj: str,
        *,
        ended: str | None = None,
    ) -> int:
        end = ended or datetime.now(UTC).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE relations SET valid_to = ?
                WHERE subject = ? AND predicate = ? AND object = ?
                  AND (valid_to IS NULL OR valid_to = '')
                """,
                (end, subject, predicate, obj),
            )
            conn.commit()
            return cursor.rowcount

    def query(
        self,
        entity: str,
        *,
        as_of: str | None = None,
        limit: int = 50,
    ) -> list[RelationRecord]:
        entity = entity.strip()
        sql = "SELECT * FROM relations WHERE (subject = ? OR object = ?)"
        params: list[Any] = [entity, entity]
        if as_of:
            sql += " AND (valid_from IS NULL OR valid_from <= ?)"
            sql += " AND (valid_to IS NULL OR valid_to = '' OR valid_to >= ?)"
            params.extend([as_of, as_of])
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        records: list[RelationRecord] = []
        with self._connect() as conn:
            for row in conn.execute(sql, params):
                records.append(
                    RelationRecord(
                        relation_id=row["relation_id"],
                        subject=row["subject"],
                        predicate=row["predicate"],
                        object=row["object"],
                        valid_from=row["valid_from"],
                        valid_to=row["valid_to"],
                        memory_id=row["memory_id"],
                    )
                )
        return records