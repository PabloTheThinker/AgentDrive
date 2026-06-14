"""Pattern 1 — per-session event stream recording and replay.

Appends all default_bus events for a chat session to:
``~/.agentdrive/agents/<agent>/sessions/<session_id>/events.jsonl``
"""

from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType

from agentdrive.constants import get_agentdrive_home
from agentdrive.events import (
    EventBus,
    EventRecorder,
    SubscriptionToken,
    default_bus,
    unsubscribe,
)
from agentdrive.utils.safe_paths import safe_name


def resolve_session_id(agent_id: str, token: str) -> str | None:
    """Resolve a session id or short suffix (from /sessions) to the full id."""
    from agentdrive.agent.session import AgentSession

    needle = token.strip()
    if not needle:
        return None

    sessions = AgentSession.list_sessions(agent_id, limit=100)
    for row in sessions:
        sid = str(row.get("session_id") or "")
        if sid == needle or sid.endswith(needle):
            return sid
    return needle if session_events_path(agent_id, needle).exists() else None


def session_events_path(agent_id: str, session_id: str) -> Path:
    """Return the JSONL path for a session's typed event stream."""
    safe_agent = safe_name(agent_id)
    safe_session = safe_name(session_id)
    return (
        get_agentdrive_home() / "agents" / safe_agent / "sessions" / safe_session / "events.jsonl"
    )


class SessionEventRecorder:
    """Attach an :class:`EventRecorder` to a bus for one agent session."""

    def __init__(self, agent_id: str, session_id: str) -> None:
        self.agent_id = agent_id
        self.session_id = session_id
        self.path = session_events_path(agent_id, session_id)
        self._recorder = EventRecorder(self.path)
        self._token: SubscriptionToken | None = None

    @property
    def attached(self) -> bool:
        return self._token is not None

    def attach(self, bus: EventBus | None = None) -> None:
        """Subscribe the underlying recorder to ``bus`` (default: ``default_bus``)."""
        if self._token is not None:
            return
        target = bus if bus is not None else default_bus
        self._token = self._recorder.attach(target)

    def detach(self) -> None:
        """Unsubscribe from the bus without closing the file handle."""
        if self._token is not None:
            unsubscribe(self._token)
            self._token = None

    def close(self) -> None:
        """Detach and flush/close the JSONL file."""
        self.detach()
        self._recorder.close()

    def __enter__(self) -> SessionEventRecorder:
        self.attach()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


def replay_events(path: Path | str) -> list[dict]:
    """Read a session events JSONL file; skip blank or malformed lines."""
    p = Path(path)
    if not p.exists():
        return []

    events: list[dict] = []
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                events.append(row)
    return events


def format_event_summary(ev_dict: dict) -> str:
    """One-line human summary for a recorded event dict."""
    ev_type = str(ev_dict.get("type") or "Event")
    ts = str(ev_dict.get("timestamp") or "")[:19].replace("T", " ")

    def _clip(text: str, limit: int = 72) -> str:
        text = " ".join(str(text).split())
        if len(text) <= limit:
            return text
        return text[: limit - 1] + "…"

    prefix = f"{ts}  {ev_type}" if ts else ev_type

    if ev_type == "MessageStart":
        return f"{prefix}  role={ev_dict.get('role', '?')}"
    if ev_type == "MessageDelta":
        return f"{prefix}  {_clip(ev_dict.get('text', ''))}"
    if ev_type == "MessageComplete":
        tokens = ev_dict.get("tokens", 0)
        return f"{prefix}  {_clip(ev_dict.get('text', ''))}  ({tokens} tok)"
    if ev_type == "ThinkingDelta":
        return f"{prefix}  {_clip(ev_dict.get('text', ''))}"
    if ev_type == "ToolStart":
        return f"{prefix}  {ev_dict.get('tool', '?')}"
    if ev_type == "ToolProgress":
        return f"{prefix}  {ev_dict.get('tool', '?')}: {_clip(ev_dict.get('message', ''))}"
    if ev_type == "ToolComplete":
        ok = "ok" if ev_dict.get("ok", True) else "fail"
        return (
            f"{prefix}  {ev_dict.get('tool', '?')} · {ok} · "
            f"{_clip(ev_dict.get('result_summary', ''))}"
        )
    if ev_type == "PoolMatch":
        genomes = ev_dict.get("genomes") or []
        scores = ev_dict.get("scores") or []
        if not genomes:
            return f"{prefix}  (no DNA matched)"
        top = genomes[0]
        score = scores[0] if scores else "?"
        extra = f" +{len(genomes) - 1}" if len(genomes) > 1 else ""
        return f"{prefix}  {top} · score {score}{extra}"
    if ev_type == "PoolIngest":
        return (
            f"{prefix}  {ev_dict.get('genome_id', '?')} · "
            f"src {ev_dict.get('source', '?')} · actor {ev_dict.get('actor', '?')}"
        )
    if ev_type == "PoolOutcome":
        return f"{prefix}  {ev_dict.get('genome_id', '?')} · score {ev_dict.get('score', 0)}"
    if ev_type == "SubagentSpawn":
        return (
            f"{prefix}  {ev_dict.get('label') or ev_dict.get('subagent_id') or '?'} "
            f"← parent {ev_dict.get('parent_id', '?')}"
        )
    if ev_type == "SubagentDone":
        ok = "ok" if ev_dict.get("ok", True) else "fail"
        return f"{prefix}  {ok} · {ev_dict.get('duration_s', 0):.1f}s"
    if ev_type == "StatusUpdate":
        return f"{prefix}  [{ev_dict.get('level', 'info')}] {_clip(ev_dict.get('message', ''))}"

    # Generic fallback — surface any short string field if present.
    for key in ("message", "text", "genome_id", "tool", "signal_type"):
        if ev_dict.get(key):
            return f"{prefix}  {_clip(ev_dict[key])}"
    return prefix


def summarize_event_types(events: list[dict]) -> dict[str, int]:
    """Count events by ``type`` field, highest count first."""
    counts: dict[str, int] = {}
    for ev in events:
        ev_type = str(ev.get("type") or "Event")
        counts[ev_type] = counts.get(ev_type, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def filter_events_by_type(
    events: list[dict],
    type_filter: str | list[str] | None,
) -> list[dict]:
    """Return events whose ``type`` matches ``type_filter`` (case-insensitive)."""
    if not type_filter:
        return list(events)

    if isinstance(type_filter, str):
        needles = {type_filter.strip()}
    else:
        needles = {t.strip() for t in type_filter if str(t).strip()}

    if not needles:
        return list(events)

    lowered = {n.lower() for n in needles}
    out: list[dict] = []
    for ev in events:
        ev_type = str(ev.get("type") or "")
        if ev_type in needles or ev_type.lower() in lowered:
            out.append(ev)
    return out


def format_type_histogram(counts: dict[str, int], *, max_types: int = 10) -> str:
    """Compact histogram string for panel headers."""
    if not counts:
        return "(no events)"
    parts: list[str] = []
    for idx, (ev_type, n) in enumerate(counts.items()):
        if idx >= max_types:
            parts.append(f"+{len(counts) - max_types} more")
            break
        parts.append(f"{ev_type}×{n}")
    return " · ".join(parts)


__all__ = [
    "SessionEventRecorder",
    "filter_events_by_type",
    "format_event_summary",
    "format_type_histogram",
    "replay_events",
    "resolve_session_id",
    "session_events_path",
    "summarize_event_types",
]
