"""gstack-style sprint chains — structured ship workflow with STOP gates."""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentdrive.drive.drive import get_default_drive
from agentdrive.reconciliation import ReconciliationRunner
from agentdrive.registry import GenomeRegistry
from agentdrive.sprint.checkpoint import CheckpointPending, CheckpointStore
from agentdrive.synthesis.engine import _ensure_mandatory_gaps

_DATED_SECTION_RE = re.compile(r"^## \[(?:\d{4}-\d{2}-\d{2}|Unreleased)\]", re.MULTILINE)


@dataclass(frozen=True)
class SprintStep:
    id: str
    name: str
    description: str
    stop_gate: bool = False


@dataclass
class SprintResult:
    step_id: str
    name: str
    success: bool
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


SHIP_CHAIN: tuple[SprintStep, ...] = (
    SprintStep(
        id="reconcile",
        name="Reconcile",
        description="Scan drive for new/updated DNA and reconciliation health",
        stop_gate=False,
    ),
    SprintStep(
        id="test",
        name="Test",
        description="Run pytest suite before shipping",
        stop_gate=False,
    ),
    SprintStep(
        id="think_gaps",
        name="Think Gaps",
        description="Drive.think gap review — honest blockers before release",
        stop_gate=True,
    ),
    SprintStep(
        id="changelog_check",
        name="Changelog Check",
        description="Verify CHANGELOG.md has Unreleased or a recent dated section",
        stop_gate=True,
    ),
)


def _find_project_root(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    for parent in [start, *start.parents]:
        if (parent / ".git").is_dir():
            return parent
        if (parent / "CHANGELOG.md").is_file() and (parent / "pyproject.toml").is_file():
            return parent
    return start


def _run_reconcile(*, dry_run: bool) -> SprintResult:
    pool = get_default_drive()
    registry = pool.registry if hasattr(pool, "registry") else GenomeRegistry()
    runner = ReconciliationRunner(registry=registry, pool=pool)

    if dry_run:
        status = runner.status()
        ok = bool(status.get("ok", True))
        return SprintResult(
            step_id="reconcile",
            name="Reconcile",
            success=ok,
            message="Reconciliation status (dry-run; no scan executed)",
            detail=status,
        )

    report = runner.scan_once()
    status = runner.status()
    ok = bool(status.get("ok", True))
    return SprintResult(
        step_id="reconcile",
        name="Reconcile",
        success=ok,
        message=(
            f"Reconciliation complete: {len(report.new_genomes)} new, "
            f"{len(report.updated_genomes)} updated"
        ),
        detail={
            "since": report.since,
            "until": report.until,
            "new_genomes": list(report.new_genomes),
            "updated_genomes": list(report.updated_genomes),
            "consecutive_failures": status.get("consecutive_failures", 0),
        },
    )


def _run_test(*, dry_run: bool, pytest_path: str) -> SprintResult:
    if dry_run:
        return SprintResult(
            step_id="test",
            name="Test",
            success=True,
            message="Pytest skipped (dry-run)",
            detail={"skipped": True, "pytest_path": pytest_path},
        )

    cmd = [sys.executable, "-m", "pytest", pytest_path, "-q", "--tb=no"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    ok = proc.returncode == 0
    tail = (proc.stdout or proc.stderr or "").strip().splitlines()
    summary = tail[-1] if tail else f"exit {proc.returncode}"
    return SprintResult(
        step_id="test",
        name="Test",
        success=ok,
        message=summary,
        detail={
            "returncode": proc.returncode,
            "pytest_path": pytest_path,
            "stdout_tail": tail[-5:],
        },
    )


def _run_think_gaps(*, dry_run: bool) -> SprintResult:
    question = "What gaps remain before shipping AgentDrive?"
    if dry_run:
        gaps = [
            {
                "description": "Dry-run: mandatory gap placeholder for sprint chain",
                "severity": "medium",
                "suggested_action": "Re-run without --dry-run for live Drive.think synthesis",
            }
        ]
        return SprintResult(
            step_id="think_gaps",
            name="Think Gaps",
            success=True,
            message=f"{len(gaps)} gap(s) recorded (dry-run stub)",
            detail={"gaps": gaps, "dry_run": True},
        )

    drive = get_default_drive()
    result = drive.think(question)
    payload = _ensure_mandatory_gaps(result.to_mcp_dict(), question)
    gaps = payload.get("gaps") or []
    if not gaps:
        return SprintResult(
            step_id="think_gaps",
            name="Think Gaps",
            success=False,
            message="No gaps surfaced — STOP gate requires honest gap review",
            detail={"gaps": [], "question": question},
        )
    return SprintResult(
        step_id="think_gaps",
        name="Think Gaps",
        success=True,
        message=f"{len(gaps)} gap(s) surfaced for ship review",
        detail={
            "gaps": gaps,
            "question": question,
            "correlation_id": payload.get("correlation_id"),
        },
    )


def _run_changelog_check(*, project_root: Path | None = None) -> SprintResult:
    root = project_root or _find_project_root()
    changelog = root / "CHANGELOG.md"
    if not changelog.is_file():
        return SprintResult(
            step_id="changelog_check",
            name="Changelog Check",
            success=False,
            message=f"CHANGELOG.md not found under {root}",
            detail={"root": str(root)},
        )

    text = changelog.read_text(encoding="utf-8")
    has_unreleased = "## Unreleased" in text
    has_dated = bool(_DATED_SECTION_RE.search(text))
    ok = has_unreleased or has_dated
    return SprintResult(
        step_id="changelog_check",
        name="Changelog Check",
        success=ok,
        message=(
            "CHANGELOG.md has release section"
            if ok
            else "CHANGELOG.md missing ## Unreleased or dated section"
        ),
        detail={
            "path": str(changelog),
            "has_unreleased": has_unreleased,
            "has_dated_section": has_dated,
        },
    )


_STEP_RUNNERS = {
    "reconcile": lambda *, dry_run, pytest_path, project_root: _run_reconcile(dry_run=dry_run),
    "test": lambda *, dry_run, pytest_path, project_root: _run_test(
        dry_run=dry_run, pytest_path=pytest_path
    ),
    "think_gaps": lambda *, dry_run, pytest_path, project_root: _run_think_gaps(dry_run=dry_run),
    "changelog_check": lambda *, dry_run, pytest_path, project_root: _run_changelog_check(
        project_root=project_root
    ),
}


def _raise_stop_gate(
    store: CheckpointStore,
    step: SprintStep,
    message: str,
    *,
    prior_failed: bool,
) -> None:
    if prior_failed:
        msg = f"Prior step failed — review before {step.name}: {message}"
    else:
        msg = f"STOP gate at {step.name}: {message}"
    cp_id = store.create(step.id, msg)
    raise CheckpointPending(step.id, cp_id, msg)


def run_ship_chain(
    *,
    dry_run: bool = False,
    ack_ids: list[str] | None = None,
    pytest_path: str = "tests",
    project_root: Path | None = None,
    reset: bool = False,
) -> list[SprintResult]:
    """Execute the gstack-style /ship sprint chain with STOP gates.

    Parameters
    ----------
    dry_run:
        Skip pytest subprocess and Drive.think; bypass STOP gate pauses so all
        step results are returned (used by CI and ``--dry-run`` CLI flag).
    ack_ids:
        Checkpoint ids to acknowledge before running (resume after STOP).
    reset:
        Clear persisted chain progress before starting.
    """
    store = CheckpointStore("ship")
    if reset:
        store.reset_chain()

    for cp_id in ack_ids or []:
        store.ack(cp_id)

    results: list[SprintResult] = []
    prior_failed = False

    for step in SHIP_CHAIN:
        if store.is_step_completed(step.id):
            continue

        if step.stop_gate and not dry_run:
            pending = store.list_pending()
            if pending:
                first = pending[0]
                raise CheckpointPending(
                    first["step_id"],
                    first["id"],
                    first["message"],
                )
            if prior_failed:
                _raise_stop_gate(
                    store,
                    step,
                    "resolve failing step before continuing",
                    prior_failed=True,
                )

        runner = _STEP_RUNNERS[step.id]
        result = runner(
            dry_run=dry_run,
            pytest_path=pytest_path,
            project_root=project_root,
        )
        results.append(result)

        if not result.success:
            prior_failed = True
            if step.stop_gate and not dry_run:
                _raise_stop_gate(store, step, result.message, prior_failed=True)
            continue

        store.mark_step_completed(step.id)

        if step.stop_gate and not dry_run:
            _raise_stop_gate(
                store,
                step,
                result.message,
                prior_failed=False,
            )

    return results
