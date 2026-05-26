"""Tests for ``agentdrive.local_models`` — the AgentDrive local-model adapter layer.

HTTP is mocked at the ``httpx`` boundary via ``unittest.mock`` — no test
touches a real Ollama / LM Studio / vLLM endpoint.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from agentdrive import local_models
from agentdrive.local_models import (
    LocalModelAdapter,
    LocalModelError,
    LocalModelSpec,
    OllamaAdapter,
    OpenAICompatAdapter,
    generate,
    get_adapter,
    get_local_models_path,
    load_specs,
)

# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _mock_resp(
    status: int = 200,
    json_body: dict[str, Any] | None = None,
    text: str = "",
) -> MagicMock:
    """Build a ``httpx.Response``-shaped mock."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.text = text or (json.dumps(json_body) if json_body is not None else "")
    if json_body is None:
        resp.json.side_effect = json.JSONDecodeError("no body", "", 0)
    else:
        resp.json.return_value = json_body
    return resp


# ─────────────────────────────────────────────────────────────────────
# Loader / config-file tests
# ─────────────────────────────────────────────────────────────────────


def test_load_specs_creates_default_file_if_missing() -> None:
    path = get_local_models_path()
    assert not path.exists()
    specs = load_specs()
    assert path.exists(), "loader must scaffold the default YAML"
    text = path.read_text()
    assert "AgentDrive local LLM backends" in text
    # Default ships two Ollama entries (qwen-coder + qwen-reasoner).
    names = {s.name for s in specs}
    assert {"qwen-coder", "qwen-reasoner"} <= names
    for s in specs:
        assert s.backend == "ollama"
        assert s.endpoint.startswith("http://")


def test_load_specs_parses_yaml(tmp_path: Path) -> None:
    yaml_path = tmp_path / "custom.yaml"
    yaml_path.write_text(
        """
models:
  - name: lm-studio-local
    backend: openai-compat
    model: qwen2.5-coder
    endpoint: http://127.0.0.1:1234
    api_key: sk-abc
  - name: vllm-cluster
    backend: openai-compat
    model: meta-llama/Llama-3.1-70B-Instruct
    endpoint: http://internal-vllm:8000
    timeout_s: 120
  - {}  # malformed — must be skipped, not crash
""".strip()
    )
    specs = load_specs(yaml_path)
    assert len(specs) == 2
    by_name = {s.name: s for s in specs}
    assert by_name["lm-studio-local"].api_key == "sk-abc"
    assert by_name["lm-studio-local"].backend == "openai-compat"
    assert by_name["vllm-cluster"].timeout_s == 120.0


# ─────────────────────────────────────────────────────────────────────
# Adapter registry
# ─────────────────────────────────────────────────────────────────────


def test_get_adapter_returns_none_for_unknown_backend() -> None:
    assert get_adapter("does-not-exist") is None
    # Both built-in adapters must be present.
    assert isinstance(get_adapter("ollama"), OllamaAdapter)
    assert isinstance(get_adapter("openai-compat"), OpenAICompatAdapter)


# ─────────────────────────────────────────────────────────────────────
# OllamaAdapter
# ─────────────────────────────────────────────────────────────────────


def test_ollama_adapter_is_available_handles_connection_refused() -> None:
    adapter = OllamaAdapter()
    spec = LocalModelSpec(backend="ollama", model="qwen3:14b", endpoint="http://127.0.0.1:11434")
    with patch.object(local_models.httpx, "get", side_effect=httpx.ConnectError("refused")):
        assert adapter.is_available(spec) is False


def test_ollama_adapter_is_available_true_when_model_listed() -> None:
    adapter = OllamaAdapter()
    spec = LocalModelSpec(
        backend="ollama",
        model="qwen2.5-coder:14b",
        endpoint="http://127.0.0.1:11434",
    )
    resp = _mock_resp(200, {"models": [{"name": "qwen2.5-coder:14b"}]})
    with patch.object(local_models.httpx, "get", return_value=resp):
        assert adapter.is_available(spec) is True


def test_ollama_adapter_generate_parses_response() -> None:
    adapter = OllamaAdapter()
    spec = LocalModelSpec(
        backend="ollama",
        model="qwen3:14b",
        endpoint="http://127.0.0.1:11434",
    )
    resp = _mock_resp(200, {"response": "hello world", "done": True})
    with patch.object(local_models.httpx, "post", return_value=resp) as post:
        out = adapter.generate(spec, "say hi", system="be brief")
        assert out == "hello world"
        # Confirm body shape: /api/generate, system passed, stream off.
        assert post.call_args.args[0].endswith("/api/generate")
        body = post.call_args.kwargs["json"]
        assert body["model"] == "qwen3:14b"
        assert body["prompt"] == "say hi"
        assert body["system"] == "be brief"
        assert body["stream"] is False


# ─────────────────────────────────────────────────────────────────────
# OpenAICompatAdapter
# ─────────────────────────────────────────────────────────────────────


def test_openai_compat_adapter_generate_with_bearer() -> None:
    adapter = OpenAICompatAdapter()
    spec = LocalModelSpec(
        backend="openai-compat",
        model="qwen2.5-coder",
        endpoint="http://127.0.0.1:1234",
        api_key="sk-local",
    )
    resp = _mock_resp(
        200,
        {"choices": [{"message": {"role": "assistant", "content": "hi back"}}]},
    )
    with patch.object(local_models.httpx, "post", return_value=resp) as post:
        out = adapter.generate(spec, "ping", system="you are a bot")
        assert out == "hi back"
        called_url = post.call_args.args[0]
        assert called_url == "http://127.0.0.1:1234/v1/chat/completions"
        headers = post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer sk-local"
        body = post.call_args.kwargs["json"]
        assert body["model"] == "qwen2.5-coder"
        assert body["messages"][0] == {"role": "system", "content": "you are a bot"}
        assert body["messages"][1] == {"role": "user", "content": "ping"}


def test_openai_compat_adapter_handles_4xx_gracefully() -> None:
    adapter = OpenAICompatAdapter()
    spec = LocalModelSpec(
        backend="openai-compat",
        model="missing-model",
        endpoint="http://127.0.0.1:1234",
    )
    resp = _mock_resp(404, text="model not found")
    with patch.object(local_models.httpx, "post", return_value=resp):
        with pytest.raises(LocalModelError) as exc_info:
            adapter.generate(spec, "ping")
        assert "404" in str(exc_info.value)


def test_openai_compat_adapter_normalizes_v1_suffix() -> None:
    """Endpoint without trailing /v1 must still hit /v1/models on probe."""
    adapter = OpenAICompatAdapter()
    spec = LocalModelSpec(backend="openai-compat", model="x", endpoint="http://host:9000")
    resp = _mock_resp(200, {"data": []})
    with patch.object(local_models.httpx, "get", return_value=resp) as get:
        assert adapter.is_available(spec) is True
        assert get.call_args.args[0] == "http://host:9000/v1/models"


# ─────────────────────────────────────────────────────────────────────
# Top-level dispatcher
# ─────────────────────────────────────────────────────────────────────


def test_top_level_generate_dispatches_to_correct_adapter() -> None:
    spec = LocalModelSpec(backend="openai-compat", model="x", endpoint="http://h:1/v1")

    class _Fake(LocalModelAdapter):
        BACKEND = "openai-compat"
        seen: dict[str, Any] = {}

        def is_available(self, spec):  # noqa: D401
            return True

        def generate(self, spec, prompt, *, system=""):
            self.seen["spec"] = spec
            self.seen["prompt"] = prompt
            self.seen["system"] = system
            return "fake-output"

    fake = _Fake()
    original = get_adapter("openai-compat")
    local_models.register_adapter(fake)
    try:
        out = generate(spec, "hi", system="sys")
        assert out == "fake-output"
        assert fake.seen["prompt"] == "hi"
        assert fake.seen["system"] == "sys"
        assert fake.seen["spec"] is spec
    finally:
        # Restore the real adapter so other tests aren't perturbed.
        if original is not None:
            local_models.register_adapter(original)


def test_top_level_generate_raises_for_unknown_backend() -> None:
    spec = LocalModelSpec(backend="nope", model="x", endpoint="http://h:1")
    with pytest.raises(LocalModelError):
        generate(spec, "hi")
