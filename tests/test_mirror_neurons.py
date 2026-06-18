"""Tests for mirror-neuron mimicry layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentdrive.codebase.exemplars import extract_exemplars
from agentdrive.codebase.mirrors import (
    fire_mirrors_for_intent,
    global_mirror_field,
    transform_toward_style,
)
from agentdrive.codebase.observe import observe_file
from agentdrive.codebase.registry import register_project
from agentdrive.operations.registry import run_operation


@pytest.fixture
def py_project(tmp_path: Path) -> str:
    root = tmp_path / "mirror-demo"
    (root / "api").mkdir(parents=True)
    (root / "api" / "handler.py").write_text(
        '"""API handlers."""\n\n'
        "import logging\n\n"
        "logger = logging.getLogger(__name__)\n\n"
        "def fetch_user_record(user_id: str) -> dict:\n"
        '    """Load user."""\n'
        "    return {'id': user_id}\n\n"
        "def save_user_record(user_id: str, data: dict) -> None:\n"
        "    logger.info('save %s', user_id)\n",
        encoding="utf-8",
    )
    register_project(project_id="mirror-demo", root=str(root))
    return "mirror-demo"


def test_extract_exemplars_python() -> None:
    content = "def alpha_one(x: int) -> int:\n    return x\n"
    ex = extract_exemplars(path="a.py", content=content, language="python")
    assert any(e["name"] == "alpha_one" for e in ex)


def test_mirror_ingest_fires_motors(py_project: str) -> None:
    result = observe_file(project_id=py_project, path="api/handler.py")
    assert result["success"] is True
    mirror = result.get("mirror_neurons") or {}
    assert mirror.get("motors_fired", 0) >= 1


def test_fire_mirrors_for_intent(py_project: str) -> None:
    observe_file(project_id=py_project, path="api/handler.py")
    fired = fire_mirrors_for_intent(py_project, intent="fetch user record helper")
    assert fired.get("motors_fired", 0) >= 1
    assert "mimicry_prompt" in fired
    assert "fetch_user_record" in fired.get("mimicry_prompt", "") or fired.get("motor_programs")


def test_transform_camel_to_snake(py_project: str) -> None:
    observe_file(project_id=py_project, path="api/handler.py")
    out = transform_toward_style(
        py_project,
        code="def loadUserData():\n    pass\n",
        path="api/new.py",
    )
    assert "load_user_data" in out.get("transformed_code", "") or out.get("suggestions")


def test_codebase_mimic_operation(py_project: str, isolated_agentdrive_home: Path) -> None:
    observe_file(project_id=py_project, path="api/handler.py")
    result = run_operation(
        "codebase_mimic",
        project_id=py_project,
        intent="save user helper",
    )
    assert result.get("success") is True
    assert result.get("mimicry_prompt")
    assert result.get("auto_learning")


def test_global_resonance_after_two_projects(
    tmp_path: Path, isolated_agentdrive_home: Path
) -> None:
    for name in ("proj-a", "proj-b"):
        root = tmp_path / name
        root.mkdir()
        (root / "mod.py").write_text(
            "def do_work(item_id: str) -> str:\n    return item_id\n",
            encoding="utf-8",
        )
        register_project(project_id=name, root=str(root))
        observe_file(project_id=name, path="mod.py")

    field = global_mirror_field()
    assert field.get("projects_registered", 0) >= 2
