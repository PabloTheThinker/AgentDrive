"""Import Fabric ``data/patterns/*/system.md`` into AgentDrive pattern-as-genome dirs."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path

import yaml

from agentdrive.constants import get_agentdrive_home
from agentdrive.genome.models import GenomeAuthor, GenomeManifest

_FABRIC_VERSION_SUFFIX = "-fabric-v1"
_GENOME_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$")


class FabricPatternNotFoundError(FileNotFoundError):
    """Raised when a Fabric pattern directory or system.md is missing."""

    def __init__(self, pattern_name: str, fabric_root: Path) -> None:
        super().__init__(
            f"Fabric pattern not found: {pattern_name} "
            f"(expected {fabric_root / 'data' / 'patterns' / pattern_name / 'system.md'})"
        )
        self.pattern_name = pattern_name
        self.fabric_root = fabric_root


class FabricPatternExistsError(FileExistsError):
    """Raised when importing would overwrite an existing pattern genome."""

    def __init__(self, dest: Path) -> None:
        super().__init__(f"Pattern genome already exists: {dest} (pass overwrite=True to replace)")
        self.dest = dest


def sanitize_pattern_name(pattern_name: str) -> str:
    """Normalize a Fabric pattern folder name into a genome id segment."""
    cleaned = pattern_name.strip().lower()
    cleaned = re.sub(r"[_\s]+", "-", cleaned)
    cleaned = re.sub(r"[^a-z0-9._-]", "-", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    if not cleaned:
        raise ValueError(f"Invalid Fabric pattern name: {pattern_name!r}")
    if not _GENOME_ID_RE.match(cleaned):
        cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned).strip("-") or "fabric-pattern"
    return cleaned


def pattern_genome_dir_name(pattern_name: str) -> str:
    """Return the on-disk pattern genome directory name for a Fabric pattern."""
    return f"{sanitize_pattern_name(pattern_name)}{_FABRIC_VERSION_SUFFIX}"


def resolve_fabric_root(source: Path | str | None = None) -> Path:
    """Resolve the Fabric repository root.

    Resolution order:
    1. Explicit ``source`` argument
    2. ``FABRIC_PATTERNS_ROOT`` environment variable
    3. Walk up from cwd for ``Research/GitHub-Archive/Fabric``
    """
    if source is not None:
        root = Path(source).expanduser().resolve()
        _validate_fabric_root(root)
        return root

    env_root = os.environ.get("FABRIC_PATTERNS_ROOT", "").strip()
    if env_root:
        root = Path(env_root).expanduser().resolve()
        _validate_fabric_root(root)
        return root

    cwd = Path.cwd().resolve()
    for parent in (cwd, *cwd.parents):
        candidate = parent / "Research" / "GitHub-Archive" / "Fabric"
        if _is_fabric_root(candidate):
            return candidate.resolve()

    raise FileNotFoundError(
        "Fabric repository not found. Set FABRIC_PATTERNS_ROOT, pass --source, "
        "or run from a tree containing Research/GitHub-Archive/Fabric."
    )


def _is_fabric_root(path: Path) -> bool:
    return path.is_dir() and (path / "data" / "patterns").is_dir()


def _validate_fabric_root(path: Path) -> None:
    if not _is_fabric_root(path):
        raise FileNotFoundError(f"Not a Fabric repository (missing data/patterns): {path}")


def _fabric_patterns_root(fabric_root: Path) -> Path:
    return fabric_root / "data" / "patterns"


def list_fabric_patterns(fabric_root: Path) -> list[str]:
    """Return sorted Fabric pattern names that contain ``system.md``."""
    root = _fabric_patterns_root(fabric_root)
    if not root.is_dir():
        return []
    names: list[str] = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "system.md").is_file():
            names.append(child.name)
    return names


def _humanize_pattern_name(pattern_name: str) -> str:
    return sanitize_pattern_name(pattern_name).replace("-", " ").replace("_", " ").title()


def _ensure_user_md(user_content: str | None) -> str:
    """Ensure the user prompt section contains the ``{{input}}`` placeholder."""
    if not user_content or not user_content.strip():
        return "{{input}}"
    if "{{input}}" not in user_content:
        return user_content.rstrip() + "\n\n{{input}}\n"
    return user_content


def _build_manifest(pattern_name: str) -> GenomeManifest:
    genome_id = sanitize_pattern_name(pattern_name)
    now = datetime.now(UTC)
    return GenomeManifest(
        id=genome_id,
        version="1.0.0",
        content_hash="sha256:pending",
        created=now,
        last_improved=now,
        authors=[
            GenomeAuthor(type="human", name="Fabric"),
            GenomeAuthor(type="agent", name="agentdrive-fabric-import"),
        ],
        applicability={
            "domains": ["fabric-import", "prompting"],
            "problem_signatures": [
                f"apply Fabric pattern {pattern_name}",
            ],
            "source_pattern": pattern_name,
        },
        dependencies={"genomes": [], "agent_capabilities": ["prompting"]},
        evaluation_score={},
        schema_version="1.0",
    )


def _build_framework(pattern_name: str) -> dict[str, object]:
    genome_id = sanitize_pattern_name(pattern_name)
    display_name = _humanize_pattern_name(pattern_name)
    return {
        "framework": {
            "id": genome_id,
            "version": "1.0.0",
            "display_name": display_name,
            "description": (
                f"Fabric-style pattern genome imported from Fabric pattern `{pattern_name}`."
            ),
            "category": "fabric-import",
            "tags": ["fabric", "fabric-import", genome_id, pattern_name],
            "inputs": [
                {
                    "name": "input",
                    "type": "string",
                    "required": True,
                    "description": "Operator input substituted for the {{input}} placeholder.",
                }
            ],
            "steps": [
                {
                    "id": "apply_fabric_pattern",
                    "type": "reasoning",
                    "description": (
                        f"Execute the imported Fabric system prompt for `{pattern_name}`."
                    ),
                }
            ],
            "output": {"formats": ["markdown"]},
        }
    }


def import_fabric_pattern(
    fabric_root: Path | str,
    pattern_name: str,
    dest_root: Path | str,
    *,
    overwrite: bool = False,
) -> Path:
    """Import one Fabric pattern into a pattern-as-genome directory."""
    fabric_path = Path(fabric_root).expanduser().resolve()
    destination_root = Path(dest_root).expanduser().resolve()
    pattern_dir = _fabric_patterns_root(fabric_path) / pattern_name
    system_path = pattern_dir / "system.md"
    if not system_path.is_file():
        raise FabricPatternNotFoundError(pattern_name, fabric_path)

    dest = destination_root / pattern_genome_dir_name(pattern_name)
    if dest.exists() and not overwrite:
        raise FabricPatternExistsError(dest)

    user_path = pattern_dir / "user.md"
    system_content = system_path.read_text(encoding="utf-8")
    user_content = user_path.read_text(encoding="utf-8") if user_path.is_file() else ""
    user_md = _ensure_user_md(user_content)

    if dest.exists() and overwrite:
        for child in dest.iterdir():
            if child.is_file():
                child.unlink()
    dest.mkdir(parents=True, exist_ok=True)

    manifest = _build_manifest(pattern_name)
    (dest / "manifest.json").write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (dest / "framework.yaml").write_text(
        yaml.safe_dump(_build_framework(pattern_name), sort_keys=False),
        encoding="utf-8",
    )
    (dest / "system.md").write_text(system_content, encoding="utf-8")
    (dest / "user.md").write_text(user_md, encoding="utf-8")
    return dest.resolve()


def import_fabric_corpus(
    fabric_root: Path | str,
    dest_root: Path | str | None = None,
    *,
    limit: int = 10,
    pattern_names: list[str] | None = None,
    overwrite: bool = False,
) -> list[Path]:
    """Import multiple Fabric patterns into the user patterns overlay."""
    fabric_path = Path(fabric_root).expanduser().resolve()
    destination_root = (
        Path(dest_root).expanduser().resolve()
        if dest_root is not None
        else get_agentdrive_home() / "patterns"
    )

    available = list_fabric_patterns(fabric_path)
    if pattern_names is not None:
        selected = pattern_names
    else:
        selected = available[: max(limit, 0)]

    imported: list[Path] = []
    for name in selected:
        dest = destination_root / pattern_genome_dir_name(name)
        if dest.exists() and not overwrite:
            continue
        try:
            imported.append(
                import_fabric_pattern(
                    fabric_path,
                    name,
                    destination_root,
                    overwrite=overwrite,
                )
            )
        except FabricPatternNotFoundError:
            continue
    return imported
