"""Tests for agentdrive.events — typed bus, recorder, thread safety."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from agentdrive.events import (
    EventBus,
    EventRecorder,
    MessageDelta,
    MessageStart,
    StatusUpdate,
    ToolStart,
)


def test_subscribe_all_events_fires_on_emit() -> None:
    bus = EventBus()
    received: list = []
    bus.subscribe(received.append)

    bus.emit(MessageStart(role="user"))
    bus.emit(ToolStart(tool="bash", args={"cmd": "ls"}))

    assert len(received) == 2
    assert isinstance(received[0], MessageStart)
    assert isinstance(received[1], ToolStart)


def test_subscribe_filtered_by_type() -> None:
    bus = EventBus()
    received: list = []
    bus.subscribe(received.append, event_types=[MessageDelta])

    bus.emit(MessageDelta(text="hello"))
    bus.emit(ToolStart(tool="bash", args={}))

    assert len(received) == 1
    assert isinstance(received[0], MessageDelta)
    assert received[0].text == "hello"


def test_subscribe_filtered_matches_subclass() -> None:
    # Filter on the Event base class — every concrete event should match
    # because isinstance() walks the MRO.
    from agentdrive.events import Event

    bus = EventBus()
    received: list = []
    bus.subscribe(received.append, event_types=[Event])

    bus.emit(MessageDelta(text="x"))
    bus.emit(StatusUpdate(message="ok"))

    assert len(received) == 2


def test_unsubscribe_stops_delivery() -> None:
    bus = EventBus()
    received: list = []
    token = bus.subscribe(received.append)

    bus.emit(MessageDelta(text="first"))
    bus.unsubscribe(token)
    bus.emit(MessageDelta(text="second"))

    assert len(received) == 1
    assert received[0].text == "first"


def test_failing_handler_does_not_break_others() -> None:
    bus = EventBus()
    received: list = []

    def bad(_event):
        raise RuntimeError("boom")

    bus.subscribe(bad)
    bus.subscribe(received.append)

    bus.emit(MessageDelta(text="still-delivered"))

    assert len(received) == 1
    assert received[0].text == "still-delivered"


def test_recorder_writes_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    rec = EventRecorder(path)
    try:
        rec.record(MessageStart(role="user"))
        rec.record(MessageDelta(text="hi"))
        rec.record(ToolStart(tool="bash", args={"cmd": "ls"}))
    finally:
        rec.close()

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    types = [json.loads(line)["type"] for line in lines]
    assert types == ["MessageStart", "MessageDelta", "ToolStart"]

    parsed = json.loads(lines[2])
    assert parsed["tool"] == "bash"
    assert parsed["args"] == {"cmd": "ls"}


def test_recorder_context_manager(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    with EventRecorder(path) as rec:
        rec.record(StatusUpdate(message="ready"))

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["type"] == "StatusUpdate"


def test_thread_safety_smoke() -> None:
    bus = EventBus()
    counter = {"n": 0}
    lock = threading.Lock()

    def count(_event) -> None:
        with lock:
            counter["n"] += 1

    bus.subscribe(count)

    def worker() -> None:
        for _ in range(100):
            bus.emit(MessageDelta(text="x"))

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert counter["n"] == 400
