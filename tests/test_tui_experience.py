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