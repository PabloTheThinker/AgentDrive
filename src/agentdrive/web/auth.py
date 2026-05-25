"""SQLite auth/session store for the AgentDrive web UI."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

from agentdrive.constants import get_agentdrive_home

SESSION_DAYS = 7
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.@-]{3,80}$")


@dataclass(frozen=True)
class User:
    id: int
    username: str
    role: str
    disabled: bool = False


def default_db_path() -> Path:
    return get_agentdrive_home() / "auth.db"


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    salt = secrets.token_bytes(16)
    kdf = Argon2id(salt=salt, length=32, iterations=3, lanes=4, memory_cost=64 * 1024)
    return kdf.derive_phc_encoded(password.encode("utf-8"))


def verify_password(password: str, password_hash: str) -> bool:
    try:
        Argon2id.verify_phc_encoded(password.encode("utf-8"), password_hash)
        return True
    except (InvalidKey, ValueError):
        return False


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_token() -> str:
    raw = secrets.token_bytes(32)
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class AuthStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        from agentdrive.db_pragmas import apply_pragmas

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        apply_pragmas(conn)
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'user', 'pending')),
                    disabled INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    approved_at TEXT
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                );
                """
            )

    def bootstrap_from_env(self) -> User | None:
        if self.has_users():
            return None
        username = os.environ.get("AGENTDRIVE_ADMIN_USERNAME", "").strip()
        password_file = os.environ.get("AGENTDRIVE_ADMIN_PASSWORD_FILE", "").strip()
        if not username or not password_file:
            return None
        password = Path(password_file).read_text(encoding="utf-8").strip()
        return self.create_user(username, password, role="admin")

    def has_users(self) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT 1 FROM users LIMIT 1").fetchone()
            return row is not None

    def count_users(self) -> int:
        with self.connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    def create_user(self, username: str, password: str, role: str = "pending") -> User:
        username = username.strip()
        if not USERNAME_RE.fullmatch(username):
            raise ValueError("username must be 3-80 chars: letters, numbers, _, ., @, -")
        if role not in {"admin", "user", "pending"}:
            raise ValueError("invalid role")
        password_hash = hash_password(password)
        now = utcnow()
        approved_at = iso(now) if role in {"admin", "user"} else None
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO users (username, password_hash, role, disabled, created_at, approved_at)
                VALUES (?, ?, ?, 0, ?, ?)
                """,
                (username, password_hash, role, iso(now), approved_at),
            )
            uid = int(cur.lastrowid)
        return User(id=uid, username=username, role=role)

    def get_user(self, user_id: int) -> User | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id, username, role, disabled FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return self._row_to_user(row)

    def get_user_by_username(self, username: str) -> User | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id, username, role, disabled FROM users WHERE username = ?",
                (username.strip(),),
            ).fetchone()
        return self._row_to_user(row)

    def authenticate(self, username: str, password: str) -> User | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, username, password_hash, role, disabled
                FROM users WHERE username = ?
                """,
                (username.strip(),),
            ).fetchone()
        if row is None or bool(row["disabled"]):
            return None
        if row["role"] == "pending":
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        return User(id=int(row["id"]), username=str(row["username"]), role=str(row["role"]))

    def create_session(self, user_id: int) -> str:
        token = constant_time_token()
        now = utcnow()
        expires = now + timedelta(days=SESSION_DAYS)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (token_hash, user_id, created_at, expires_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (hash_session_token(token), user_id, iso(now), iso(expires), iso(now)),
            )
        return token

    def user_for_session(self, token: str | None) -> User | None:
        if not token:
            return None
        token_hash = hash_session_token(token)
        now = utcnow()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT s.expires_at, u.id, u.username, u.role, u.disabled
                FROM sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if row is None:
                return None
            if (
                parse_iso(row["expires_at"]) <= now
                or bool(row["disabled"])
                or row["role"] == "pending"
            ):
                conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
                return None
            conn.execute(
                """
                UPDATE sessions
                SET last_seen_at = ?, expires_at = ?
                WHERE token_hash = ?
                """,
                (iso(now), iso(now + timedelta(days=SESSION_DAYS)), token_hash),
            )
        return User(id=int(row["id"]), username=str(row["username"]), role=str(row["role"]))

    def delete_session(self, token: str | None) -> None:
        if not token:
            return
        with self.connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_session_token(token),))

    def list_users(self) -> list[User]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, username, role, disabled FROM users ORDER BY id"
            ).fetchall()
        return [u for row in rows if (u := self._row_to_user(row)) is not None]

    def approve_user(self, user_id: int) -> User | None:
        now = iso(utcnow())
        with self.connect() as conn:
            conn.execute(
                "UPDATE users SET role = 'user', approved_at = ? WHERE id = ? AND role = 'pending'",
                (now, user_id),
            )
        return self.get_user(user_id)

    @staticmethod
    def _row_to_user(row: sqlite3.Row | None) -> User | None:
        if row is None:
            return None
        return User(
            id=int(row["id"]),
            username=str(row["username"]),
            role=str(row["role"]),
            disabled=bool(row["disabled"]),
        )


def is_signup_disabled() -> bool:
    value = os.environ.get("AGENTDRIVE_DISABLE_SIGNUP", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def secure_cookie_enabled() -> bool:
    value = os.environ.get("AGENTDRIVE_SECURE_COOKIES", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def compare_csrf(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
