"""
Pytest configuration and shared fixtures for Savant.

Provides isolated AGENTDRIVE_HOME per test (via context override) so tests
never touch the user's real ~/.agentdrive .
"""

import tempfile
from collections.abc import Iterator
from datetime import UTC
from pathlib import Path

import pytest

from agentdrive.constants import (
    reset_agentdrive_home_override,
    set_agentdrive_home_override,
)


@pytest.fixture(autouse=True)
def isolated_savant_home(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """
    Automatically give every test its own temporary Savant home directory.
    This is the most important fixture for test isolation.
    """
    with tempfile.TemporaryDirectory(prefix="savant-test-") as td:
        home = Path(td)
        token = set_agentdrive_home_override(home)
        # Also clear any AGENTDRIVE_HOME env the test process may have inherited
        monkeypatch.delenv("AGENTDRIVE_HOME", raising=False)
        try:
            yield home
        finally:
            reset_agentdrive_home_override(token)


@pytest.fixture
def sample_genome_dir(tmp_path: Path) -> Path:
    """A minimal valid genome directory for tests."""
    from datetime import datetime

    from agentdrive.genome.models import Genome, GenomeManifest

    gdir = tmp_path / "test-genome-v1"
    gdir.mkdir()

    manifest = GenomeManifest(
        id="test-genome",
        version="1.0.0",
        content_hash="sha256:" + "deadbeef" * 8,
        created=datetime.now(UTC),
        authors=[],
    )
    g = Genome(manifest=manifest, framework={"steps": [{"id": "1", "name": "test"}]})
    g.save(gdir)
    return gdir


@pytest.fixture
def registry(isolated_savant_home: Path) -> "GenomeRegistry":
    from agentdrive.registry import GenomeRegistry

    return GenomeRegistry()
