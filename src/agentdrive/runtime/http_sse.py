"""HTTP + Server-Sent Events runtime adapter."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

from agentdrive.runtime.base import AgentRuntimeAdapter


class HTTPSSEAdapter(AgentRuntimeAdapter):
    """POST chat messages to an agent runtime and parse SSE text chunks."""

    kind = "http_sse"

    def __init__(
        self,
        agent_id: str,
        config: dict[str, Any],
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.config = dict(config)
        self.url = str(config.get("url") or "")
        self.auth_env = str(config.get("auth_env") or "")
        self.timeout_s = float(config.get("timeout_s") or 120)
        self.transport = transport

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        if not self.url:
            yield self._error("missing runtime url")
            return
        headers = self._headers()
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_s,
                transport=self.transport,
            ) as client:
                async with client.stream(
                    "POST",
                    self.url,
                    headers=headers,
                    json={"messages": messages},
                ) as resp:
                    if resp.status_code >= 400:
                        body = await resp.aread()
                        yield self._error(
                            f"HTTP {resp.status_code}: {body.decode('utf-8', 'replace')[:200]}"
                        )
                        return
                    event_lines: list[str] = []
                    async for line in resp.aiter_lines():
                        if line.strip():
                            event_lines.append(line)
                            continue
                        async for piece in self._pieces_from_event(event_lines):
                            yield piece
                        if self._is_done(event_lines):
                            return
                        event_lines = []
                    if event_lines:
                        async for piece in self._pieces_from_event(event_lines):
                            yield piece
        except httpx.HTTPError as exc:
            yield self._error(str(exc))

    async def health(self) -> dict[str, Any]:
        base = self.display_config()
        if not self.url:
            return {**base, "healthy": False, "detail": "missing url"}
        try:
            async with httpx.AsyncClient(
                timeout=min(self.timeout_s, 10),
                transport=self.transport,
            ) as client:
                resp = await client.head(self.url, headers=self._headers())
            if resp.status_code < 500:
                return {**base, "healthy": True, "detail": "connected"}
            return {
                **base,
                "healthy": False,
                "detail": f"HTTP {resp.status_code}",
            }
        except httpx.HTTPError as exc:
            return {**base, "healthy": False, "detail": str(exc)}

    def display_config(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind, "url": self.url}
        if self.auth_env:
            out["auth_env"] = self.auth_env
        return out

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "text/event-stream"}
        if self.auth_env:
            token = os.environ.get(self.auth_env, "")
            if token:
                headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _pieces_from_event(self, lines: list[str]) -> AsyncIterator[str]:
        if self._is_done(lines):
            return
        data_lines = [
            line.removeprefix("data:").strip() for line in lines if line.startswith("data:")
        ]
        if not data_lines:
            return
        payload = "\n".join(data_lines).strip()
        if payload == "[DONE]":
            return
        try:
            event = json.loads(payload)
        except ValueError:
            return
        text = event.get("text", "")
        if text:
            yield str(text)

    def _is_done(self, lines: list[str]) -> bool:
        for line in lines:
            clean = line.strip()
            if clean == "event: done":
                return True
            if clean == "data: [DONE]":
                return True
        return False

    def _error(self, detail: str) -> str:
        return f"[runtime {self.agent_id} error: {detail}]"
