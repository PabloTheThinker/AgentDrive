"""Bootstrap registry path alignment for personal vs swarm drives."""

from __future__ import annotations

from pathlib import Path

from agentdrive.constants import get_default_drive_path, get_genomes_dir
from agentdrive.drive.bootstrap import (
    _migrate_legacy_personal_genomes,
    _resolve_registry_root,
    ensure_experience_layer_seed,
)
from agentdrive.registry import GenomeRegistry


def test_resolve_registry_root_personal_uses_home_genomes(
    isolated_agentdrive_home: Path,
) -> None:
    drive_path = get_default_drive_path()
    assert _resolve_registry_root(drive_path, swarm_id=None) == get_genomes_dir()


def test_resolve_registry_root_swarm_uses_drive_genomes(
    isolated_agentdrive_home: Path,
) -> None:
    swarm_drive = isolated_agentdrive_home / "swarms" / "alpha" / "drive"
    swarm_drive.mkdir(parents=True)
    assert _resolve_registry_root(swarm_drive, swarm_id="alpha") == swarm_drive / "genomes"


def test_migrate_legacy_personal_genomes(isolated_agentdrive_home: Path) -> None:
    drive_path = get_default_drive_path()
    legacy = drive_path / "genomes" / "legacy-seed"
    legacy.mkdir(parents=True)
    (legacy / "manifest.json").write_text('{"id": "legacy-seed", "version": "1.0.0"}')
    target = get_genomes_dir()
    _migrate_legacy_personal_genomes(drive_path, target)
    assert (target / "legacy-seed" / "manifest.json").exists()


def test_ensure_experience_layer_seed_registers_in_home_genomes(
    isolated_agentdrive_home: Path,
) -> None:
    ensure_experience_layer_seed()
    home_reg = GenomeRegistry()
    ids = home_reg.list_genomes()
    assert any("living-experience-seed-v3" in gid for gid in ids)
    assert (get_genomes_dir() / "living-experience-seed-v3").exists()
