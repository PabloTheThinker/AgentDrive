"""Per-request capability enforcement for the AgentDrive web daemon.

Two principals can talk to a mutating route:

1. **The operator** — the human logged into the browser. They hold an
   admin session cookie. Treat that as an implicit owner capability
   (``*:*:*``) — they're the root authority on this machine.
2. **A non-browser agent** — anything calling the API directly (an SDK,
   a sub-agent, an external orchestrator). They have NO session cookie
   and instead present an Ed25519-signed capability via:

       Authorization: Bearer <cap_id>

   The ``cap_id`` is the UUID returned by ``CapStore.mint()``. The store
   looks up the signed cap and runs ``verify_request`` against the
   route's ``CapVerifyContext`` (resource + action + scope). Deny on any
   mismatch — narrower-than rules in ``cap.uri`` already handle subset
   matching.

Every check — allow or deny, both — is appended to an audit log at
``~/.agentdrive/audit.log`` (JSONL). Operators can ``tail`` it. Failures
to write the log do not break the request; we log the failure to stdout
and move on.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request, status

from agentdrive.cap.store import CapInvalidError, CapStore
from agentdrive.cap.store import CapVerifyContext as RawCapContext
from agentdrive.constants import get_agentdrive_home
from agentdrive.web.auth import User

_logger = logging.getLogger("agentdrive.web.authz")


@dataclass(frozen=True)
class RouteCap:
    """The cap a particular route requires.

    The route handler declares the four-tuple (scheme, action,
    resource_kind, resource_id). We rebuild ``CapVerifyContext`` per
    request because the resource_id can be path-derived (e.g. the
    ``{agent_id}`` in ``/snapshots/{agent_id}/{snapshot_id}/pin``).
    """

    scheme: str
    action: str
    resource_kind: str
    resource_id: str

    def context(self) -> RawCapContext:
        return RawCapContext(
            scheme=self.scheme,
            action=self.action,
            resource_kind=self.resource_kind,
            resource_id=self.resource_id,
        )


# ── audit log ─────────────────────────────────────────────────────────


def _audit_path() -> Path:
    return get_agentdrive_home() / "audit.log"


def _append_audit(record: dict[str, Any]) -> None:
    """Best-effort write to the audit JSONL. Failures don't break the
    request — they're logged to stdout so an operator can see the
    backlog grow if the disk fills.
    """
    record = {"ts": time.time(), **record}
    try:
        path = _audit_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, separators=(",", ":")) + "\n")
    except Exception:  # pragma: no cover
        from agentdrive.utils.log_safe import safe_for_log

        _logger.exception("audit_log_write_failed", extra={"record": safe_for_log(record)})


# ── cap resolution helpers ────────────────────────────────────────────


def _shared_cap_store() -> CapStore:
    db_path = get_agentdrive_home() / "caps.db"
    return CapStore(db_path=db_path)


def _bearer_cap_id(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("bearer "):
        return None
    token = header.split(" ", 1)[1].strip()
    return token or None


# ── the dependency factory ────────────────────────────────────────────


def require_cap(
    scheme: str,
    action: str,
    *,
    resource_kind: str = "agent",
    resource_id: str = "personal",
    resource_id_arg: str | None = None,
):
    """Build a FastAPI dependency that enforces a capability for a route.

    Usage::

        @app.post("/personal/import")
        def import_genome(
            request: Request,
            ...,
            user: User = Depends(require_user),
            authz = Depends(require_cap("drive", "write", resource_kind="personal")),
        ):
            ...

    Resolution order on each request:

    1. **Admin session** — if the logged-in user has ``role == "admin"``,
       allow and audit with principal ``user:<username>``.
    2. **Bearer cap** — if there is an ``Authorization: Bearer <cap_id>``
       header, resolve the cap, verify against the route's
       ``CapVerifyContext``; allow + audit on success, 403 + audit on
       fail.
    3. **Anything else** — 403 + audit.

    ``resource_id_arg`` lets a route override the cap's
    ``resource_id`` from a path variable (e.g. ``"agent_id"``). When
    unset, the route's default ``resource_kind`` is used as the id.
    """

    def _dep(request: Request):
        # Resolve the route's expected cap from the request path/path-params.
        rid = request.path_params.get(resource_id_arg) if resource_id_arg else None
        route_cap = RouteCap(
            scheme=scheme,
            action=action,
            resource_kind=resource_kind,
            resource_id=rid or resource_id,
        )
        request_id = getattr(request.state, "request_id", None)

        # Principal 1: admin session.
        user: User | None = getattr(request.state, "user", None)
        if user is None:
            # require_user hasn't necessarily populated request.state yet;
            # fall back to the auth store via the cookie.
            user = _resolve_session_user(request)
        if user is not None and user.role == "admin":
            _append_audit(
                {
                    "decision": "allow",
                    "reason": "admin_session",
                    "principal": f"user:{user.username}",
                    "scheme": scheme,
                    "action": action,
                    "resource_kind": resource_kind,
                    "resource_id": route_cap.resource_id,
                    "request_id": request_id,
                    "path": request.url.path,
                }
            )
            return route_cap

        # Principal 2: bearer cap.
        cap_id = _bearer_cap_id(request)
        if cap_id:
            try:
                store = _shared_cap_store()
                signed = store.get(cap_id)
                store.verify_request(signed, route_cap.context())
            except (CapInvalidError, Exception) as exc:  # noqa: BLE001
                _append_audit(
                    {
                        "decision": "deny",
                        "reason": exc.__class__.__name__,
                        "principal": f"cap:{cap_id[:8]}",
                        "scheme": scheme,
                        "action": action,
                        "resource_kind": resource_kind,
                        "resource_id": route_cap.resource_id,
                        "request_id": request_id,
                        "path": request.url.path,
                    }
                )
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cap_denied")
            _append_audit(
                {
                    "decision": "allow",
                    "reason": "bearer_cap",
                    "principal": f"cap:{cap_id[:8]}",
                    "scheme": scheme,
                    "action": action,
                    "resource_kind": resource_kind,
                    "resource_id": route_cap.resource_id,
                    "request_id": request_id,
                    "path": request.url.path,
                }
            )
            return route_cap

        # No principal at all.
        _append_audit(
            {
                "decision": "deny",
                "reason": "no_principal",
                "principal": "anonymous",
                "scheme": scheme,
                "action": action,
                "resource_kind": resource_kind,
                "resource_id": route_cap.resource_id,
                "request_id": request_id,
                "path": request.url.path,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication_required"
        )

    return _dep


def _resolve_session_user(request: Request) -> User | None:
    """Fallback: look up the user from the session cookie + AuthStore on
    app.state. Used when ``require_user`` hasn't run yet (because the
    cap dependency is the outermost auth layer for SDK callers).
    """
    try:
        store = request.app.state.auth_store
        cookie = request.cookies.get("agentdrive_session")
        if not cookie:
            return None
        return store.user_for_session(cookie)
    except Exception:  # pragma: no cover
        return None
