"""Tests for ``agentdrive doctor --verbose``."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from rich.console import Console

from agentdrive.cli import _run_doctor


def test_run_doctor_verbose_does_not_crash(isolated_agentdrive_home) -> None:
    """Verbose doctor path completes without error on an isolated home."""
    with patch("agentdrive.cli.console.print"):
        rc = _run_doctor(verbose=True)
    assert rc in (0, 1)


def test_run_doctor_verbose_prints_diagnostics_panel(isolated_agentdrive_home) -> None:
    """Verbose mode emits the dedicated diagnostics section."""
    printed: list[object] = []

    def _capture(*args, **kwargs) -> None:
        printed.extend(args)

    with patch("agentdrive.cli.console.print", side_effect=_capture):
        _run_doctor(verbose=True)

    buf = StringIO()
    render_console = Console(file=buf, width=240, force_terminal=True)
    for arg in printed:
        render_console.print(arg)
    rendered = buf.getvalue()
    assert "Verbose diagnostics" in rendered