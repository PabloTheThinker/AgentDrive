"""Swarm demo — two sub-agents sharing one swarm Drive (v2 / Milestone 2a).

Each sub-agent in a swarm now writes to the SAME Drive, namespacing its
writes via the Genome author field. Siblings can read each other's work
without any cross-config — this is the "we work together" experience pool.

Run:
    python3 examples/03_swarm.py
"""

from __future__ import annotations

from agentdrive.drive.swarm_manager import get_swarm_drive_manager
from agentdrive.genome.models import Genome

SWARM = "examples-swarm-2026-05"

mgr = get_swarm_drive_manager()
worker_a = mgr.get_or_create_pool(swarm_id=SWARM, subagent_id="worker-a")
worker_b = mgr.get_or_create_pool(swarm_id=SWARM, subagent_id="worker-b")

print(f"worker-a Drive: {worker_a.drive_path}")
print(f"worker-b Drive: {worker_b.drive_path}")
print(f"Same Drive instance? {worker_a is worker_b}")
print()

# A learns one thing. B learns a different thing.
worker_a.ingest(
    Genome.create(
        id="postmortem-causality",
        version="1.0.0",
        framework={"steps": [{"id": "1", "name": "Establish facts before assigning blame"}]},
    ),
    source="worker-a",
    subagent_id="worker-a",
)
worker_b.ingest(
    Genome.create(
        id="changelog-craft",
        version="1.0.0",
        framework={"steps": [{"id": "1", "name": "Lead with WHY, not WHAT"}]},
    ),
    source="worker-b",
    subagent_id="worker-b",
)

print(f"Shared Drive content objects: {worker_a.content_count()}")
print(f"Sub-agents who have written : {worker_a.writers()}")
print()
print("What did worker-a write?")
for entry in worker_a.genomes_by_subagent("worker-a"):
    print(f"  - {entry['genome_id']}")
print()
print("worker-b can ask the same question and see worker-a's contribution:")
for entry in worker_b.genomes_by_subagent("worker-a"):
    print(f"  - {entry['genome_id']}")
print()
print("Sibling learning is on by default. v2 / Milestone 2a — shipped.")
