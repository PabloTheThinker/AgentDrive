"""
Pytest configuration and shared fixtures for Agent Drive.

Provides isolated AGENTDRIVE_HOME per test (via context override) so tests
never touch the user's real ~/.agentdrive .
"""

import asyncio
import os
import tempfile
from collections.abc import Iterator
from datetime import UTC
from pathlib import Path

import fastapi.testclient as _fastapi_testclient
import httpx
import pytest

from agentdrive.constants import (
    reset_agentdrive_home_override,
    set_agentdrive_home_override,
)


class _InlineASGITestClient:
    """Small TestClient replacement for this sandbox's thread portal deadlock."""

    __test__ = False

    def __init__(
        self,
        app,
        *,
        follow_redirects: bool = True,
        base_url: str = "http://testserver",
        **_: object,
    ) -> None:
        self.app = app
        self.follow_redirects = follow_redirects
        self.base_url = base_url
        self.cookies = httpx.Cookies()

    def request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        follow_redirects = kwargs.pop("follow_redirects", self.follow_redirects)
        allow_redirects = kwargs.pop("allow_redirects", None)
        if allow_redirects is not None:
            follow_redirects = bool(allow_redirects)

        async def _send() -> httpx.Response:
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url=self.base_url,
                cookies=self.cookies,
                follow_redirects=bool(follow_redirects),
            ) as client:
                response = await client.request(method, url, **kwargs)
                self.cookies.update(client.cookies)
                return response

        return asyncio.run(_send())

    def get(self, url: str, **kwargs: object) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: object) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: object) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs: object) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: object) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        return None


_CODEX_SANDBOX = (
    os.environ.get("CODEX_CI") == "1" or os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED") == "1"
)

if _CODEX_SANDBOX:
    _fastapi_testclient.TestClient = _InlineASGITestClient


@pytest.fixture(autouse=True)
def isolated_agentdrive_home(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """
    Automatically give every test its own temporary Agent Drive home directory.
    This is the most important fixture for test isolation.
    """
    with tempfile.TemporaryDirectory(prefix="agentdrive-test-") as td:
        home = Path(td)
        token = set_agentdrive_home_override(home)
        # Also clear any AGENTDRIVE_HOME env the test process may have inherited
        monkeypatch.delenv("AGENTDRIVE_HOME", raising=False)
        monkeypatch.setenv("AGENTDRIVE_DISABLE_RETENTION_LOOP", "1")
        if _CODEX_SANDBOX:
            import anyio.to_thread

            async def _run_sync_inline(func, *args, **kwargs):  # noqa: ANN001, ANN202
                return func(*args)

            async def _asyncio_to_thread_inline(func, /, *args, **kwargs):  # noqa: ANN001, ANN202
                return func(*args, **kwargs)

            monkeypatch.setattr(anyio.to_thread, "run_sync", _run_sync_inline)
            monkeypatch.setattr(asyncio, "to_thread", _asyncio_to_thread_inline)
        try:
            yield home
        finally:
            reset_agentdrive_home_override(token)


@pytest.fixture
def sample_genome_dir(tmp_path: Path) -> Path:
    """A minimal valid genome directory for tests."""
    from datetime import datetime

    from agentdrive.genome.models import Genome, GenomeManifest

    gdir = tmp_path / "test-genome-v1"
    gdir.mkdir()

    manifest = GenomeManifest(
        id="test-genome",
        version="1.0.0",
        content_hash="sha256:" + "deadbeef" * 8,
        created=datetime.now(UTC),
        authors=[],
    )
    g = Genome(manifest=manifest, framework={"steps": [{"id": "1", "name": "test"}]})
    g.save(gdir)
    return gdir


@pytest.fixture
def registry(isolated_agentdrive_home: Path) -> "GenomeRegistry":
    from agentdrive.registry import GenomeRegistry

    return GenomeRegistry()
