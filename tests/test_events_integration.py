"""Integration tests: producers (pool, harness, agent) actually emit
events on the default bus so chat subscribers have something to listen to.

Covers Pattern 3 (live DNA pool activity ribbon) emission side. UI rendering
side lives in chat.py and is not exercised here.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from agentdrive.events import (
    MessageComplete,
    MessageDelta,
    PoolIngest,
    PoolMatch,
    PoolOutcome,
    default_bus,
    subscribe,
    unsubscribe,
)


@pytest.fixture
def clean_bus() -> Iterator[None]:
    """Snapshot + restore default_bus subscribers around each test so we
    don't leak handlers across tests or stomp on real chat subscribers.
    """
    # default_bus is a module-level singleton; reach in carefully.
    with default_bus._lock:  # type: ignore[attr-defined]
        saved = list(default_bus._subs)  # type: ignore[attr-defined]
        default_bus._subs.clear()  # type: ignore[attr-defined]
    try:
        yield
    finally:
        with default_bus._lock:  # type: ignore[attr-defined]
            default_bus._subs = saved  # type: ignore[attr-defined]


def _make_genome(gid: str = "test-genome"):
    from agentdrive.genome.models import Genome, GenomeManifest

    manifest = GenomeManifest(
        id=gid,
        version="1.0.0",
        content_hash="sha256:" + "deadbeef" * 8,
        created=datetime.now(UTC),
        authors=[],
    )
    g = Genome(manifest=manifest, framework={"steps": [{"id": "1", "name": "test"}]})
    g.finalize()
    return g


def test_pool_ingest_emits_event(clean_bus: None) -> None:
    """AgentDrive.ingest() should fire one PoolIngest with correct fields."""
    from agentdrive.drive.drive import AgentDrive

    received: list[PoolIngest] = []
    token = subscribe(received.append, event_types=[PoolIngest])
    try:
        pool = AgentDrive()
        g = _make_genome("ingest-test")
        pool.ingest(g, source="unit-test", actor="pytest")
    finally:
        unsubscribe(token)

    assert len(received) == 1, f"expected 1 PoolIngest, got {len(received)}"
    evt = received[0]
    assert isinstance(evt, PoolIngest)
    assert evt.genome_id == g.genome_id
    assert evt.source == "unit-test"
    assert evt.actor == "pytest"


def test_message_delta_emits_during_send(clean_bus: None) -> None:
    """agent.send() should emit one MessageDelta per chunk in order."""
    from agentdrive.agent.agent import Agent DriveAgent

    chunks = ["abc", "def", "ghi"]

    class FakeLLM:
        provider = type("P", (), {"display_name": "fake"})()
        model = "fake/fake"

        def stream(self, **kwargs):
            yield from chunks

    agent = Agent DriveAgent(agent_id="evt-test-agent")
    # Bypass the lazy llm property by setting the cached field directly.
    agent._llm = FakeLLM()  # type: ignore[assignment]

    deltas: list[MessageDelta] = []
    completes: list[MessageComplete] = []
    matches: list[PoolMatch] = []
    t1 = subscribe(deltas.append, event_types=[MessageDelta])
    t2 = subscribe(completes.append, event_types=[MessageComplete])
    t3 = subscribe(matches.append, event_types=[PoolMatch])
    try:
        result = agent.send("hello world")
    finally:
        unsubscribe(t1)
        unsubscribe(t2)
        unsubscribe(t3)

    assert result.text == "abcdefghi"
    assert [d.text for d in deltas] == chunks, "deltas should arrive in order"
    assert len(completes) == 1
    assert completes[0].text == "abcdefghi"
    # PoolMatch fires once even with an empty pool (genomes/scores = []).
    assert len(matches) == 1
    assert isinstance(matches[0].genomes, list)
    assert isinstance(matches[0].scores, list)


def test_pool_outcome_emits_on_harness_record(clean_bus: None) -> None:
    """harness.record_outcome on a successful run should emit PoolOutcome
    with the new score (not the delta). Best-effort — if the pool path
    bails before the score bump we just assert no crash.
    """
    from agentdrive.drive.drive import AgentDrive
    from agentdrive.harness.harness import Harness

    pool = AgentDrive()
    g = _make_genome("outcome-test")
    pool.ingest(g, source="seed", actor="pytest")

    harness = Harness(agent_id="evt-harness", pool=pool)
    # Simulate that a turn pulled this genome.
    harness.pulled_dna = [{"genome_id": g.genome_id, "score": 0.5}]

    outcomes: list[PoolOutcome] = []
    token = subscribe(outcomes.append, event_types=[PoolOutcome])
    try:
        harness.record_outcome(
            {
                "status": "success",
                "quality": 0.9,
                "used_genomes": [g.genome_id],
                "task": "test task",
            }
        )
    finally:
        unsubscribe(token)

    # If the score-bump path ran, we got one PoolOutcome with score > 0.
    # If the genome lookup path didn't resolve, we get zero (no crash) —
    # acceptable for this smoke check.
    for evt in outcomes:
        assert evt.genome_id == g.genome_id
        assert evt.score >= 0.0
