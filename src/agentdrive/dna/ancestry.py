"""Ancestry closure table — the spine of AgentDrive's DNA inheritance.

Records the parent/child relationships between agents in a SQLite-backed
closure table so any descendant can find its ancestors (and any ancestor
can find its descendants) in O(1) per row.

**Schema**

```sql
CREATE TABLE agents (
  agent_id   TEXT PRIMARY KEY,
  created_at REAL NOT NULL          -- unix epoch; the cycle-prevention anchor
);

CREATE TABLE ancestor_closure (
  ancestor_id   TEXT NOT NULL,
  descendant_id TEXT NOT NULL,
  min_depth     INTEGER NOT NULL,    -- shortest path through the DAG
  PRIMARY KEY (ancestor_id, descendant_id),
  FOREIGN KEY (ancestor_id)   REFERENCES agents(agent_id),
  FOREIGN KEY (descendant_id) REFERENCES agents(agent_id)
);
CREATE INDEX idx_descendant ON ancestor_closure(descendant_id);
CREATE INDEX idx_ancestor   ON ancestor_closure(ancestor_id);
```

Every agent is its own ancestor at depth 0; this makes
``ancestors_of(agent_id)`` and ``descendants_of(agent_id)`` self-inclusive
unless explicitly filtered.

**Cycle prevention.** A new agent's parents must already exist in the
``agents`` table at the time the child is added. Combined with the
``created_at`` invariant (child's timestamp > parent's), this makes the
ancestry graph a DAG by construction. There is no online cycle check;
the constraint is enforced at write time and that's the whole story.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path


class AncestryClosureError(Exception):
    """Raised when an attempt would corrupt the closure table — e.g. adding
    a parent that doesn't exist, or re-adding an agent that already has
    different parents recorded."""


class NoSuchAgentError(KeyError):
    """Raised by walks that hit an agent_id not present in the table."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
  agent_id   TEXT PRIMARY KEY,
  created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS ancestor_closure (
  ancestor_id   TEXT NOT NULL,
  descendant_id TEXT NOT NULL,
  min_depth     INTEGER NOT NULL,
  PRIMARY KEY (ancestor_id, descendant_id)
);

CREATE INDEX IF NOT EXISTS idx_descendant ON ancestor_closure(descendant_id);
CREATE INDEX IF NOT EXISTS idx_ancestor   ON ancestor_closure(ancestor_id);
"""


class Ancestry:
    """Closure-table-backed ancestry graph for AgentDrive's DNA inheritance.

    Cheap to instantiate (no I/O until first read/write). Thread-safe via
    an internal lock — SQLite itself serializes writes, the lock is there
    to make the read-modify-write of closure entries atomic.

    The default DB path is ``<agentdrive_home>/dna/_ancestry.db``; tests
    inject their own path.
    """

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript(_SCHEMA)

    # ── write path ──────────────────────────────────────────────────────────

    def add_agent(
        self,
        agent_id: str,
        parents: Iterable[str] | None = None,
        created_at: float | None = None,
    ) -> None:
        """Record a new agent with its direct parents.

        ``parents`` defaults to none (a root agent — typical for the very
        first agent in a tree). Every parent must already exist. The
        closure table is updated transitively: the new agent inherits an
        edge to every one of its parents' ancestors, with ``min_depth``
        being the shortest path through the DAG.

        Idempotent: re-adding the same agent with the same parents is a
        no-op. Re-adding the same agent with *different* parents raises
        ``AncestryClosureError`` — ancestry is immutable once recorded.
        """
        parents = list(parents or [])
        ts = created_at if created_at is not None else time.time()

        with self._lock, self._conn() as c:
            existing = c.execute(
                "SELECT created_at FROM agents WHERE agent_id = ?", (agent_id,)
            ).fetchone()

            if existing is not None:
                # Idempotent check: existing parents must match.
                existing_parents = [
                    r["ancestor_id"]
                    for r in c.execute(
                        "SELECT ancestor_id FROM ancestor_closure "
                        "WHERE descendant_id = ? AND min_depth = 1",
                        (agent_id,),
                    )
                ]
                if sorted(existing_parents) != sorted(parents):
                    raise AncestryClosureError(
                        f"agent {agent_id!r} already exists with different parents: "
                        f"existing={sorted(existing_parents)} new={sorted(parents)}"
                    )
                return  # idempotent no-op

            # Validate every claimed parent exists AND was created before this child.
            for pid in parents:
                row = c.execute(
                    "SELECT created_at FROM agents WHERE agent_id = ?", (pid,)
                ).fetchone()
                if row is None:
                    raise AncestryClosureError(
                        f"agent {agent_id!r} claims parent {pid!r} which does not exist"
                    )
                if row["created_at"] >= ts:
                    raise AncestryClosureError(
                        f"agent {agent_id!r} (t={ts}) cannot claim parent {pid!r} "
                        f"(t={row['created_at']}) — child must be younger than parent"
                    )

            c.execute(
                "INSERT INTO agents(agent_id, created_at) VALUES (?, ?)",
                (agent_id, ts),
            )

            # Self-edge: every agent is its own ancestor at depth 0.
            c.execute(
                "INSERT INTO ancestor_closure(ancestor_id, descendant_id, min_depth) "
                "VALUES (?, ?, 0)",
                (agent_id, agent_id),
            )

            # For each parent, copy that parent's ancestor set (including
            # the parent itself) into this child's row, incrementing depth.
            # If multiple parents share an ancestor, keep the SHORTER path.
            for pid in parents:
                rows = c.execute(
                    "SELECT ancestor_id, min_depth FROM ancestor_closure WHERE descendant_id = ?",
                    (pid,),
                ).fetchall()
                for r in rows:
                    new_depth = r["min_depth"] + 1
                    c.execute(
                        """
                        INSERT INTO ancestor_closure(ancestor_id, descendant_id, min_depth)
                        VALUES (?, ?, ?)
                        ON CONFLICT(ancestor_id, descendant_id) DO UPDATE
                          SET min_depth = MIN(min_depth, excluded.min_depth)
                        """,
                        (r["ancestor_id"], agent_id, new_depth),
                    )

    # ── read path ───────────────────────────────────────────────────────────

    def has_agent(self, agent_id: str) -> bool:
        with self._conn() as c:
            return (
                c.execute("SELECT 1 FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
                is not None
            )

    def ancestors_of(
        self,
        agent_id: str,
        *,
        max_depth: int | None = None,
        include_self: bool = False,
    ) -> list[tuple[str, int]]:
        """Return ``[(ancestor_id, depth), ...]`` for ``agent_id``.

        Includes the agent itself at depth 0 only if ``include_self=True``.
        Sorted by depth ascending — closest ancestors first, the order a
        DNA pull wants for relevance.
        """
        if not self.has_agent(agent_id):
            raise NoSuchAgentError(agent_id)

        params: list = [agent_id]
        depth_clause = "" if max_depth is None else "AND min_depth <= ?"
        if max_depth is not None:
            params.append(max_depth)
        self_clause = "" if include_self else "AND min_depth > 0"

        with self._conn() as c:
            rows = c.execute(
                f"""
                SELECT ancestor_id, min_depth
                FROM ancestor_closure
                WHERE descendant_id = ?
                  {self_clause}
                  {depth_clause}
                ORDER BY min_depth ASC, ancestor_id ASC
                """,
                params,
            ).fetchall()
        return [(r["ancestor_id"], r["min_depth"]) for r in rows]

    def descendants_of(
        self,
        agent_id: str,
        *,
        max_depth: int | None = None,
        include_self: bool = False,
    ) -> list[tuple[str, int]]:
        """Return ``[(descendant_id, depth), ...]``. Inverse of
        ``ancestors_of`` — used to enumerate who would inherit from a
        given ancestor."""
        if not self.has_agent(agent_id):
            raise NoSuchAgentError(agent_id)

        params: list = [agent_id]
        depth_clause = "" if max_depth is None else "AND min_depth <= ?"
        if max_depth is not None:
            params.append(max_depth)
        self_clause = "" if include_self else "AND min_depth > 0"

        with self._conn() as c:
            rows = c.execute(
                f"""
                SELECT descendant_id, min_depth
                FROM ancestor_closure
                WHERE ancestor_id = ?
                  {self_clause}
                  {depth_clause}
                ORDER BY min_depth ASC, descendant_id ASC
                """,
                params,
            ).fetchall()
        return [(r["descendant_id"], r["min_depth"]) for r in rows]

    def parents_of(self, agent_id: str) -> list[str]:
        """Direct parents (depth=1) only."""
        return [aid for aid, _ in self.ancestors_of(agent_id, max_depth=1) if _ == 1]

    def all_agents(self) -> list[str]:
        with self._conn() as c:
            return [
                r["agent_id"]
                for r in c.execute("SELECT agent_id FROM agents ORDER BY created_at ASC")
            ]
