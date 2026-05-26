"""
AgentDrive Exceptions.

All public exceptions live here for easy catching by integrators and downstream
tools (external adapters, custom workers, scanners, etc.).
"""

from __future__ import annotations


class AgentDriveError(Exception):
    """Base exception for all Agent Drive errors. Catch this for generic handling."""

    pass


class AgentDriveConfigError(AgentDriveError):
    """Errors related to configuration loading, saving, or validation."""

    pass


class AgentDriveRegistryError(AgentDriveError):
    """Errors from the GenomeRegistry (load, save, migration, etc.)."""

    pass


class AgentDriveWorkerError(AgentDriveError):
    """Errors from worker execution or adapter interaction."""

    pass


class AgentDriveScanError(AgentDriveError):
    """Errors during DNA scanning / genome extraction."""

    pass


__all__ = [
    "AgentDriveError",
    "AgentDriveConfigError",
    "AgentDriveRegistryError",
    "AgentDriveWorkerError",
    "AgentDriveScanError",
]
