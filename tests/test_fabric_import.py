"""Tests for Fabric corpus import into pattern-as-genome directories."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentdrive.patterns import (
    apply_pattern,
    import_fabric_corpus,
    import_fabric_pattern,
    list_patterns,
    pattern_genome_dir_name,
    resolve_fabric_root,
    sanitize_pattern_name,
)
from agentdrive.patterns.fabric_import import (
    FabricPatternExistsError,
    FabricPatternNotFoundError,
)


def _make_fabric_pattern(
    fabric_root: Path,
    pattern_name: str,
    *,
    system_md: str,
    user_md: str = "",
) -> Path:
    pattern_dir = fabric_root / "data" / "patterns" / pattern_name
    pattern_dir.mkdir(parents=True, exist_ok=True)
    (pattern_dir / "system.md").write_text(system_md, encoding="utf-8")
    (pattern_dir / "user.md").write_text(user_md, encoding="utf-8")
    return pattern_dir


def test_sanitize_pattern_name_normalizes_underscores() -> None:
    assert sanitize_pattern_name("hello_world") == "hello-world"
    assert pattern_genome_dir_name("hello_world") == "hello-world-fabric-v1"


def test_import_fabric_pattern_writes_genome_files(
    tmp_path: Path,
    isolated_agentdrive_home: Path,
) -> None:
    fabric_root = tmp_path / "fabric"
    _make_fabric_pattern(
        fabric_root,
        "hello_world",
        system_md="# IDENTITY\n\nYou greet the operator.\n\n# INPUT\n\n",
        user_md="",
    )
    dest_root = isolated_agentdrive_home / "patterns"

    imported = import_fabric_pattern(fabric_root, "hello_world", dest_root)

    assert imported.name == "hello-world-fabric-v1"
    assert (imported / "manifest.json").is_file()
    assert (imported / "framework.yaml").is_file()
    assert (imported / "system.md").is_file()
    assert (imported / "user.md").read_text(encoding="utf-8") == "{{input}}"


def test_imported_pattern_is_listed_and_applicable(
    tmp_path: Path,
    isolated_agentdrive_home: Path,
) -> None:
    fabric_root = tmp_path / "fabric"
    _make_fabric_pattern(
        fabric_root,
        "summarize",
        system_md="# IDENTITY\n\nSummarize this:\n",
        user_md="CONTENT:\n",
    )
    dest_root = isolated_agentdrive_home / "patterns"
    import_fabric_pattern(fabric_root, "summarize", dest_root)

    names = [record.name for record in list_patterns()]
    assert "summarize-fabric-v1" in names

    input_text = "Quarterly revenue rose 12 percent."
    prompt = apply_pattern("summarize-fabric-v1", input_text)
    assert input_text in prompt
    assert "{{input}}" not in prompt
    assert "# SYSTEM" in prompt
    assert "# USER" in prompt


def test_import_fabric_corpus_respects_limit(
    tmp_path: Path,
    isolated_agentdrive_home: Path,
) -> None:
    fabric_root = tmp_path / "fabric"
    for name in ("alpha", "beta", "gamma"):
        _make_fabric_pattern(
            fabric_root,
            name,
            system_md=f"# IDENTITY\n\nPattern {name}\n",
        )
    dest_root = isolated_agentdrive_home / "patterns"

    imported = import_fabric_corpus(fabric_root, dest_root, limit=2)

    assert len(imported) == 2
    assert imported[0].name == "alpha-fabric-v1"
    assert imported[1].name == "beta-fabric-v1"


def test_import_fabric_pattern_raises_when_missing(tmp_path: Path) -> None:
    fabric_root = tmp_path / "fabric"
    (fabric_root / "data" / "patterns").mkdir(parents=True)

    with pytest.raises(FabricPatternNotFoundError):
        import_fabric_pattern(fabric_root, "missing", tmp_path / "dest")


def test_import_fabric_pattern_raises_without_overwrite(
    tmp_path: Path,
    isolated_agentdrive_home: Path,
) -> None:
    fabric_root = tmp_path / "fabric"
    _make_fabric_pattern(
        fabric_root,
        "repeat_me",
        system_md="# IDENTITY\n\nRepeat.\n",
    )
    dest_root = isolated_agentdrive_home / "patterns"
    import_fabric_pattern(fabric_root, "repeat_me", dest_root)

    with pytest.raises(FabricPatternExistsError):
        import_fabric_pattern(fabric_root, "repeat_me", dest_root)


def test_resolve_fabric_root_from_explicit_source(tmp_path: Path) -> None:
    fabric_root = tmp_path / "fabric"
    (fabric_root / "data" / "patterns").mkdir(parents=True)

    resolved = resolve_fabric_root(fabric_root)

    assert resolved == fabric_root.resolve()


def test_resolve_fabric_root_from_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fabric_root = tmp_path / "fabric-env"
    (fabric_root / "data" / "patterns").mkdir(parents=True)
    monkeypatch.setenv("FABRIC_PATTERNS_ROOT", str(fabric_root))

    resolved = resolve_fabric_root()

    assert resolved == fabric_root.resolve()
