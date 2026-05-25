"""Dedup demo.

Two Genomes with **different ids** but **identical content** ingest into one
underlying object on disk. This is the content-addressing payoff: two
sub-agents that independently discover the same pattern store it once.

Run:
    python3 examples/02_dedup.py
"""

from __future__ import annotations

from agentdrive import AgentDrive
from agentdrive.genome.models import Genome

SHARED_FRAMEWORK = {
    "steps": [
        {"id": "1", "name": "Audit the surface — class, kwarg, env var, path"},
        {"id": "2", "name": "One sed pass per layer; never cross layers"},
        {"id": "3", "name": "Re-run tests after every layer"},
    ],
}


def _make(gid: str) -> Genome:
    """Same framework, different id. The framework defines identity; the id
    is just a human-readable label."""
    return Genome.create(
        id=gid,
        version="1.0.0",
        framework=SHARED_FRAMEWORK,
        applicability={"domains": ["refactor"]},
    )


drive = AgentDrive()
before = drive.content_count()

drive.ingest(_make("alpha-discovers-the-pattern"), source="agent-A")
drive.ingest(_make("beta-discovers-the-same-pattern"), source="agent-B")

after = drive.content_count()

print(f"Before: {before} objects")
print(f"After : {after} objects (+{after - before}, NOT +2 — the second ingest deduped)")
print()
print("Ingest log shows the dedup flag for visibility:")
for entry in drive.get_ingest_history(limit=2)[-2:]:
    print(f"  {entry['genome_id']:40s}  deduped={entry['deduped']}")
