"""Tests for savant.genome.models"""

from datetime import UTC, datetime

import pytest

from agentdrive.genome.models import Genome, GenomeManifest


def test_manifest_validation():
    m = GenomeManifest(
        id="sec-postmortem",
        version="2.1.0",
        content_hash="sha256:" + "a" * 64,
        created=datetime.now(UTC),
    )
    assert m.id == "sec-postmortem"
    assert "2.1.0" in str(m.version)


def test_manifest_bad_version():
    with pytest.raises(ValueError):
        GenomeManifest(
            id="x",
            version="beta",  # no digits
            content_hash="b" * 64,
            created=datetime.now(UTC),
        )


def test_genome_roundtrip(sample_genome_dir: "Path"):
    # load what the fixture wrote
    g = Genome.load(sample_genome_dir)
    assert g.manifest.id == "test-genome"
    assert g.framework is not None

    # re-save to another dir and compare
    out = sample_genome_dir.parent / "roundtrip"
    g.save(out)
    g2 = Genome.load(out)
    assert g2.manifest.version == g.manifest.version
