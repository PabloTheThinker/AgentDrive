"""Tests for codebase pattern recognition framework."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentdrive.codebase.analyzer import analyze_content
from agentdrive.codebase.framework import crystallize_framework, match_against_framework
from agentdrive.codebase.observe import observe_file
from agentdrive.codebase.registry import register_project
from agentdrive.learning.auto_absorb import reset_sessions
from agentdrive.operations.registry import run_operation


@pytest.fixture(autouse=True)
def _clean_learning():
    reset_sessions()
    yield
    reset_sessions()


@pytest.fixture
def sample_project(tmp_path: Path) -> tuple[str, Path]:
    root = tmp_path / "demo-app"
    lib = root / "lib"
    lib.mkdir(parents=True)
    (lib / "service.py").write_text(
        '"""Service module."""\n\n'
        "import logging\n\n"
        "logger = logging.getLogger(__name__)\n\n"
        "def fetch_data(item_id: str) -> dict:\n"
        '    """Fetch one item."""\n'
        "    return {'id': item_id}\n",
        encoding="utf-8",
    )
    (lib / "models.py").write_text(
        "from dataclasses import dataclass\n\n"
        "@dataclass\n"
        "class ItemRecord:\n"
        "    item_id: str\n"
        "    label: str\n",
        encoding="utf-8",
    )
    (root / "test_service.py").write_text(
        "import pytest\n\ndef test_fetch():\n    assert True\n",
        encoding="utf-8",
    )
    register_project(project_id="demo-app", root=str(root), primary_language="python")
    return "demo-app", root


def test_analyze_python_snake_case() -> None:
    signals = analyze_content(
        path="lib/service.py",
        content="def load_user_data() -> str:\n    pass\n",
    )
    assert signals.language == "python"
    assert signals.signals.get("function_naming") == "snake_case"


def test_observe_files_builds_framework(sample_project: tuple[str, Path]) -> None:
    project_id, _ = sample_project
    for rel in ("lib/service.py", "lib/models.py", "test_service.py"):
        result = observe_file(project_id=project_id, path=rel)
        assert result["success"] is True

    framework = crystallize_framework(project_id, force=True)
    patterns = framework.get("patterns") or []
    assert framework["file_count"] == 3
    assert any(p["id"].startswith("naming-functions-") for p in patterns)
    assert framework.get("writing_guide")


def test_match_snippet_alignment(sample_project: tuple[str, Path]) -> None:
    project_id, _ = sample_project
    observe_file(project_id=project_id, path="lib/service.py")
    observe_file(project_id=project_id, path="lib/models.py")
    observe_file(project_id=project_id, path="test_service.py")
    crystallize_framework(project_id, force=True)

    good = match_against_framework(
        project_id,
        code="def save_user_record(user_id: str) -> None:\n    pass\n",
        path="lib/new.py",
    )
    assert good["alignment_score"] >= 0.0

    bad = match_against_framework(
        project_id,
        code="function loadUserData() { return null; }",
        path="lib/bad.ts",
    )
    assert "conflicts" in bad


def test_run_operation_observe_with_auto_learning(
    sample_project: tuple[str, Path],
    isolated_agentdrive_home: Path,
) -> None:
    project_id, _ = sample_project
    result = run_operation(
        "codebase_observe_file",
        project_id=project_id,
        path="lib/service.py",
    )
    assert result.get("success") is True
    assert result.get("auto_learning") is not None
    skill = (result.get("auto_learning") or {}).get("skill") or {}
    assert skill.get("name", "").startswith(f"learned-{project_id}-observe")


def test_register_and_list_via_operations(sample_project: tuple[str, Path]) -> None:
    project_id, root = sample_project
    listed = run_operation("codebase_list_projects")
    assert listed.get("success") is True
    assert listed.get("count", 0) >= 1
    profile = run_operation("codebase_patterns_profile", project_id=project_id)
    assert profile.get("success") is True
    assert profile.get("framework") is not None
