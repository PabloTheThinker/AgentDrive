"""Pattern-as-genome catalog — Fabric-compatible prompts packaged as Genomes.

Scans bundled ``genomes/patterns/`` and user overlay ``~/.agentdrive/patterns/``.
On name collision the user overlay wins.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from agentdrive.constants import get_agentdrive_home
from agentdrive.genome.models import GenomeManifest


class PatternNotFoundError(FileNotFoundError):
    """Raised when a pattern name cannot be resolved in any catalog root."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Pattern not found: {name}")
        self.name = name


@dataclass(frozen=True, slots=True)
class PatternRecord:
    """A discovered pattern directory and its parsed manifest."""

    name: str
    path: Path
    source: Literal["bundled", "user"]
    manifest: GenomeManifest | None = None
    framework: dict[str, Any] | None = None


def _bundled_patterns_root() -> Path:
    """Return the repository's bundled ``genomes/patterns`` directory."""
    module_dir = Path(__file__).resolve().parent
    for ancestor in module_dir.parents:
        candidate = ancestor / "genomes" / "patterns"
        if candidate.is_dir():
            return candidate
    return module_dir.parents[3] / "genomes" / "patterns"


def _user_patterns_root() -> Path:
    return get_agentdrive_home() / "patterns"


def _is_pattern_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    return (path / "manifest.json").is_file() or (path / "manifest.yaml").is_file()


def _load_manifest(path: Path) -> GenomeManifest | None:
    for filename in ("manifest.json", "manifest.yaml"):
        manifest_path = path / filename
        if not manifest_path.is_file():
            continue
        raw = manifest_path.read_text(encoding="utf-8")
        data = json.loads(raw) if filename.endswith(".json") else yaml.safe_load(raw)
        if not isinstance(data, dict):
            continue
        return GenomeManifest.model_validate(data)
    return None


def _load_framework(path: Path) -> dict[str, Any] | None:
    framework_path = path / "framework.yaml"
    if not framework_path.is_file():
        framework_path = path / "framework.json"
        if not framework_path.is_file():
            return None
        data = json.loads(framework_path.read_text(encoding="utf-8"))
    else:
        data = yaml.safe_load(framework_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    framework = data.get("framework", data)
    return framework if isinstance(framework, dict) else None


def _scan_root(root: Path, source: Literal["bundled", "user"]) -> dict[str, PatternRecord]:
    patterns: dict[str, PatternRecord] = {}
    if not root.is_dir():
        return patterns
    for child in sorted(root.iterdir()):
        if not _is_pattern_dir(child):
            continue
        patterns[child.name] = PatternRecord(
            name=child.name,
            path=child.resolve(),
            source=source,
            manifest=_load_manifest(child),
            framework=_load_framework(child),
        )
    return patterns


def _catalog() -> dict[str, PatternRecord]:
    """Build the merged catalog; user overlay wins on name collision."""
    merged = _scan_root(_bundled_patterns_root(), "bundled")
    merged.update(_scan_root(_user_patterns_root(), "user"))
    return merged


def list_patterns() -> list[PatternRecord]:
    """Return all known patterns sorted by name."""
    catalog = _catalog()
    return [catalog[name] for name in sorted(catalog)]


def resolve_pattern_path(name: str) -> Path:
    """Resolve a pattern name to its on-disk directory."""
    record = _catalog().get(name)
    if record is None:
        raise PatternNotFoundError(name)
    return record.path


def get_pattern(name: str) -> PatternRecord:
    """Return metadata for a single pattern."""
    record = _catalog().get(name)
    if record is None:
        raise PatternNotFoundError(name)
    return record


def apply_pattern(name: str, input_text: str) -> str:
    """Compose the system + user prompt with ``{{input}}`` replaced."""
    path = resolve_pattern_path(name)
    system_path = path / "system.md"
    user_path = path / "user.md"

    system = system_path.read_text(encoding="utf-8") if system_path.is_file() else ""
    user = user_path.read_text(encoding="utf-8") if user_path.is_file() else "{{input}}"

    system = system.replace("{{input}}", input_text)
    user = user.replace("{{input}}", input_text)

    parts: list[str] = []
    if system.strip():
        parts.append(f"# SYSTEM\n\n{system.strip()}")
    if user.strip():
        parts.append(f"# USER\n\n{user.strip()}")
    return "\n\n".join(parts)