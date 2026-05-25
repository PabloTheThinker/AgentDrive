"""AgentDrive capability URIs — the single access primitive.

The "AgentDrive moment" identified in ``docs/AGENTDRIVE-PROGRESS.md`` is
that capability URIs become the *one* way every component talks about
access. Every Drive surface — Personal Drive, Swarm Drive, DNA Drive,
peer federation, Snapshot Backup — verifies the same cap the same way.

A capability looks like a URI for human eyes and a signed bytestring for
the verifier:

    drive:read:swarm:demo-2026/sub:planner
    drive:write:swarm:demo-2026
    dna:pull:lineage:agent-7:max_hops=3:min_eval=0.7
    backup:restore:agent:agent-7

The wire form is the URI + a detached Ed25519 signature + the issuer's
public key. Verification is a single function call against a known root.

Three operations:

- **mint** — an authority creates a cap for a grantee. Subset minting:
  a holder can mint a cap that is STRICTLY narrower than their own.
- **derive** — a write-cap implicitly grants the matching read-cap. A
  swarm-wide cap implicitly grants per-sub-agent caps. Derivation is a
  one-way structural attenuation; the derived cap is signed by the same
  authority as the parent.
- **verify** — checks signature, expiry, revocation, and that the cap's
  scope actually covers the requested action.

Two principles the design holds to:

1. **Possession is permission.** No identity layer. A cap presented at a
   Drive boundary either verifies or doesn't. This is the Tahoe-LAFS
   pattern — also Resilio's — and it's what makes the model scale
   without an ACL service.
2. **One bound knot.** All Drive surfaces verify caps via the same
   ``CapStore.verify_request()`` call. The 30-line cap resolver lives
   in this module and that's the AgentDrive moment.

See ``docs/AGENTDRIVE-V2.md`` (move #2 + #3) and
``docs/AGENTDRIVE-V2-INHERITANCE.md`` for the full architectural rationale.
"""

from .store import (
    CapDerivationError,
    CapInvalidError,
    CapStore,
    CapVerifyContext,
    InsufficientCapability,
)
from .uri import Capability, CapURIError, parse_uri

__all__ = [
    "Capability",
    "CapURIError",
    "CapStore",
    "CapInvalidError",
    "CapDerivationError",
    "InsufficientCapability",
    "CapVerifyContext",
    "parse_uri",
]
