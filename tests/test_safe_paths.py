"""Unit tests for the path-traversal guards used to clear CodeQL findings.

These tests are deliberately blunt — the safe_join contract is "anything
that resolves outside root raises". If we relax that, every cleared CodeQL
finding can regress silently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentdrive.utils.safe_paths import PathTraversalError, safe_join, safe_name


def test_safe_join_happy_path(tmp_path: Path) -> None:
    out = safe_join(tmp_path, "agent-a", "drive")
    assert out == (tmp_path / "agent-a" / "drive").resolve()


def test_safe_join_rejects_dotdot(tmp_path: Path) -> None:
    with pytest.raises(PathTraversalError):
        safe_join(tmp_path, "..")


def test_safe_join_rejects_embedded_dotdot(tmp_path: Path) -> None:
    # Even a single path part that *contains* a slash + .. escapes via resolve()
    with pytest.raises(PathTraversalError):
        safe_join(tmp_path, "ok/../../etc")


def test_safe_join_rejects_absolute_segment(tmp_path: Path) -> None:
    with pytest.raises(PathTraversalError):
        safe_join(tmp_path, "/etc/passwd")


def test_safe_join_rejects_empty_segment(tmp_path: Path) -> None:
    with pytest.raises(PathTraversalError):
        safe_join(tmp_path, "")


def test_safe_join_requires_at_least_one_part(tmp_path: Path) -> None:
    with pytest.raises(PathTraversalError):
        safe_join(tmp_path)


def test_safe_join_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / "evil").symlink_to(outside)
    with pytest.raises(PathTraversalError):
        safe_join(root, "evil")


def test_safe_name_accepts_normal_id() -> None:
    assert safe_name("agent-a") == "agent-a"
    assert safe_name("swarm_42") == "swarm_42"


def test_safe_name_rejects_separators() -> None:
    with pytest.raises(PathTraversalError):
        safe_name("a/b")
    with pytest.raises(PathTraversalError):
        safe_name("a\\b")


def test_safe_name_rejects_dotdot_and_dot() -> None:
    with pytest.raises(PathTraversalError):
        safe_name("..")
    with pytest.raises(PathTraversalError):
        safe_name(".")


def test_safe_name_rejects_empty() -> None:
    with pytest.raises(PathTraversalError):
        safe_name("")
