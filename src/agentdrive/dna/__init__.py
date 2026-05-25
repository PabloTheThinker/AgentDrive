"""AgentDrive DNA — the ancestral inheritance layer.

The third tier of v2's Drive topology. Each agent has its own DNA Drive
holding Genomes inherited from its direct ancestors, plus Genomes it has
earned that will pass to its descendants.

Forward-only by default: descendants pull from ancestors by walking the
ancestry DAG. Cycles are forbidden by construction (an agent can only
declare parents from agents that already exist; ``created_at(parent) <
created_at(child)`` is enforced at write time).

Sideways flow across cousin agents from different swarms is opt-in via
``LineageShareGrant`` (Milestone 2c). The DNA Drive itself only knows
about ancestry — grants are a separate primitive that layers on top.

See ``docs/AGENTDRIVE-V2-INHERITANCE.md`` for the full design rationale.
"""

from .ancestry import Ancestry, AncestryClosureError, NoSuchAgentError
from .drive import DNADrive, InheritedGenome
from .grants import (
    GrantInvalidError,
    GrantQuotaExceededError,
    GrantScope,
    GrantStore,
    LineageShareGrant,
    ReducerKind,
    pull_via_grant,
)

__all__ = [
    "Ancestry",
    "AncestryClosureError",
    "NoSuchAgentError",
    "DNADrive",
    "InheritedGenome",
    # v2 / Milestone 2c: lineage_share grants
    "LineageShareGrant",
    "GrantScope",
    "GrantStore",
    "GrantInvalidError",
    "GrantQuotaExceededError",
    "ReducerKind",
    "pull_via_grant",
]
