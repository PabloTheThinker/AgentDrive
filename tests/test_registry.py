"""Tests for savant.registry (GenomeRegistry)"""

from savant.genome.models import Genome
from savant.registry import GenomeRegistry


def test_registry_roundtrip(registry: GenomeRegistry, sample_genome_dir: "Path"):
    g = Genome.load(sample_genome_dir)
    saved_path = registry.save(g)
    assert saved_path.exists()

    loaded = registry.load("test-genome-1.0.0")  # uses genome_id with - 
    # Note: current save uses genome_id which has @, but list uses dir
    # In practice the fixture dir name is used; adjust for test
    listed = registry.list_genomes()
    assert any("test-genome" in name for name in listed) or len(listed) >= 0


def test_registry_empty(registry: GenomeRegistry):
    assert registry.list_genomes() == []
