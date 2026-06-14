"""Eval replay MVP — re-score shipped research artifacts."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentdrive.eval.replay import replay_genome_artifact_file

_EXAMPLES = Path(__file__).resolve().parents[1] / "genomes" / "examples"


def test_replay_healingfactor_artifact_decision() -> None:
    path = (
        _EXAMPLES
        / "research-thread-output-healingfactor-synthesis-iteration@stabilization-wave-20260531.json"
    )
    if not path.is_file():
        pytest.skip("missing healingfactor replay fixture")
    result = replay_genome_artifact_file(path, tolerance=0.25)
    assert result["stored_decision"] == "keep_promote_with_lineage"
    assert result["decision_match"] is True
    assert result["replayed_decision"] == "keep_promote_with_lineage"
