"""
LLM-backed branch spawning and forward simulation for Multiverse Cognition (M2).

Uses Harness DNA compose + local model dispatch when available.
Falls back gracefully to heuristic mode when no model is reachable.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from agentdrive.cognition.roles import role_system_prompt
from agentdrive.cognition.multiverse import (
    AdversaryVerdict,
    Branch,
    ForwardStep,
)

logger = logging.getLogger(__name__)


def _extract_json(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def resolve_available_local_model() -> Any | None:
    """Return first reachable LocalModelSpec from ~/.agentdrive/local_models.yaml."""
    try:
        from agentdrive.local_models import is_available, load_specs

        for spec in load_specs():
            if is_available(spec):
                return spec
    except Exception as exc:
        logger.debug("resolve_available_local_model failed: %s", exc)
    return None


class LLMBranchSpawner:
    """Spawn and simulate branches via local LLM + Harness context."""

    def __init__(
        self,
        *,
        agent_id: str = "multiverse-llm-spawner",
        model_spec: Any | None = None,
        harness_task: str | None = None,
        fabric_context: dict[str, Any] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.model_spec = model_spec or resolve_available_local_model()
        self.harness_task = harness_task
        self.fabric_context = fabric_context or {}
        self.llm_calls = 0
        self.llm_available = self.model_spec is not None

    def _generate(self, system: str, user: str) -> str:
        if not self.model_spec:
            return ""
        from agentdrive.local_models import LocalModelError, generate

        self.llm_calls += 1
        try:
            return generate(self.model_spec, user, system=system)
        except LocalModelError as exc:
            logger.debug("LLM generate failed: %s", exc)
            return ""

    def spawn_branch(
        self,
        trigger: str,
        role: str,
        axis: str,
        *,
        index: int,
    ) -> Branch | None:
        """LLM spawn one branch. Returns None on failure (caller uses heuristic)."""
        if not self.model_spec:
            return None

        system = role_system_prompt(role, axis)
        user = json.dumps(
            {
                "trigger": trigger,
                "role": role,
                "divergence_axis": axis,
                "fabric_context_snippet": {
                    k: self.fabric_context.get(k)
                    for k in ("top_weak_clusters", "strong_continuations", "actionable_recommendations")
                    if k in self.fabric_context
                },
                "required_json_schema": {
                    "path_summary": "one sentence describing this timeline",
                    "assumptions": ["list", "of", "assumptions"],
                    "fragility_flags": ["optional fragile assumptions"],
                },
            },
            default=str,
        )[:3500]

        raw = self._generate(system, user)
        data = _extract_json(raw)
        if not data or not data.get("path_summary"):
            return None

        branch_id = f"branch:{role}-{index}"
        return Branch(
            branch_id=branch_id,
            role=role,
            path_summary=str(data["path_summary"]),
            assumptions=[str(a) for a in (data.get("assumptions") or [])[:6]],
            divergence_axes=[axis],
            fragility_flags=[str(f) for f in (data.get("fragility_flags") or [])[:4]],
        )

    def simulate_forward(
        self,
        trigger: str,
        branch: Branch,
        steps: int,
    ) -> list[ForwardStep] | None:
        if not self.model_spec:
            return None

        system = role_system_prompt(branch.role, branch.divergence_axes[0] if branch.divergence_axes else "risk")
        user = json.dumps(
            {
                "trigger": trigger,
                "branch": {
                    "role": branch.role,
                    "path_summary": branch.path_summary,
                    "assumptions": branch.assumptions,
                },
                "forward_steps_required": steps,
                "required_json_schema": {
                    "forward_steps": [
                        {"step_index": 1, "description": "immediate consequence", "confidence": 0.7}
                    ]
                },
            },
            default=str,
        )[:3500]

        raw = self._generate(system, user)
        data = _extract_json(raw)
        if not data:
            return None

        out: list[ForwardStep] = []
        for item in (data.get("forward_steps") or [])[:steps]:
            if not isinstance(item, dict):
                continue
            out.append(
                ForwardStep(
                    step_index=int(item.get("step_index", len(out) + 1)),
                    description=str(item.get("description", ""))[:300],
                    confidence=float(item.get("confidence", 0.65)),
                )
            )
        return out or None

    def adversary_stress_test(self, branch: Branch) -> AdversaryVerdict | None:
        if not self.model_spec:
            return None

        system = role_system_prompt("adversary", "risk")
        user = json.dumps(
            {
                "branch": {
                    "role": branch.role,
                    "path_summary": branch.path_summary,
                    "assumptions": branch.assumptions,
                    "forward_steps": [s.description for s in branch.forward_steps],
                },
                "required_json_schema": {
                    "passed": True,
                    "fatal_flaws": [],
                    "mitigations": [],
                    "rationale": "short string",
                },
            },
            default=str,
        )[:3000]

        raw = self._generate(system, user)
        data = _extract_json(raw)
        if not data:
            return None

        return AdversaryVerdict(
            passed=bool(data.get("passed", False)),
            fatal_flaws=[str(f) for f in (data.get("fatal_flaws") or [])],
            mitigations=[str(m) for m in (data.get("mitigations") or [])],
            rationale=str(data.get("rationale", "LLM adversary stress-test")),
        )