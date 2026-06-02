"""
Swarm Status Helper

Used by the Conductor and all role-swarm participants to get a quick view of what the
specialized swarms are currently working on.
"""

import os


def print_swarm_family_status():
    current = os.environ.get("AGENTDRIVE_SWARM_ID", "main")
    print("\n=== AgentDrive Role-Swarm Family Status ===")
    print(f"Current context: {current}")
    print("Active role-swarm participants:")
    for rid in ["dissector", "synthesis", "graph", "schema", "dream"]:
        print(f"  - {rid}")
    print("Experience and calibration layers:")
    for rid in ["calibration", "experience"]:
        print(f"  - {rid}")
    print("  (Experience Layer: living-experience genomes as Conductor daily starting point)")
    print("\nShared infrastructure:")
    print("  - knowledge_graph (typed edges + multi-hop)")
    print("  - synthesis engine (with gaps)")
    print("  - schema_packs")
    print("  - durable dreaming primitives")
    print("  - central coordination + roadmap")
    print(
        "  - living-experience layer (fused One Experience -> versioned genome family; entry point for drive.think)"
    )
    print("\nAll work is automatically shared via the main AgentDrive + knowledge_graph.")
    print(
        "The experience layer wires fused genomes as the single source of truth for new Conductors."
    )
