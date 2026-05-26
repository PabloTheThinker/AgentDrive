"""
AgentDrive Exceptions.

All public exceptions live here for easy catching by integrators and downstream
tools (external adapters, custom workers, scanners, etc.).
"""

from __future__ import annotations


class SavantError(Exception):
    """Base exception for all Savant errors. Catch this for generic handling."""

    pass


class SavantConfigError(SavantError):
    """Errors related to configuration loading, saving, or validation."""

    pass


class SavantRegistryError(SavantError):
    """Errors from the GenomeRegistry (load, save, migration, etc.)."""

    pass


class SavantWorkerError(SavantError):
    """Errors from worker execution or adapter interaction."""

    pass


class SavantScanError(SavantError):
    """Errors during DNA scanning / genome extraction."""

    pass


__all__ = [
    "SavantError",
    "SavantConfigError",
    "SavantRegistryError",
    "SavantWorkerError",
    "SavantScanError",
]
