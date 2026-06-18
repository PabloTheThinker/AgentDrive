"""
Persistent multiverse session store — survives process restarts and MCP calls.

Sessions are first-class drive artifacts under:
    drive/meta_evolution/multiverse/sessions/<session_id>.json
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from agentdrive.cognition.multiverse import (
    AdversaryVerdict,
    Branch,
    CollapsePolicy,
    ForwardStep,
    Invariant,
    InvariantKind,
    MultiverseSession,
    SessionStatus,
)


def _sessions_dir(drive_path: Path) -> Path:
    d = drive_path / "meta_evolution" / "multiverse" / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _enum_val(obj: Any) -> Any:
    if hasattr(obj, "value"):
        return obj.value
    return obj


def session_to_dict(session: MultiverseSession) -> dict[str, Any]:
    """JSON-serializable dict for persistence."""
    data = asdict(session)
    data["status"] = session.status.value
    data["collapse_policy"] = session.collapse_policy.value if session.collapse_policy else None
    for inv in data.get("invariants", []):
        if isinstance(inv.get("kind"), InvariantKind):
            inv["kind"] = inv["kind"].value
    return data


def session_from_dict(data: dict[str, Any]) -> MultiverseSession:
    """Rehydrate MultiverseSession from persisted JSON."""
    branches: list[Branch] = []
    for raw in data.get("branches", []):
        steps = [
            ForwardStep(**s) if isinstance(s, dict) else s for s in raw.get("forward_steps", [])
        ]
        st = raw.get("stress_test")
        stress = AdversaryVerdict(**st) if isinstance(st, dict) else None
        branches.append(
            Branch(
                branch_id=raw["branch_id"],
                role=raw["role"],
                path_summary=raw["path_summary"],
                assumptions=list(raw.get("assumptions", [])),
                divergence_axes=list(raw.get("divergence_axes", [])),
                forward_steps=steps,
                robustness_score=float(raw.get("robustness_score", 0.0)),
                fragility_flags=list(raw.get("fragility_flags", [])),
                stress_test=stress,
            )
        )

    invariants: list[Invariant] = []
    for raw in data.get("invariants", []):
        kind = raw.get("kind", InvariantKind.ROBUST)
        if isinstance(kind, str):
            kind = InvariantKind(kind)
        invariants.append(
            Invariant(
                statement=raw["statement"],
                branch_coverage=float(raw.get("branch_coverage", 0.0)),
                kind=kind,
                source_branches=list(raw.get("source_branches", [])),
            )
        )

    status = data.get("status", SessionStatus.OPEN)
    if isinstance(status, str):
        status = SessionStatus(status)

    collapse_policy = data.get("collapse_policy")
    if isinstance(collapse_policy, str):
        collapse_policy = CollapsePolicy(collapse_policy)

    return MultiverseSession(
        session_id=data["session_id"],
        trigger=data["trigger"],
        cycle_id=data["cycle_id"],
        correlation_id=data["correlation_id"],
        branches=branches,
        invariants=invariants,
        convergence_points=list(data.get("convergence_points", [])),
        divergence_points=list(data.get("divergence_points", [])),
        status=status,
        collapsed_branch_id=data.get("collapsed_branch_id"),
        collapse_reason=data.get("collapse_reason"),
        collapse_policy=collapse_policy,
        program_id=data.get("program_id"),
        constitution_refs=list(data.get("constitution_refs", [])),
        user_objective_refs=list(data.get("user_objective_refs", [])),
        created_at=float(data.get("created_at", 0.0)),
        reasoning_provider=data.get("reasoning_provider"),
        llm_mode=str(data.get("llm_mode", "heuristic")),
        external_fabric_reasoning=data.get("external_fabric_reasoning"),
    )


class MultiverseSessionStore:
    """Read/write multiverse sessions on the drive."""

    def __init__(self, drive_path: Path) -> None:
        self.drive_path = Path(drive_path)

    def save(self, session: MultiverseSession) -> Path:
        path = _sessions_dir(self.drive_path) / f"{session.session_id}.json"
        path.write_text(
            json.dumps(session_to_dict(session), indent=2, default=str),
            encoding="utf-8",
        )
        return path

    def load(self, session_id: str) -> MultiverseSession | None:
        path = _sessions_dir(self.drive_path) / f"{session_id}.json"
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return session_from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def list_recent(self, *, limit: int = 10) -> list[MultiverseSession]:
        sessions_dir = _sessions_dir(self.drive_path)
        paths = sorted(
            sessions_dir.glob("multiverse-session:*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        out: list[MultiverseSession] = []
        for path in paths[:limit]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                out.append(session_from_dict(data))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return out

    def briefing_context(self, *, limit: int = 5) -> dict[str, Any]:
        """Compact multiverse context for Parent/Overseer briefings."""
        recent = self.list_recent(limit=limit)
        collapsed = [s for s in recent if s.status == SessionStatus.COLLAPSED]
        open_sessions = [s for s in recent if s.status == SessionStatus.OPEN]

        top_invariants: list[str] = []
        for s in collapsed[:3]:
            for inv in s.invariants:
                if inv.kind == InvariantKind.ROBUST and inv.statement not in top_invariants:
                    top_invariants.append(inv.statement)

        return {
            "recent_collapses": [
                {
                    "session_id": s.session_id,
                    "trigger": s.trigger[:120],
                    "collapsed_branch_id": s.collapsed_branch_id,
                    "collapse_policy": _enum_val(s.collapse_policy),
                    "robust_invariant_count": sum(
                        1 for i in s.invariants if i.kind == InvariantKind.ROBUST
                    ),
                }
                for s in collapsed[:3]
            ],
            "open_superposition": [
                {
                    "session_id": s.session_id,
                    "trigger": s.trigger[:120],
                    "branch_count": len(s.branches),
                }
                for s in open_sessions[:2]
            ],
            "top_invariants_from_recent_sessions": top_invariants[:5],
            "session_count_recent": len(recent),
        }
