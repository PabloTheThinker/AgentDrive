"""Fabric-style layered prompt composition for the AgentDrive Harness.

Layers (outer → inner): STRATEGY (genome) → CONTEXT → PATTERN → SESSION → base task.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentdrive.constants import get_agentdrive_home
from agentdrive.patterns.catalog import apply_pattern


@dataclass
class ComposeLayers:
    """Optional Fabric-style composition layers for ``Harness.compose_context``."""

    strategy: str | None = None
    context: str | None = None
    pattern: str | None = None
    session_id: str | None = None
    input_text: str | None = None

    @property
    def active(self) -> bool:
        """True when at least one layer field is set."""
        return any(
            field is not None and str(field).strip()
            for field in (self.strategy, self.context, self.pattern, self.session_id)
        )


def _get_genome(pool: Any, genome_id: str) -> Any | None:
    """Resolve a genome from a pool-like object."""
    if hasattr(pool, "get_genome"):
        genome = pool.get_genome(genome_id)
        if genome is None:
            base = genome_id.split("@", 1)[0] if "@" in genome_id else genome_id
            genome = pool.get_genome(base)
        return genome
    if hasattr(pool, "registry"):
        registry = pool.registry
        genome = registry.get_genome(genome_id)
        if genome is None:
            base = genome_id.split("@", 1)[0] if "@" in genome_id else genome_id
            genome = registry.get_genome(base) or registry.load(base)
        return genome
    return None


def resolve_genome_layer(pool: Any, genome_id: str) -> str:
    """Build a short STRATEGY block from a genome framework description and steps."""
    genome = _get_genome(pool, genome_id)
    if genome is None:
        return f"(genome not found: {genome_id})"

    framework = getattr(genome, "framework", None) or {}
    if not isinstance(framework, dict):
        framework = {}

    lines: list[str] = []
    description = framework.get("description")
    if description:
        lines.append(str(description).strip())

    steps = framework.get("steps") or []
    if isinstance(steps, list) and steps:
        lines.append("Steps:")
        for index, step in enumerate(steps[:6], start=1):
            if isinstance(step, dict):
                label = step.get("name") or step.get("id") or str(step)
            else:
                label = str(step)
            lines.append(f"  {index}. {label}")

    if lines:
        return "\n".join(lines)
    return f"Genome: {genome_id}"


def resolve_pattern_layer(pattern_name: str, input_text: str | None = None) -> str:
    """Apply a catalog pattern, substituting ``input_text`` for ``{{input}}``."""
    return apply_pattern(pattern_name, input_text or "")


def resolve_session_layer(session_id: str, limit: int = 5) -> str:
    """Read recent entries from ``~/.agentdrive/sessions/<id>.jsonl``."""
    path = get_agentdrive_home() / "sessions" / f"{session_id}.jsonl"
    if not path.is_file():
        return f"(session not found: {session_id})"

    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    records.append(record)
    except OSError:
        return f"(session unreadable: {session_id})"

    if not records:
        return f"(session empty: {session_id})"

    lines: list[str] = []
    for record in records[-limit:]:
        event = record.get("event")
        if event == "meta":
            title = record.get("title", record.get("session_id", session_id))
            lines.append(f"[meta] {title}")
            continue
        if event == "turn":
            role = record.get("role", "unknown")
            content = str(record.get("content", "")).strip()
            if content:
                preview = content if len(content) <= 200 else content[:197] + "..."
                lines.append(f"[{role}] {preview}")
            continue

        role = record.get("role", record.get("type", "entry"))
        content = record.get("content", record.get("message", record.get("text", "")))
        if content:
            preview = str(content).strip()
            if len(preview) > 200:
                preview = preview[:197] + "..."
            lines.append(f"[{role}] {preview}")
        elif record.get("insight"):
            lines.append(f"[{role}] {record['insight']}")

    if not lines:
        return f"(session has no readable entries: {session_id})"
    return "\n".join(lines)


def _section(title: str, body: str) -> str:
    body = body.strip()
    if not body:
        return ""
    return f"## {title}\n\n{body}"


def assemble_layered_prompt(base: str, layers: ComposeLayers, pool: Any) -> str:
    """Assemble STRATEGY → CONTEXT → PATTERN → SESSION sections, then the base prompt."""
    sections: list[str] = []

    if layers.strategy and layers.strategy.strip():
        sections.append(_section("STRATEGY", resolve_genome_layer(pool, layers.strategy.strip())))

    if layers.context and layers.context.strip():
        sections.append(_section("CONTEXT", layers.context.strip()))

    if layers.pattern and layers.pattern.strip():
        sections.append(
            _section(
                "PATTERN",
                resolve_pattern_layer(layers.pattern.strip(), layers.input_text),
            )
        )

    if layers.session_id and layers.session_id.strip():
        sections.append(_section("SESSION", resolve_session_layer(layers.session_id.strip())))

    sections = [section for section in sections if section]
    if sections:
        return "\n\n".join(sections) + f"\n\n{base}"
    return base


def sessions_dir() -> Path:
    """Return the top-level sessions directory used by ``resolve_session_layer``."""
    return get_agentdrive_home() / "sessions"
