"""Hello, AgentDrive — smallest end-to-end (fully working today).

Ingest a Genome (structured, versioned, content-addressed "DNA" / reasoning
pattern an agent learned) into your Personal Drive, verify deduplication
semantics via the content store, then pull relevant DNA via the Harness.

This is the absolute minimum "agent participates in the living pool".

Run:
    python3 examples/01_hello_drive.py

See also:
- 02_dedup.py (content-addressing payoff)
- 03_swarm.py (shared swarm substrate)
- 04_quarantine_workflow.py (the mandatory foreign-DNA gate)
- 05_lineage_dna_grants.py (DNA, grants, immune system, evolver — the new lineage-enhanced features)
"""

from __future__ import annotations

from agentdrive import AgentDrive, Harness
from agentdrive.genome.models import Genome

# 1. Open the default Drive (lives at ~/.agentdrive/drive/).
drive = AgentDrive()
print(f"Drive ready at: {drive.drive_path}")

# 2. Create a Genome — a structured "I learned to do X" record.
g = Genome.create(
    id="dedup-via-content-hash",
    version="1.0.0",
    framework={
        "steps": [
            {
                "id": "1",
                "name": "Canonicalize the payload — sorted keys, minimal separators, UTF-8",
            },
            {"id": "2", "name": "SHA-256 the canonical bytes"},
            {"id": "3", "name": "Write to objects/<aa>/<rest>.json; existing path is a dedup hit"},
        ],
    },
    authors=[{"type": "agent", "name": "ExampleAgent", "id": "demo-1"}],
    applicability={
        "domains": ["storage", "agents"],
        "problem_signatures": ["dedup identical agent outputs"],
    },
    evaluation_score={"reference_tasks": 0.9},
)

# 3. Ingest. The Drive writes to both the registry (legacy path) and the
# content-addressed object store (the v2 path that enables dedup + provenance).
result = drive.ingest(g, source="examples/01_hello_drive", actor="you")
print(f"Ingested: {result.genome_id}  accepted={result.accepted}")

# 4. Verify it's content-addressed.
print(f"Content hash : {g.compute_content_hash()}")
print(f"In store?    : {drive.has_content(g.compute_content_hash())}")

# 5. Query as an agent would.
harness = Harness(agent_id="example-1", pool=drive)
hits = harness.pull_relevant_dna(task="how do I dedup identical agent outputs?", top_k=3)
print(f"\nQuery returned {len(hits)} relevant Genome(s):")
for h in hits:
    gid = h["genome_id"] if isinstance(h, dict) else h.manifest.id
    print(f"  - {gid}")
