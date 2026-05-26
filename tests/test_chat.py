"""Tests for the substrate-grounded chat sidebar."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentdrive.web.app import create_app
from agentdrive.web.chat import (
    ChatMessage,
    ChatStore,
    SubstrateContext,
    SubstrateRead,
    build_system_prompt,
)

# ── ChatStore round-trip ─────────────────────────────────────────────


def test_chat_store_create_and_round_trip(tmp_path: Path):
    store = ChatStore(root=tmp_path / "threads")
    thread = store.create_thread(model="qwen3:14b", title="test")
    assert thread.thread_id.startswith("chat-")

    threads = store.list_threads()
    assert len(threads) == 1
    assert threads[0].thread_id == thread.thread_id
    assert threads[0].model == "qwen3:14b"

    store.append_message(thread.thread_id, ChatMessage(role="user", content="hello"))
    store.append_message(
        thread.thread_id,
        ChatMessage(
            role="assistant",
            content="hi",
            model="qwen3:14b",
            substrate_reads=[
                SubstrateRead(kind="dreams", path="dreams/runs/x", summary="1 candidate")
            ],
        ),
    )
    messages = store.get_messages(thread.thread_id)
    assert len(messages) == 2
    assert messages[0].role == "user" and messages[0].content == "hello"
    assert messages[1].role == "assistant" and messages[1].content == "hi"
    assert messages[1].substrate_reads[0].kind == "dreams"


def test_chat_store_get_thread_missing(tmp_path: Path):
    store = ChatStore(root=tmp_path / "threads")
    assert store.get_thread("chat-nonexistent") is None
    assert store.get_messages("chat-nonexistent") == []


def test_chat_store_append_to_missing_thread_raises(tmp_path: Path):
    store = ChatStore(root=tmp_path / "threads")
    with pytest.raises(FileNotFoundError):
        store.append_message("chat-nope", ChatMessage(role="user", content="x"))


# ── SubstrateContext shape ──────────────────────────────────────────


def test_substrate_context_empty_home_is_safe(tmp_path: Path):
    ctx = SubstrateContext(home=tmp_path)
    block, reads = ctx.build()
    assert block == ""
    assert reads == []


def test_substrate_context_reads_genomes_and_ingest(tmp_path: Path):
    (tmp_path / "genomes" / "alpha" / "1.0.0").mkdir(parents=True)
    (tmp_path / "drive").mkdir()
    log = tmp_path / "drive" / "ingest.jsonl"
    log.write_text(json.dumps({"event": "ingest", "source": "x"}) + "\n", encoding="utf-8")

    ctx = SubstrateContext(home=tmp_path)
    block, reads = ctx.build()
    kinds = {r.kind for r in reads}
    assert "genomes" in kinds
    assert "drive_ingest" in kinds
    assert "alpha/1.0.0" in block
    assert "ingest: x" in block


def test_build_system_prompt_with_and_without_substrate():
    identity = "You are ILO."
    assert build_system_prompt(identity, "") == identity
    full = build_system_prompt(identity, "## Dreams\n- foo")
    assert identity in full
    assert "## Dreams" in full
    assert "LIVE SUBSTRATE" in full


# ── API surface (requires auth) ─────────────────────────────────────


def _make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "auth.db")
    return TestClient(app, follow_redirects=False)


def _login(client: TestClient) -> None:
    resp = client.post(
        "/setup",
        data={"username": "admin", "password": "admin password 123"},
    )
    assert resp.status_code == 303


def test_chat_routes_require_login(tmp_path: Path):
    client = _make_client(tmp_path)
    # before any user exists, /setup happens to be the gate; we just check
    # the unauthenticated routes don't 200.
    resp = client.get("/api/chat/threads")
    assert resp.status_code in (302, 303, 401, 403)


def test_chat_thread_lifecycle(tmp_path: Path):
    client = _make_client(tmp_path)
    _login(client)

    # Empty list initially
    resp = client.get("/api/chat/threads")
    assert resp.status_code == 200
    assert resp.json() == {"threads": []}

    # Create thread
    resp = client.post("/api/chat/threads", json={"model": "qwen3:14b", "title": "smoke"})
    assert resp.status_code == 200
    thread_id = resp.json()["thread_id"]
    assert thread_id.startswith("chat-")

    # List now has one
    resp = client.get("/api/chat/threads")
    assert resp.status_code == 200
    assert len(resp.json()["threads"]) == 1

    # Get the thread (empty messages)
    resp = client.get(f"/api/chat/threads/{thread_id}")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["thread_id"] == thread_id
    assert payload["messages"] == []

    # Missing thread returns 404
    resp = client.get("/api/chat/threads/chat-missing")
    assert resp.status_code == 404


def test_chat_message_requires_content(tmp_path: Path):
    client = _make_client(tmp_path)
    _login(client)
    resp = client.post("/api/chat/threads", json={})
    thread_id = resp.json()["thread_id"]

    resp = client.post(f"/api/chat/threads/{thread_id}/messages", json={"content": "   "})
    assert resp.status_code == 400
