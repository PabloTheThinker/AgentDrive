from __future__ import annotations

import json
from pathlib import Path

from agentdrive.providers import agent_providers
from agentdrive.providers.base import ProviderProfile


def _profile(name: str, default_model: str = "") -> ProviderProfile:
    return ProviderProfile(
        name=name,
        display_name=name.title(),
        description=f"{name} test provider",
        default_model=default_model or f"{name}-default",
        requires_key=False,
    )


def _write_config(home: Path, agent_id: str, data: dict) -> None:
    agent_dir = home / "agents" / agent_id
    agent_dir.mkdir(parents=True)
    (agent_dir / "providers.json").write_text(json.dumps(data), encoding="utf-8")


def test_no_config_returns_available_providers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    available = [_profile("openai"), _profile("ollama")]
    monkeypatch.setattr(agent_providers, "list_available", lambda: available)

    assert agent_providers.resolve_agent_providers("field-agent", home=tmp_path) == available


def test_allow_list_intersects_available_providers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    available = [_profile("openai"), _profile("ollama")]
    monkeypatch.setattr(agent_providers, "list_available", lambda: available)
    _write_config(
        tmp_path,
        "field-agent",
        {"providers": ["anthropic", "ollama", "missing"]},
    )

    providers = agent_providers.resolve_agent_providers("field-agent", home=tmp_path)

    assert [p.name for p in providers] == ["ollama"]


def test_star_allow_list_returns_all_available(
    tmp_path: Path,
    monkeypatch,
) -> None:
    available = [_profile("openai"), _profile("ollama")]
    monkeypatch.setattr(agent_providers, "list_available", lambda: available)
    _write_config(tmp_path, "field-agent", {"providers": ["*"]})

    assert agent_providers.resolve_agent_providers("field-agent", home=tmp_path) == available


def test_resolve_agent_default_honors_explicit_default(
    tmp_path: Path,
    monkeypatch,
) -> None:
    available = [_profile("openai", "gpt-default"), _profile("ollama", "llama3.2")]
    monkeypatch.setattr(agent_providers, "list_available", lambda: available)
    _write_config(
        tmp_path,
        "field-agent",
        {
            "providers": ["openai", "ollama"],
            "default": {"provider": "ollama", "model": "qwen3:14b"},
        },
    )

    assert agent_providers.resolve_agent_default("field-agent", home=tmp_path) == (
        "ollama",
        "qwen3:14b",
    )


def test_resolve_agent_default_picks_first_available_without_default(
    tmp_path: Path,
    monkeypatch,
) -> None:
    available = [_profile("openai", "gpt-default"), _profile("ollama", "llama3.2")]
    monkeypatch.setattr(agent_providers, "list_available", lambda: available)

    assert agent_providers.resolve_agent_default("field-agent", home=tmp_path) == (
        "openai",
        "gpt-default",
    )
