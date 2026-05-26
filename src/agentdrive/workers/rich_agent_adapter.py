"""
Rich Agent Adapter — Canonical Example

A concrete, working demonstration of a rich external worker that participates
in the AgentDrive using the Harness.

This is THE reference implementation showing how any capable external agent
(rich custom agents, or compatible systems) can:

  1. Pull relevant "DNA" (Genomes) for the current task
  2. Adapt its prompts, tool selection, and reasoning using that DNA
  3. Execute rich, multi-step, tool-augmented work (simulated here)
  4. Record the full outcome / trajectory signal back into the Drive
     (contribute back for future agents and automatic genome improvement)

Location: agentdrive/workers/rich_agent_adapter.py

Run as a script (the intended canonical demo):

    # From the agentdrive/ project root
    PYTHONPATH=src python -m agentdrive.workers.rich_agent_adapter \
        --task "Analyze the recent production database outage and write a blameless postmortem"

Or import and use programmatically:

    from agentdrive.workers.rich_agent_adapter import RichAgentAdapter
    worker = RichAgentAdapter(agent_id="my-rich-agent-007")
    result = worker.run("your task description here")

The class does NOT inherit from the base Worker yet (to stay lightweight
and focused on the harness usage pattern). A real integration would also
implement `as_worker()` via the AgentAdapter protocol.

This file is intentionally self-documenting and runnable in one command.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


# ------------------------------------------------------------------
# Path bootstrap so the module is robust whether run via:
#   - python -m agentdrive.workers.rich_agent_adapter  (with PYTHONPATH=src)
#   - direct execution of the .py file
#   - after `pip install -e .`
# ------------------------------------------------------------------
def _ensure_importable():
    """Make 'import agentdrive' succeed even when the file is executed directly."""
    here = Path(__file__).resolve()
    # .../agentdrive/src/agentdrive/workers/rich_agent_adapter.py
    # parents[0]=workers, [1]=agentdrive, [2]=src, [3]=agentdrive-project-root
    src_dir = here.parents[2]
    project_root = here.parents[3]

    for p in (str(src_dir), str(project_root)):
        if p not in sys.path:
            sys.path.insert(0, p)


_ensure_importable()

# Direct submodule imports (avoids reliance on partial 'agentdrive' package namespace during __init__.py execution)
from agentdrive.drive.drive import get_default_drive
from agentdrive.harness.harness import Harness
from agentdrive.registry import GenomeRegistry

# Rich is a hard dependency of Agent Drive (see pyproject.toml)
try:
    from rich import print as rprint
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    HAS_RICH = True
except Exception:  # pragma: no cover
    HAS_RICH = False
    console = None  # type: ignore[assignment]

    def rprint(*a, **k):  # type: ignore
        print(*a, **k)


class RichAgentAdapter:
    """
    A simulated rich external agent that uses Harness for every run.

    Rich worker traits demonstrated:
    - Explicit, named tool invocations with arguments
    - Structured internal monologue / trajectory (steps, observations, claims)
    - Heavy use of injected reasoning patterns from the Agent Drive DNA pool
    - Self-scoring, reflection, and discovery of new micro-patterns
    - Clean separation of "pull DNA → adapt → execute → record/contribute"

    The entire `run(task)` is wrapped in `harness.task_context(...)` so the
    full pull-adapt-work-contribute loop happens automatically.

    This serves as the canonical example of how external agents integrate
    with Agent Drive for DNA-enhanced execution.
    """

    name: str = "rich-agentdrive-harness-worker"

    def __init__(self, agent_id: str = "rich-agent-001"):
        self.agent_id = agent_id
        self.harness = Harness(agent_id=agent_id)
        self.trajectory: list[dict[str, Any]] = []  # full execution trace

    # ---------- internal rich worker logging ----------
    def _log(self, step_type: str, content: Any, **meta: Any) -> None:
        entry: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "type": step_type,
            "content": content,
            "meta": meta,
        }
        self.trajectory.append(entry)

        prefix = f"[bold cyan]{step_type}[/]" if HAS_RICH else f"[{step_type}]"
        if HAS_RICH:
            rprint(f"{prefix} {content}")
        else:
            print(f"{prefix} {content}")

    # ---------- the core public API ----------
    def run(self, task: str) -> dict[str, Any]:
        """
        Execute a complete rich task while participating in the AgentDrive.

        This is the method that external agents should model for full integration.
        """
        header = "=" * 64
        print(f"\n{header}")
        print(f"  RichAgentAdapter  |  agent={self.agent_id}")
        print(f"  Task: {task}")
        print(header + "\n")

        # Make sure the Drive has seed DNA (the security-incident genome etc.)
        registry = GenomeRegistry()
        bootstrapped = registry.register_example_if_needed()
        if bootstrapped:
            self._log("BOOTSTRAP", f"Registered seed genome: {bootstrapped}")

        pool = get_default_drive()
        stats = pool.get_pool_stats()
        self._log("POOL_STATUS", f"{stats['total_genomes']} genomes available in AgentDrive")

        outcome: dict[str, Any] = {}

        # ======================================================
        # THE FULL LOOP — wrapped by the harness
        # ======================================================
        with self.harness.task_context(task):
            # --- 1. PULL DNA ---
            dna = self.harness.pull_relevant_dna(task=task, top_k=5)
            self._log("PULL_DNA", f"Retrieved {len(dna)} high-value genomes for this task")

            if dna and HAS_RICH:
                t = Table(title="Pulled Agent Drive DNA (top matches)")
                t.add_column("genome_id", style="green")
                t.add_column("score", justify="right")
                t.add_column("key_reasoning_patterns")
                for pkt in dna:
                    pats = ", ".join(pkt.get("top_reasoning", [])[:3]) or "(none)"
                    t.add_row(
                        pkt["genome_id"],
                        f"{pkt.get('score', 0.0):.2f}",
                        pats,
                    )
                console.print(t)
            elif dna:
                for pkt in dna[:3]:
                    print(f"  • {pkt['genome_id']} (score={pkt.get('score', 0):.2f})")

            # --- 2. ADAPT (inject DNA into prompt / policy) ---
            base = (
                "You are a production-grade autonomous agent augmented by Agent Drive DNA.\n"
                f"User task: {task}\n\n"
                "Instructions:\n"
                "- Maintain a complete execution ledger (observations, claims, reflections).\n"
                "- Make every tool call explicit and named.\n"
                "- Use the highest-scoring reasoning patterns available from the AgentDrive.\n"
                "- End with a synthesized, actionable framework."
            )
            enriched = self.harness.inject_into_context(
                base,
                extra_instructions=(
                    "Heavily weight any causal-analysis, blameless-postmortem, or "
                    "framework-synthesis patterns present in the injected Agent Drive DNA. "
                    "Cite the genome_ids you actually used in your final trace."
                ),
            )
            self._log("ADAPT_PROMPT", "DNA successfully injected into system prompt / policy")
            if HAS_RICH:
                console.print(
                    Panel(
                        enriched[:280] + "…", title="Enriched Agent Drive-Augmented Prompt", expand=False
                    )
                )
            else:
                print("   Prompt head:", enriched[:120], "…")

            # --- 3. WORK — rich simulated agent reasoning + tool calls ---
            self._log("REASONING", "Starting tool-augmented, DNA-guided execution loop")

            tools_used: list[str] = []
            patterns_applied: list[str] = []

            # Simulate consulting the pulled genomes
            for pkt in dna[:3]:
                gid = pkt["genome_id"]
                for pat in pkt.get("top_reasoning", [])[:2]:
                    tool = f"apply_pattern:{pat}"
                    self._log(
                        "TOOL_CALL",
                        f"→ {tool}",
                        genome=gid,
                        confidence=round(0.82 + len(tools_used) * 0.03, 2),
                    )
                    tools_used.append(tool)
                    patterns_applied.append(pat)

                    # Fake observation / ledger entry (rich worker style)
                    self._log(
                        "OBSERVATION",
                        f"Applied {pat} from {gid} → causal density increased",
                        genome=gid,
                    )

            # Additional classic rich agent internal tools
            self._log("TOOL_CALL", "→ reflect_on_contradictions")
            tools_used.append("reflect_on_contradictions")
            self._log("CLAIM", "No critical contradictions found after cross-check against DNA")

            self._log("TOOL_CALL", "→ synthesize_actionable_framework")
            tools_used.append("synthesize_actionable_framework")
            self._log("REFLECTION", "Self-assessed output quality: 0.94 (DNA-augmented)")

            # Final rich worker result object
            work_payload = {
                "final_answer": f"Task completed with Agent Drive-augmented reasoning: {task}",
                "framework": "dna_harness_postmortem_v1",
                "patterns_applied": list(set(patterns_applied)),
                "genomes_consulted": self.harness.get_pulled_genomes(),
            }

            self._log("EXECUTION_COMPLETE", "Rich agent finished the task successfully")

            # --- 4. CONTRIBUTE BACK ---
            outcome = {
                "success": True,
                "agent_id": self.agent_id,
                "task": task,
                "quality_score": 0.94,
                "tools_used": tools_used,
                "patterns_applied": patterns_applied,
                "used_genomes": self.harness.get_pulled_genomes(),
                "trajectory_length": len(self.trajectory),
                "work_payload": work_payload,
                "new_micro_patterns_discovered": [
                    "harness_dna_injection_v1",
                    "rich_agent_reflection_with_pool",
                ],
                "recorded_at": datetime.now(UTC).isoformat(),
            }

            self.harness.record_outcome(outcome)
            self._log(
                "CONTRIBUTE_BACK",
                "Outcome + full trajectory recorded via Harness → pool can now evolve",
            )

            # (In a production integration the raw trajectory would also be
            #  fed to Agent DriveRunScanner to auto-extract a new/improved Genome.)

        # End of harness context

        print(f"\n{header}")
        print("  LOOP COMPLETE: pull → adapt → work → contribute")
        print(header + "\n")

        return outcome

    def get_last_trajectory(self) -> list[dict[str, Any]]:
        """Return the full execution trace from the last run()."""
        return list(self.trajectory)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m agentdrive.workers.rich_agent_adapter",
        description="Canonical runnable example of a rich external agent using Harness.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python -m agentdrive.workers.rich_agent_adapter --task "Write a postmortem for the API latency spike"\n'
            '  PYTHONPATH=src python -m agentdrive.workers.rich_agent_adapter --task "..." --agent-id "prod-rich-42"\n'
        ),
    )
    parser.add_argument(
        "--task",
        default="Produce a high-quality blameless postmortem for the recent production database outage",
        help="Natural language task the rich worker should solve while using the harness.",
    )
    parser.add_argument(
        "--agent-id",
        default="rich-agent-demo-001",
        help="Identifier used for harness attribution and pool contributions.",
    )
    args = parser.parse_args()

    worker = RichAgentAdapter(agent_id=args.agent_id)
    result = worker.run(args.task)

    # Pretty final summary
    summary = (
        f"quality={result['quality_score']:.2f}  "
        f"genomes={len(result['used_genomes'])}  "
        f"tools={len(result['tools_used'])}  "
        f"new_patterns={len(result.get('new_micro_patterns_discovered', []))}"
    )
    if HAS_RICH:
        console.print(Panel(summary, title="Final Outcome", style="green"))
    else:
        print("Final outcome:", summary)

    print("\nYou just witnessed the complete Agent Drive participation loop in action.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
