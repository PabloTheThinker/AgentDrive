"""Local-model adapter layer for AgentDrive.

A small, dependency-free dispatch layer so the healing-loop repair swarm —
and, eventually, any Agent Drive LLM call that wants to target a locally hosted
model — can talk to *any* local backend without code paths that hard-code
Ollama.

The shape follows the standard ``providers/`` adapter pattern used by
mature multi-backend agent CLIs:

* Each backend has a ``LocalModelAdapter`` subclass that knows three things:
  how to probe its endpoint (``is_available``), how to do a single
  synchronous generation (``generate``), and what its ``BACKEND`` identifier
  is.  A module-level ``register_adapter`` collects them into a registry.
* Adapters declare their fields via a single ``LocalModelSpec`` dataclass.
  Adapters do not own configuration — that's the loader's job.
* The user-facing surface is a YAML file at ``~/.agentdrive/local_models.yaml``.
  The loader creates a sensible default file on first read so the user has
  something to edit.
* Probing is silent: a failed probe just means "this spec isn't reachable
  right now".  Callers iterate, skip the unreachable, and dispatch with
  whatever survives — a "fall back, don't crash" policy.

v1 ships two adapters:

* :class:`OllamaAdapter` — native Ollama (``/api/generate`` + ``/api/tags``).
* :class:`OpenAICompatAdapter` — ``/v1/chat/completions`` for LM Studio,
  vLLM, llama.cpp HTTP server, and anything else that speaks the OpenAI
  REST surface.  An optional bearer token covers the few backends that
  want one.

All network calls go through ``httpx`` (already a project dependency) with
short, configurable timeouts.  No new third-party packages.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import httpx
import yaml

from agentdrive.constants import get_agentdrive_home

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Errors + dataclass
# ─────────────────────────────────────────────────────────────────────


class LocalModelError(Exception):
    """Raised by ``LocalModelAdapter.generate`` on backend failure."""


@dataclass
class LocalModelSpec:
    """Connection metadata for one configured local model.

    Backends are identified by string id (``"ollama"``, ``"openai-compat"``,
    …) so the YAML stays human-friendly. ``name`` is a free-form label the
    operator uses to reference the spec in CLI output.
    """

    backend: str
    model: str
    endpoint: str
    name: str = ""
    timeout_s: float = 90.0
    api_key: str | None = None
    # Free-form options bag — used by adapters that need extra knobs
    # without polluting the top-level shape (e.g. Ollama ``num_predict``).
    options: dict[str, object] = field(default_factory=dict)

    def display_name(self) -> str:
        return self.name or f"{self.backend}:{self.model}"


# ─────────────────────────────────────────────────────────────────────
# Adapter base + registry
# ─────────────────────────────────────────────────────────────────────


class LocalModelAdapter(ABC):
    """Abstract base — one subclass per local backend.

    Subclasses set ``BACKEND`` to the string id used in ``LocalModelSpec``.
    """

    BACKEND: ClassVar[str] = ""

    @abstractmethod
    def is_available(self, spec: LocalModelSpec) -> bool:
        """Probe the endpoint. Must return quickly (<2s) without raising."""

    @abstractmethod
    def generate(self, spec: LocalModelSpec, prompt: str, *, system: str = "") -> str:
        """Synchronous generate. Raises :class:`LocalModelError` on failure."""


_REGISTRY: dict[str, LocalModelAdapter] = {}


def register_adapter(adapter: LocalModelAdapter) -> None:
    """Add (or replace) an adapter in the registry by ``BACKEND``."""
    if not adapter.BACKEND:
        raise ValueError("LocalModelAdapter must set BACKEND")
    _REGISTRY[adapter.BACKEND] = adapter


def get_adapter(backend: str) -> LocalModelAdapter | None:
    """Return the registered adapter for ``backend``, or ``None``."""
    return _REGISTRY.get(backend)


def list_backends() -> list[str]:
    """Return all registered backend ids (stable order)."""
    return sorted(_REGISTRY.keys())


# ─────────────────────────────────────────────────────────────────────
# OllamaAdapter — native Ollama HTTP API
# ─────────────────────────────────────────────────────────────────────


class OllamaAdapter(LocalModelAdapter):
    """Native Ollama backend.

    * Probe via ``GET <endpoint>/api/tags``; checks the requested model is
      in the daemon's loaded list (exact id or tag-prefix match).
    * Generate via ``POST <endpoint>/api/generate`` with ``stream=false``.
    """

    BACKEND: ClassVar[str] = "ollama"

    _PROBE_TIMEOUT_S: ClassVar[float] = 2.0

    def is_available(self, spec: LocalModelSpec) -> bool:
        url = spec.endpoint.rstrip("/") + "/api/tags"
        try:
            resp = httpx.get(url, timeout=self._PROBE_TIMEOUT_S)
            if resp.status_code != 200:
                return False
            payload = resp.json()
        except Exception as exc:
            logger.debug("ollama probe %s failed: %s", spec.endpoint, exc)
            return False
        names = {m.get("name", "") for m in payload.get("models", [])}
        return spec.model in names or any(n.startswith(spec.model) for n in names if n)

    def generate(self, spec: LocalModelSpec, prompt: str, *, system: str = "") -> str:
        url = spec.endpoint.rstrip("/") + "/api/generate"
        body: dict[str, object] = {
            "model": spec.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            body["system"] = system
        # Pass through any caller-supplied Ollama options (num_predict, etc.).
        opts = {k: v for k, v in spec.options.items() if v is not None}
        if opts:
            body["options"] = opts
        try:
            resp = httpx.post(url, json=body, timeout=spec.timeout_s)
        except httpx.HTTPError as exc:
            raise LocalModelError(f"ollama request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise LocalModelError(f"ollama HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            raise LocalModelError(f"ollama returned non-JSON: {exc}") from exc
        return data.get("response", "") or ""


register_adapter(OllamaAdapter())


# ─────────────────────────────────────────────────────────────────────
# OpenAICompatAdapter — LM Studio / vLLM / llama.cpp / generic
# ─────────────────────────────────────────────────────────────────────


class OpenAICompatAdapter(LocalModelAdapter):
    """OpenAI-compatible local backend.

    One adapter covers LM Studio, vLLM, llama.cpp's HTTP server, and any
    other endpoint that speaks ``/v1/chat/completions``.

    * Probe via ``GET <endpoint>/v1/models``.
    * Generate via ``POST <endpoint>/v1/chat/completions``.
    * Optional ``Authorization: Bearer <api_key>`` header — some local
      servers want one (vLLM with ``--api-key``, hosted LM Studio
      deployments, …), most don't.
    """

    BACKEND: ClassVar[str] = "openai-compat"

    _PROBE_TIMEOUT_S: ClassVar[float] = 2.0

    @staticmethod
    def _base(spec: LocalModelSpec) -> str:
        base = spec.endpoint.rstrip("/")
        # Accept either a bare host (http://x:1234) or one that already
        # ends with /v1 — normalize so callers can configure either.
        if not base.endswith("/v1"):
            base += "/v1"
        return base

    def _headers(self, spec: LocalModelSpec) -> dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if spec.api_key:
            h["Authorization"] = f"Bearer {spec.api_key}"
        return h

    def is_available(self, spec: LocalModelSpec) -> bool:
        url = self._base(spec) + "/models"
        try:
            resp = httpx.get(url, headers=self._headers(spec), timeout=self._PROBE_TIMEOUT_S)
        except Exception as exc:
            logger.debug("openai-compat probe %s failed: %s", spec.endpoint, exc)
            return False
        return resp.status_code == 200

    def generate(self, spec: LocalModelSpec, prompt: str, *, system: str = "") -> str:
        url = self._base(spec) + "/chat/completions"
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body: dict[str, object] = {
            "model": spec.model,
            "messages": messages,
            "stream": False,
        }
        # Pass through options the caller put on the spec (max_tokens,
        # temperature, …). We don't validate — that's the server's job.
        for k, v in spec.options.items():
            if v is not None:
                body[k] = v
        try:
            resp = httpx.post(url, headers=self._headers(spec), json=body, timeout=spec.timeout_s)
        except httpx.HTTPError as exc:
            raise LocalModelError(f"openai-compat request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise LocalModelError(f"openai-compat HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            raise LocalModelError(f"openai-compat returned non-JSON: {exc}") from exc
        choices = data.get("choices") or []
        if not choices:
            return ""
        msg = choices[0].get("message") or {}
        return msg.get("content", "") or ""


register_adapter(OpenAICompatAdapter())


# ─────────────────────────────────────────────────────────────────────
# Top-level dispatcher
# ─────────────────────────────────────────────────────────────────────


def generate(spec: LocalModelSpec, prompt: str, *, system: str = "") -> str:
    """Dispatch to the adapter for ``spec.backend``.

    Raises :class:`LocalModelError` if no adapter is registered for the
    spec's backend, or if the underlying adapter fails.
    """
    adapter = get_adapter(spec.backend)
    if adapter is None:
        raise LocalModelError(f"no adapter registered for backend {spec.backend!r}")
    return adapter.generate(spec, prompt, system=system)


def is_available(spec: LocalModelSpec) -> bool:
    """Convenience: probe ``spec`` via its adapter. Returns False on miss."""
    adapter = get_adapter(spec.backend)
    if adapter is None:
        return False
    try:
        return adapter.is_available(spec)
    except Exception as exc:
        logger.debug("is_available(%s) raised: %s", spec.display_name(), exc)
        return False


# ─────────────────────────────────────────────────────────────────────
# YAML config loader
# ─────────────────────────────────────────────────────────────────────


_DEFAULT_YAML = """\
# AgentDrive local LLM backends.
#
# Each entry registers a local model Agent Drive can dispatch to. The healing
# loop and any future LocalModelAdapter consumer iterates this list and
# uses the entries whose endpoint probes succeed at runtime. Failures are
# silent — only configured + reachable models get used, so it's safe to
# leave entries here for backends you haven't started yet.
#
# Supported backends:
#   - ollama        : native Ollama daemon  (http://127.0.0.1:11434)
#   - openai-compat : LM Studio / vLLM / llama.cpp server / any
#                     OpenAI-compatible /v1/chat/completions endpoint
models:
  - name: qwen-coder
    backend: ollama
    model: qwen2.5-coder:14b
    endpoint: http://127.0.0.1:11434

  - name: qwen-reasoner
    backend: ollama
    model: qwen3:14b
    endpoint: http://127.0.0.1:11434

  # Examples (uncomment + edit to enable):
  # - name: local-lmstudio
  #   backend: openai-compat
  #   model: qwen2.5-coder
  #   endpoint: http://127.0.0.1:1234
  #
  # - name: vllm-cluster
  #   backend: openai-compat
  #   model: meta-llama/Llama-3.1-70B-Instruct
  #   endpoint: http://internal-vllm:8000
  #   api_key: sk-local
"""


def get_local_models_path() -> Path:
    """Resolve ``$AGENTDRIVE_HOME/local_models.yaml`` (does not create it)."""
    return get_agentdrive_home() / "local_models.yaml"


def _ensure_default_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(_DEFAULT_YAML)


def _coerce_spec(raw: dict[str, object], *, source: str) -> LocalModelSpec | None:
    """Build a LocalModelSpec from one YAML entry, logging + skipping bad rows."""
    if not isinstance(raw, dict):
        logger.warning("local_models.yaml (%s): entry is not a mapping, skipped", source)
        return None
    backend = str(raw.get("backend") or "").strip()
    model = str(raw.get("model") or "").strip()
    endpoint = str(raw.get("endpoint") or "").strip()
    if not (backend and model and endpoint):
        logger.warning(
            "local_models.yaml (%s): entry missing backend/model/endpoint, skipped",
            source,
        )
        return None
    name = str(raw.get("name") or "").strip()
    timeout_s = float(raw.get("timeout_s") or 90.0)
    api_key = raw.get("api_key")
    api_key_s = str(api_key).strip() if api_key else None
    options = raw.get("options") or {}
    if not isinstance(options, dict):
        options = {}
    return LocalModelSpec(
        backend=backend,
        model=model,
        endpoint=endpoint,
        name=name,
        timeout_s=timeout_s,
        api_key=api_key_s,
        options=dict(options),
    )


def load_specs(path: Path | None = None) -> list[LocalModelSpec]:
    """Load configured local-model specs from YAML.

    If the file is missing, write the default scaffold first so the user
    has something to edit; then parse it.  Malformed entries are logged
    and skipped, never raised — the caller iterates whatever survives.
    """
    target = Path(path) if path else get_local_models_path()
    _ensure_default_file(target)
    try:
        text = target.read_text()
    except OSError as exc:
        logger.warning("could not read %s: %s", target, exc)
        return []
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        logger.warning("local_models.yaml parse error: %s", exc)
        return []
    entries = data.get("models") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return []
    specs: list[LocalModelSpec] = []
    for raw in entries:
        spec = _coerce_spec(raw, source=str(target))
        if spec is not None:
            specs.append(spec)
    return specs


__all__ = [
    "LocalModelError",
    "LocalModelSpec",
    "LocalModelAdapter",
    "OllamaAdapter",
    "OpenAICompatAdapter",
    "register_adapter",
    "get_adapter",
    "list_backends",
    "generate",
    "is_available",
    "load_specs",
    "get_local_models_path",
]
