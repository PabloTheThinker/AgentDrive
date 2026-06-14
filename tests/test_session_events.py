"""Tests for Pattern 1 session event recording and replay."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from agentdrive.events import MessageDelta, PoolMatch, default_bus, emit
from agentdrive.session_events import (
    SessionEventRecorder,
    filter_events_by_type,
    format_event_summary,
    format_type_histogram,
    replay_events,
    session_events_path,
    summarize_event_types,
)


@pytest.fixture
def clean_bus() -> Iterator[None]:
    """Isolate default_bus subscribers for the duration of a test."""
    with default_bus._lock:  # type: ignore[attr-defined]
        saved = list(default_bus._subs)  # type: ignore[attr-defined]
        default_bus._subs.clear()  # type: ignore[attr-defined]
    try:
        yield
    finally:
        with default_bus._lock:  # type: ignore[attr-defined]
            default_bus._subs = saved  # type: ignore[attr-defined]


def test_session_events_path(isolated_agentdrive_home: Path) -> None:
    path = session_events_path("my-agent", "sess-123")
    assert path == (
        isolated_agentdrive_home / "agents" / "my-agent" / "sessions" / "sess-123" / "events.jsonl"
    )


def test_session_event_recorder_writes_jsonl(
    isolated_agentdrive_home: Path, clean_bus: None
) -> None:
    recorder = SessionEventRecorder("evt-agent", "sess-abc")
    recorder.attach()
    try:
        emit(MessageDelta(text="hello", session_id="sess-abc"))
        emit(PoolMatch(genomes=["g1"], scores=[0.9], session_id="sess-abc"))
    finally:
        recorder.close()

    events = replay_events(recorder.path)
    assert len(events) == 2
    assert events[0]["type"] == "MessageDelta"
    assert events[0]["text"] == "hello"
    assert events[1]["type"] == "PoolMatch"
    assert events[1]["genomes"] == ["g1"]


def test_session_event_recorder_context_manager(
    isolated_agentdrive_home: Path, clean_bus: None
) -> None:
    with SessionEventRecorder("ctx-agent", "sess-ctx") as recorder:
        emit(MessageDelta(text="via ctx"))
    assert recorder.path.exists()
    assert len(replay_events(recorder.path)) == 1


def test_replay_events_skips_bad_lines(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text(
        '{"type":"MessageDelta","text":"ok"}\n'
        "not json\n"
        "\n"
        '{"type":"StatusUpdate","message":"ready"}\n',
        encoding="utf-8",
    )
    events = replay_events(path)
    assert len(events) == 2
    assert events[0]["text"] == "ok"
    assert events[1]["message"] == "ready"


def test_summarize_and_filter_event_types() -> None:
    events = [
        {"type": "MessageDelta", "text": "a"},
        {"type": "MessageDelta", "text": "b"},
        {"type": "PoolMatch", "genomes": ["g1"], "scores": [0.5]},
    ]
    counts = summarize_event_types(events)
    assert counts["MessageDelta"] == 2
    assert counts["PoolMatch"] == 1
    assert "MessageDelta×2" in format_type_histogram(counts)
    filtered = filter_events_by_type(events, "poolmatch")
    assert len(filtered) == 1
    assert filtered[0]["type"] == "PoolMatch"


def test_format_event_summary_covers_common_types() -> None:
    assert "user" in format_event_summary({"type": "MessageStart", "role": "user"})
    assert "hello" in format_event_summary({"type": "MessageDelta", "text": "hello"})
    assert "bash" in format_event_summary({"type": "ToolStart", "tool": "bash"})
    assert "g1" in format_event_summary({"type": "PoolMatch", "genomes": ["g1"], "scores": [0.87]})
    assert "no DNA" in format_event_summary({"type": "PoolMatch", "genomes": [], "scores": []})


def test_agent_attach_session_recorder_on_send(
    isolated_agentdrive_home: Path, clean_bus: None
) -> None:
    from agentdrive.agent.agent import AgentDriveAgent

    class FakeLLM:
        provider = type("P", (), {"display_name": "fake"})()
        model = "fake/fake"

        def stream(self, **kwargs):
            yield "hi"

    agent = AgentDriveAgent(agent_id="rec-agent")
    agent._llm = FakeLLM()  # type: ignore[assignment]
    agent.send("ping")

    path = session_events_path(agent.agent_id, agent.session.session_id)
    events = replay_events(path)
    types = [ev["type"] for ev in events]
    assert "MessageDelta" in types
    assert "MessageComplete" in types
    assert "PoolMatch" in types


def _run_cli(*args: str, home: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "AGENTDRIVE_HOME": str(home), "AGENTDRIVE_DISABLE_RETENTION_LOOP": "1"}
    return subprocess.run(
        [sys.executable, "-m", "agentdrive.cli", *args],
        capture_output=True,
        text=True,
        timeout=20,
        env=env,
    )


def test_cli_session_events_and_replay(isolated_agentdrive_home: Path) -> None:
    session_id = "cli-sess-001"
    path = session_events_path("agentdrive-agent", session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "MessageDelta", "text": "cli event"}) + "\n")
        fh.write(json.dumps({"type": "PoolMatch", "genomes": ["g-cli"], "scores": [0.5]}) + "\n")

    listed = _run_cli("session", "events", session_id, home=isolated_agentdrive_home)
    assert listed.returncode == 0
    assert "MessageDelta" in listed.stdout
    assert "cli event" in listed.stdout

    replay = _run_cli("session", "replay", session_id, home=isolated_agentdrive_home)
    assert replay.returncode == 0
    assert "Session replay" in replay.stdout
    assert "PoolMatch" in replay.stdout

    filtered = _run_cli(
        "session",
        "replay",
        session_id,
        "--type",
        "PoolMatch",
        home=isolated_agentdrive_home,
    )
    assert filtered.returncode == 0
    assert "PoolMatch" in filtered.stdout
    assert "cli event" not in filtered.stdout


def test_cli_session_panel(isolated_agentdrive_home: Path) -> None:
    session_id = "cli-sess-panel"
    path = session_events_path("agentdrive-agent", session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "StatusUpdate", "message": "ready"}) + "\n")

    panel = _run_cli("session", "panel", session_id, home=isolated_agentdrive_home)
    assert panel.returncode == 0
    assert "Session replay" in panel.stdout
    assert "StatusUpdate" in panel.stdout
