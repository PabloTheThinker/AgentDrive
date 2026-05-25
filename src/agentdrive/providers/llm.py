"""
SavantLLM — lightweight chat completion client for any configured provider.

Usage:
    llm = SavantLLM()
    reply = llm.chat("What does this code do?")

    # Or with system prompt and history:
    reply = llm.chat("Explain this genome", system="You are a DNA analyst.")

    # Stream:
    for chunk in llm.stream("Tell me about my pool"):
        print(chunk, end="")
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Generator
from typing import Any

import httpx

from agentdrive.config import get_config_value
from agentdrive.providers.base import ProviderProfile, get, load_config_provider

logger = logging.getLogger(__name__)


class SavantLLM:
    """Lightweight LLM client using the configured provider."""

    def __init__(self, provider_name: str | None = None, model: str | None = None):
        self.provider: ProviderProfile | None = None
        self.model: str = ""
        self._resolve_provider(provider_name, model)

    def _resolve_provider(self, provider_name: str | None, model: str | None):
        cfg = load_config_provider()
        if cfg:
            cfg_name, cfg_model = cfg
        else:
            cfg_name, cfg_model = None, ""

        pname = provider_name or cfg_name
        self.model = model or cfg_model or ""

        if pname:
            self.provider = get(pname)

        if not self.provider:
            from agentdrive.providers.base import detect

            self.provider = detect()

        if not self.provider:
            self.provider = get("openai")

        if not self.model and self.provider:
            self.model = self.provider.default_model

    @property
    def base_url(self) -> str:
        override = get_config_value("provider.base_url", "")
        if override:
            return override
        return self.provider.base_url if self.provider else ""

    def _headers(self) -> dict[str, str]:
        h = {
            "Content-Type": "application/json",
        }
        if not self.provider:
            return h
        key = self.provider.get_api_key()
        if key:
            if self.provider.api_mode == "anthropic":
                h["x-api-key"] = key
                h["anthropic-version"] = "2023-06-01"
            else:
                h["Authorization"] = f"Bearer {key}"
        return h

    def _build_body(self, messages: list[dict], system: str = "", **kwargs) -> dict:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            **kwargs,
        }
        if system and self.provider and self.provider.api_mode == "anthropic":
            body["system"] = system
        elif system:
            body["messages"].insert(0, {"role": "system", "content": system})
        return body

    def chat(
        self,
        prompt: str,
        system: str = "",
        history: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        messages = list(history or [])
        messages.append({"role": "user", "content": prompt})

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        body = self._build_body(
            messages, system=system, temperature=temperature, max_tokens=max_tokens
        )

        try:
            resp = httpx.post(url, headers=self._headers(), json=body, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            choice = data.get("choices", [{}])[0]
            return choice.get("message", {}).get("content", "")
        except httpx.HTTPStatusError as e:
            # Log only the status code — provider response bodies can echo back
            # Authorization headers, key-validation messages, or quoted request
            # payloads. Operators who need the full body for debugging can
            # enable AGENTDRIVE_LOG_PROVIDER_BODIES=1 in an environment that
            # is not retained in shared log aggregators.
            logger.error("LLM API error: HTTP %s from provider", e.response.status_code)
            if os.environ.get("AGENTDRIVE_LOG_PROVIDER_BODIES") == "1":
                logger.debug(
                    "LLM error body (first 300 chars, opt-in): %s",
                    e.response.text[:300],
                )
            return f"[API error: {e.response.status_code}]"
        except Exception as e:
            # Bare repr() to keep arbitrary exception payloads out of the log.
            logger.error("LLM request failed: %s", type(e).__name__)
            return f"[Error: {type(e).__name__}]"

    def stream(
        self,
        prompt: str,
        system: str = "",
        history: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Generator[str, None, None]:
        messages = list(history or [])
        messages.append({"role": "user", "content": prompt})

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        body = self._build_body(
            messages,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        try:
            with httpx.Client(timeout=120) as client:
                with client.stream("POST", url, headers=self._headers(), json=body) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line or line.startswith(":"):
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
        except httpx.HTTPStatusError as e:
            yield f"[API error: {e.response.status_code}]"
        except Exception as e:
            yield f"[Error: {e}]"

    def query_pool(self, question: str) -> str:
        from agentdrive.drive.drive import get_default_drive

        pool = get_default_drive()
        packets = pool.get_dna_for_task(question, top_k=5)

        context = ""
        if packets:
            genome_list = "\n".join(
                f"- {p['genome_id']} (score: {p['relevance_score']:.2f}): {p.get('why_relevant', '')[:120]}"
                for p in packets
            )
            context = f"Relevant genomes from my AgentDrive:\n{genome_list}"

        system = (
            "You are Savant, an AI assistant for the Savant Framework — a living ecosystem "
            "for agent DNA (genomes, reasoning patterns, frameworks). "
            "Answer questions helpfully, reference the user's pool genomes when relevant, "
            "and suggest actions like querying, importing, or creating new genomes."
        )

        full_prompt = question
        if context:
            full_prompt = f"{context}\n\nUser question: {question}"

        return self.chat(full_prompt, system=system)

    def stream_query_pool(self, question: str) -> Generator[str, None, None]:
        from agentdrive.drive.drive import get_default_drive

        pool = get_default_drive()
        packets = pool.get_dna_for_task(question, top_k=5)

        context = ""
        if packets:
            genome_list = "\n".join(
                f"- {p['genome_id']} (score: {p['relevance_score']:.2f}): {p.get('why_relevant', '')[:120]}"
                for p in packets
            )
            context = f"Relevant genomes:\n{genome_list}"

        system = (
            "You are Savant, an AI assistant for the Savant Framework — a living ecosystem "
            "for agent DNA. Reference the user's pool genomes when relevant."
        )

        full_prompt = question
        if context:
            full_prompt = f"{context}\n\nUser: {question}"

        yield from self.stream(full_prompt, system=system)
