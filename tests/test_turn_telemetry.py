"""Tests for chat turn subagent telemetry."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agentdrive.agent.agent import AgentDriveAgent
from agentdrive.agent.turn_telemetry import ChatTurnTelemetry
from agentdrive.events import default_bus


def test_chat_turn_telemetry_emits_spawn_and_done():
    events: list = []
    token = default_bus.subscribe(lambda ev: events.append(type(ev).__name__))

    telemetry = ChatTurnTelemetry(session_id="sess-abc12345")
    telemetry.begin()
    telemetry.tool("pool.query(2 genomes)")
    telemetry.add_chunk("hello world")
    telemetry.finish(ok=True)

    default_bus.unsubscribe(token)
    assert "SubagentSpawn" in events
    assert "SubagentTool" in events
    assert "SubagentTokens" in events
    assert "SubagentDone" in events


def test_agent_send_emits_subagent_events(isolated_agentdrive_home):
    """Integration: a mocked LLM turn emits subagent bus events."""
    captured: list[str] = []
    token = default_bus.subscribe(lambda ev: captured.append(type(ev).__name__))

    agent = AgentDriveAgent(agent_id="telemetry-test")
    mock_llm = MagicMock()
    mock_llm.provider = MagicMock()
    mock_llm.provider.display_name = "Test"
    mock_llm.provider.name = "test"
    mock_llm.model = "test-model"
    mock_llm.stream.return_value = iter(["Hi ", "there"])
    agent._llm = mock_llm

    with patch.object(
        agent.harness,
        "pull_relevant_dna",
        return_value=[{"genome_id": "g1", "relevance_score": 0.9}],
    ):
        with patch.object(agent.harness, "record_outcome"):
            result = agent.send("hello")

    default_bus.unsubscribe(token)
    assert result.text == "Hi there"
    assert "SubagentSpawn" in captured
    assert "SubagentTool" in captured
    assert "SubagentDone" in captured


def test_stream_lanes_combined_renderable():
    """Both lanes can produce renderables from the same event burst."""
    from agentdrive.events import PoolMatch, SubagentSpawn, emit
    from agentdrive.tui.pool_lane import PoolActivityLane
    from agentdrive.tui.swarm_lane import SwarmActivityLane

    swarm = SwarmActivityLane()
    pool = PoolActivityLane()
    swarm.attach()
    pool.attach()
    try:
        emit(
            SubagentSpawn(
                subagent_id="chat-deadbeef",
                parent_id="orchestrator",
                label="chat turn",
            )
        )
        emit(PoolMatch(genomes=["dna-1"], scores=[0.88]))
        assert swarm.renderable() is not None
        assert pool.renderable() is not None
    finally:
        swarm.detach()
        pool.detach()