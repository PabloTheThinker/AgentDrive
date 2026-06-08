"""Tests for TUI golden-path experience layer."""

from __future__ import annotations

from pathlib import Path

from agentdrive.tui.experience import (
    golden_path_status_segment,
    is_golden_path_marked_complete,
    mark_golden_path_complete,
    should_show_golden_path_gate,
)


def test_mark_and_check_complete(isolated_agentdrive_home: Path):
    assert is_golden_path_marked_complete() is False
    mark_golden_path_complete(source="test")
    assert is_golden_path_marked_complete() is True


def test_gate_hidden_after_complete(isolated_agentdrive_home: Path):
    mark_golden_path_complete(source="test")
    assert should_show_golden_path_gate() is False


def test_status_segment(isolated_agentdrive_home: Path):
    seg = golden_path_status_segment()
    assert "golden" in seg.lower()


def test_session_slash_renders_events(isolated_agentdrive_home: Path):
    from io import StringIO

    from rich.console import Console

    from agentdrive.events import MessageDelta, emit
    from agentdrive.session_events import SessionEventRecorder, session_events_path
    from agentdrive.tui.experience import handle_ops_slash

    agent_id = "agentdrive-agent"
    session_id = "test-session-001"
    path = session_events_path(agent_id, session_id)
    rec = SessionEventRecorder(agent_id, session_id)
    rec.attach()
    emit(MessageDelta(text="hello from test", session_id=session_id))
    rec.close()

    out = StringIO()
    console = Console(file=out, force_terminal=True, width=120)
    handle_ops_slash(
        console,
        "/session",
        f"events {session_id}",
        agent_id=agent_id,
        current_session_id=session_id,
    )
    text = out.getvalue()
    assert "MessageDelta" in text or "hello" in text
    assert path.exists()