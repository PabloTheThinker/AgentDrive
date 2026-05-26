"""Pattern memory — persist inferred / extracted frameworks and signatures,
recognize them across runs for Genome enrichment.

Core reasoning primitive in Agent Drive.

In Agent Drive DNA context:
- Scanners and the evolutionary engine use `PatternMemory` to remember
  signatures of successful reasoning patterns extracted from runs
  (intents + fields observed).
- `recognize` finds similar past patterns → enables "this run matches
  the security-postmortem pattern at 0.81" → can propose merging or
  forking the corresponding Genome.
- Stored under `~/.agentdrive/reasoning/patterns/<corpus>.jsonl`
- Supports `genome.reasoning_patterns["recognized_patterns"]` and
  persistent cross-genome learning.

Adapted:
- Removed hard dependency on inferencer (not ported in this batch).
- PatternSignature can be built directly or via `from_run_data`.
- from_report removed; use constructor or from_run_data(framework_id, intents, fields).
- Default root now Agent Drive reasoning dir.
- Jaccard logic and remember/recognize behavior 100% preserved.

This is the "learn from shape" companion to calibration and ledger.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


def _agentdrive_reasoning_root() -> Path:
    base = os.environ.get("AGENTDRIVE_REASONING_ROOT")
    if base:
        return Path(base)
    return Path.home() / ".agentdrive" / "reasoning"


def _default_root() -> Path:
    return _agentdrive_reasoning_root() / "patterns"


@dataclass(slots=True)
class PatternSignature:
    framework_id: str
    intents: list[str]  # sorted unique
    fields: list[str]  # sorted unique
    display_name: str = ""
    occurrences: int = 1
    last_seen_ts: float = 0.0

    def to_dict(self) -> dict:
        return {
            "framework_id": self.framework_id,
            "intents": list(self.intents),
            "fields": list(self.fields),
            "display_name": self.display_name,
            "occurrences": self.occurrences,
            "last_seen_ts": self.last_seen_ts,
        }

    @classmethod
    def from_run_data(
        cls, framework_id: str, intents: list[str], fields: list[str], display_name: str = ""
    ) -> PatternSignature:
        """Build directly from scanner / run analysis results (preferred in Agent Drive)."""
        return cls(
            framework_id=framework_id,
            intents=sorted(set(intents or [])),
            fields=sorted(set(fields or [])),
            display_name=display_name,
            occurrences=1,
            last_seen_ts=time.time(),
        )


@dataclass(slots=True)
class PatternMatch:
    signature: PatternSignature
    score: float
    intent_overlap: float
    field_overlap: float

    def to_dict(self) -> dict:
        return {
            "signature": self.signature.to_dict(),
            "score": round(self.score, 3),
            "intent_overlap": round(self.intent_overlap, 3),
            "field_overlap": round(self.field_overlap, 3),
        }


def _jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sa | sb))


class PatternMemory:
    """JSONL-backed pattern store for Agent Drive reasoning patterns / genomes."""

    def __init__(self, root: Path | None = None, *, corpus: str = "default") -> None:
        self.root = Path(root) if root else _default_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self.corpus = corpus
        self.path = self.root / f"{corpus}.jsonl"

    def _load(self) -> list[PatternSignature]:
        if not self.path.exists():
            return []
        out: list[PatternSignature] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                out.append(
                    PatternSignature(
                        framework_id=str(data.get("framework_id") or ""),
                        intents=list(data.get("intents") or []),
                        fields=list(data.get("fields") or []),
                        display_name=str(data.get("display_name") or ""),
                        occurrences=int(data.get("occurrences") or 1),
                        last_seen_ts=float(data.get("last_seen_ts") or 0.0),
                    )
                )
        return out

    def _rewrite(self, sigs: list[PatternSignature]) -> None:
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for s in sigs:
                fh.write(json.dumps(s.to_dict(), separators=(",", ":")) + "\n")
        tmp.replace(self.path)

    def remember(self, signature: PatternSignature) -> PatternSignature:
        """Add or merge a signature by framework_id."""
        sig = signature
        sigs = self._load()
        merged = False
        for existing in sigs:
            if existing.framework_id == sig.framework_id:
                existing.intents = sorted(set(existing.intents) | set(sig.intents))
                existing.fields = sorted(set(existing.fields) | set(sig.fields))
                existing.occurrences += 1
                existing.last_seen_ts = sig.last_seen_ts or time.time()
                if sig.display_name and not existing.display_name:
                    existing.display_name = sig.display_name
                merged = True
                stored = existing
                break
        if not merged:
            sigs.append(sig)
            stored = sig
        self._rewrite(sigs)
        return stored

    def recognize(
        self, signature: PatternSignature, *, k: int = 3, min_score: float = 0.1
    ) -> list[PatternMatch]:
        """Top-k closest stored signatures by Jaccard(intents) + Jaccard(fields)."""
        sig = signature
        sigs = self._load()
        matches: list[PatternMatch] = []
        for s in sigs:
            if s.framework_id == sig.framework_id:
                # Same id = same framework; don't self-match.
                continue
            io = _jaccard(sig.intents, s.intents)
            fo = _jaccard(sig.fields, s.fields)
            score = 0.5 * io + 0.5 * fo
            if score >= min_score:
                matches.append(
                    PatternMatch(signature=s, score=score, intent_overlap=io, field_overlap=fo)
                )
        matches.sort(key=lambda m: -m.score)
        return matches[:k]

    def all_signatures(self) -> list[PatternSignature]:
        return self._load()


def summarize_matches(matches: Iterable[PatternMatch]) -> str:
    """One-line render of a list of matches for logs or genome metadata."""
    rows = list(matches)
    if not rows:
        return "no familiar patterns recognized."
    fragments = [
        f"{m.signature.framework_id}@{m.score:.2f} (seen×{m.signature.occurrences})" for m in rows
    ]
    return "matches: " + "; ".join(fragments)
