"""Unit tests for ``agentdrive.tui.subagent_tree``."""

from __future__ import annotations

from rich.tree import Tree as RichTree

from agentdrive.events import (
    SubagentDone,
    SubagentSpawn,
    SubagentTokens,
    SubagentTool,
)
from agentdrive.tui.chrome import Palette
from agentdrive.tui.subagent_tree import SubagentNode, SubagentTree


def _palette() -> Palette:
    return Palette(None)


def _spawn(subagent_id: str, parent_id: str, label: str) -> SubagentSpawn:
    # SubagentSpawn inherits ``subagent_id`` from the Event base; the spec
    # treats it as the field that identifies the new node.
    return SubagentSpawn(subagent_id=subagent_id, parent_id=parent_id, label=label)


def _make_tree() -> SubagentTree:
    return SubagentTree(root_id="root", root_label="orchestrator")


def test_apply_spawn_adds_node() -> None:
    tree = _make_tree()
    tree.apply(_spawn("ingest-1", "root", "ingest worker"))

    node = tree.get("ingest-1")
    assert isinstance(node, SubagentNode)
    assert node.subagent_id == "ingest-1"
    assert node.parent_id == "root"
    assert node.label == "ingest worker"
    assert node.status == "queued"
    assert node.current_tool is None
    assert node.tokens == 0
    assert node.cost_usd == 0.0


def test_apply_tool_updates_current_tool_field() -> None:
    tree = _make_tree()
    tree.apply(_spawn("trace-2", "root", "tracer"))
    tree.apply(SubagentTool(subagent_id="trace-2", tool="bash(ls)"))

    node = tree.get("trace-2")
    assert node is not None
    assert node.current_tool == "bash(ls)"
    # First tool event also promotes queued → running.
    assert node.status == "running"


def test_apply_tokens_accumulates_tokens_and_cost() -> None:
    tree = _make_tree()
    tree.apply(_spawn("scorer-1", "root", "scorer"))

    tree.apply(SubagentTokens(subagent_id="scorer-1", tokens=1200, cost_usd=0.03))
    tree.apply(SubagentTokens(subagent_id="scorer-1", tokens=800, cost_usd=0.02))

    node = tree.get("scorer-1")
    assert node is not None
    assert node.tokens == 2000
    assert abs(node.cost_usd - 0.05) < 1e-9
    assert node.status == "running"


def test_apply_done_marks_terminal_status_and_duration() -> None:
    tree = _make_tree()
    tree.apply(_spawn("author-1", "root", "author"))
    tree.apply(SubagentTool(subagent_id="author-1", tool="write_file"))
    tree.apply(SubagentDone(subagent_id="author-1", ok=True, duration_s=12.5))

    ok_node = tree.get("author-1")
    assert ok_node is not None
    assert ok_node.status == "done"
    assert ok_node.duration_s == 12.5
    assert ok_node.current_tool is None
    assert ok_node.is_terminal is True

    tree.apply(_spawn("fail-1", "root", "failing worker"))
    tree.apply(SubagentDone(subagent_id="fail-1", ok=False, duration_s=3.1))
    failed = tree.get("fail-1")
    assert failed is not None
    assert failed.status == "failed"
    assert failed.is_terminal is True


def test_render_produces_tree_with_correct_node_count() -> None:
    tree = _make_tree()
    tree.apply(_spawn("a", "root", "alpha"))
    tree.apply(_spawn("b", "root", "beta"))
    tree.apply(_spawn("b1", "b", "beta-child"))

    rich_tree = tree.render(_palette())
    assert isinstance(rich_tree, RichTree)

    # 1 root + 3 spawned children. Count both root + descendants.
    def _count(node: RichTree) -> int:
        return 1 + sum(_count(child) for child in node.children)

    assert _count(rich_tree) == 4


def test_is_done_only_true_when_all_terminal() -> None:
    tree = _make_tree()
    tree.apply(_spawn("x", "root", "x"))
    tree.apply(_spawn("y", "root", "y"))

    # Root + two queued/running children → not done.
    assert tree.is_done() is False

    # Mark children terminal — root is still "running".
    tree.apply(SubagentDone(subagent_id="x", ok=True, duration_s=1.0))
    tree.apply(SubagentDone(subagent_id="y", ok=False, duration_s=2.0))
    assert tree.is_done() is False

    # Finish the root too.
    tree.apply(SubagentDone(subagent_id="root", ok=True, duration_s=3.0))
    assert tree.is_done() is True


def test_apply_idempotent_for_same_event_twice() -> None:
    tree = _make_tree()
    spawn = _spawn("dup-1", "root", "dup")
    tree.apply(spawn)
    tree.apply(spawn)  # second application must not duplicate the node.

    nodes = [n for n in tree.nodes() if n.subagent_id == "dup-1"]
    assert len(nodes) == 1

    # Child should appear under root exactly once.
    rich_tree = tree.render(_palette())
    # Root has exactly one child branch.
    assert len(rich_tree.children) == 1

    # A repeated Done with the same payload also stays graceful.
    done = SubagentDone(subagent_id="dup-1", ok=True, duration_s=4.0)
    tree.apply(done)
    tree.apply(done)
    node = tree.get("dup-1")
    assert node is not None
    assert node.status == "done"
    assert node.duration_s == 4.0
