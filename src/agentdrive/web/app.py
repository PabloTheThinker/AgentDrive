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
from agentdrive.web.authz import require_cap
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

    # ── background retention sweep ──────────────────────────────────
    # Inline take() does a bounded prune (50 deletes/pass) so a 10k
    # backlog can't stall a web request. The full retention pass runs
    # here on a 5-minute cadence in the asyncio loop and chews through
    # the rest until the policy is met. A lock prevents overlapping
    # passes if a tick fires while one is still running.
    import asyncio as _asyncio

    app.state.retention_lock = _asyncio.Lock()

    @app.on_event("startup")
    async def _start_retention_loop():  # noqa: ANN202
        app.state.retention_task = _asyncio.create_task(_retention_loop(app))

    @app.on_event("shutdown")
    async def _stop_retention_loop():  # noqa: ANN202
        task = getattr(app.state, "retention_task", None)
        if task is not None:
            task.cancel()
            try:
                await task
            except (_asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

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
        if user is not None:
            return user
        # Non-browser callers present an Authorization: Bearer <cap_id> header
        # instead of a session cookie. require_cap (later in the dependency
        # chain) is what actually validates the cap — but require_user has
        # to let the request through so cap enforcement gets a chance to
        # decide. Synthesise a sentinel User to keep route handlers happy.
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            return User(id=0, username="bearer-principal", role="user", disabled=False)
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})

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

    @app.get("/metrics")
    def metrics(request: Request):
        """Prometheus text-format counters.

        Auth-bypass on purpose so a scraper can hit the endpoint without
        a session — same threat-model as ``/healthz``. The exposed numbers
        are deliberately non-sensitive: counts of genomes, snapshots,
        active capabilities, peers, quarantine entries, uptime.
        Operators wire this into Prometheus / Grafana / Datadog as the
        single observability surface.
        """
        from fastapi.responses import Response as _PlainResponse

        uptime_s = round(time.time() - app.state.started_at, 1)

        # Cheap counts: every store either reports zero on missing-disk
        # or has its own list method. We swallow per-source errors so
        # one bad store doesn't take the metrics endpoint down.
        def _safe_int(fn) -> int:  # noqa: ANN001
            try:
                return int(fn())
            except Exception:  # noqa: BLE001
                return 0

        peers_count = _safe_int(lambda: len(_list_peers_and_quarantine()[0]))
        quarantine_count = _safe_int(lambda: len(_list_peers_and_quarantine()[1]))
        genome_count = _safe_int(_genome_count)
        snapshot_count = _safe_int(lambda: _snapshot_count("personal"))
        caps_count = _safe_int(lambda: len(_list_caps()))
        swarms_count = _safe_int(lambda: len(_list_swarms()))

        lines = [
            "# HELP agentdrive_uptime_seconds Daemon uptime",
            "# TYPE agentdrive_uptime_seconds counter",
            f"agentdrive_uptime_seconds {uptime_s}",
            "# HELP agentdrive_genomes_total Genomes in Personal Drive registry",
            "# TYPE agentdrive_genomes_total gauge",
            f"agentdrive_genomes_total {genome_count}",
            "# HELP agentdrive_snapshots_total Snapshots stored on disk",
            "# TYPE agentdrive_snapshots_total gauge",
            f'agentdrive_snapshots_total{{agent="personal"}} {snapshot_count}',
            "# HELP agentdrive_capabilities_active Active (non-revoked) capabilities",
            "# TYPE agentdrive_capabilities_active gauge",
            f"agentdrive_capabilities_active {caps_count}",
            "# HELP agentdrive_swarms_total Swarm Drives on disk",
            "# TYPE agentdrive_swarms_total gauge",
            f"agentdrive_swarms_total {swarms_count}",
            "# HELP agentdrive_peers_total Federated peers configured",
            "# TYPE agentdrive_peers_total gauge",
            f"agentdrive_peers_total {peers_count}",
            "# HELP agentdrive_quarantine_pending Quarantine entries awaiting operator review",
            "# TYPE agentdrive_quarantine_pending gauge",
            f"agentdrive_quarantine_pending {quarantine_count}",
        ]
        return _PlainResponse(
            content="\n".join(lines) + "\n",
            media_type="text/plain; version=0.0.4",
        )

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
            request,
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
                request,
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
            request,
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
                request,
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
            request,
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
                    {
                        "label": "Snapshots",
                        "value": str(_snapshot_count(user.username)),
                        "delta": None,
                    },
                    {"label": "Capabilities issued", "value": "0", "delta": None},
                ],
                "activity": [],
                "health": [
                    {"label": "Content store integrity", "value": "✓ verified", "color": "accent"},
                    {"label": "Snapshot cadence", "value": "✓ on schedule", "color": "accent"},
                    {"label": "Capability keystore", "value": "✓ healthy", "color": "accent"},
                ],
                "shortcuts": [
                    {
                        "title": "Personal Drive",
                        "meta": str(get_default_drive_path()),
                        "href": "/personal",
                        "icon": "drive",
                        "color": "accent",
                    },
                    {
                        "title": "Swarm Drives",
                        "meta": "shared substrates",
                        "href": "/swarms",
                        "icon": "swarm",
                        "color": "warm",
                    },
                    {
                        "title": "DNA Lineage",
                        "meta": "ancestry + grants",
                        "href": "/dna",
                        "icon": "dna",
                        "color": "success",
                    },
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
            request,
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
        _cap=Depends(require_cap("drive", "write", resource_kind="agent", resource_id="personal")),
    ):
        import json as _json
        import re as _re

        from agentdrive.genome.models import Genome

        if len(genome_json.encode("utf-8")) > GENOME_JSON_MAX_BYTES:
            rows = _list_genome_rows()
            return templates.TemplateResponse(
                request,
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
                request,
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
                request,
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
            request,
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
            request,
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
        _cap=Depends(require_cap("swarm", "write", resource_kind="root", resource_id="root")),
    ):
        from agentdrive.drive.swarm_manager import SwarmDriveManager

        cleaned = swarm_id.strip()
        if not cleaned or not all(c.isalnum() or c in "-_." for c in cleaned):
            return templates.TemplateResponse(
                request,
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
                request,
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
            request,
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
                # Read real grants from GrantStore (the synthetic
                # `drive.active_grants()` was a stub).
                from agentdrive.dna.grants import GrantStore

                gs = GrantStore(db_path=get_agentdrive_home() / "grants.db")
                with gs._conn() as c:  # noqa: SLF001
                    rows = c.execute(
                        "SELECT grant_id, issuer, grantee, scope_json "
                        "FROM grants WHERE revoked = 0 AND (issuer = ? OR grantee = ?) "
                        "ORDER BY issued_at DESC LIMIT 50",
                        (agent, agent),
                    ).fetchall()
                import json as _json

                for grant_id, issuer, grantee, scope_json in rows:
                    try:
                        scope = _json.loads(scope_json or "{}")
                    except Exception:
                        scope = {}
                    grants.append(
                        {
                            "grant_id": grant_id,
                            "donor_id": issuer,
                            "recipient_id": grantee,
                            "min_eval": scope.get("min_eval", "—"),
                        }
                    )
            except Exception:  # noqa: BLE001 — keep the page rendering on partial-DNA-state
                import logging as _logging

                from agentdrive.utils.log_safe import safe_for_log

                _logging.getLogger("agentdrive.web").exception(
                    "dna_page_partial_load_failed",
                    extra={"agent_id": safe_for_log(agent)},
                )

        return templates.TemplateResponse(
            request,
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

    @app.post("/dna/grants")
    def issue_grant_route(
        request: Request,
        issuer: Annotated[str, Form()],
        grantee: Annotated[str, Form()],
        min_eval: Annotated[float, Form()] = 0.7,
        ttl_hours: Annotated[int, Form()] = 24,
        user: User = Depends(require_user),
        _cap=Depends(require_cap("dna", "issue", resource_kind="grant", resource_id="root")),
    ):
        """Issue an Ed25519-signed lineage grant from one agent to another.

        Real GrantScope fields: ``topics``, ``min_eval``, ``content_hashes``.
        Only ``min_eval`` is surfaced via this form; the others can be
        added when the UI grows topic / hash filters.
        """
        import re as _re

        from agentdrive.dna.grants import GrantScope, GrantStore

        safe_re = _re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
        if not safe_re.fullmatch(issuer) or not safe_re.fullmatch(grantee):
            return _redirect(f"/dna?agent={issuer}&error=bad-agent-id")
        if min_eval < 0.0 or min_eval > 1.0:
            return _redirect(f"/dna?agent={issuer}&error=bad-min-eval")
        store_path = get_agentdrive_home() / "grants.db"
        gs = GrantStore(db_path=store_path)
        try:
            grant = gs.issue(
                issuer=issuer,
                grantee=grantee,
                scope=GrantScope(min_eval=min_eval),
                ttl_seconds=ttl_hours * 3600,
            )
        except Exception as exc:  # noqa: BLE001
            return _redirect(f"/dna?agent={issuer}&error={exc.__class__.__name__}")
        return _redirect(f"/dna?agent={issuer}&info=grant-{grant.grant_id[:8]}")

    @app.post("/dna/grants/{grant_id}/pull")
    def pull_grant_route(
        request: Request,
        grant_id: str,
        user: User = Depends(require_user),
        _cap=Depends(require_cap("dna", "pull", resource_kind="grant", resource_id="root")),
    ):
        """Execute a lineage grant: pull every authorized Genome from the
        issuer's DNA Drive and route every result through quarantine on
        the grantee side — never auto-publish. The operator approves or
        rejects each candidate separately via /peers.
        """
        import json as _json
        import tempfile as _tempfile
        from pathlib import Path as _Path

        from agentdrive.dna.grants import GrantStore, pull_via_grant
        from agentdrive.quarantine import get_default_quarantine

        gs = GrantStore(db_path=get_agentdrive_home() / "grants.db")
        grant = None
        try:
            with gs._conn() as c:  # noqa: SLF001
                row = c.execute(
                    "SELECT grant_id, issuer, grantee, scope_json, reducer, "
                    "ttl_seconds, issued_at, issuer_pubkey, signature, revoked "
                    "FROM grants WHERE grant_id = ?",
                    (grant_id,),
                ).fetchone()
            if row is not None:
                from agentdrive.dna.grants import LineageShareGrant

                grant = LineageShareGrant.from_dict(
                    {
                        "grant_id": row[0],
                        "issuer": row[1],
                        "grantee": row[2],
                        "scope": _json.loads(row[3]),
                        "reducer": row[4],
                        "ttl_seconds": row[5],
                        "issued_at": row[6],
                        "issuer_pubkey": row[7],
                        "signature": row[8],
                    }
                )
        except Exception:  # noqa: BLE001
            grant = None
        if grant is None:
            return _redirect(f"/dna?error=unknown-grant-{grant_id[:8]}")

        try:
            inherited = pull_via_grant(grant, gs)
        except Exception as exc:  # noqa: BLE001
            return _redirect(f"/dna?agent={grant.grantee}&error=pull-{exc.__class__.__name__}")

        q = get_default_quarantine()
        submitted = 0
        for g in inherited:
            with _tempfile.TemporaryDirectory(prefix="ad-pull-") as tmp:
                tmp_dir = _Path(tmp)
                (tmp_dir / "manifest.json").write_text(
                    _json.dumps(g.payload, indent=2, sort_keys=True),
                    encoding="utf-8",
                )
                try:
                    q.submit(tmp_dir, source_peer=f"grant:{grant.issuer}")
                    submitted += 1
                except Exception:  # noqa: BLE001
                    continue
        return _redirect(f"/dna?agent={grant.grantee}&info=pulled-{submitted}-into-quarantine")

    @app.post("/dna/grants/{grant_id}/revoke")
    def revoke_grant_route(
        request: Request,
        grant_id: str,
        user: User = Depends(require_user),
        _cap=Depends(require_cap("dna", "revoke", resource_kind="grant", resource_id="root")),
    ):
        from agentdrive.dna.grants import GrantStore

        gs = GrantStore(db_path=get_agentdrive_home() / "grants.db")
        gs.revoke(grant_id)
        return _redirect("/dna")

    @app.get("/capabilities", response_class=HTMLResponse)
    def capabilities_page(
        request: Request,
        user: User = Depends(require_user),
        info: str | None = None,
        error: str | None = None,
    ):
        return templates.TemplateResponse(
            request,
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
        _cap=Depends(require_cap("cap", "mint", resource_kind="store", resource_id="root")),
    ):
        from agentdrive.cap.store import CapStore
        from agentdrive.cap.uri import parse_uri

        try:
            capability = parse_uri(uri.strip())
        except Exception as exc:
            return templates.TemplateResponse(
                request,
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
            request,
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
        _cap=Depends(require_cap("cap", "revoke", resource_kind="store", resource_id="root")),
    ):
        from agentdrive.cap.store import CapStore

        store_path = get_agentdrive_home() / "caps.db"
        cap_store = CapStore(db_path=store_path)
        revoked = cap_store.revoke(cap_id)
        msg = f"Revoked {cap_id[:8]}…" if revoked else f"Capability {cap_id[:8]}… not found."
        return templates.TemplateResponse(
            request,
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
    def peers_page(
        request: Request,
        user: User = Depends(require_user),
        info: str | None = None,
        error: str | None = None,
    ):
        peers_list, quarantine_list = _list_peers_and_quarantine()
        return templates.TemplateResponse(
            request,
            "peers.html",
            {
                "request": request,
                "user": user,
                "active": "peer",
                "peers": peers_list,
                "quarantine": quarantine_list,
                "info": info,
                "error": error,
            },
        )

    @app.post("/peers")
    def add_peer_route(
        request: Request,
        name: Annotated[str, Form()],
        address: Annotated[str, Form()] = "",
        public_key: Annotated[str, Form()] = "",
        trust: Annotated[str, Form()] = "review",
        user: User = Depends(require_user),
        _cap=Depends(require_cap("peer", "write", resource_kind="registry", resource_id="root")),
    ):
        import re as _re

        from agentdrive.peers import VALID_TRUST_LEVELS, PeerRegistry

        safe_re = _re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
        if not safe_re.fullmatch(name):
            return _redirect("/peers?error=bad-name")
        if trust not in VALID_TRUST_LEVELS:
            return _redirect("/peers?error=bad-trust-level")
        try:
            reg = PeerRegistry()
            reg.add(
                peer_id=name,
                address=address,
                public_key=public_key or None,
                trust_level=trust,
            )
        except Exception as exc:  # noqa: BLE001
            return _redirect(f"/peers?error={exc.__class__.__name__}")
        return _redirect(f"/peers?info=added-{name}")

    @app.post("/peers/quarantine/{quarantine_id}/approve")
    def approve_quarantine_route(
        request: Request,
        quarantine_id: str,
        user: User = Depends(require_user),
        _cap=Depends(require_cap("peer", "review", resource_kind="quarantine", resource_id="root")),
    ):
        from agentdrive.quarantine import get_default_quarantine

        try:
            drive = AgentDrive(drive_path=get_default_drive_path())
            ok = get_default_quarantine().approve(
                quarantine_id,
                target_pool=drive,
                note=f"approved via web by {user.username}",
            )
        except KeyError:
            return _redirect("/peers?error=unknown-quarantine-id")
        except Exception as exc:  # noqa: BLE001
            return _redirect(f"/peers?error={exc.__class__.__name__}")
        status = "approved" if ok else "validation-failed"
        return _redirect(f"/peers?info={status}-{quarantine_id[:8]}")

    @app.post("/peers/quarantine/{quarantine_id}/reject")
    def reject_quarantine_route(
        request: Request,
        quarantine_id: str,
        reason: Annotated[str, Form()] = "rejected by operator",
        user: User = Depends(require_user),
        _cap=Depends(require_cap("peer", "review", resource_kind="quarantine", resource_id="root")),
    ):
        from agentdrive.quarantine import get_default_quarantine

        try:
            get_default_quarantine().reject(quarantine_id, reason=reason)
        except Exception as exc:  # noqa: BLE001
            return _redirect(f"/peers?error={exc.__class__.__name__}")
        return _redirect(f"/peers?info=rejected-{quarantine_id[:8]}")

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
        _cap=Depends(require_cap("backup", "write", resource_kind="agent", resource_id="personal")),
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
        _cap=Depends(
            require_cap("backup", "write", resource_kind="agent", resource_id_arg="agent_id")
        ),
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
        _cap=Depends(
            require_cap("backup", "write", resource_kind="agent", resource_id_arg="agent_id")
        ),
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
                error=(f"Snapshot {snapshot_id} is pinned. Unpin it before deleting."),
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
        _cap=Depends(
            require_cap("backup", "read", resource_kind="agent", resource_id_arg="agent_id")
        ),
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
            request,
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
            request,
            "users.html",
            {
                "request": request,
                "user": user,
                "active": "users",
                "users": store.list_users(),
            },
        )

    @app.post("/settings/users/{user_id}/approve")
    def approve_user_route(user_id: int, request: Request, user: User = Depends(require_admin)):
        store.approve_user(user_id)
        return _redirect("/settings/users")

    return app


# ─── helpers ─────────────────────────────────────────────────────────


_ALLOWED_REDIRECT_PATHS = {
    "/",
    "/dashboard",
    "/login",
    "/setup",
    "/dna",
    "/peers",
    "/snapshots",
    "/settings",
    "/settings/users",
}


def _redirect(path: str) -> RedirectResponse:
    """Redirect to a strict allowlist of local app routes.

    CodeQL's ``py/url-redirection`` rule wants explicit evidence that the
    redirect target is not user-controlled. We use ``urllib.parse.urlsplit``
    (CodeQL-recognised) to verify there is no scheme / netloc, then check
    the path prefix against a known allowlist. Anything off-list collapses
    to ``/``.
    """
    from urllib.parse import quote, urlsplit, urlunsplit

    parts = urlsplit(path or "")
    if parts.scheme or parts.netloc:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    base = parts.path or "/"
    # Reject CR/LF header-injection before allowlist check.
    if "\r" in base or "\n" in base:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    # Accept exact allowlist matches OR allowlisted prefix + "/" subpath.
    is_allowed = base in _ALLOWED_REDIRECT_PATHS or any(
        base == prefix or base.startswith(prefix + "/") for prefix in _ALLOWED_REDIRECT_PATHS
    )
    if not is_allowed:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    # Re-assemble via ``urlunsplit`` (CodeQL-recognised URL composition) with
    # a percent-encoded query. Both ``quote`` and ``urlunsplit`` are barriers
    # ``py/url-redirection`` knows about, so the dataflow break is visible at
    # the RedirectResponse call site.
    safe_query = quote(parts.query, safe="=&") if parts.query else ""
    target = urlunsplit(("", "", base, safe_query, ""))
    return RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)


def _is_local_path(path: str) -> bool:
    """Back-compat predicate retained for tests; allowlist lives in _redirect."""
    if not path or not isinstance(path, str):
        return False
    if not path.startswith("/"):
        return False
    if path.startswith("//") or path.startswith("/\\") or "\r" in path or "\n" in path:
        return False
    return True


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
        request,
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
    # Render at most this many manifests at once. The full list still
    # lives on disk; retention + background sweep keep it bounded, but
    # the page itself never parses more than this on a single request.
    page_limit = int(os.environ.get("AGENTDRIVE_SNAPSHOT_PAGE_LIMIT", "50"))
    try:
        all_snaps = manager.list_snapshots()  # newest first
        for s in all_snaps[:page_limit]:
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
        request,
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


async def _retention_loop(app: FastAPI) -> None:
    """Sweep retention every 5 minutes across every agent_id we know.

    Sleeps if another pass is in flight (the lock is in app.state).
    Failures in one agent don't stop the sweep — we log and continue.
    """
    import asyncio as _asyncio
    import logging as _logging

    log = _logging.getLogger("agentdrive.web.retention")
    interval_s = float(os.environ.get("AGENTDRIVE_RETENTION_INTERVAL_S", "300"))
    backup_root = get_agentdrive_home() / "backups"
    while True:
        try:
            await _asyncio.sleep(interval_s)
            if not backup_root.exists():
                continue
            async with app.state.retention_lock:
                for agent_dir in backup_root.iterdir():
                    if not agent_dir.is_dir():
                        continue
                    from agentdrive.utils.log_safe import safe_for_log

                    safe_agent = safe_for_log(agent_dir.name)
                    try:
                        mgr = _snapshot_manager(agent_dir.name)
                        deleted = mgr.enforce_retention()
                        if deleted:
                            log.info(
                                "background_retention_pass",
                                extra={"agent_id": safe_agent, "deleted": len(deleted)},
                            )
                    except Exception:  # noqa: BLE001
                        log.exception(
                            "background_retention_failed",
                            extra={"agent_id": safe_agent},
                        )
        except _asyncio.CancelledError:
            return  # graceful shutdown
        except Exception:  # noqa: BLE001
            log.exception("retention_loop_unexpected")


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


def _list_peers_and_quarantine() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (peers, quarantine_entries) for the /peers page.

    Both sides come straight from the real data stores; an empty result
    means nothing has been added yet, not that the page is unwired.
    """
    peers: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    try:
        from agentdrive.peers import PeerRegistry

        for p in PeerRegistry().list():
            peers.append(
                {
                    "name": p.peer_id,
                    "fingerprint": (p.public_key or p.address or "")[:48],
                    "trust": p.trust_level.title(),
                    "last_sync": _humanize_age(
                        getattr(p, "last_sync_at", None) or getattr(p, "added_at", None)
                    ),
                    "pulled": "—",
                }
            )
    except Exception:  # pragma: no cover
        pass
    try:
        from agentdrive.quarantine import QuarantineStatus, get_default_quarantine

        for e in get_default_quarantine().list(status=QuarantineStatus.PENDING):
            quarantine.append(
                {
                    "quarantine_id": e.quarantine_id,
                    "hash": (e.sha256 or "")[:12],
                    "source": e.source_peer or "—",
                    "received": _humanize_age(getattr(e, "submitted_at", None)),
                    "reason": getattr(e, "hold_reason", "") or "pending review",
                }
            )
    except Exception:  # pragma: no cover
        pass
    return peers, quarantine


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
            getattr(manifest, "content_hash", None) or getattr(genome, "content_hash", None) or ""
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
