from agentdrive.dna import DNADrive
from agentdrive.genome.models import Genome
from agentdrive.harness.harness import Harness


def _genome(gid: str, score: float = 0.8) -> Genome:
    return Genome.create(
        id=gid,
        version="1.0.0",
        framework={"steps": [{"id": "1", "name": f"Use inherited pattern {gid}"}]},
        reasoning_patterns={"heuristics": [f"{gid} heuristic"]},
        evaluations={"reference_tasks": score},
    )


def test_harness_can_publish_to_own_dna() -> None:
    dna = DNADrive("agent-a")
    harness = Harness(agent_id="agent-a", dna_drive=dna)

    content_hash = harness.publish_to_dna(_genome("owned-pattern"))

    assert content_hash in dna.own()


def test_harness_pulls_inherited_dna_packets() -> None:
    parent = DNADrive("parent-agent")
    parent_hash = parent.publish(_genome("parent-pattern", score=0.9))
    child = DNADrive("child-agent", parents=["parent-agent"])
    harness = Harness(agent_id="child-agent", dna_drive=child)

    packets = harness.pull_inherited_dna()

    assert packets == [
        {
            "genome_id": parent_hash,
            "content_hash": parent_hash,
            "framework": {"steps": [{"id": "1", "name": "Use inherited pattern parent-pattern"}]},
            "top_reasoning": ["heuristics"],
            "score": 0.9,
            "source_agent": "parent-agent",
            "lineage_depth": 1,
            "inherited": True,
        }
    ]
    assert harness.pulled_dna == packets


def test_harness_inherited_dna_respects_min_eval_gate() -> None:
    parent = DNADrive("parent-agent")
    parent.publish(_genome("weak-pattern", score=0.2))
    child = DNADrive("child-agent", parents=["parent-agent"])
    harness = Harness(agent_id="child-agent", dna_drive=child)

    assert harness.pull_inherited_dna(min_eval=0.7) == []
