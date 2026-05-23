"""
Savant Swarm Pool Policies — Professional, user-controlled rules for DNA sharing in agent swarms.

Professional approach to subagent isolation with clear delegation controls,
depth limits, approval callbacks, and config-driven behavior.

Every policy decision is:
- Explicit and auditable
- User-overridable (via config or direct instruction to any connected AI)
- Safe by default (sub-agents are isolated unless the user relaxes rules)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Set

IsolationLevel = Literal["none", "swarm", "subagent"]
SharingPolicy = Literal["none", "read", "selective", "full"]


@dataclass(frozen=True)
class SwarmPoolPolicy:
    """
    Controls how DNA (genomes) can flow between agents in a swarm.

    This is the core of professional swarm behavior:
    - Sub-agents start with strong isolation (restricted toolsets and data access by default)
    - The user (or user-instructed AI) can relax policies per swarm or globally
    - All sharing is explicit and logged for audit
    """

    # How strongly sub-agent pools are isolated from each other and the parent
    isolation_level: IsolationLevel = "subagent"

    # What a child pool is allowed to do with the parent's DNA
    parent_to_child: SharingPolicy = "read"          # children can usually read parent's best practices

    # What children are allowed to contribute upward
    child_to_parent: SharingPolicy = "selective"     # safe default: only high-value DNA bubbles up

    # Can siblings (other sub-agents in the same swarm) share DNA with each other?
    sibling_sharing: SharingPolicy = "none"

    # Automatically accept high-quality genomes discovered by children?
    auto_ingest_from_children: bool = True

    # Minimum quality score a genome must have to be shared across pool boundaries
    min_quality_for_sharing: float = 0.80

    # Explicitly blocked genome categories (e.g. "personal", "experimental", "security-sensitive")
    blocked_categories: Set[str] = field(default_factory=set)

    # Maximum depth of nested swarms (prevents uncontrolled grandchild proliferation)
    max_swarm_depth: int = 2

    def allows_read(self, from_level: str, to_level: str) -> bool:
        """Helper for policy checks."""
        if self.isolation_level == "none":
            return True
        if self.isolation_level == "swarm" and from_level == "swarm" and to_level == "swarm":
            return self.sibling_sharing in ("read", "selective", "full")
        # Add more granular rules as needed
        return False

    def is_safe_default(self) -> bool:
        """Returns True if this policy matches the recommended safe starting point."""
        return (
            self.isolation_level == "subagent"
            and self.parent_to_child == "read"
            and self.child_to_parent == "selective"
            and self.sibling_sharing == "none"
        )
