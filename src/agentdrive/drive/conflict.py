"""Conflict-copy emission for AgentDrive v2 / Milestone 4.

When two writes with ``merge_strategy='last-write'`` target the same Genome id
with different content, we refuse to silently clobber. Instead we ingest a
*conflict copy* — a clone of the incoming Genome whose ``manifest.id`` is
suffixed with ``conflict-<sha8(version_vector)>-<sanitized_author>``. The
original stays put; both are visible to the next reconciler.

The suffix is fully deterministic so that re-ingesting the same losing write
produces the same conflict id (idempotent — no duplicate copies on retry).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentdrive.genome.models import Genome


_AUTHOR_SANITIZE = re.compile(r"[^a-zA-Z0-9-]+")
_AUTHOR_MAX_LEN = 32


def sanitize_author(author: str) -> str:
    """Reduce an author string to ``[a-zA-Z0-9-]`` (max 32 chars).

    Empty / unknown authors collapse to ``unknown`` so the suffix always has
    a non-empty trailing segment.
    """
    if not author:
        return "unknown"
    cleaned = _AUTHOR_SANITIZE.sub("-", author).strip("-")
    if not cleaned:
        return "unknown"
    return cleaned[:_AUTHOR_MAX_LEN]


def conflict_suffix(version_vector: dict[str, int], author: str) -> str:
    """Deterministic ``conflict-<sha8>-<author>`` token for a losing write."""
    canon = json.dumps(version_vector, sort_keys=True, separators=(",", ":")).encode()
    sha8 = hashlib.sha256(canon).hexdigest()[:8]
    return f"conflict-{sha8}-{sanitize_author(author)}"


def emit_conflict_genome(
    original: "Genome",
    incoming: "Genome",
    vector: dict[str, int],
) -> "Genome":
    """Clone ``incoming`` as a conflict copy that cannot collide with ``original``.

    Rewrites the manifest id to ``<original_id>-<suffix>``, recomputes the
    content hash, and stamps a ``conflict-copy`` lineage entry pointing back at
    the original so the relationship is queryable.
    """
    from agentdrive.genome.models import Genome  # noqa: PLC0415  (avoid import cycle)

    author = _first_author_id(incoming)
    suffix = conflict_suffix(vector, author)

    clone = incoming.model_copy(deep=True)
    clone.manifest.id = f"{original.manifest.id}-{suffix}"
    clone.manifest.content_hash = "sha256:pending"
    clone.manifest.last_improved = datetime.now(UTC)
    clone.provenance.add_lineage_entry(
        parent=original.manifest.content_hash,
        relation="conflict-copy",
        notes=f"conflict copy of {original.manifest.id} from author={author!r}",
    )
    clone.finalize(update_timestamp=False)

    # Pydantic v2: model_copy doesn't re-run validators. Re-validate to ensure
    # the rewritten id passes the manifest id regex.
    return Genome.model_validate(clone.model_dump())


def _first_author_id(genome: "Genome") -> str:
    for author in genome.manifest.authors or []:
        if author.id:
            return author.id
        if author.name:
            return author.name
    return "unknown"
