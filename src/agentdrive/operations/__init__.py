"""Contract-first operations registry — single source of truth for CLI + MCP surfaces."""

from agentdrive.operations.registry import (
    OPERATIONS,
    OperationSpec,
    describe_operation,
    export_operations_json,
    get_operation,
    list_operations,
    parse_operation_kwargs,
    run_operation,
)

__all__ = [
    "OPERATIONS",
    "OperationSpec",
    "describe_operation",
    "export_operations_json",
    "get_operation",
    "list_operations",
    "parse_operation_kwargs",
    "run_operation",
]