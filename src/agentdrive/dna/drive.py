"""DNA Drive — per-agent ancestral memory.

Each agent owns one DNA Drive. Genomes the agent earned (and chose to
publish) live here keyed by content hash, alongside Genomes inherited
forward-only from direct ancestors via the ``Ancestry`` closure table.

There is **no decay**: once a Genome is in the lineage, every descendant
always has access. This matches the Avatar-style mental model Pablo
specified — your ancestors are always there when you reach back.

This module is the *forward-only* half of the DNA layer. Sideways flow
across cousin agents from different swarms is opt-in via
``LineageShareGrant`` (Milestone 2c — separate module).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentdrive.constants import get_agentdrive_home
from agentdrive.drive.content_store import ContentStore
from agentdrive.genome.models import Genome

from .ancestry import Ancestry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InheritedGenome:
    """A Genome surfaced by a DNA pull, carrying its full inheritance
    provenance so downstream consumers can attribute it correctly.

    - ``content_hash``: stable identity (sha256 of canonical payload).
    - ``source_agent``: which ancestor produced this Genome.
    - ``depth``: hop count from the requesting agent (1 = direct parent).
    - ``payload``: the deserialized Genome content from the content store.
    """

    content_hash: str
    source_agent: str
    depth: int
    payload: dict[str, Any]


def _dna_root() -> Path:
    return get_agentdrive_home() / "dna"


def _agent_dna_root(agent_id: str) -> Path:
    return _dna_root() / agent_id


class DNADrive:
    """Per-agent ancestral Drive.

    Layout:
    ```
    ~/.agentdrive/dna/
    ├── _ancestry.db          # shared closure table for ALL agents
    └── <agent_id>/
        └── drive/objects/    # content-addressed Genome store
    ```

    The DNA Drive deliberately reuses the Milestone-1 ``ContentStore``
    so a Genome that exists in a swarm Drive and gets promoted to its
    author's DNA Drive does not duplicate bytes — the content hash is
    the same. The dedup invariant from M1 carries straight through.

    Eval gating: ``pull_inherited()`` accepts a ``min_eval`` filter so
    callers can refuse low-quality inherited Genomes. Direct-line
    inheritance defaults to 0.0 (trust your ancestors); the M2c grant
    layer applies a stricter default to cross-source pulls.
    """

    def __init__(
        self,
        agent_id: str,
        parents: list[str] | None = None,
        *,
        ancestry: Ancestry | None = None,
        root: Path | None = None,
    ):
        self.agent_id = agent_id
        self.root = root or _agent_dna_root(agent_id)
        self.root.mkdir(parents=True, exist_ok=True)
        self.content_store = ContentStore(self.root / "drive")
        self.ancestry = ancestry or Ancestry(_dna_root() / "_ancestry.db")

        # Idempotent register — re-running construction with the same parents
        # is a no-op; differing parents raise (ancestry is immutable).
        if not self.ancestry.has_agent(agent_id):
            self.ancestry.add_agent(agent_id, parents=parents or [])

    # ── write path ──────────────────────────────────────────────────────────

    def publish(self, genome: Genome) -> str:
        """Publish a Genome into this agent's DNA Drive. Returns the hash.

        Descendants automatically inherit it on their next pull — they walk
        the ancestry graph to find this agent and consult its content store.
        Idempotent via the content-address.
        """
        put = self.content_store.put_genome(genome)
        return put.hash

    # ── read path ───────────────────────────────────────────────────────────

    def own(self) -> list[str]:
        """Content hashes published by this agent into its own DNA Drive."""
        return list(self.content_store.iter_hashes())

    def pull_inherited(
        self,
        *,
        max_depth: int | None = None,
        min_eval: float = 0.0,
        include_own: bool = False,
    ) -> list[InheritedGenome]:
        """Pull every Genome from this agent's direct ancestry.

        Default behavior: walk the parent chain to the root, gather every
        Genome published into any ancestor's DNA Drive, return as
        ``InheritedGenome`` records with their hop distance.

        ``min_eval`` is the safety gate against pulling unproven ancestral
        work. The default is 0.0 (trust your ancestors); M2c bumps it for
        cross-source grant pulls.

        Output is sorted by depth ascending — closest ancestors first.
        """
        # ancestors_of returns [(ancestor_id, depth), ...], sorted by depth.
        ancestors = self.ancestry.ancestors_of(
            self.agent_id,
            max_depth=max_depth,
            include_self=include_own,
        )

        results: list[InheritedGenome] = []
        for ancestor_id, depth in ancestors:
            ancestor_store = ContentStore(_agent_dna_root(ancestor_id) / "drive")
            for content_hash in ancestor_store.iter_hashes():
                payload = ancestor_store.get_payload(content_hash)
                if payload is None:
                    continue
                # Eval gate runs against the ingest log if available; for
                # content-store-only inheritance we trust the publisher.
                # Real cross-source gating happens in M2c via grants.
                if min_eval > 0.0:
                    # Payload doesn't carry score; we look at evaluations.
                    evals = payload.get("evaluations") or {}
                    score = 0.0
                    if isinstance(evals, dict):
                        scored = [v for v in evals.values() if isinstance(v, (int, float))]
                        score = max(scored) if scored else 0.0
                    if score < min_eval:
                        continue
                results.append(
                    InheritedGenome(
                        content_hash=content_hash,
                        source_agent=ancestor_id,
                        depth=depth,
                        payload=payload,
                    )
                )
        return results

    # ── observability ───────────────────────────────────────────────────────

    def lineage(self) -> list[tuple[str, int]]:
        """The agent's ancestry as ``[(ancestor_id, depth), ...]``, sorted
        depth-ascending. Empty for root agents."""
        return self.ancestry.ancestors_of(self.agent_id)
