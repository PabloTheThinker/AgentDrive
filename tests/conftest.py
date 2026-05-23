"""
Pytest configuration and shared fixtures for Savant.

Provides isolated SAVANT_HOME per test (via context override) so tests
never touch the user's real ~/.savant .
"""

import os
import tempfile
from pathlib import Path
from typing import Iterator

import pytest

from savant.constants import (
    reset_savant_home_override,
    set_savant_home_override,
)


@pytest.fixture(autouse=True)
def isolated_savant_home(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """
    Automatically give every test its own temporary Savant home directory.
    This is the most important fixture for test isolation.
    """
    with tempfile.TemporaryDirectory(prefix="savant-test-") as td:
        home = Path(td)
        token = set_savant_home_override(home)
        # Also clear any SAVANT_HOME env the test process may have inherited
        monkeypatch.delenv("SAVANT_HOME", raising=False)
        try:
            yield home
        finally:
            reset_savant_home_override(token)


@pytest.fixture
def sample_genome_dir(tmp_path: Path) -> Path:
    """A minimal valid genome directory for tests."""
    from datetime import datetime, timezone

    from savant.genome.models import Genome, GenomeManifest

    gdir = tmp_path / "test-genome-v1"
    gdir.mkdir()

    manifest = GenomeManifest(
        id="test-genome",
        version="1.0.0",
        content_hash="sha256:" + "deadbeef" * 8,
        created=datetime.now(timezone.utc),
        authors=[],
    )
    g = Genome(manifest=manifest, framework={"steps": [{"id": "1", "name": "test"}]})
    g.save(gdir)
    return gdir


@pytest.fixture
def registry(isolated_savant_home: Path) -> "GenomeRegistry":
    from savant.registry import GenomeRegistry

    return GenomeRegistry()
