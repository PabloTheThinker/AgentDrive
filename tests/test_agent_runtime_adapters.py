from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from agentdrive.runtime import load_runtime_config, resolve_adapter
from agentdrive.runtime.http_sse import HTTPSSEAdapter
from agentdrive.runtime.model import ModelAdapter


@pytest.mark.anyio
async def test_http_sse_adapter_parses_text_events() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert json.loads(request.content) == {"messages": [{"role": "user", "content": "hi"}]}
        return httpx.Response(
            200,
            content=(b'data: {"text":"hel"}\n\ndata: {"text":"lo"}\n\nevent: done\n\n'),
        )

    adapter = HTTPSSEAdapter(
        "ilo",
        {"kind": "http_sse", "url": "https://runtime.test/chat"},
        transport=httpx.MockTransport(handler),
    )

    chunks = [piece async for piece in adapter.stream([{"role": "user", "content": "hi"}])]

    assert chunks == ["hel", "lo"]


@pytest.mark.anyio
async def test_http_sse_adapter_surfaces_http_error_as_chunk() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, content=b"bad gateway")

    adapter = HTTPSSEAdapter(
        "ilo",
        {"kind": "http_sse", "url": "https://runtime.test/chat"},
        transport=httpx.MockTransport(handler),
    )

    chunks = [piece async for piece in adapter.stream([{"role": "user", "content": "hi"}])]

    assert chunks == ["[runtime ilo error: HTTP 502: bad gateway]"]


@pytest.mark.anyio
async def test_http_sse_adapter_uses_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ILO_RUNTIME_TOKEN", "secret-value")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret-value"
        return httpx.Response(200, content=b"data: [DONE]\n\n")

    adapter = HTTPSSEAdapter(
        "ilo",
        {
            "kind": "http_sse",
            "url": "https://runtime.test/chat",
            "auth_env": "ILO_RUNTIME_TOKEN",
        },
        transport=httpx.MockTransport(handler),
    )

    chunks = [piece async for piece in adapter.stream([{"role": "user", "content": "hi"}])]

    assert chunks == []


def test_model_adapter_explicit_provider_model_uses_profile() -> None:
    adapter = ModelAdapter(
        "bare-agent",
        {"kind": "model", "provider": "ollama", "model": "qwen3:14b"},
    )

    assert adapter.profile is not None
    assert adapter.profile.name == "ollama"
    assert adapter.model == "qwen3:14b"


def test_resolve_adapter_defaults_to_model_when_runtime_missing() -> None:
    adapter = resolve_adapter("missing-agent")

    assert isinstance(adapter, ModelAdapter)


def test_load_runtime_config_returns_model_for_missing_file(tmp_path: Path) -> None:
    assert load_runtime_config("missing-agent", home=tmp_path) == {"kind": "model"}
