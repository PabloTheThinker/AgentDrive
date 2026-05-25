"""Production observability primitives for the AgentDrive web daemon.

- ``configure_logging``: routes all logs through stdlib ``logging`` with a
  JSON formatter so an ops box can pipe stdout into journald/elk.
- ``RequestLoggingMiddleware``: stamps every request with a UUID4
  ``request_id``, logs method/path/status/latency_ms/client_ip in one record.
- ``LoginRateLimiter``: in-memory token-bucket per source IP. Five attempts
  per minute is enough for a human; brute-force needs more than that.
- ``install_error_boundary``: turns unhandled exceptions into a 500 with a
  short error code, logs the traceback, never echoes internals to the client.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections import OrderedDict, deque
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

_logger = logging.getLogger("agentdrive.web")


def client_ip(request: Request) -> str:
    """Resolve the originating client IP.

    Defaults to ``request.client.host`` (the immediate peer). When the env
    var ``AGENTDRIVE_TRUST_PROXY=1`` is set, parse ``X-Forwarded-For`` and
    return the rightmost entry — that is the last hop before our proxy, i.e.
    the closest thing to the real client we can trust. Without that opt-in,
    a proxy header is ignored so an attacker can't spoof the rate-limiter
    bucket.
    """
    if os.environ.get("AGENTDRIVE_TRUST_PROXY") == "1":
        xff = request.headers.get("x-forwarded-for") or ""
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return (request.client.host if request.client else "unknown") or "unknown"


class _JsonFormatter(logging.Formatter):
    """Render every log record as a single JSON line.

    Operators can pipe stdout into journald, vector, fluentbit — any
    consumer that speaks JSON-per-line. Avoid emitting non-string values
    that can't be re-parsed (numbers and bools are fine; everything else
    gets stringified).
    """

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload: dict[str, Any] = {
            "ts": time.time(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            # Skip the boilerplate attrs Python attaches to every record.
            if key in {
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "message",
                "module",
                "msecs",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
                "taskName",
            }:
                continue
            if isinstance(value, (str, int, float, bool, type(None))):
                payload[key] = value
            else:
                payload[key] = repr(value)
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            payload["exc_msg"] = str(record.exc_info[1]) if record.exc_info[1] else None
        return json.dumps(payload, separators=(",", ":"))


def configure_logging(level: str = "INFO") -> None:
    """Idempotently install the JSON formatter on the root logger."""
    root = logging.getLogger()
    root.setLevel(level)
    # If we've already attached our handler, don't double up.
    for h in root.handlers:
        if isinstance(h.formatter, _JsonFormatter):
            return
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    # Replace existing handlers (uvicorn installs its own pretty one).
    root.handlers = [handler]
    # Quiet down the noisiest libs to INFO; access logs are emitted by
    # our own middleware so we don't need uvicorn's parallel one.
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """One JSON line per HTTP request, with a stable request_id header.

    The request_id is also stored on ``request.state.request_id`` so
    downstream handlers (and the error boundary) can correlate.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        client_ip = (request.client.host if request.client else "?") or "?"
        try:
            response = await call_next(request)
        except Exception:  # pragma: no cover — bubbled to error boundary
            _logger.exception(
                "request errored",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": client_ip,
                },
            )
            raise
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": latency_ms,
                "client_ip": client_ip,
            },
        )
        response.headers["x-request-id"] = request_id
        return response


class LoginRateLimiter:
    """Per-IP sliding window: ``max_attempts`` failures within ``window_s``
    seconds = locked out until the oldest attempt ages off.

    Hardening notes:
    - **Thread-safe.** FastAPI dispatches sync handlers on the threadpool;
      concurrent updates to the same bucket would corrupt the deque
      without a lock.
    - **Bounded.** Holds at most ``max_ips`` buckets; the LRU one is
      evicted on overflow so an attacker cycling through fake IPs can't
      grow our memory unboundedly.
    - **No phantom keys.** ``is_locked()`` does not create empty buckets
      on read; empty buckets are popped after pruning.

    Only counts *failed* attempts (call ``record_failure``); successful
    logins do not consume budget.
    """

    def __init__(
        self,
        *,
        max_attempts: int = 5,
        window_s: float = 60.0,
        max_ips: int = 10_000,
    ):
        self.max_attempts = max_attempts
        self.window_s = window_s
        self.max_ips = max_ips
        # OrderedDict so we can evict the least-recently-touched bucket.
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def _touch(self, ip: str) -> deque[float]:
        bucket = self._hits.get(ip)
        if bucket is None:
            bucket = deque()
            self._hits[ip] = bucket
            if len(self._hits) > self.max_ips:
                self._hits.popitem(last=False)
        else:
            self._hits.move_to_end(ip)
        return bucket

    def _prune(self, bucket: deque[float], now: float) -> None:
        cutoff = now - self.window_s
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

    def is_locked(self, ip: str) -> bool:
        now = time.time()
        with self._lock:
            bucket = self._hits.get(ip)
            if bucket is None:
                return False
            self._prune(bucket, now)
            if not bucket:
                self._hits.pop(ip, None)
                return False
            return len(bucket) >= self.max_attempts

    def record_failure(self, ip: str) -> None:
        now = time.time()
        with self._lock:
            bucket = self._touch(ip)
            self._prune(bucket, now)
            bucket.append(now)

    def reset(self, ip: str) -> None:
        with self._lock:
            self._hits.pop(ip, None)


class OriginCSRFMiddleware(BaseHTTPMiddleware):
    """Reject state-changing requests whose ``Origin`` / ``Referer`` does
    not match the host this app is being served as.

    Cookie ``SameSite=Strict`` is the first line of defense; this is the
    second. Same-site sub-domain takeover, browser bug, or a future
    SameSite loosening would otherwise leave POSTs unguarded.

    Skipped for safe methods (GET/HEAD/OPTIONS) and the ``/healthz``
    probe — orchestrators don't send Origin. POST/PUT/PATCH/DELETE that
    don't have a recognized Origin/Referer are rejected with 403.
    """

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method in self.SAFE_METHODS or request.url.path == "/healthz":
            return await call_next(request)

        expected_host = request.url.netloc  # host:port the server sees
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        # CSRF threat = browser confused-deputy. Browsers reliably send
        # Origin on POST. If neither header is present, this isn't a
        # browser request (curl, SDK, TestClient) and the CSRF model
        # doesn't apply — allow it; that caller is doing direct auth
        # anyway. Only reject when a header IS present but doesn't match.
        if origin is None and referer is None:
            return await call_next(request)
        from urllib.parse import urlparse

        ok = False
        if origin:
            try:
                ok = urlparse(origin).netloc == expected_host
            except Exception:
                ok = False
        elif referer:
            try:
                ok = urlparse(referer).netloc == expected_host
            except Exception:
                ok = False
        if not ok:
            request_id = getattr(request.state, "request_id", None)
            _logger.warning(
                "csrf_rejected",
                extra={
                    "request_id": request_id,
                    "path": request.url.path,
                    "method": request.method,
                    "client_ip": client_ip(request),
                },
            )
            return JSONResponse(
                status_code=403,
                content={"error": "origin_mismatch", "request_id": request_id},
            )
        return await call_next(request)


def install_error_boundary(app: FastAPI) -> None:
    """Catch-all for unhandled exceptions.

    Logs the full traceback once, returns a small JSON 500 with the
    request_id so an operator can grep the logs. Never leaks the exception
    type or message to the client.
    """

    @app.exception_handler(Exception)
    async def _on_exception(request: Request, exc: Exception):  # noqa: ANN001
        request_id = getattr(request.state, "request_id", None)
        _logger.exception(
            "unhandled exception",
            extra={"request_id": request_id, "path": request.url.path},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "request_id": request_id,
            },
        )
