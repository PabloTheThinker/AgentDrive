"""
User-facing CLI handlers for AgentDrive operations not yet wired in cli.py.

Keeps cli.py thinner: discovery, think, learnings, harness, graph, eval.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from agentdrive.cli_catalog import (
    CATALOG,
    CATEGORY_LABELS,
    catalog_by_category,
    format_epilog,
    iter_tree_lines,
    search_catalog,
)
from agentdrive.operations import run_operation

console = Console()


def print_operation_result(
    name: str,
    result: dict[str, Any],
    *,
    json_output: bool = False,
    preview_limit: int = 4000,
) -> None:
    """Pretty-print or JSON-emit an operation handler result."""
    if json_output:
        console.print(json.dumps(result, indent=2, default=str))
        return

    success = result.get("success", False)
    style = "green" if success else "red"
    console.print(f"[{style}]{name}[/] → success={success}")
    if result.get("dry_run"):
        console.print("[dim]dry-run mode[/]")
    if result.get("error"):
        console.print(f"[red]error:[/] {result['error']}")
        return

    if name == "think" and isinstance(result.get("result"), dict):
        payload = result["result"]
        answer = payload.get("answer") or payload.get("synthesis") or ""
        if answer:
            console.print()
            console.print(str(answer))
        gaps = payload.get("gaps") or []
        if gaps:
            console.print()
            console.print("[yellow]Gaps:[/]")
            for gap in gaps[:8]:
                console.print(f"  • {gap}")
        return

    if name == "harness_compose" and result.get("composed_prompt"):
        console.print()
        text = str(result["composed_prompt"])
        if len(text) > preview_limit:
            text = text[:preview_limit] + "\n…"
        console.print(text)
        return

    if name == "experience_graph_context_pack" and result.get("context_pack"):
        pack = result["context_pack"]
        if isinstance(pack, dict):
            for key in ("summary", "briefing", "narrative", "text"):
                if pack.get(key):
                    console.print()
                    console.print(str(pack[key]))
                    return
        preview = json.dumps(pack, indent=2, default=str)
        if len(preview) > preview_limit:
            preview = preview[:preview_limit] + "\n…"
        console.print(preview)
        return

    preview = json.dumps(result, indent=2, default=str)
    if len(preview) > preview_limit:
        preview = preview[:preview_limit] + "\n…"
    console.print(preview)


def _run_op(name: str, kwargs: dict[str, Any], *, json_output: bool) -> int:
    result = run_operation(name, **kwargs)
    print_operation_result(name, result, json_output=json_output)
    return 0 if result.get("success", False) else 1


def cmd_think(args: argparse.Namespace) -> int:
    """Cited Drive.think synthesis with mandatory gap analysis."""
    question = getattr(args, "question", None) or ""
    if not question.strip():
        console.print("[red]Usage: agentdrive think \"your question\"[/]")
        return 1
    kwargs: dict[str, Any] = {
        "question": question.strip(),
        "prefer_experience_layer": not getattr(args, "no_experience_layer", False),
    }
    if getattr(args, "dry_run", False):
        kwargs["dry_run"] = True
    return _run_op("think", kwargs, json_output=getattr(args, "json_output", False))


def cmd_learnings(args: argparse.Namespace) -> int:
    """gstack-style operational learnings (log / list / search)."""
    sub = getattr(args, "learnings_subcommand", None) or "list"

    if sub == "log":
        insight = getattr(args, "insight", None) or ""
        if not insight.strip():
            console.print(
                "[red]Usage: agentdrive learnings log --key <key> --insight \"...\"[/]"
            )
            return 1
        kwargs: dict[str, Any] = {
            "key": getattr(args, "key", None) or "cli-entry",
            "insight": insight.strip(),
            "type": getattr(args, "type", None) or "pattern",
            "confidence": getattr(args, "confidence", 5),
            "source": getattr(args, "source", None) or "observed",
            "skill": getattr(args, "skill", None) or "harness",
        }
        if getattr(args, "slug", None):
            kwargs["slug"] = args.slug
        if getattr(args, "dry_run", False):
            kwargs["dry_run"] = True
        return _run_op("learnings_log", kwargs, json_output=getattr(args, "json_output", False))

    if sub == "list":
        kwargs = {"limit": getattr(args, "limit", 20)}
        if getattr(args, "slug", None):
            kwargs["slug"] = args.slug
        if getattr(args, "dry_run", False):
            kwargs["dry_run"] = True
        result = run_operation("learnings_list", **kwargs)
        if getattr(args, "json_output", False):
            console.print(json.dumps(result, indent=2, default=str))
            return 0 if result.get("success") else 1

        entries = result.get("entries") or []
        table = Table(
            title=f"Learnings ({result.get('count', len(entries))}) slug={result.get('slug', '')}",
            show_header=True,
        )
        table.add_column("Key", style="cyan")
        table.add_column("Type")
        table.add_column("Conf")
        table.add_column("Insight", overflow="fold")
        for entry in entries:
            table.add_row(
                str(entry.get("key", "")),
                str(entry.get("type", "")),
                str(entry.get("confidence", "")),
                str(entry.get("insight", "")),
            )
        console.print(table)
        return 0 if result.get("success") else 1

    if sub == "search":
        query = getattr(args, "query", None) or ""
        if not query.strip():
            console.print("[red]Usage: agentdrive learnings search <query>[/]")
            return 1
        from agentdrive.learnings import LearningsStore

        store = LearningsStore(slug=getattr(args, "slug", None))
        hits = store.search(query.strip(), limit=getattr(args, "limit", 10))
        if getattr(args, "json_output", False):
            console.print(
                json.dumps(
                    {"success": True, "slug": store.slug, "query": query, "hits": hits},
                    indent=2,
                    default=str,
                )
            )
            return 0

        table = Table(title=f"Learnings search: {query!r}", show_header=True)
        table.add_column("Key", style="cyan")
        table.add_column("Type")
        table.add_column("Conf")
        table.add_column("Insight", overflow="fold")
        for entry in hits:
            table.add_row(
                str(entry.get("key", "")),
                str(entry.get("type", "")),
                str(entry.get("confidence", "")),
                str(entry.get("insight", "")),
            )
        console.print(table)
        if not hits:
            console.print("[dim]No matches.[/]")
        return 0

    console.print("[red]Unknown learnings subcommand[/]")
    return 1


def cmd_harness(args: argparse.Namespace) -> int:
    """Harness prompt composition."""
    sub = getattr(args, "harness_subcommand", None) or "compose"
    if sub != "compose":
        console.print("[red]Unknown harness subcommand[/]")
        return 1

    kwargs: dict[str, Any] = {}
    if getattr(args, "task", None):
        kwargs["task"] = args.task
    if getattr(args, "prompt", None):
        kwargs["base_prompt"] = args.prompt
    if getattr(args, "slug", None):
        kwargs["slug"] = args.slug
    if getattr(args, "pattern", None):
        kwargs["pattern"] = args.pattern
    if getattr(args, "strategy", None):
        kwargs["strategy"] = args.strategy
    if getattr(args, "context", None):
        kwargs["context"] = args.context
    if getattr(args, "session_id", None):
        kwargs["session_id"] = args.session_id
    if getattr(args, "input_text", None):
        kwargs["input_text"] = args.input_text
    if getattr(args, "agent_id", None):
        kwargs["agent_id"] = args.agent_id
    if getattr(args, "dry_run", False):
        kwargs["dry_run"] = True

    if not kwargs.get("task") and not kwargs.get("base_prompt") and sys.stdin.isatty():
        console.print(
            "[red]Usage: agentdrive harness compose --task \"...\" [--pattern NAME][/]"
        )
        return 1

    return _run_op("harness_compose", kwargs, json_output=getattr(args, "json_output", False))


def cmd_graph(args: argparse.Namespace) -> int:
    """Experience Graph operations (context-pack / record / suggest)."""
    sub = getattr(args, "graph_subcommand", None) or "context-pack"

    if sub == "context-pack":
        kwargs: dict[str, Any] = {
            "reasoning_style": getattr(args, "reasoning_style", "balanced"),
            "lookback_days": getattr(args, "lookback_days", 7),
            "max_tokens": getattr(args, "max_tokens", 1800),
        }
        if getattr(args, "swarm_id", None):
            kwargs["swarm_id"] = args.swarm_id
        if getattr(args, "dry_run", False):
            kwargs["dry_run"] = True
        return _run_op(
            "experience_graph_context_pack",
            kwargs,
            json_output=getattr(args, "json_output", False),
        )

    if sub == "suggest":
        kwargs = {}
        if getattr(args, "swarm_id", None):
            kwargs["swarm_id"] = args.swarm_id
        if getattr(args, "dry_run", False):
            kwargs["dry_run"] = True
        return _run_op(
            "experience_graph_suggest_reasoning",
            kwargs,
            json_output=getattr(args, "json_output", False),
        )

    if sub == "record":
        kwargs: dict[str, Any] = {}
        if getattr(args, "swarm_id", None):
            kwargs["swarm_id"] = args.swarm_id
        if getattr(args, "cycle_id", None):
            kwargs["cycle_id"] = args.cycle_id
        if getattr(args, "summary", None):
            kwargs["summary"] = args.summary
        if getattr(args, "reasoning_file", None):
            path = Path(args.reasoning_file).expanduser()
            if not path.is_file():
                console.print(f"[red]File not found:[/] {path}")
                return 1
            try:
                kwargs["reasoning"] = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                console.print(f"[red]Invalid JSON in reasoning file:[/] {exc}")
                return 1
        elif getattr(args, "summary", None):
            kwargs["reasoning"] = {
                "summary": args.summary,
                "elements": getattr(args, "elements", None) or [],
            }
        else:
            console.print(
                "[red]Usage: agentdrive graph record --summary \"...\" "
                "or --reasoning-file path.json[/]"
            )
            return 1
        if getattr(args, "dry_run", False):
            kwargs["dry_run"] = True
        return _run_op(
            "experience_graph_record_reasoning",
            kwargs,
            json_output=getattr(args, "json_output", False),
        )

    console.print("[red]Unknown graph subcommand[/]")
    return 1


def cmd_eval(args: argparse.Namespace) -> int:
    """Evaluation utilities (artifact replay)."""
    sub = getattr(args, "eval_subcommand", None) or "replay"
    if sub != "replay":
        console.print("[red]Unknown eval subcommand[/]")
        return 1

    path = getattr(args, "artifact", None)
    if not path:
        console.print("[red]Usage: agentdrive eval replay <artifact.json>[/]")
        return 1

    from agentdrive.eval.replay import replay_genome_artifact_file

    artifact_path = Path(str(path)).expanduser()
    if not artifact_path.is_file():
        console.print(f"[red]Artifact not found:[/] {artifact_path}")
        return 1

    tolerance = float(getattr(args, "tolerance", 0.05))
    result = replay_genome_artifact_file(artifact_path, tolerance=tolerance)

    if getattr(args, "json_output", False):
        console.print(json.dumps(result, indent=2, default=str))
    else:
        passed = result.get("pass", False)
        style = "green" if passed else "red"
        console.print(f"[{style}]eval replay[/] → pass={passed}")
        for key in (
            "path",
            "artifact_id",
            "stored_decision",
            "replayed_decision",
            "stored_overall_goodness",
            "replayed_overall_goodness",
            "decision_match",
            "goodness_match",
        ):
            if key in result:
                console.print(f"  {key}: {result[key]}")

    return 0 if result.get("pass") else 1


def cmd_commands(args: argparse.Namespace) -> int:
    """CLI discovery: list / tree / search."""
    sub = getattr(args, "commands_subcommand", None) or "list"

    if sub == "list":
        grouped = catalog_by_category()
        table = Table(title=f"AgentDrive commands ({len(CATALOG)})", show_header=True)
        table.add_column("Category")
        table.add_column("Command", style="cyan")
        table.add_column("Summary", overflow="fold")
        table.add_column("Op", style="dim")
        for category, entries in grouped.items():
            label = CATEGORY_LABELS.get(category, category)
            for entry in entries:
                table.add_row(
                    label,
                    f"agentdrive {entry.command}",
                    entry.summary,
                    entry.operation or "—",
                )
        console.print(table)
        console.print()
        console.print("[dim]Tip: agentdrive commands search <keyword>[/]")
        return 0

    if sub == "tree":
        for line in iter_tree_lines():
            if line.startswith("["):
                console.print(f"\n[bold]{line}[/]")
            else:
                console.print(f"[dim]{line}[/]")
        return 0

    if sub == "search":
        query = getattr(args, "query", None) or ""
        if not query.strip():
            console.print("[red]Usage: agentdrive commands search <query>[/]")
            return 1
        hits = search_catalog(query.strip())
        if not hits:
            console.print(f"[yellow]No commands match[/] {query!r}")
            return 0
        table = Table(title=f"Search: {query!r} ({len(hits)})", show_header=True)
        table.add_column("Command", style="cyan")
        table.add_column("Summary", overflow="fold")
        table.add_column("Category")
        for entry in hits:
            table.add_row(
                f"agentdrive {entry.command}",
                entry.summary,
                CATEGORY_LABELS.get(entry.category, entry.category),
            )
        console.print(table)
        return 0

    console.print("[red]Unknown commands subcommand[/]")
    return 1


def cmd_golden_path(args: argparse.Namespace) -> int:
    """Run or verify the canonical first-run golden path."""
    from agentdrive.golden_path import GOLDEN_STEPS, run_walkthrough, verify_all, verify_step

    sub = getattr(args, "golden_subcommand", None) or "verify"
    json_output = getattr(args, "json_output", False)

    if sub == "steps":
        if json_output:
            payload = [
                {
                    "id": s.id,
                    "title": s.title,
                    "command": s.command,
                    "description": s.description,
                    "optional": s.optional,
                }
                for s in GOLDEN_STEPS
            ]
            print(json.dumps(payload, indent=2))
        else:
            table = Table(title="AgentDrive golden path", show_header=True)
            table.add_column("#", style="dim", width=3)
            table.add_column("Step", style="cyan")
            table.add_column("Command", overflow="fold")
            table.add_column("Notes", overflow="fold")
            for i, step in enumerate(GOLDEN_STEPS, 1):
                note = "optional (auto-seeds)" if step.optional else ""
                table.add_row(str(i), step.title, step.command, note)
            console.print(table)
            console.print()
            console.print("[dim]Docs: docs/GOLDEN_PATH.md[/]")
            console.print("[dim]Run: agentdrive golden-path run[/]")
        return 0

    if sub == "verify":
        step_id = getattr(args, "step", None)
        if step_id:
            result = verify_step(step_id)
        else:
            result = verify_all(include_optional=not getattr(args, "skip_optional", False))
        if json_output:
            print(json.dumps(result, indent=2, default=str))
        else:
            steps = result.get("steps") or [result]
            table = Table(title="Golden path verification", show_header=True)
            table.add_column("Step", style="cyan")
            table.add_column("Status")
            table.add_column("Detail", overflow="fold")
            for item in steps:
                ok = item.get("success", False)
                status = "[green]pass[/]" if ok else "[red]fail[/]"
                table.add_row(
                    str(item.get("step") or item.get("title") or "?"),
                    status,
                    str(item.get("detail") or item.get("error") or ""),
                )
            console.print(table)
            if "passed" in result:
                console.print(f"\n[dim]{result['passed']}/{result['total']} steps passed[/]")
        return 0 if result.get("success") else 1

    if sub == "run":
        result = run_walkthrough(
            dry_run=bool(getattr(args, "dry_run", False)),
            stop_on_fail=not getattr(args, "continue_on_fail", False),
        )
        if json_output:
            print(json.dumps(result, indent=2, default=str))
        else:
            table = Table(
                title=f"Golden path run ({'dry-run' if result.get('dry_run') else 'live'})",
                show_header=True,
            )
            table.add_column("Step", style="cyan")
            table.add_column("Status")
            table.add_column("Notes", overflow="fold")
            for item in result.get("steps") or []:
                ok = item.get("success", False)
                status = "[green]ok[/]" if ok else "[red]fail[/]"
                note = item.get("detail") or item.get("note") or ""
                if item.get("skipped"):
                    status = "[dim]skip[/]"
                    note = item.get("detail") or "already satisfied"
                table.add_row(str(item.get("step", "?")), status, str(note))
            console.print(table)
            console.print(f"\n[dim]{result.get('passed', 0)}/{result.get('total', 0)} steps[/]")
            console.print("[dim]Full guide: docs/GOLDEN_PATH.md[/]")
        return 0 if result.get("success") else 1

    console.print("[red]Unknown golden-path subcommand[/]")
    return 1


def build_help_epilog() -> str:
    """Epilog string for the root argparse parser."""
    return format_epilog()