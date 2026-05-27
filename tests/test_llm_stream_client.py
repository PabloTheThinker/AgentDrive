from __future__ import annotations

import httpx
import pytest

from agentdrive.providers.base import ProviderProfile
from agentdrive.web.chat import LLMStreamClient


def _profile(
    name: str, api_mode: str, base_url: str = "https://example.test/v1"
) -> ProviderProfile:
    return ProviderProfile(
        name=name,
        display_name=name.title(),
        description=f"{name} test provider",
        api_mode=api_mode,
        base_url=base_url,
        env_var=f"{name.upper()}_API_KEY",
        requires_key=False,
    )


@pytest.mark.anyio
async def test_openai_style_sse_parsing() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://example.test/v1/chat/completions"
        return httpx.Response(
            200,
            content=(
                b'data: {"choices":[{"delta":{"content":"hel"}}]}\n\n'
                b'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'
                b"data: [DONE]\n\n"
            ),
        )

    client = LLMStreamClient(
        _profile("openai", "chat_completions"),
        transport=httpx.MockTransport(handler),
    )

    chunks = [
        piece async for piece in client.stream_chat("gpt-test", [{"role": "user", "content": "hi"}])
    ]

    assert chunks == ["hel", "lo"]


@pytest.mark.anyio
async def test_anthropic_sse_parsing() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://example.test/v1/messages"
        assert request.headers["anthropic-version"] == "2023-06-01"
        return httpx.Response(
            200,
            content=(
                b"event: content_block_delta\n"
                b'data: {"type":"content_block_delta","delta":{"text":"hel"}}\n\n'
                b"event: content_block_delta\n"
                b'data: {"type":"content_block_delta","delta":{"text":"lo"}}\n\n'
            ),
        )

    client = LLMStreamClient(
        _profile("anthropic", "anthropic"),
        transport=httpx.MockTransport(handler),
    )

    chunks = [
        piece
        async for piece in client.stream_chat("claude-test", [{"role": "user", "content": "hi"}])
    ]

    assert chunks == ["hel", "lo"]


@pytest.mark.anyio
async def test_http_error_surfaces_as_chunk() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, content=b"bad key")

    client = LLMStreamClient(
        _profile("openai", "chat_completions"),
        transport=httpx.MockTransport(handler),
    )

    chunks = [
        piece async for piece in client.stream_chat("gpt-test", [{"role": "user", "content": "hi"}])
    ]

    assert chunks == ["[openai HTTP 401: bad key]"]
