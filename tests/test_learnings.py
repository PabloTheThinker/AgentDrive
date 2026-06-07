"""Tests for gstack-style learnings JSONL store + harness integration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentdrive.constants import get_learnings_dir
from agentdrive.drive.drive import AgentDrive
from agentdrive.harness.harness import Harness
from agentdrive.learnings import LearningsStore, ingest_learnings_to_experience
from agentdrive.learnings.store import resolve_learnings_slug


def _sample_entry(
    *,
    key: str = "pytest-fixture",
    insight: str = "Use isolated AGENTDRIVE_HOME in tests",
    ts: str = "2026-06-01T00:00:00+00:00",
    learning_type: str = "pattern",
) -> dict:
    return {
        "skill": "harness",
        "type": learning_type,
        "key": key,
        "insight": insight,
        "confidence": 8,
        "source": "observed",
        "ts": ts,
    }


def test_learnings_dir_uses_isolated_home(isolated_agentdrive_home: Path) -> None:
    assert get_learnings_dir() == isolated_agentdrive_home / "learnings"


def test_log_search_count_and_dedup(isolated_agentdrive_home: Path) -> None:
    store = LearningsStore(slug="test-project")
    store.log(_sample_entry(key="foo", insight="foo related guidance", ts="2026-06-01T00:00:00+00:00"))
    store.log(
        _sample_entry(
            key="foo",
            insight="updated foo guidance",
            ts="2026-06-02T00:00:00+00:00",
            learning_type="pattern",
        )
    )
    store.log(
        _sample_entry(
            key="bar",
            insight="bar related guidance",
            ts="2026-06-03T00:00:00+00:00",
            learning_type="pitfall",
        )
    )

    assert store.count() == 2
    hits = store.search("foo bar", limit=5)
    assert len(hits) == 2
    keys = {h["key"] for h in hits}
    assert keys == {"foo", "bar"}
    foo_hit = next(h for h in hits if h["key"] == "foo")
    assert foo_hit["insight"] == "updated foo guidance"

    recent = store.list_recent(limit=1)
    assert len(recent) == 1
    assert recent[0]["key"] == "bar"


def test_log_validation_errors() -> None:
    store = LearningsStore(slug="validation")
    with pytest.raises(ValueError, match="invalid learning type"):
        store.log({"type": "bogus", "key": "x", "insight": "nope", "confidence": 5})
    with pytest.raises(ValueError, match="key must be alphanumeric"):
        store.log({"type": "pattern", "key": "bad key", "insight": "nope", "confidence": 5})
    with pytest.raises(ValueError, match="confidence must be"):
        store.log({"type": "pattern", "key": "ok", "insight": "nope", "confidence": 11})


def test_resolve_learnings_slug_from_git_repo(tmp_path: Path) -> None:
    repo = tmp_path / "My-Project"
    repo.mkdir()
    (repo / ".git").mkdir()
    assert resolve_learnings_slug(repo) == "My-Project"


def test_resolve_learnings_slug_defaults_without_git(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plain = tmp_path / "nowhere"
    plain.mkdir()
    monkeypatch.setattr("agentdrive.learnings.store._git_repo_root", lambda _p: None)
    assert resolve_learnings_slug(plain) == "default"


def test_ingest_learnings_to_experience_is_idempotent(isolated_agentdrive_home: Path) -> None:
    slug = "ingest-test"
    store = LearningsStore(slug=slug)
    store.log(_sample_entry(key="ingest-a", insight="first learning"))
    store.log(
        _sample_entry(
            key="ingest-b",
            insight="second learning",
            ts="2026-06-02T00:00:00+00:00",
            learning_type="operational",
        )
    )

    drive = AgentDrive()
    obs_dir = drive.drive_path / "living-experience"

    first = ingest_learnings_to_experience(drive, slug)
    second = ingest_learnings_to_experience(drive, slug)

    assert first == 2
    assert second == 0
    assert len(list(obs_dir.glob("learnings-ingest-test-*.json"))) == 2

    sample = json.loads(next(obs_dir.glob("learnings-ingest-test-*.json")).read_text())
    assert sample["page_type"] == "living-experience"
    assert sample["type"] == "learning"
    assert sample["content"]["project_slug"] == slug


def test_harness_record_learning_and_compose_context(isolated_agentdrive_home: Path) -> None:
    harness = Harness(agent_id="test-agent")
    harness.current_task = "fix pytest isolation failures"

    harness.record_learning(
        insight="Always use isolated_agentdrive_home fixture",
        key="pytest-isolation",
        learning_type="pattern",
        slug="harness-test",
    )
    harness.record_learning(
        insight="Reset global singletons between tests",
        key="singleton-reset",
        learning_type="operational",
        slug="harness-test",
    )

    composed = harness.compose_context("Base task prompt", slug="harness-test")

    assert "Base task prompt" in composed
    assert "Project learnings:" in composed
    assert "[pytest-isolation]" in composed
    assert "isolated_agentdrive_home" in composed