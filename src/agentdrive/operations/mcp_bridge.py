"""Bridge contract-first operations to MCP tools via run_operation()."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from agentdrive.operations.registry import OPERATIONS, OperationSpec, run_operation

OperationToolFn = Callable[..., str]


def _default_mcp_tool_name(op_name: str, mcp_tool: str | None) -> str | None:
    if mcp_tool:
        return mcp_tool
    if op_name.startswith("experience_graph_"):
        return op_name.replace("experience_graph_", "experience_graph_", 1)
    return f"agentdrive_{op_name}"


def _rich_doc_for_op(op: "OperationSpec") -> str:
    """Produce a model-friendly, self-contained docstring for MCP tool registration.

    Any AI model (Grok, Claude, Cursor, local LLM, custom agent) benefits from
    explicit guidance on category, mutability, usage, and return shape.
    """
    lines: list[str] = [op.description.strip()]

    lines.append(f"\n[category={op.category}] [read_only={op.read_only}]")
    if op.read_only:
        lines.append("Safe for frequent / exploratory calls. No side effects on the Drive.")
    else:
        lines.append("Mutating operation — use with care and prefer dry_run=True first when available.")

    if getattr(op, "when_to_use", None):
        lines.append(f"\nWhen to use: {op.when_to_use}")

    if getattr(op, "examples", None):
        exs = op.examples or []
        lines.append("Examples: " + " | ".join(exs[:3]))

    lines.append(
        "\nReturns: Always a JSON string (parse it!). Supports dry_run=True for most ops "
        "(returns a plan instead of executing). All results include an 'operation' and 'success' field for reliable handling by any model."
    )
    lines.append(
        "Tip for arbitrary models: Call agentdrive_mcp_catalog() early in a conversation to get the full live list of tools with usage notes."
    )
    return "\n".join(lines)


def _make_op_tool(op_name: str, description: str) -> OperationToolFn:
    def tool_fn(
        arguments: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> str:
        kwargs = dict(arguments or {})
        if dry_run:
            kwargs["dry_run"] = True
        payload = run_operation(op_name, **kwargs)
        return json.dumps(payload, indent=2, default=str)

    tool_fn.__doc__ = description
    tool_fn.__name__ = f"mcp_op_{op_name}"
    return tool_fn


def register_operations_as_mcp_tools(
    mcp: Any,
    *,
    skip_names: set[str] | None = None,
    expose_unmapped: bool = True,
) -> list[str]:
    """Register registry operations as MCP tools. Returns names registered."""
    skip = skip_names or set()
    registered: list[str] = []
    for op in OPERATIONS:
        tool_name = _default_mcp_tool_name(op.name, op.mcp_tool)
        if not tool_name or tool_name in skip:
            continue
        if not expose_unmapped and op.mcp_tool is None:
            continue
        if tool_name in skip:
            continue
        rich_doc = _rich_doc_for_op(op)
        fn = _make_op_tool(op.name, rich_doc)
        # Pass readOnlyHint so capable MCP clients / models can reason about safety
        annotations: dict[str, Any] | None = {"readOnlyHint": bool(op.read_only)}
        try:
            mcp.add_tool(fn, name=tool_name, description=op.description, annotations=annotations)
        except TypeError:
            # Older FastMCP may not accept annotations kwarg — fall back gracefully
            mcp.add_tool(fn, name=tool_name, description=op.description)
        registered.append(tool_name)
        skip.add(tool_name)
    return registered


def existing_mcp_tool_names(mcp: Any) -> set[str]:
    """Return tool names already registered on a FastMCP instance."""
    try:
        return set(mcp._tool_manager._tools.keys())  # noqa: SLF001
    except Exception:
        return set()