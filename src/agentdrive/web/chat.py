"""
chat — substrate-grounded chat module for the Agent Drive web UI.

Design goals:
- Talk to Ollama via streaming HTTP; emit SSE-friendly chunks.
- Ground every assistant turn in real substrate reads: dreams,
  genomes, reasoning ledger, drive ingest events. Every read is
  recorded as a structured SubstrateRead so the UI can render
  tool-call cards proving the substrate touched the answer.
- Persist threads to ``~/.agentdrive/chat/threads/`` as append-only
  JSONL — one file per thread, one message per line.

No new magic — just disciplined composition + Agent Drive / Genome idioms.
"""

from __future__ import annotations

import json
import secrets
import time
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

from agentdrive.constants import get_agentdrive_home
from agentdrive.providers.base import ProviderProfile
from agentdrive.utils.safe_paths import safe_name

OLLAMA_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen3:14b"
SUBSTRATE_TOKEN_BUDGET_CHARS = 6000

DEFAULT_AGENT_LABEL = "Agent Drive"
GENERIC_IDENTITY_PROMPT = (
    "You speak from inside the Agent Drive substrate — the live state "
    "block below is your ground truth. When you cite the substrate, "
    "reference the exact path/key shown. Never invent a substrate "
    "read; if the operator asks something the substrate doesn't cover, "
    "say so plainly. Be direct. No filler."
)
# Back-compat alias for callers that imported the old name.
DEFAULT_IDENTITY_PROMPT = GENERIC_IDENTITY_PROMPT


# ─────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────


@dataclass
class SubstrateRead:
    """One structured proof-of-grounding the UI renders as a tool-call card."""

    kind: str
    path: str
    summary: str
    latency_ms: int = 0
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatMessage:
    """One turn in a thread. Persisted as JSONL line."""

    role: str
    content: str
    created_at: float = field(default_factory=time.time)
    model: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    substrate_reads: list[SubstrateRead] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChatMessage:
        reads = [SubstrateRead(**r) for r in data.get("substrate_reads") or []]
        return cls(
            role=data["role"],
            content=data["content"],
            created_at=float(data.get("created_at", time.time())),
            model=data.get("model"),
            tool_calls=list(data.get("tool_calls") or []),
            substrate_reads=reads,
        )


@dataclass
class ChatThread:
    """Conversation handle; messages live on disk in the thread's JSONL file."""

    thread_id: str
    created_at: float
    model: str = DEFAULT_MODEL
    provider: str = ""
    title: str = ""
    agent_id: str = ""
    runtime_kind: str = ""


@dataclass
class AgentDescriptor:
    """One agent the operator has on this Agent Drive."""

    agent_id: str
    label: str
    identity_path: str = ""


def list_agents(home: Path | None = None) -> list[AgentDescriptor]:
    """Return the agents the user has under ``~/.agentdrive/agents/``.

    Each directory under ``agents/`` is one agent. An optional
    ``identity.md`` inside lets the operator define the chat identity for
    that agent. Empty list means the user has no agents — the chat
    falls back to a generic ``Agent Drive`` label.
    """
    base = (home or get_agentdrive_home()) / "agents"
    if not base.exists():
        return []
    out: list[AgentDescriptor] = []
    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        identity = d / "identity.md"
        out.append(
            AgentDescriptor(
                agent_id=d.name,
                label=d.name,
                identity_path=str(identity) if identity.exists() else "",
            )
        )
    return out


def resolve_identity_prompt(agent_id: str, home: Path | None = None) -> str:
    """Load the operator-defined identity for ``agent_id`` if present.

    Falls back to the generic prompt when no agent is selected or the
    agent has no ``identity.md``. The agent's label is prepended so the
    model knows who it is.
    """
    if not agent_id:
        return GENERIC_IDENTITY_PROMPT
    safe_id = safe_name(agent_id)
    base = (home or get_agentdrive_home()) / "agents" / safe_id
    identity_file = base / "identity.md"
    body = ""
    if identity_file.exists():
        try:
            body = identity_file.read_text(encoding="utf-8").strip()
        except OSError:
            body = ""
    header = f"You are {agent_id}, an agent on this Agent Drive."
    if body:
        return f"{header}\n\n{body}\n\n{GENERIC_IDENTITY_PROMPT}"
    return f"{header} {GENERIC_IDENTITY_PROMPT}"


# ─────────────────────────────────────────────────────────────────────
# Store
# ─────────────────────────────────────────────────────────────────────


class ChatStore:
    """Append-only JSONL store under ``~/.agentdrive/chat/threads/``."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or (get_agentdrive_home() / "chat" / "threads")
        self.root.mkdir(parents=True, exist_ok=True)

    def _thread_path(self, thread_id: str) -> Path:
        return self.root / f"{thread_id}.jsonl"

    def create_thread(
        self,
        model: str = DEFAULT_MODEL,
        provider: str = "",
        title: str = "",
        agent_id: str = "",
        runtime_kind: str = "",
    ) -> ChatThread:
        thread_id = "chat-" + secrets.token_hex(6)
        thread = ChatThread(
            thread_id=thread_id,
            created_at=time.time(),
            model=model,
            provider=provider,
            title=title,
            agent_id=agent_id,
            runtime_kind=runtime_kind,
        )
        head = {"__meta__": True, **asdict(thread)}
        path = self._thread_path(thread_id)
        path.write_text(json.dumps(head) + "\n", encoding="utf-8")
        return thread

    def list_threads(self, limit: int = 20) -> list[ChatThread]:
        threads: list[ChatThread] = []
        for path in sorted(self.root.glob("chat-*.jsonl")):
            try:
                first = path.read_text(encoding="utf-8").splitlines()[0]
                meta = json.loads(first)
            except (OSError, ValueError, IndexError):
                continue
            if not meta.get("__meta__"):
                continue
            meta.pop("__meta__", None)
            threads.append(ChatThread(**meta))
        threads.sort(key=lambda t: t.created_at, reverse=True)
        return threads[:limit]

    def get_thread(self, thread_id: str) -> ChatThread | None:
        path = self._thread_path(thread_id)
        if not path.exists():
            return None
        try:
            first = path.read_text(encoding="utf-8").splitlines()[0]
            meta = json.loads(first)
        except (OSError, ValueError, IndexError):
            return None
        if not meta.get("__meta__"):
            return None
        meta.pop("__meta__", None)
        return ChatThread(**meta)

    def get_messages(self, thread_id: str) -> list[ChatMessage]:
        path = self._thread_path(thread_id)
        if not path.exists():
            return []
        out: list[ChatMessage] = []
        for line in path.read_text(encoding="utf-8").splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(ChatMessage.from_dict(json.loads(line)))
            except (ValueError, KeyError):
                continue
        return out

    def append_message(self, thread_id: str, message: ChatMessage) -> None:
        path = self._thread_path(thread_id)
        if not path.exists():
            raise FileNotFoundError(f"thread not found: {thread_id}")
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(message.to_dict(), default=str) + "\n")

    def update_thread(self, thread: ChatThread) -> None:
        path = self._thread_path(thread.thread_id)
        if not path.exists():
            raise FileNotFoundError(f"thread not found: {thread.thread_id}")
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        head = {"__meta__": True, **asdict(thread)}
        rest = lines[1:] if lines else []
        body = [json.dumps(head), *rest]
        path.write_text("\n".join(body) + "\n", encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────
# Substrate context builder
# ─────────────────────────────────────────────────────────────────────


class SubstrateContext:
    """Pulls small slices of live Agent Drive state for grounding."""

    def __init__(self, home: Path | None = None) -> None:
        self.home = home or get_agentdrive_home()

    def build(self) -> tuple[str, list[SubstrateRead]]:
        """Return (prompt_block, structured_reads). Best effort — never raises."""
        reads: list[SubstrateRead] = []
        blocks: list[str] = []

        for fn in (
            self._read_dreams,
            self._read_genomes,
            self._read_reasoning_ledger,
            self._read_drive_ingest,
        ):
            try:
                block, read = fn()
            except Exception as exc:  # substrate is best effort
                block, read = (
                    "",
                    SubstrateRead(
                        kind="error",
                        path=fn.__name__,
                        summary=f"failed: {exc}",
                    ),
                )
            if read:
                reads.append(read)
            if block:
                blocks.append(block)

        body = "\n\n".join(blocks)
        if len(body) > SUBSTRATE_TOKEN_BUDGET_CHARS:
            body = body[:SUBSTRATE_TOKEN_BUDGET_CHARS] + "\n…(truncated)"
        return body, reads

    # ── dreams ────────────────────────────────────────────────────────
    def _read_dreams(self) -> tuple[str, SubstrateRead | None]:
        t0 = time.time()
        runs_dir = self.home / "dreams" / "runs"
        promo_dir = self.home / "dreams" / "promotions"
        if not runs_dir.exists():
            return "", None
        run_dirs = sorted(runs_dir.glob("dream-*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not run_dirs:
            return "", None
        latest = run_dirs[0]
        lines = [f"## Dreams · latest run {latest.name}"]
        for lane in ("memory", "genome", "pattern"):
            lane_dir = promo_dir / lane
            if not lane_dir.exists():
                continue
            candidates = sorted(
                lane_dir.glob(f"{latest.name}-*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )[:3]
            for c in candidates:
                try:
                    data = json.loads(c.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                cand = data.get("candidate") or {}
                key = cand.get("canonical_key", c.stem)
                score = cand.get("total_score", 0.0)
                lines.append(f"- [{lane}] {key} · score={score:.2f}")
        latency = int((time.time() - t0) * 1000)
        summary = f"latest run {latest.name}, {len(lines) - 1} staged candidates"
        return (
            "\n".join(lines),
            SubstrateRead(
                kind="dreams",
                path=str(latest.relative_to(self.home)),
                summary=summary,
                latency_ms=latency,
                payload={"run": latest.name},
            ),
        )

    # ── genomes ───────────────────────────────────────────────────────
    def _read_genomes(self) -> tuple[str, SubstrateRead | None]:
        t0 = time.time()
        genomes_dir = self.home / "genomes"
        if not genomes_dir.exists():
            return "", None
        names: list[str] = []
        for d in sorted(genomes_dir.iterdir())[:8]:
            if not d.is_dir():
                continue
            versions = sorted(p.name for p in d.iterdir() if p.is_dir())
            if versions:
                names.append(f"- {d.name}/{versions[-1]}")
        if not names:
            return "", None
        body = "## Genomes · registered (top 8)\n" + "\n".join(names)
        latency = int((time.time() - t0) * 1000)
        return (
            body,
            SubstrateRead(
                kind="genomes",
                path="genomes/",
                summary=f"{len(names)} genomes",
                latency_ms=latency,
            ),
        )

    # ── reasoning ledger ──────────────────────────────────────────────
    def _read_reasoning_ledger(self) -> tuple[str, SubstrateRead | None]:
        t0 = time.time()
        ledger_dir = self.home / "reasoning" / "ledger"
        if not ledger_dir.exists():
            return "", None
        files = sorted(ledger_dir.rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[
            :10
        ]
        if not files:
            return "", None
        lines = ["## Reasoning ledger · recent 10"]
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            kind = data.get("kind") or data.get("type") or f.parent.name
            note = data.get("summary") or data.get("note") or ""
            lines.append(f"- {kind}: {note[:80]}")
        latency = int((time.time() - t0) * 1000)
        return (
            "\n".join(lines),
            SubstrateRead(
                kind="reasoning",
                path="reasoning/ledger",
                summary=f"{len(files)} recent entries",
                latency_ms=latency,
            ),
        )

    # ── drive ingest ──────────────────────────────────────────────────
    def _read_drive_ingest(self) -> tuple[str, SubstrateRead | None]:
        t0 = time.time()
        log = self.home / "drive" / "ingest.jsonl"
        if not log.exists():
            return "", None
        try:
            lines_raw = log.read_text(encoding="utf-8").splitlines()[-10:]
        except OSError:
            return "", None
        if not lines_raw:
            return "", None
        events: list[str] = []
        for line in lines_raw:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            kind = ev.get("event") or ev.get("kind") or "ingest"
            src = ev.get("source") or ev.get("path") or ""
            events.append(f"- {kind}: {src}")
        body = "## Drive ingest · last 10\n" + "\n".join(events)
        latency = int((time.time() - t0) * 1000)
        return (
            body,
            SubstrateRead(
                kind="drive_ingest",
                path="drive/ingest.jsonl",
                summary=f"{len(events)} events",
                latency_ms=latency,
            ),
        )


# ─────────────────────────────────────────────────────────────────────
# Provider streaming client
# ─────────────────────────────────────────────────────────────────────


class LLMStreamClient:
    """Async streaming client for registry-backed LLM provider profiles."""

    def __init__(
        self,
        profile: ProviderProfile,
        timeout_s: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.profile = profile
        self.base_url = profile.base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.transport = transport

    async def stream_chat(
        self,
        model: str,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        """Yield response token chunks as plain strings."""
        if self.profile.api_mode == "anthropic":
            async for piece in self._stream_anthropic(model, messages):
                yield piece
            return
        async for piece in self._stream_chat_completions(model, messages):
            yield piece

    async def _stream_chat_completions(
        self,
        model: str,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        url = f"{self.base_url}/chat/completions"
        headers: dict[str, str] = {}
        key = self.profile.get_api_key()
        if self.profile.requires_key and key:
            headers["Authorization"] = f"Bearer {key}"
        body = {"model": model, "messages": messages, "stream": True}
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_s,
                transport=self.transport,
            ) as client:
                async with client.stream("POST", url, headers=headers, json=body) as resp:
                    if resp.status_code >= 400:
                        text = await resp.aread()
                        yield self._http_error(resp.status_code, text)
                        return
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        if not line.startswith("data:"):
                            continue
                        payload = line.removeprefix("data:").strip()
                        if payload == "[DONE]":
                            return
                        try:
                            chunk = json.loads(payload)
                        except ValueError:
                            continue
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        piece = delta.get("content", "")
                        if piece:
                            yield piece
        except httpx.HTTPError as exc:
            yield self._unreachable_error(exc)

    async def _stream_anthropic(
        self,
        model: str,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        url = f"{self.base_url}/messages"
        headers = {"anthropic-version": "2023-06-01"}
        key = self.profile.get_api_key()
        if self.profile.requires_key and key:
            headers["x-api-key"] = key
        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        chat_messages = [m for m in messages if m.get("role") in ("user", "assistant")]
        body: dict[str, Any] = {
            "model": model,
            "messages": chat_messages,
            "stream": True,
            "max_tokens": 4096,
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_s,
                transport=self.transport,
            ) as client:
                async with client.stream("POST", url, headers=headers, json=body) as resp:
                    if resp.status_code >= 400:
                        text = await resp.aread()
                        yield self._http_error(resp.status_code, text)
                        return
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        payload = line.removeprefix("data:").strip()
                        if payload == "[DONE]":
                            return
                        try:
                            chunk = json.loads(payload)
                        except ValueError:
                            continue
                        if chunk.get("type") != "content_block_delta":
                            continue
                        delta = chunk.get("delta") or {}
                        piece = delta.get("text", "")
                        if piece:
                            yield piece
        except httpx.HTTPError as exc:
            yield self._unreachable_error(exc)

    def _http_error(self, status_code: int, body: bytes) -> str:
        text = body.decode("utf-8", "replace")[:200]
        return f"[{self.profile.name} HTTP {status_code}: {text}]"

    def _unreachable_error(self, exc: httpx.HTTPError) -> str:
        return f"[{self.profile.name} unreachable: {exc}]"


# Back-compat alias for callers that imported the old name.
OllamaStreamClient = LLMStreamClient


# ─────────────────────────────────────────────────────────────────────
# Top-level orchestration
# ─────────────────────────────────────────────────────────────────────


def build_system_prompt(identity: str, substrate_block: str) -> str:
    if not substrate_block:
        return identity
    return (
        identity
        + "\n\n=== LIVE SUBSTRATE (read at start of this turn) ===\n"
        + substrate_block
        + "\n=== END SUBSTRATE ==="
    )


async def stream_chat_response(
    thread_id: str,
    user_text: str,
    *,
    store: ChatStore | None = None,
    substrate: SubstrateContext | None = None,
    client: LLMStreamClient | None = None,
    model: str | None = None,
    provider: str | None = None,
    use_substrate: bool = True,
    identity: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Stream SSE-shaped events for one chat turn.

    Yields events of shape ``{"event": <name>, "data": <payload>}`` for the
    route handler to format as ``event: <name>\\ndata: <json>\\n\\n``.

    Events:
      - ``substrate_read`` — one per SubstrateRead, before the LLM starts
      - ``token`` — streaming token chunk
      - ``done`` — final summary with full assistant message
      - ``error`` — surfaced as an event with payload {"error": "..."}
    """
    store = store or ChatStore()
    substrate = substrate or SubstrateContext()
    thread = store.get_thread(thread_id)
    if thread is None:
        yield {"event": "error", "data": {"error": f"thread not found: {thread_id}"}}
        return

    # Resolve identity per-thread so each thread targets the user's chosen
    # agent. If no identity is passed explicitly, look up the thread's
    # agent_id and load that agent's identity file from disk; fall back
    # to the generic prompt when the user has no agents.
    if identity is None:
        identity = resolve_identity_prompt(thread.agent_id)

    from agentdrive.runtime import build, load_runtime_config
    from agentdrive.runtime.model import ModelAdapter

    runtime_config = load_runtime_config(thread.agent_id)
    runtime_kind = str(runtime_config.get("kind") or "model")
    if runtime_kind == "model":
        runtime_config = dict(runtime_config)
        if "provider" not in runtime_config and (provider or thread.provider):
            runtime_config["provider"] = provider or thread.provider
        if "model" not in runtime_config and (model or thread.model):
            runtime_config["model"] = model or thread.model
        adapter = ModelAdapter(thread.agent_id, runtime_config, stream_client=client)
    else:
        adapter = build(thread.agent_id, runtime_config)

    if thread.runtime_kind != adapter.kind:
        thread.runtime_kind = adapter.kind
        store.update_thread(thread)

    # 1. record the user message
    user_msg = ChatMessage(role="user", content=user_text)
    store.append_message(thread_id, user_msg)

    # 2. build substrate context
    substrate_block = ""
    reads: list[SubstrateRead] = []
    if use_substrate:
        substrate_block, reads = substrate.build()
        for read in reads:
            yield {"event": "substrate_read", "data": asdict(read)}

    # 3. assemble messages: system + prior history + new user
    system_prompt = build_system_prompt(identity, substrate_block)
    history = store.get_messages(thread_id)
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for m in history:
        if m.role in ("user", "assistant"):
            messages.append({"role": m.role, "content": m.content})

    # 4. stream tokens
    pieces: list[str] = []
    async for piece in adapter.stream(messages):
        pieces.append(piece)
        yield {"event": "token", "data": {"text": piece}}

    # 5. persist the assistant message and emit done
    chosen_model = getattr(adapter, "model", None)
    chosen_provider = getattr(adapter, "provider_name", "")
    assistant_msg = ChatMessage(
        role="assistant",
        content="".join(pieces),
        model=chosen_model,
        substrate_reads=reads,
    )
    store.append_message(thread_id, assistant_msg)
    yield {
        "event": "done",
        "data": {
            "content": assistant_msg.content,
            "model": chosen_model,
            "provider": chosen_provider,
            "runtime_kind": adapter.kind,
            "substrate_reads": [asdict(r) for r in reads],
        },
    }
