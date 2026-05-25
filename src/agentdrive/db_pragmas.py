"""Shared SQLite pragma policy for every connection AgentDrive opens.

Single source of truth so a code review can verify every ``sqlite3.connect``
site goes through the same WAL / synchronous / busy_timeout choices.

Imported from ``agentdrive.web.auth``, ``agentdrive.cap.store``,
``agentdrive.dna.ancestry``, ``agentdrive.dna.grants``.
"""

from __future__ import annotations

import sqlite3


def apply_pragmas(conn: sqlite3.Connection) -> None:
    """Configure a fresh sqlite3 connection for safe concurrent use.

    - **WAL** lets reads proceed alongside a writer without blocking
      (critical when the FastAPI threadpool fans out concurrent handlers).
    - **synchronous=NORMAL** trades a tiny crash-window for ~5x write
      throughput. Acceptable: AgentDrive snapshots cover catastrophic loss.
    - **busy_timeout=5000ms** keeps "database is locked" errors away
      during a contended checkpoint.
    - **foreign_keys=ON** so cascade deletes work as documented.
    """
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
