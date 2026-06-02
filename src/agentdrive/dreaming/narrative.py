"""
narrative — write Dream Diary entries as a byproduct of substantive dream work.

Design goals:
- Keep diary generation secondary to actual consolidation and hypothetical agent emergence.
- Preserve phase context and provenance for auditability.
- No new magic — just disciplined composition + Agent Drive / Genome idioms.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from agentdrive.genome.models import Genome


@dataclass
class NarrativeConfig:
    """Paths and formatting rules for Dream Diary output."""

    diary_root: Path = field(
        default_factory=lambda: Path("~/.agentdrive/dreams/diary").expanduser()
    )
    diary_name: str = "DREAMS.md"
    append_jsonl: bool = True


@dataclass
class DreamDiaryEntry:
    """Narrative record emitted after a dream phase finishes."""

    run_id: str = ""
    phase: str = ""
    created_at: float = 0.0
    summary: str = ""
    prompt: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DreamNarrator:
    """Diary writer that can use a subagent or raw primitives."""

    config: NarrativeConfig = field(default_factory=NarrativeConfig)

    def render_phase_prompt(self, run_id: str, phase: str, payload: dict[str, Any]) -> str:
        """Render the prompt/context passed to the Dream Diary writer."""
        prompt_lines = [
            f"Run: {run_id}",
            f"Phase: {phase}",
            "Summarize the Loom's reflection in operationally precise terms.",
        ]
        metrics = payload.get("metrics")
        if metrics:
            prompt_lines.append(f"Metrics: {json.dumps(metrics, sort_keys=True, default=str)}")
        return "\n".join(prompt_lines)

    def dispatch_phase_diary(
        self, run_id: str, phase: str, payload: dict[str, Any]
    ) -> DreamDiaryEntry:
        """Dispatch or synthesize a Dream Diary entry for one completed phase."""
        prompt = self.render_phase_prompt(run_id, phase, payload)
        metrics = payload.get("metrics") or {}
        summary = f"Loom Dreaming completed {phase} for {run_id} with {len(metrics)} metric fields."
        return DreamDiaryEntry(
            run_id=run_id,
            phase=phase,
            created_at=time.time(),
            summary=summary,
            prompt=prompt,
            metadata={"metrics": metrics},
        )

    def write_phase_entry(self, entry: DreamDiaryEntry) -> Path:
        """Persist a Dream Diary entry to markdown and optional JSONL."""
        self.config.diary_root.mkdir(parents=True, exist_ok=True)
        markdown_path = self.config.diary_root / self.config.diary_name
        with markdown_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n## {entry.run_id} / {entry.phase}\n\n")
            handle.write(f"{entry.summary}\n")
        if self.config.append_jsonl:
            jsonl_path = self.config.diary_root / "dreams.jsonl"
            with jsonl_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(entry), sort_keys=True, default=str) + "\n")
        return markdown_path


def genome_narrative_anchor(genome: Genome | None) -> str:
    """Return a stable Genome anchor for future diary subagent dispatch."""
    return genome.genome_id if genome else ""
