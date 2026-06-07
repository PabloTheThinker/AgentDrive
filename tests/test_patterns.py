"""Tests for the Fabric-style pattern-as-genome catalog."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentdrive.genome.models import GenomeManifest
from agentdrive.patterns import (
    PatternNotFoundError,
    apply_pattern,
    get_pattern,
    list_patterns,
    resolve_pattern_path,
)


def test_list_patterns_includes_morning_brief_v1() -> None:
    names = [record.name for record in list_patterns()]
    assert "morning-brief-v1" in names


def test_apply_pattern_replaces_input_placeholder() -> None:
    input_text = "Team standup 9am. Ship patterns catalog before lunch."
    prompt = apply_pattern("morning-brief-v1", input_text)

    assert input_text in prompt
    assert "{{input}}" not in prompt
    assert "# SYSTEM" in prompt
    assert "# USER" in prompt


def test_get_pattern_loads_manifest() -> None:
    record = get_pattern("morning-brief-v1")
    assert record.manifest is not None
    assert record.manifest.id == "morning-brief"
    assert record.source == "bundled"


def test_resolve_pattern_path_returns_directory() -> None:
    path = resolve_pattern_path("morning-brief-v1")
    assert path.is_dir()
    assert (path / "manifest.json").is_file()
    assert (path / "system.md").is_file()


def test_user_overlay_wins_on_name_collision(
    isolated_agentdrive_home: Path,
) -> None:
    overlay_root = isolated_agentdrive_home / "patterns" / "morning-brief-v1"
    overlay_root.mkdir(parents=True)

    manifest = GenomeManifest(
        id="morning-brief",
        version="9.9.9",
        content_hash="sha256:pending",
        created=datetime.now(UTC),
    )
    (overlay_root / "manifest.json").write_text(manifest.model_dump_json(indent=2))
    (overlay_root / "system.md").write_text("CUSTOM OVERLAY {{input}}")
    (overlay_root / "framework.yaml").write_text("framework:\n  id: morning-brief\n")

    record = get_pattern("morning-brief-v1")
    assert record.source == "user"
    assert record.manifest is not None
    assert record.manifest.version == "9.9.9"

    prompt = apply_pattern("morning-brief-v1", "operator-notes")
    assert "CUSTOM OVERLAY operator-notes" in prompt
    assert "{{input}}" not in prompt


def test_unknown_pattern_raises() -> None:
    with pytest.raises(PatternNotFoundError):
        resolve_pattern_path("does-not-exist-pattern")