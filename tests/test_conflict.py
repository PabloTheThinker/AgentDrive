"""Unit tests for v2 / M4 conflict-copy emission — drive/conflict.py.

When two last-write writes target the same Genome id with different content,
ingest emits a conflict copy instead of clobbering. The suffix has to be
deterministic so retrying the same losing write doesn't pile up duplicate
conflict objects, and the lineage entry has to point back at the original so
the relationship is queryable.
"""

from __future__ import annotations

from agentdrive.drive.conflict import (
    conflict_suffix,
    emit_conflict_genome,
    sanitize_author,
)
from agentdrive.genome.models import Genome


def _make_genome(genome_id: str, framework: dict | None = None) -> Genome:
    return Genome.create(
        id=genome_id,
        version="1.0.0",
        framework=framework or {"steps": ["one"]},
        authors=[{"type": "agent", "id": "sub:alpha", "name": "alpha"}],
    )


# ─── sanitize_author ────────────────────────────────────────────────────────


def test_sanitize_author_basic() -> None:
    assert sanitize_author("sub:alpha") == "sub-alpha"
    assert sanitize_author("normal-name") == "normal-name"
    assert sanitize_author("a.b.c") == "a-b-c"


def test_sanitize_author_strips_unicode() -> None:
    # Non-ascii runs collapse to a single '-'; surviving ascii letters stay.
    assert sanitize_author("ünîçødé-name") == "n-d--name"
    assert sanitize_author("🎉🎉") == "unknown"


def test_sanitize_author_empty_to_unknown() -> None:
    assert sanitize_author("") == "unknown"
    assert sanitize_author("---") == "unknown"


def test_sanitize_author_length_capped() -> None:
    long = "a" * 200
    assert len(sanitize_author(long)) == 32


# ─── conflict_suffix ────────────────────────────────────────────────────────


def test_conflict_suffix_deterministic() -> None:
    v = {"sub:alpha": 1234567890}
    a = conflict_suffix(v, "sub:alpha")
    b = conflict_suffix(v, "sub:alpha")
    assert a == b
    assert a.startswith("conflict-")
    assert a.endswith("-sub-alpha")


def test_conflict_suffix_vector_dependent() -> None:
    v1 = {"sub:alpha": 100}
    v2 = {"sub:alpha": 200}
    assert conflict_suffix(v1, "sub:alpha") != conflict_suffix(v2, "sub:alpha")


# ─── emit_conflict_genome ───────────────────────────────────────────────────


def test_emit_conflict_genome_preserves_content() -> None:
    original = _make_genome("plan-a", framework={"steps": ["original"]})
    incoming = _make_genome("plan-a", framework={"steps": ["different"]})
    conflict = emit_conflict_genome(original, incoming, {"sub:alpha": 42})

    assert conflict.framework == {"steps": ["different"]}
    assert conflict.manifest.id.startswith("plan-a-conflict-")
    # Same content payload → same content hash (correct content-addressing).
    # The conflict copy's identity sits in the manifest.id, not the hash.
    assert conflict.manifest.content_hash == incoming.manifest.content_hash


def test_emit_conflict_genome_stamps_lineage() -> None:
    original = _make_genome("plan-b", framework={"steps": ["a"]})
    incoming = _make_genome("plan-b", framework={"steps": ["b"]})
    conflict = emit_conflict_genome(original, incoming, {"sub:alpha": 1})

    lineage = conflict.provenance.lineage
    assert len(lineage) == 1
    assert lineage[0]["parent"] == original.manifest.content_hash
    assert lineage[0]["relation"] == "conflict-copy"


def test_emit_conflict_genome_is_idempotent_per_vector() -> None:
    original = _make_genome("plan-c", framework={"steps": ["o"]})
    incoming = _make_genome("plan-c", framework={"steps": ["x"]})
    vector = {"sub:alpha": 999}
    a = emit_conflict_genome(original, incoming, vector)
    b = emit_conflict_genome(original, incoming, vector)
    # Same id (deterministic suffix). Note: lineage timestamp / provenance dates
    # may differ; the id is the part downstream code uses to dedup.
    assert a.manifest.id == b.manifest.id
