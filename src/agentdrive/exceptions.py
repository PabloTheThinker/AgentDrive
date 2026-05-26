"""
AgentDrive Exceptions.

All public exceptions live here for easy catching by integrators and downstream
tools (external adapters, custom workers, scanners, etc.).
"""

from __future__ import annotations


class Agent DriveError(Exception):
    """Base exception for all Agent Drive errors. Catch this for generic handling."""

    pass


class Agent DriveConfigError(Agent DriveError):
    """Errors related to configuration loading, saving, or validation."""

    pass


class Agent DriveRegistryError(Agent DriveError):
    """Errors from the GenomeRegistry (load, save, migration, etc.)."""

    pass


class Agent DriveWorkerError(Agent DriveError):
    """Errors from worker execution or adapter interaction."""

    pass


class Agent DriveScanError(Agent DriveError):
    """Errors during DNA scanning / genome extraction."""

    pass


__all__ = [
    "Agent DriveError",
    "Agent DriveConfigError",
    "Agent DriveRegistryError",
    "Agent DriveWorkerError",
    "Agent DriveScanError",
]
