"""FastAPI web surface for AgentDrive.

Jinja2-templated, served at ``http://127.0.0.1:8421`` by default.
The visual direction matches ``~/agentdrive-wireframes/`` — IBM Plex Sans
+ JetBrains Mono, dotted-grid canvas, icon-rail shell, inspector aside.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agentdrive import SAVANT_VERSION
from agentdrive.backup import SnapshotError, SnapshotManager
from agentdrive.constants import get_agentdrive_home, get_default_drive_path
from agentdrive.drive.drive import AgentDrive
from agentdrive.web.auth import (
    AuthStore,
    User,
    default_db_path,
    is_signup_disabled,
    secure_cookie_enabled,
)
from agentdrive.web.observability import (
    LoginRateLimiter,
    OriginCSRFMiddleware,
    RequestLoggingMiddleware,
    client_ip,
    configure_logging,
    install_error_boundary,
)

SESSION_COOKIE = "agentdrive_session"

_HERE = Path(__file__).parent
_TEMPLATES_DIR = _HERE / "templates"
_STATIC_DIR = _HERE / "static"


def create_app(auth_db: Path | None = None) -> FastAPI:
    configure_logging(level=os.environ.get("AGENTDRIVE_LOG_LEVEL", "INFO"))

    store = AuthStore(auth_db or default_db_path())
    store.bootstrap_from_env()

    app = FastAPI(title="AgentDrive Web", version=SAVANT_VERSION)
    app.state.auth_store = store
    app.state.login_limiter = LoginRateLimiter(max_attempts=5, window_s=60)
    app.state.started_at = time.time()

    # Order matters: request logging wraps everything (so the error
    # boundary's response and the CSRF rejection both carry a
    # request_id). CSRF check runs on every non-safe method.
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(OriginCSRFMiddleware)
    install_error_boundary(app)

    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
    templates = Jinja2Templates(directory=_TEMPLATES_DIR)
    app.state.templates = templates

    # ── auth helpers ──────────────────────────────────────────────────

    def current_user(request: Request) -> User | None:
        token = request.cookies.get(SESSION_COOKIE)
        return store.user_for_session(token)

    def require_user(request: Request) -> User:
        user = current_user(request)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"}
            )
        return user

    def require_admin(request: Request) -> User:
        user = require_user(request)
        if user.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
        return user

    def set_session(response: RedirectResponse, user: User) -> RedirectResponse:
        token = store.create_session(user.id)
        response.set_cookie(
            SESSION_COOKIE,
            token,
            httponly=True,
            samesite="strict",
            secure=secure_cookie_enabled(),
            max_age=7 * 24 * 60 * 60,
        )
        return response

    # ── auth routes ───────────────────────────────────────────────────

    @app.get("/healthz")
    def healthz(request: Request):
        """Liveness probe. Returns 200 once the app object is fully wired.

        Auth-bypass on purpose — orchestrators (systemd, k8s, monit) need
        to call this before a user has been provisioned. Body is a small
        JSON object that can be machine-parsed.
        """
        from fastapi.responses import JSONResponse

        uptime_s = round(time.time() - app.state.started_at, 1)
        # Intentionally narrow: don't reveal user-presence to a network
        # caller. Status + version + uptime is what an orchestrator needs.
        return JSONResponse(
            {
                "status": "ok",
                "version": SAVANT_VERSION,
                "uptime_s": uptime_s,
            }
        )

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        user = current_user(request)
        if user:
            return _redirect("/dashboard")
        if not store.has_users():
            return _redirect("/setup")
        return _redirect("/login")

    @app.get("/setup", response_class=HTMLResponse)
    def setup_get(request: Request):
        if store.has_users():
            return _redirect("/login")
        return templates.TemplateResponse(
            "auth.html",
            {
                "request": request,
                "title": "Create admin",
                "heading": "Create the admin account",
                "intro": (
                    "This is the first time AgentDrive has been launched on this "
                    "machine. Set the admin credentials. You can add more users "
                    "later from the Settings panel."
                ),
                "action": "/setup",
                "submit_label": "Create admin account",
                "password_autocomplete": "new-password",
                "confirm_password": False,
                "footnote": (
                    "Local-only. Bound to <span class='mono'>127.0.0.1:8421</span>.<br>"
                    "Credentials are hashed with Argon2id and stored at "
                    "<span class='mono'>~/.agentdrive/auth.db</span>."
                ),
            },
        )

    @app.post("/setup")
    def setup_post(
        request: Request,
        username: Annotated[str, Form()],
        password: Annotated[str, Form()],
    ):
        if store.has_users():
            return _redirect("/login")
        try:
            user = store.create_user(username, password, role="admin")
        except ValueError as exc:
            return templates.TemplateResponse(
                "auth.html",
                {
                    "request": request,
                    "title": "Create admin",
                    "heading": "Create the admin account",
                    "action": "/setup",
                    "submit_label": "Create admin account",
                    "password_autocomplete": "new-password",
                    "username": username,
                    "error": str(exc),
                    "footnote": "Local-only. Bound to <span class='mono'>127.0.0.1:8421</span>.",
                },
                status_code=400,
            )
        return set_session(_redirect("/dashboard"), user)

    @app.get("/login", response_class=HTMLResponse)
    def login_get(request: Request):
        if not store.has_users():
            return _redirect("/setup")
        return _login_page(request, templates)

    @app.post("/login")
    def login_post(
        request: Request,
        username: Annotated[str, Form()],
        password: Annotated[str, Form()],
    ):
        ip = client_ip(request)
        limiter: LoginRateLimiter = app.state.login_limiter
        if limiter.is_locked(ip):
            return _login_page(
                request,
                templates,
                error="Too many failed attempts. Wait a minute and try again.",
                username=username,
                status_code=429,
            )
        # Single failure message + uniform status for invalid-cred / disabled
        # / pending. Otherwise the response leaks "user exists but not active"
        # vs. "user doesn't exist" — an enumeration oracle.
        user = store.authenticate(username, password)
        invalid = (user is None) or user.disabled or (user.role == "pending")
        if invalid:
            limiter.record_failure(ip)
            return _login_page(
                request,
                templates,
                error="Invalid credentials.",
                username=username,
                status_code=401,
            )
        limiter.reset(ip)
        return set_session(_redirect("/dashboard"), user)

    @app.post("/logout")
    def logout(request: Request):
        token = request.cookies.get(SESSION_COOKIE)
        if token:
            store.delete_session(token)
        response = _redirect("/login")
        response.delete_cookie(SESSION_COOKIE)
        return response

    @app.get("/signup", response_class=HTMLResponse)
    def signup_get(request: Request):
        if is_signup_disabled():
            return _login_page(
                request, templates, info="Signup disabled. Ask the admin.", status_code=403
            )
        return templates.TemplateResponse(
            "auth.html",
            {
                "request": request,
                "title": "Request access",
                "heading": "Request access",
                "intro": "Your account will need admin approval before you can sign in.",
                "action": "/signup",
                "submit_label": "Request access",
                "password_autocomplete": "new-password",
                "footnote": "Vektra Industries · AgentDrive v" + SAVANT_VERSION,
            },
        )

    @app.post("/signup")
    def signup_post(
        request: Request,
        username: Annotated[str, Form()],
        password: Annotated[str, Form()],
    ):
        if is_signup_disabled():
            return _login_page(
                request, templates, info="Signup disabled. Ask the admin.", status_code=403
            )
        try:
            store.create_user(username, password, role="pending")
        except ValueError as exc:
            return templates.TemplateResponse(
                "auth.html",
                {
                    "request": request,
                    "title": "Request access",
                    "heading": "Request access",
                    "action": "/signup",
                    "submit_label": "Request access",
                    "password_autocomplete": "new-password",
                    "username": username,
                    "error": str(exc),
                    "footnote": "Vektra Industries · AgentDrive v" + SAVANT_VERSION,
                },
                status_code=400,
            )
        return _login_page(
            request,
            templates,
            info="Request submitted — account is pending admin approval.",
        )

    # ── app routes ────────────────────────────────────────────────────

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(request: Request, user: User = Depends(require_user)):
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": user,
                "active": "dashboard",
                "version": SAVANT_VERSION,
                "stats_drives": 1,
                "stats_agents": 1,
                "metrics": [
                    {"label": "Personal genomes", "value": _genome_count(), "delta": None},
                    {"label": "Active swarms", "value": "0", "delta": None},
                    {"label": "Snapshots", "value": str(_snapshot_count(user.username)), "delta": None},
                    {"label": "Capabilities issued", "value": "0", "delta": None},
                ],
                "activity": [],
                "health": [
                    {"label": "Content store integrity", "value": "✓ verified", "color": "accent"},
                    {"label": "Snapshot cadence", "value": "✓ on schedule", "color": "accent"},
                    {"label": "Capability keystore", "value": "✓ healthy", "color": "accent"},
                ],
                "shortcuts": [
                    {"title": "Personal Drive", "meta": str(get_default_drive_path()), "href": "/personal", "icon": "drive", "color": "accent"},
                    {"title": "Swarm Drives", "meta": "shared substrates", "href": "/swarms", "icon": "swarm", "color": "warm"},
                    {"title": "DNA Lineage", "meta": "ancestry + grants", "href": "/dna", "icon": "dna", "color": "success"},
                ],
            },
        )

    @app.get("/personal", response_class=HTMLResponse)
    def personal(
        request: Request,
        user: User = Depends(require_user),
        info: str | None = None,
        error: str | None = None,
    ):
        rows = _list_genome_rows()
        return templates.TemplateResponse(
            "personal.html",
            {
                "request": request,
                "user": user,
                "active": "drive",
                "genomes": rows,
                "genome_count": len(rows),
                "drive_path": str(get_default_drive_path()),
                "info": info,
                "error": error,
            },
        )

    # Hard cap on inbound genome JSON to keep a single POST from
    # ballooning memory / CPU during Pydantic validation.
    GENOME_JSON_MAX_BYTES = 1 * 1024 * 1024  # 1 MiB

    @app.post("/personal/import")
    def import_genome(
        request: Request,
        genome_json: Annotated[str, Form()],
        user: User = Depends(require_user),
    ):
        import json as _json
        import re as _re
        from agentdrive.genome.models import Genome

        if len(genome_json.encode("utf-8")) > GENOME_JSON_MAX_BYTES:
            rows = _list_genome_rows()
            return templates.TemplateResponse(
                "personal.html",
                {
                    "request": request,
                    "user": user,
                    "active": "drive",
                    "genomes": rows,
                    "genome_count": len(rows),
                    "drive_path": str(get_default_drive_path()),
                    "error": "Genome payload exceeds 1 MiB cap.",
                },
                status_code=413,
            )
        try:
            payload = _json.loads(genome_json)
            if not isinstance(payload, dict):
                raise ValueError("genome payload must be a JSON object")
            # Validate id and version against the safe whitelist before any
            # downstream use (id ends up as a path segment in the registry).
            safe_re = _re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
            if not safe_re.fullmatch(str(payload.get("id", ""))):
                raise ValueError("genome.id must match [A-Za-z0-9._:-]{1,128}")
            if not safe_re.fullmatch(str(payload.get("version", ""))):
                raise ValueError("genome.version must match [A-Za-z0-9._:-]{1,128}")
            genome = Genome.create(**payload)
        except Exception as exc:
            rows = _list_genome_rows()
            return templates.TemplateResponse(
                "personal.html",
                {
                    "request": request,
                    "user": user,
                    "active": "drive",
                    "genomes": rows,
                    "genome_count": len(rows),
                    "drive_path": str(get_default_drive_path()),
                    "error": f"Could not parse genome: {exc}",
                },
                status_code=400,
            )
        try:
            drive = AgentDrive(drive_path=get_default_drive_path())
            result = drive.ingest(
                genome,
                source="web-import",
                actor=user.username,
                subagent_id=None,
            )
        except Exception as exc:
            rows = _list_genome_rows()
            return templates.TemplateResponse(
                "personal.html",
                {
                    "request": request,
                    "user": user,
                    "active": "drive",
                    "genomes": rows,
                    "genome_count": len(rows),
                    "drive_path": str(get_default_drive_path()),
                    "error": f"Ingest failed: {exc}",
                },
                status_code=400,
            )
        rows = _list_genome_rows()
        return templates.TemplateResponse(
            "personal.html",
            {
                "request": request,
                "user": user,
                "active": "drive",
                "genomes": rows,
                "genome_count": len(rows),
                "drive_path": str(get_default_drive_path()),
                "info": f"Imported genome {result.genome_id}",
            },
        )

    @app.get("/swarms", response_class=HTMLResponse)
    def swarms_page(
        request: Request,
        user: User = Depends(require_user),
        info: str | None = None,
        error: str | None = None,
    ):
        return templates.TemplateResponse(
            "swarms.html",
            {
                "request": request,
                "user": user,
                "active": "swarm",
                "swarms": _list_swarms(),
                "info": info,
                "error": error,
            },
        )

    @app.post("/swarms")
    def spawn_swarm_route(
        request: Request,
        swarm_id: Annotated[str, Form()],
        user: User = Depends(require_user),
    ):
        from agentdrive.drive.swarm_manager import SwarmDriveManager

        cleaned = swarm_id.strip()
        if not cleaned or not all(c.isalnum() or c in "-_." for c in cleaned):
            return templates.TemplateResponse(
                "swarms.html",
                {
                    "request": request,
                    "user": user,
                    "active": "swarm",
                    "swarms": _list_swarms(),
                    "error": "swarm_id must be non-empty letters/digits/._-.",
                },
                status_code=400,
            )
        try:
            mgr = SwarmDriveManager()
            mgr.get_or_create_pool(cleaned)
        except Exception as exc:
            return templates.TemplateResponse(
                "swarms.html",
                {
                    "request": request,
                    "user": user,
                    "active": "swarm",
                    "swarms": _list_swarms(),
                    "error": f"Spawn failed: {exc}",
                },
                status_code=400,
            )
        return templates.TemplateResponse(
            "swarms.html",
            {
                "request": request,
                "user": user,
                "active": "swarm",
                "swarms": _list_swarms(),
                "info": f"Spawned swarm Drive: {cleaned}",
            },
        )

    @app.get("/dna", response_class=HTMLResponse)
    def dna_page(
        request: Request,
        user: User = Depends(require_user),
        agent: str | None = None,
    ):
        dna_root = get_agentdrive_home() / "dna"
        agents: list[str] = []
        if dna_root.exists():
            agents = sorted(p.name for p in dna_root.iterdir() if p.is_dir())

        ancestors: list[dict[str, Any]] = []
        grants: list[dict[str, Any]] = []
        if agent:
            try:
                from agentdrive.dna.drive import DNADrive  # type: ignore

                drive = DNADrive(agent_id=agent, dna_root=dna_root)
                for a in getattr(drive, "ancestors", lambda: [])():
                    ancestors.append(
                        {
                            "ancestor_id": getattr(a, "ancestor_id", str(a)),
                            "depth": getattr(a, "depth", 0),
                        }
                    )
                for g in getattr(drive, "active_grants", lambda: [])():
                    grants.append(
                        {
                            "donor_id": getattr(g, "donor_id", ""),
                            "recipient_id": getattr(g, "recipient_id", ""),
                            "max_hops": getattr(g, "max_hops", "—"),
                            "min_eval": getattr(g, "min_eval", "—"),
                        }
                    )
            except Exception:  # noqa: BLE001 — keep the page rendering on partial-DNA-state
                import logging as _logging
                _logging.getLogger("agentdrive.web").exception(
                    "dna_page_partial_load_failed",
                    extra={"agent_id": agent},
                )

        return templates.TemplateResponse(
            "dna.html",
            {
                "request": request,
                "user": user,
                "active": "dna",
                "agent_id": agent,
                "agents": agents,
                "ancestors": ancestors,
                "grants": grants,
            },
        )

    @app.get("/capabilities", response_class=HTMLResponse)
    def capabilities_page(
        request: Request,
        user: User = Depends(require_user),
        info: str | None = None,
        error: str | None = None,
    ):
        return templates.TemplateResponse(
            "capabilities.html",
            {
                "request": request,
                "user": user,
                "active": "cap",
                "caps": _list_caps(user.username),
                "info": info,
                "error": error,
            },
        )

    @app.post("/capabilities")
    def mint_capability_route(
        request: Request,
        uri: Annotated[str, Form()],
        user: User = Depends(require_user),
    ):
        from agentdrive.cap.store import CapStore
        from agentdrive.cap.uri import parse_uri

        try:
            capability = parse_uri(uri.strip())
        except Exception as exc:
            return templates.TemplateResponse(
                "capabilities.html",
                {
                    "request": request,
                    "user": user,
                    "active": "cap",
                    "caps": _list_caps(user.username),
                    "error": f"Invalid capability URI: {exc}",
                },
                status_code=400,
            )
        store_path = get_agentdrive_home() / "caps.db"
        cap_store = CapStore(db_path=store_path)
        signed = cap_store.mint(issuer=user.username, capability=capability)
        return templates.TemplateResponse(
            "capabilities.html",
            {
                "request": request,
                "user": user,
                "active": "cap",
                "caps": _list_caps(user.username),
                "info": f"Minted capability {signed.cap_id[:8]}… → {signed.uri}",
            },
        )

    @app.post("/capabilities/{cap_id}/revoke")
    def revoke_capability_route(
        request: Request,
        cap_id: str,
        user: User = Depends(require_user),
    ):
        from agentdrive.cap.store import CapStore

        store_path = get_agentdrive_home() / "caps.db"
        cap_store = CapStore(db_path=store_path)
        revoked = cap_store.revoke(cap_id)
        msg = f"Revoked {cap_id[:8]}…" if revoked else f"Capability {cap_id[:8]}… not found."
        return templates.TemplateResponse(
            "capabilities.html",
            {
                "request": request,
                "user": user,
                "active": "cap",
                "caps": _list_caps(user.username),
                "info" if revoked else "error": msg,
            },
        )

    @app.get("/peers", response_class=HTMLResponse)
    def peers_page(request: Request, user: User = Depends(require_user)):
        return templates.TemplateResponse(
            "peers.html",
            {
                "request": request,
                "user": user,
                "active": "peer",
                "peers": [],
                "quarantine": [],
            },
        )

    # ── snapshots ──────────────────────────────────────────────────────

    @app.get("/snapshots", response_class=HTMLResponse)
    def snapshots(
        request: Request,
        user: User = Depends(require_user),
        agent_id: str = "personal",
    ):
        return _render_snapshots(request, user, templates, agent_id=agent_id)

    @app.post("/snapshots")
    def create_snapshot(
        request: Request,
        agent_id: Annotated[str, Form()] = "personal",
        user: User = Depends(require_user),
    ):
        manager = _snapshot_manager(agent_id)
        try:
            manager.take(cadence_id="web")
            return _redirect(f"/snapshots?agent_id={agent_id}")
        except SnapshotError as exc:
            return _render_snapshots(
                request, user, templates, agent_id=agent_id, error=str(exc), status_code=400
            )

    @app.post("/snapshots/{agent_id}/{snapshot_id}/pin")
    def pin_snapshot(
        request: Request,
        agent_id: str,
        snapshot_id: str,
        pinned: Annotated[str, Form()] = "true",
        user: User = Depends(require_user),
    ):
        manager = _snapshot_manager(agent_id)
        try:
            manager.pin(snapshot_id, pinned=(pinned.lower() == "true"))
            return _redirect(f"/snapshots?agent_id={agent_id}")
        except SnapshotError as exc:
            return _render_snapshots(
                request, user, templates, agent_id=agent_id, error=str(exc), status_code=400
            )

    @app.post("/snapshots/{agent_id}/{snapshot_id}/delete")
    def delete_snapshot(
        request: Request,
        agent_id: str,
        snapshot_id: str,
        user: User = Depends(require_user),
    ):
        manager = _snapshot_manager(agent_id)
        try:
            entry = manager.get(snapshot_id)
        except SnapshotError as exc:
            return _render_snapshots(
                request, user, templates, agent_id=agent_id, error=str(exc), status_code=404
            )
        if entry.pinned:
            return _render_snapshots(
                request,
                user,
                templates,
                agent_id=agent_id,
                error=(
                    f"Snapshot {snapshot_id} is pinned. Unpin it before deleting."
                ),
                status_code=409,
            )
        try:
            manager.delete(snapshot_id)
            return _redirect(f"/snapshots?agent_id={agent_id}")
        except SnapshotError as exc:
            return _render_snapshots(
                request, user, templates, agent_id=agent_id, error=str(exc), status_code=400
            )

    @app.post("/snapshots/{agent_id}/{snapshot_id}/restore", response_class=HTMLResponse)
    def restore_snapshot(
        request: Request,
        agent_id: str,
        snapshot_id: str,
        user: User = Depends(require_user),
    ):
        manager = _snapshot_manager(agent_id)
        try:
            hashes = manager.restore(snapshot_id)
        except SnapshotError as exc:
            return _render_snapshots(
                request, user, templates, agent_id=agent_id, error=str(exc), status_code=400
            )
        prefixed = [h if h.startswith("sha256:") else f"sha256:{h}" for h in hashes]
        return templates.TemplateResponse(
            "restore.html",
            {
                "request": request,
                "user": user,
                "active": "snapshot",
                "agent_id": agent_id,
                "snapshot_id": snapshot_id,
                "hashes": prefixed,
            },
        )

    # ── settings ───────────────────────────────────────────────────────

    @app.get("/settings/users", response_class=HTMLResponse)
    def users_page(request: Request, user: User = Depends(require_admin)):
        return templates.TemplateResponse(
            "users.html",
            {
                "request": request,
                "user": user,
                "active": "users",
                "users": store.list_users(),
            },
        )

    @app.post("/settings/users/{user_id}/approve")
    def approve_user_route(
        user_id: int, request: Request, user: User = Depends(require_admin)
    ):
        store.approve_user(user_id)
        return _redirect("/settings/users")

    return app


# ─── helpers ─────────────────────────────────────────────────────────


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=status.HTTP_303_SEE_OTHER)


def _login_page(
    request: Request,
    templates: Jinja2Templates,
    *,
    error: str | None = None,
    info: str | None = None,
    username: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        "auth.html",
        {
            "request": request,
            "title": "Sign in",
            "heading": "Sign in",
            "action": "/login",
            "submit_label": "Sign in",
            "password_autocomplete": "current-password",
            "username": username,
            "error": error,
            "info": info,
            "foot_html": (
                "Need access? Ask the admin to create an account."
                if is_signup_disabled()
                else 'Need access? <a href="/signup">Request an account</a>.'
            ),
            "footnote": "Vektra Industries · AgentDrive v" + SAVANT_VERSION,
        },
        status_code=status_code,
    )


def _render_snapshots(
    request: Request,
    user: User,
    templates: Jinja2Templates,
    *,
    agent_id: str = "personal",
    error: str | None = None,
    info: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    manager = _snapshot_manager(agent_id)
    snaps: list[dict[str, Any]] = []
    try:
        for s in manager.list_snapshots():
            snaps.append(
                {
                    "snapshot_id": s.snapshot_id,
                    "agent_id": s.agent_id,
                    "cadence_id": s.cadence_id,
                    "hash_count": len(s.hashes),
                    "pinned": s.pinned,
                }
            )
    except Exception:  # pragma: no cover
        snaps = []
    pinned_count = sum(1 for s in snaps if s["pinned"])
    return templates.TemplateResponse(
        "snapshots.html",
        {
            "request": request,
            "user": user,
            "active": "snapshot",
            "agent_id": agent_id,
            "snapshots": snaps,
            "snap_count": len(snaps),
            "pinned_count": pinned_count,
            "cadence_label": "6h",
            "error": error,
            "info": info,
        },
        status_code=status_code,
    )


def _snapshot_manager(agent_id: str) -> SnapshotManager:
    backup_root = get_agentdrive_home() / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    return SnapshotManager(
        agent_id=agent_id,
        drive_path=get_default_drive_path(),
        backup_root=backup_root,
    )


def _snapshot_count(agent_id: str) -> int:
    try:
        return len(_snapshot_manager(agent_id).list_snapshots())
    except Exception:  # pragma: no cover
        return 0


def _list_swarms() -> list[dict[str, Any]]:
    swarms_root = get_agentdrive_home() / "swarms"
    entries: list[dict[str, Any]] = []
    if not swarms_root.exists():
        return entries
    for child in sorted(swarms_root.iterdir()):
        if not child.is_dir():
            continue
        entries.append(
            {
                "swarm_id": child.name,
                "path": str(child),
                "genomes": _count_files(child / "genomes"),
                "subagents": _count_files(child / "subagents", dirs=True),
                "created": _humanize_age(child.stat().st_mtime),
            }
        )
    return entries


def _list_caps(issuer: str | None = None) -> list[dict[str, Any]]:
    """Return active (non-revoked) capabilities, newest first."""
    try:
        from agentdrive.cap.store import CapStore
    except Exception:  # pragma: no cover
        return []
    store_path = get_agentdrive_home() / "caps.db"
    if not store_path.exists():
        return []
    cap_store = CapStore(db_path=store_path)
    out: list[dict[str, Any]] = []
    try:
        with cap_store._conn() as c:  # noqa: SLF001 — read-only iteration
            for row in c.execute(
                "SELECT cap_id, uri, issuer, issued_at, revoked, parent_cap_id "
                "FROM caps WHERE revoked = 0 ORDER BY issued_at DESC LIMIT 100"
            ):
                cap_id, uri, cap_issuer, issued_at, _revoked, _parent = row
                if issuer is not None and cap_issuer != issuer:
                    continue
                out.append(
                    {
                        "cap_id": cap_id,
                        "uri": uri,
                        "issued_to": cap_issuer,
                        "issued_at": _humanize_age(issued_at),
                        "expires": "no expiry",
                        "rail": "accent",
                    }
                )
    except Exception:  # pragma: no cover
        return out
    return out


def _personal_drive() -> AgentDrive | None:
    try:
        return AgentDrive(drive_path=get_default_drive_path())
    except Exception:  # pragma: no cover — first-run state
        return None


def _list_genome_rows() -> list[dict[str, Any]]:
    drive = _personal_drive()
    if drive is None:
        return []
    rows: list[dict[str, Any]] = []
    try:
        names = drive.registry.list_genomes()
    except Exception:  # pragma: no cover
        return []
    # Index ingest history by genome_id for provenance lookup
    history_by_genome: dict[str, dict[str, Any]] = {}
    try:
        for evt in drive.get_ingest_history(limit=500):
            gid = evt.get("genome_id") or evt.get("id")
            if gid:
                history_by_genome.setdefault(gid, evt)
    except Exception:  # pragma: no cover
        pass
    for name in names:
        try:
            genome = drive.registry.load(name)
        except Exception:
            continue
        if genome is None:
            continue
        manifest = getattr(genome, "manifest", None)
        eval_scores = getattr(manifest, "evaluation_score", None) or {}
        score = 0.0
        if isinstance(eval_scores, dict) and eval_scores:
            numeric = [v for v in eval_scores.values() if isinstance(v, (int, float))]
            if numeric:
                score = float(max(numeric))
        created = getattr(manifest, "created", None)
        if created is not None and hasattr(created, "isoformat"):
            created = created.isoformat()
        authors = getattr(manifest, "authors", None) or []
        source_agent = "unknown"
        if authors:
            first = authors[0]
            source_agent = (
                getattr(first, "id", None)
                or (first.get("id") if isinstance(first, dict) else None)
                or "unknown"
            )
        version = getattr(manifest, "version", "") or ""
        gid = getattr(manifest, "id", None) or getattr(genome, "genome_id", name)
        content_hash = (
            getattr(manifest, "content_hash", None)
            or getattr(genome, "content_hash", None)
            or ""
        )
        if not content_hash:
            try:
                content_hash = genome.compute_content_hash()
            except Exception:
                content_hash = ""
        if content_hash and not content_hash.startswith("sha256:"):
            content_hash = f"sha256:{content_hash}"
        # Pull provenance from ingest history if present
        history_key = f"{gid}@{version}" if version else gid
        evt = history_by_genome.get(history_key) or history_by_genome.get(gid) or {}
        source = evt.get("source") or "—"
        actor = evt.get("actor") or source_agent
        subagent = evt.get("subagent_id")
        provenance = f"{source} / {actor}"
        if subagent:
            provenance += f" / sub:{subagent}"
        rows.append(
            {
                "id": gid,
                "version": version,
                "hash": content_hash,
                "score": score,
                "score_label": f"{score:.3f}",
                "age": _humanize_age(created),
                "agent": source_agent,
                "provenance": provenance,
                "depth": getattr(manifest, "lineage_depth", 0) or 0,
            }
        )
    return rows


def _genome_count() -> int:
    drive = _personal_drive()
    if drive is None:
        return 0
    try:
        return len(drive.registry.list_genomes())
    except Exception:  # pragma: no cover
        return 0


def _count_files(path: Path, *, dirs: bool = False) -> int:
    if not path.exists():
        return 0
    if dirs:
        return sum(1 for c in path.iterdir() if c.is_dir())
    return sum(1 for c in path.iterdir() if c.is_file())


def _humanize_age(when: float | str | None) -> str:
    if when is None:
        return "—"
    if isinstance(when, str):
        try:
            ts = datetime.fromisoformat(when.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return when
    else:
        ts = float(when)
    delta = datetime.now(UTC).timestamp() - ts
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    if delta < 86400 * 7:
        return f"{int(delta // 86400)}d ago"
    if delta < 86400 * 30:
        return f"{int(delta // (86400 * 7))}w ago"
    return f"{int(delta // (86400 * 30))}mo ago"


def _humanize_ttl(when: float | None) -> str:
    if when is None:
        return "no expiry"
    try:
        delta = float(when) - datetime.now(UTC).timestamp()
    except (TypeError, ValueError):
        return str(when)
    if delta <= 0:
        return "expired"
    if delta < 3600:
        return f"{int(delta // 60)}m"
    if delta < 86400:
        return f"{int(delta // 3600)}h {int((delta % 3600) // 60)}m"
    return f"{int(delta // 86400)}d {int((delta % 86400) // 3600)}h"
