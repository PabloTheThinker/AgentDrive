"""Framework synthesizer — observation blob → typed framework draft.

Core reasoning primitive in Savant for turning observations into
typed framework drafts for Genomes.

Savant / DNA role:
- Primary tool for *synthesizing new framework steps* from run observations.
- DNA Scanners feed extracted observations (timeline events, tool calls,
  state changes, claims) into `synthesize_framework` → produces
  FrameworkSynthesis with inputs/steps/output_schema + rationale.
- The result can be written into `genome.framework` (the playbook) or
  `genome.reasoning_patterns["synthesized_framework"]`.
- Pure structural (groups by kind, one step per kind) — the "Christian
  Wolff whiteboard move". LLM smoothing can be layered on top later.
- Directly supports the evolutionary engine's "propose new step"
  mutations.

Preserved: FrameworkSynthesis dataclass + to_yaml_dict, synthesize_framework,
synthesis_summary, helpers. Rigor and determinism intact.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class FrameworkSynthesis:
    framework_id: str
    version: str
    display_name: str
    category: str
    inputs: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    output_schema: dict[str, Any] = field(default_factory=dict)
    rationale: list[str] = field(default_factory=list)

    def to_yaml_dict(self) -> dict[str, Any]:
        return {
            "framework": {
                "id": self.framework_id,
                "version": self.version,
                "display_name": self.display_name,
                "category": self.category,
                "inputs": list(self.inputs),
                "steps": list(self.steps),
                "output": {
                    "schema": f"../../schemas/{self.framework_id}-v{self.version.rsplit('.', 1)[0]}.json",
                    "formats": ["markdown", "json"],
                    "title_template": self.display_name + " — {{ subject }}",
                },
            }
        }


def synthesize_framework(
    observations: Iterable[Any],
    *,
    framework_id: str,
    version: str = "0.1.0",
    display_name: str = "",
    category: str = "custom",
) -> FrameworkSynthesis:
    """Build a structural framework draft from an observation list."""
    rows = list(observations)
    by_kind: dict[str, list[Any]] = {}
    for obs in rows:
        kind = _get(obs, "kind") or "unknown"
        by_kind.setdefault(str(kind), []).append(obs)

    inputs: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    schema_props: dict[str, Any] = {}
    rationale: list[str] = []

    if not by_kind:
        rationale.append("no observations supplied; emitted single-step stub")
        steps.append(
            {"id": "summarize", "type": "reasoning", "agent": "savant-core", "output": "summary"}
        )
        schema_props["summary"] = {"type": "string"}
    else:
        for idx, (kind, group) in enumerate(sorted(by_kind.items())):
            slug = _slugify(kind)
            inputs.append(
                {
                    "name": f"{slug}_focus",
                    "type": "string",
                    "required": False,
                    "description": (
                        f"Optional filter for the {kind!r} observations ({len(group)} seen)."
                    ),
                }
            )
            step_id = f"analyze_{slug}"
            steps.append(
                {
                    "id": step_id,
                    "type": "reasoning",
                    "agent": "savant-core",
                    "inputs": [f"{slug}_focus"],
                    "output": f"{slug}_findings",
                }
            )
            schema_props[f"{slug}_findings"] = {
                "type": "object",
                "required": ["count", "themes"],
                "properties": {
                    "count": {"type": "integer"},
                    "themes": {"type": "array", "items": {"type": "string"}},
                    "examples": {"type": "array", "items": {"type": "string"}},
                },
            }
            rationale.append(
                f"step {step_id!r} added because the corpus contains "
                f"{len(group)} {kind!r} observation(s)"
            )
        steps.append(
            {
                "id": "compose_artifact",
                "type": "validate",
                "agent": "savant-core",
                "depends_on": [s["id"] for s in steps],
            }
        )

    schema_required = sorted(schema_props.keys())
    output_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": (display_name or framework_id) + " Artifact",
        "type": "object",
        "required": [
            "framework_id",
            "framework_version",
            "engagement_id",
            "produced_at",
            *schema_required,
        ],
        "properties": {
            "framework_id": {"type": "string", "const": framework_id},
            "framework_version": {
                "type": "string",
                "pattern": r"^\d+\.\d+\.\d+$",
            },
            "engagement_id": {"type": "string"},
            "produced_at": {"type": "string", "format": "date-time"},
            "inputs_hash": {"type": "string"},
            **schema_props,
        },
        "additionalProperties": True,
    }

    return FrameworkSynthesis(
        framework_id=framework_id,
        version=version,
        display_name=display_name or framework_id.replace("-", " ").title(),
        category=category,
        inputs=inputs,
        steps=steps,
        output_schema=output_schema,
        rationale=rationale,
    )


def _get(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _slugify(text: str) -> str:
    import re

    out = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return out or "section"


def synthesis_summary(synthesis: FrameworkSynthesis) -> str:
    """Render a one-paragraph summary suitable for chat output or genome docs."""
    counts = Counter(
        s["id"].split("_")[-1] for s in synthesis.steps if s["id"].startswith("analyze_")
    )
    parts = [f"framework {synthesis.framework_id!r} v{synthesis.version}:"]
    parts.append(
        f"{len(synthesis.inputs)} inputs, "
        f"{len(synthesis.steps)} steps, "
        f"{len(synthesis.output_schema.get('properties', {}))} output fields"
    )
    if counts:
        parts.append(", ".join(f"{k}={v}" for k, v in counts.items()))
    return " | ".join(parts)
