"""
Tests for agentdrive_think MCP synthesis surface and mandatory gap enforcement.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agentdrive.constants import using_correlation_id
from agentdrive.synthesis.engine import (
    Citation,
    Gap,
    SynthesisResult,
    _ensure_mandatory_gaps,
)


def _sample_result(*, gaps: list[Gap] | None = None) -> SynthesisResult:
    return SynthesisResult(
        question="How do we rotate secrets?",
        answer="Use short-lived credentials and audit rotation events.",
        citations=[
            Citation(
                source_type="genome",
                source_id="security-rotation@v1",
                snippet="Rotate secrets on schedule",
                confidence=0.9,
            )
        ],
        gaps=gaps or [],
        genomes_used=["security-rotation@v1"],
        contradictions=[{"description": "conflicting TTL guidance", "severity": "medium"}],
    )


def test_synthesis_result_to_mcp_dict_required_fields():
    with using_correlation_id("cid-mcp-think-001"):
        result = _sample_result(
            gaps=[
                Gap(
                    description="Sparse graph for security genomes",
                    severity="medium",
                    suggested_action="Ingest more security playbooks",
                )
            ]
        )
        payload = result.to_mcp_dict()

    assert payload["answer"] == result.answer
    assert payload["correlation_id"] == "cid-mcp-think-001"
    assert payload["genomes_used"] == ["security-rotation@v1"]
    assert payload["contradictions"] == result.contradictions
    assert len(payload["citations"]) == 1
    assert payload["citations"][0] == {
        "source_type": "genome",
        "source_id": "security-rotation@v1",
        "snippet": "Rotate secrets on schedule",
        "confidence": 0.9,
    }
    assert len(payload["gaps"]) == 1
    assert payload["gaps"][0] == {
        "description": "Sparse graph for security genomes",
        "severity": "medium",
        "suggested_action": "Ingest more security playbooks",
    }


def test_ensure_mandatory_gaps_injects_when_empty():
    question = "What is the promotion gate policy?"
    payload = _sample_result(gaps=[]).to_mcp_dict()
    assert payload["gaps"] == []

    enriched = _ensure_mandatory_gaps(payload, question)

    assert len(enriched["gaps"]) == 1
    gap = enriched["gaps"][0]
    assert gap["severity"] == "high"
    assert question in gap["description"]
    assert "Insufficient evidence in drive for full answer on:" in gap["description"]
    assert gap["suggested_action"]


def test_ensure_mandatory_gaps_preserves_existing_gaps():
    question = "How do we handle secret rotation?"
    payload = _sample_result(gaps=[Gap("Existing honest gap", "low", "noop")]).to_mcp_dict()

    enriched = _ensure_mandatory_gaps(payload, question)

    assert len(enriched["gaps"]) == 1
    assert enriched["gaps"][0]["description"] == "Existing honest gap"


def test_ensure_mandatory_gaps_repairs_non_list_gaps():
    payload = {"gaps": None, "answer": "partial"}
    enriched = _ensure_mandatory_gaps(payload, "orphan question")

    assert isinstance(enriched["gaps"], list)
    assert len(enriched["gaps"]) == 1
    assert enriched["gaps"][0]["severity"] == "high"


@patch("agentdrive.adapters.mcp_server._get_pool")
def test_agentdrive_think_tool_returns_mandatory_gaps(mock_get_pool):
    pytest.importorskip("mcp")

    mock_pool = MagicMock()
    mock_pool.think.return_value = _sample_result(gaps=[])
    mock_get_pool.return_value = mock_pool

    from agentdrive.adapters.mcp_server import create_mcp_server

    server = create_mcp_server()
    think_tool = None
    for name, fn in server._tool_manager._tools.items():
        if name == "agentdrive_think":
            think_tool = fn
            break

    assert think_tool is not None, "agentdrive_think tool not registered"

    raw = think_tool.fn(
        question="What is the council approval flow?",
        swarm_id="stabilization-wave-20260531",
        prefer_experience_layer=True,
    )
    payload = json.loads(raw)

    mock_pool.think.assert_called_once_with(
        "What is the council approval flow?",
        prefer_experience_layer=True,
    )
    assert payload["answer"]
    assert payload["correlation_id"]
    assert len(payload["gaps"]) >= 1
    assert payload["gaps"][0]["severity"] == "high"
    assert "Insufficient evidence in drive for full answer on:" in payload["gaps"][0]["description"]
