"""Tests for MessageStreamLane (UX Pattern 1 streaming body)."""

from __future__ import annotations

from agentdrive.events import MessageComplete, MessageDelta, emit
from agentdrive.tui.message_stream_lane import MessageStreamLane


def test_message_stream_lane_accumulates_deltas():
    lane = MessageStreamLane()
    lane.attach()
    try:
        assert lane.text() == ""
        emit(MessageDelta(text="hel", session_id="sess-a"))
        emit(MessageDelta(text="lo", session_id="sess-a"))
        assert lane.text() == "hello"
        emit(MessageComplete(text="hello", session_id="sess-a"))
        assert lane.text() == "hello"
    finally:
        lane.detach()


def test_message_stream_lane_filters_by_session():
    lane = MessageStreamLane()
    lane.set_session_id("target")
    lane.attach()
    try:
        emit(MessageDelta(text="skip", session_id="other"))
        emit(MessageDelta(text="keep", session_id="target"))
        assert lane.text() == "keep"
    finally:
        lane.detach()


def test_message_stream_lane_reset():
    lane = MessageStreamLane()
    lane.attach()
    try:
        emit(MessageDelta(text="before"))
        lane.reset()
        assert lane.text() == ""
        emit(MessageDelta(text="after"))
        assert lane.text() == "after"
    finally:
        lane.detach()