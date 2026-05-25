"""Localhost-bound UI for Snapshot Backup.

Tiny stdlib-only HTTP server (no Flask / FastAPI dep). Default bind is
``127.0.0.1:8420`` — loopback only. Operators who want remote access can
override the bind address explicitly, but the safe-by-default behavior
is local-machine-only.

Routes:

- ``GET  /``                                 — HTML dashboard
- ``GET  /api/snapshots?agent_id=<id>``      — list snapshots for an agent
- ``POST /api/snapshots?agent_id=<id>``      — take an on-demand snapshot
- ``POST /api/restore?agent_id=<id>&id=<sid>`` — return hashes from snapshot
- ``POST /api/pin?agent_id=<id>&id=<sid>``    — pin/unpin a snapshot
- ``DELETE /api/snapshots?agent_id=<id>&id=<sid>`` — delete a (non-pinned) snapshot
- ``GET  /api/health``                       — liveness probe

Run from Python:

    from agentdrive.backup.ui import serve
    serve(host="127.0.0.1", port=8420, backup_root="~/.agentdrive/backups")

Or from the CLI: ``agentdrive backup ui`` (wired in cli.py when M2d ships).
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .snapshot import (
    DEFAULT_CADENCE_SECONDS,
    SnapshotError,
    SnapshotManager,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Manager registry
# ─────────────────────────────────────────────────────────────────────


class _ManagerRegistry:
    """Per-agent SnapshotManager cache shared across HTTP requests.

    The UI doesn't know which agents exist in advance; it discovers them
    on demand. ``resolve_drive_path`` is the only knob — by default we
    assume one Drive per agent under ``<agentdrive_home>/agents/<id>/drive``,
    but the test suite (and any custom deploy) can swap that out.
    """

    def __init__(
        self,
        backup_root: Path,
        resolve_drive_path: Callable[[str], Path],
        cadence_seconds: int = DEFAULT_CADENCE_SECONDS,
    ):
        self.backup_root = backup_root
        self.resolve_drive_path = resolve_drive_path
        self.cadence_seconds = cadence_seconds
        self._cache: dict[str, SnapshotManager] = {}
        self._lock = threading.RLock()

    def get(self, agent_id: str) -> SnapshotManager:
        with self._lock:
            existing = self._cache.get(agent_id)
            if existing is not None:
                return existing
            mgr = SnapshotManager(
                agent_id=agent_id,
                drive_path=self.resolve_drive_path(agent_id),
                backup_root=self.backup_root,
                cadence_seconds=self.cadence_seconds,
            )
            self._cache[agent_id] = mgr
            return mgr


# ─────────────────────────────────────────────────────────────────────
# HTML dashboard
# ─────────────────────────────────────────────────────────────────────

_DASH_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AgentDrive Snapshots</title>
  <style>
    :root {
      --bg: #0a0a0f; --surface: #12121a; --text: #f5f6fa;
      --dim: #9ca3c4; --accent: #2563eb; --warn: #f59e0b;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text);
           font-family: ui-monospace, 'JetBrains Mono', Menlo, monospace;
           padding: 32px; }
    h1 { font-size: 20px; letter-spacing: -0.3px; margin: 0 0 4px; }
    .sub { color: var(--dim); font-size: 12px; margin-bottom: 24px; }
    .card { background: var(--surface); border-radius: 8px;
            padding: 20px; margin-bottom: 16px; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th, td { text-align: left; padding: 8px 12px;
             border-bottom: 1px solid #1e1e2a; }
    th { color: var(--dim); font-weight: 500; }
    button { background: var(--accent); color: var(--text); border: 0;
             padding: 8px 14px; border-radius: 4px; cursor: pointer;
             font-family: inherit; font-size: 12px; }
    button.danger { background: #1a1a24; color: var(--warn); }
    input[type=text] { background: var(--bg); color: var(--text);
                       border: 1px solid #1e1e2a; padding: 8px;
                       border-radius: 4px; font-family: inherit;
                       width: 240px; }
    .pinned { color: var(--warn); }
  </style>
</head>
<body>
  <h1>AgentDrive Snapshots</h1>
  <div class="sub">Localhost-only. Point-in-time backups of an agent's Drive.</div>
  <div class="card">
    <input id="agent" type="text" placeholder="agent id" />
    <button onclick="loadAgent()">load</button>
    <button onclick="takeSnap()">take snapshot now</button>
    <span id="status" style="color:var(--dim); margin-left:12px;"></span>
  </div>
  <div class="card">
    <table>
      <thead><tr>
        <th>snapshot_id</th><th>taken</th><th>cadence</th>
        <th>hashes</th><th>pinned</th><th></th>
      </tr></thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
<script>
let agentId = "";
function loadAgent() {
  agentId = document.getElementById("agent").value.trim();
  if (!agentId) return;
  fetch("/api/snapshots?agent_id=" + encodeURIComponent(agentId))
    .then(r => r.json()).then(render);
}
function takeSnap() {
  if (!agentId) { setStatus("set agent id first"); return; }
  fetch("/api/snapshots?agent_id=" + encodeURIComponent(agentId), {method: "POST"})
    .then(r => r.json()).then(_ => { setStatus("snapshot taken"); loadAgent(); });
}
function pinSnap(id, pinned) {
  fetch("/api/pin?agent_id=" + encodeURIComponent(agentId)
        + "&id=" + encodeURIComponent(id)
        + "&pinned=" + (pinned ? "true" : "false"), {method: "POST"})
    .then(_ => loadAgent());
}
function delSnap(id) {
  if (!confirm("Delete " + id + "?")) return;
  fetch("/api/snapshots?agent_id=" + encodeURIComponent(agentId)
        + "&id=" + encodeURIComponent(id), {method: "DELETE"})
    .then(r => r.json()).then(d => {
      setStatus(d.deleted ? "deleted" : (d.error || "no-op"));
      loadAgent();
    });
}
function render(data) {
  const rows = document.getElementById("rows");
  rows.innerHTML = "";
  for (const s of data.snapshots || []) {
    const taken = new Date(s.taken_at * 1000).toISOString().replace("T", " ").slice(0, 19);
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${s.snapshot_id}</td>
      <td>${taken}</td>
      <td>${s.cadence_id}</td>
      <td>${s.hashes.length}</td>
      <td class="${s.pinned ? "pinned" : ""}">${s.pinned ? "pinned" : ""}</td>
      <td>
        <button onclick="pinSnap('${s.snapshot_id}', ${!s.pinned})">${s.pinned ? "unpin" : "pin"}</button>
        <button class="danger" onclick="delSnap('${s.snapshot_id}')">delete</button>
      </td>`;
    rows.appendChild(tr);
  }
}
function setStatus(s) { document.getElementById("status").textContent = s; }
</script>
</body></html>
"""


# ─────────────────────────────────────────────────────────────────────
# HTTP handler
# ─────────────────────────────────────────────────────────────────────


def _make_handler(registry: _ManagerRegistry, allowed_origin: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # noqa: N802 — stdlib name
            logger.debug("ui %s - " + fmt, self.address_string(), *args)

        def _send_json(self, status: int, body: dict) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            # Hardening headers — even on localhost, a malicious page in
            # the same browser could otherwise CSRF / embed us.
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def _send_html(self, status: int, body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                "script-src 'self' 'unsafe-inline'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(payload)

        def _parse_qs(self) -> dict[str, str]:
            q = parse_qs(urlparse(self.path).query)
            return {k: v[0] for k, v in q.items()}

        # ── CSRF defense ────────────────────────────────────────────────
        def _csrf_ok(self) -> bool:
            """Reject any cross-origin write. A page on evil.example.com
            visited in the same browser as the operator could otherwise
            issue ``fetch('http://localhost:8420/api/snapshots', {method:'POST'})``
            and the browser would carry the request — the localhost UI's
            trust boundary is the browser's same-origin policy plus our
            explicit Origin check.

            Allow:
              - Same-origin (Origin header matches our bind)
              - No Origin AND no Referer (curl / direct local CLI use)
            Reject everything else.
            """
            origin = self.headers.get("Origin")
            referer = self.headers.get("Referer")
            if origin is not None:
                return origin == allowed_origin
            if referer is not None:
                return referer.startswith(allowed_origin)
            # No Origin and no Referer — direct (curl, fetch from server-side
            # script, our own JS via same-origin). Allow.
            return True

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/" or path == "/index.html":
                self._send_html(200, _DASH_HTML)
                return
            if path == "/api/health":
                self._send_json(200, {"ok": True})
                return
            if path == "/api/snapshots":
                qs = self._parse_qs()
                agent_id = qs.get("agent_id")
                if not agent_id:
                    self._send_json(400, {"error": "agent_id required"})
                    return
                try:
                    mgr = registry.get(agent_id)
                except ValueError as exc:
                    self._send_json(400, {"error": str(exc)})
                    return
                self._send_json(
                    200,
                    {
                        "agent_id": agent_id,
                        "snapshots": [asdict(s) for s in mgr.list_snapshots()],
                        "stats": mgr.stats(),
                    },
                )
                return
            self._send_json(404, {"error": f"no route {path}"})

        def do_POST(self) -> None:  # noqa: N802
            if not self._csrf_ok():
                self._send_json(403, {"error": "cross-origin request rejected"})
                return
            path = urlparse(self.path).path
            qs = self._parse_qs()
            agent_id = qs.get("agent_id")
            if not agent_id:
                self._send_json(400, {"error": "agent_id required"})
                return
            try:
                mgr = registry.get(agent_id)
            except ValueError as exc:  # raised by the path-traversal validator
                self._send_json(400, {"error": str(exc)})
                return

            if path == "/api/snapshots":
                entry = mgr.take(cadence_id="on-demand")
                self._send_json(201, {"snapshot": asdict(entry)})
                return
            if path == "/api/restore":
                sid = qs.get("id")
                if not sid:
                    self._send_json(400, {"error": "id required"})
                    return
                try:
                    hashes = mgr.restore(sid)
                    self._send_json(200, {"snapshot_id": sid, "hashes": hashes})
                except SnapshotError as exc:
                    self._send_json(404, {"error": str(exc)})
                return
            if path == "/api/pin":
                sid = qs.get("id")
                pinned = qs.get("pinned", "true").lower() == "true"
                if not sid:
                    self._send_json(400, {"error": "id required"})
                    return
                try:
                    updated = mgr.pin(sid, pinned=pinned)
                    self._send_json(200, {"snapshot": asdict(updated)})
                except SnapshotError as exc:
                    self._send_json(404, {"error": str(exc)})
                return
            self._send_json(404, {"error": f"no route {path}"})

        def do_DELETE(self) -> None:  # noqa: N802
            if not self._csrf_ok():
                self._send_json(403, {"error": "cross-origin request rejected"})
                return
            path = urlparse(self.path).path
            qs = self._parse_qs()
            agent_id = qs.get("agent_id")
            sid = qs.get("id")
            if not agent_id or not sid:
                self._send_json(400, {"error": "agent_id and id required"})
                return
            try:
                mgr = registry.get(agent_id)
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            if path == "/api/snapshots":
                try:
                    ok = mgr.delete(sid)
                    self._send_json(200 if ok else 404, {"deleted": ok})
                except SnapshotError as exc:
                    self._send_json(409, {"error": str(exc)})
                return
            self._send_json(404, {"error": f"no route {path}"})

    return Handler


# ─────────────────────────────────────────────────────────────────────
# Server entry
# ─────────────────────────────────────────────────────────────────────


def serve(
    *,
    host: str = "127.0.0.1",
    port: int = 8420,
    backup_root: Path | str,
    resolve_drive_path: Callable[[str], Path] | None = None,
    cadence_seconds: int = DEFAULT_CADENCE_SECONDS,
    blocking: bool = True,
) -> ThreadingHTTPServer:
    """Start the localhost backup UI.

    ``host`` defaults to ``127.0.0.1`` — loopback only. Pass another
    interface explicitly if you genuinely need remote access (and
    accept the security implications).

    ``resolve_drive_path`` maps an agent_id to the Drive directory the
    UI should snapshot. Defaults to ``<agentdrive_home>/agents/<id>/drive``.

    ``blocking=False`` returns the server immediately and runs it in a
    daemon thread — useful for tests and for callers that want to wire
    the UI into a larger process.
    """
    backup_root = Path(backup_root)

    if resolve_drive_path is None:
        from agentdrive.constants import get_agentdrive_home

        def _default_resolve(agent_id: str) -> Path:
            return get_agentdrive_home() / "agents" / agent_id / "drive"

        resolve_drive_path = _default_resolve

    registry = _ManagerRegistry(
        backup_root=backup_root,
        resolve_drive_path=resolve_drive_path,
        cadence_seconds=cadence_seconds,
    )
    # The allowed Origin is the exact bind we'll be reachable at. Used by
    # the CSRF check inside the handler to reject cross-origin POST/DELETE
    # from any other page the user happens to have open.
    allowed_origin = f"http://{host}:{port}"
    handler = _make_handler(registry, allowed_origin)
    server = ThreadingHTTPServer((host, port), handler)

    if blocking:
        logger.info("AgentDrive backup UI listening on http://%s:%d/", host, port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.shutdown()
    else:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
    return server
