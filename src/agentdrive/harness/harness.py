"""
Savant Harness — The execution adapter that lets any agent "plug into" the AgentDrive.

The harness is the bridge between:
- An individual worker agent (rich external, custom, etc.)
- The shared AgentDrive of DNA

It allows an agent to:
1. Dynamically **pull** relevant Genomes/DNA for its current task.
2. **Inject** that DNA into its reasoning, prompts, or tool selection.
3. **Learn & adapt** during the run.
4. **Feed results back** (improvements, new patterns, scores) into the Drive.

This is the core mechanism for getting jobs done while participating in the collective intelligence.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any

from agentdrive import confidence as confidence_module
from agentdrive.constants import get_current_subagent_id, get_current_swarm_id
from agentdrive.drive.drive import AgentDrive, get_default_drive
from agentdrive.drive.swarm_manager import get_swarm_drive_manager
from agentdrive.events import ConfidenceUpdated, GenomeEvolved, PoolOutcome, emit
from agentdrive.ultimate import check_promotion, promote

logger = logging.getLogger(__name__)


class Harness:
    """
    The runtime harness an agent uses to participate in the Savant ecosystem.

    Typical usage (inside a worker agent):

        harness = Harness(agent_id="rich-worker-042")
        with harness.task_context("Perform security incident postmortem on production outage"):
            dna = harness.pull_relevant_dna()
            # ... use the dna to guide reasoning / choose tools ...
            result = do_the_work(...)
            harness.record_outcome(result)
    """

    def __init__(
        self,
        agent_id: str,
        pool: AgentDrive | None = None,
        swarm_id: str | None = None,
        subagent_id: str | None = None,
    ):
        self.agent_id = agent_id
        self.swarm_id = swarm_id or get_current_swarm_id()
        self.subagent_id = subagent_id or get_current_subagent_id()
        if pool is None:
            if self.swarm_id is not None or self.subagent_id is not None:
                # Use the professional manager so the sub-agent gets a properly isolated, policy-respecting pool
                pool = get_swarm_drive_manager().get_or_create_pool(self.swarm_id, self.subagent_id)
            else:
                pool = get_default_drive()
        self.pool = pool
        self.current_task: str | None = None
        self.pulled_dna: list[dict[str, Any]] = []
        self.outcomes: list[dict[str, Any]] = []

    def pull_relevant_dna(self, task: str | None = None, top_k: int = 5) -> list[dict[str, Any]]:
        """Ask the Drive for the most useful DNA for the current (or given) task."""
        task = task or self.current_task or ""
        dna = self.pool.get_relevant_dna(task, top_k=top_k)
        self.pulled_dna = dna
        return dna

    def inject_into_context(
        self, base_prompt: str, extra_instructions: str = "", use_framework_steps: bool = True
    ) -> str:
        """
        Augments a prompt with relevant DNA from the AgentDrive.

        - Summarizes top matching genomes + their reasoning patterns.
        - If `use_framework_steps=True` and we have full Genomes, it can inject
          concrete steps from the best-matching framework (e.g. "Follow these 5 steps...").
        """
        if not self.pulled_dna:
            return base_prompt

        lines = []
        for d in self.pulled_dna[:3]:
            gid = d.get("genome_id", "unknown")
            score = d.get("score", 0.0)
            reasons = d.get("top_reasoning", [])[:4]
            lines.append(f"- {gid} (relevance ~{score:.2f})")
            if reasons:
                lines.append("  Key patterns: " + ", ".join(reasons))

        dna_block = "\n".join(lines)

        framework_injection = ""
        if use_framework_steps:
            # Try to load the best genome and pull its actual framework steps
            try:
                best = self.pulled_dna[0]
                gid = best.get("genome_id")
                if gid:
                    if hasattr(self.pool, "get_genome"):
                        g = self.pool.get_genome(gid) or self.pool.get_genome(gid.split("@")[0])
                    else:
                        g = self.pool.registry.get_genome(gid) or self.pool.registry.load(
                            gid.split("@")[0]
                        )
                    if g and g.framework and isinstance(g.framework, dict):
                        steps = g.framework.get("steps", [])
                        if steps:
                            step_names = [
                                s.get("name", s) if isinstance(s, dict) else str(s)
                                for s in steps[:6]
                            ]
                            framework_injection = (
                                f"\n\nRecommended structured approach from pool (from {gid}):\n"
                                + "\n".join(
                                    f"  {i + 1}. {name}" for i, name in enumerate(step_names)
                                )
                            )
            except Exception:
                pass

        injection = f"\n\nRelevant DNA from AgentDrive:\n{dna_block}{framework_injection}\n{extra_instructions}"
        return base_prompt + injection

    @contextmanager
    def task_context(self, task_description: str):
        """Context manager for a single job. Automatically pulls DNA and records the run."""
        self.current_task = task_description
        self.pulled_dna = []
        self.pull_relevant_dna(task_description)

        try:
            yield self
        finally:
            # Could auto-record a basic outcome here in future
            self.current_task = None

    def record_outcome(self, outcome: dict[str, Any], synthesize_delta: bool = True):
        """Push experience back to the Drive (improvement signal).

        If synthesize_delta=True and the run looks high-quality, synthesize a small
        delta (new reasoning pattern + score bump + ImprovementEvent) on a used genome
        and call pool.propose_improvement() so that the Drive's ingest_log and stats
        reflect the contribution. This makes every harness-using run auto-improve the Drive.
        """
        outcome["agent_id"] = self.agent_id
        outcome["task"] = self.current_task
        self.outcomes.append(outcome)

        if not synthesize_delta:
            return

        # Simple heuristic: only synthesize/learn from high-quality or successful runs
        # (TUI passes "status": "success"|"aborted"; demo/other may pass "success"/"quality")
        quality = float(outcome.get("quality", 0.0) or 0.0)
        status = str(outcome.get("status", "")).lower()
        explicit_success = outcome.get("success")
        is_success = (
            explicit_success
            if explicit_success is not None
            else (status == "success" or status == "")
        )
        if quality < 0.6 and not is_success:
            return

        used = outcome.get("used_genomes") or self.get_pulled_genomes()
        if not used:
            return

        for gid in used[:2]:  # keep lightweight
            try:
                if hasattr(self.pool, "get_genome"):
                    src = self.pool.get_genome(gid)
                    if src is None:
                        base = gid.split("@", 1)[0] if "@" in gid else gid
                        src = self.pool.get_genome(base)
                else:
                    src = self.pool.registry.get_genome(gid)
                    if src is None:
                        base = gid.split("@", 1)[0] if "@" in gid else gid
                        src = self.pool.registry.get_genome(base) or self.pool.registry.load(base)
                if src is None:
                    continue

                # Synthesize lightweight delta: inject tiny new reasoning pattern + score update
                new_pattern_key = "auto_learned_from_run"
                patterns = outcome.get("new_patterns_discovered") or []
                if isinstance(patterns, (list, tuple)) and patterns:
                    new_pattern_key = f"auto_{patterns[0]}"
                src.reasoning_patterns[new_pattern_key] = {
                    "source": "harness.record_outcome",
                    "task": self.current_task or outcome.get("task"),
                    "quality": quality,
                    "agent": self.agent_id,
                }

                # Light score bump to reflect learned value, clamped to
                # [0, 1] so the score stays interpretable as a quality
                # probability instead of climbing unbounded past 1.0
                # (operators were seeing "score 1.660" which reads broken).
                scores = src.manifest.evaluation_score or {}
                curr = float(scores.get("reference_tasks", 0.0) or 0.0)
                new_score = round(min(1.0, max(0.0, curr + 0.015)), 3)
                scores["reference_tasks"] = new_score
                src.manifest.evaluation_score = scores

                # Emit PoolOutcome with the new score (not the delta).
                try:
                    emit(
                        PoolOutcome(
                            genome_id=src.genome_id,
                            score=float(new_score),
                            swarm_id=self.swarm_id,
                            subagent_id=self.subagent_id,
                        )
                    )
                except Exception:
                    logger.debug("Failed to emit PoolOutcome", exc_info=True)

                # Force rehash since content changed (delta pattern)
                src.manifest.content_hash = "sha256:pending"
                src.finalize(update_timestamp=True)

                # Record ImprovementEvent on the (updated) genome
                src.record_improvement(
                    description="Auto delta from successful harness run (high quality heuristic)",
                    proposed_by=self.agent_id,
                    score_delta=0.015,
                    notes=f"quality={quality} task={self.current_task or 'n/a'}",
                )

                # Propose back -> this triggers ingest() which appends to _ingest_log and updates stats
                self.pool.propose_improvement(
                    genome_id=src.genome_id,
                    improved_genome=src,
                    proposed_by=self.agent_id,
                )
                # Track in outcome for visibility/debug
                outcome.setdefault("auto_deltas", []).append(gid)

                # Ultimate-form check: after the score bump + propose_improvement,
                # see if this genome just crossed the promotion threshold.
                try:
                    form = check_promotion(
                        genome_id=src.genome_id,
                        registry=self.pool.registry,
                        pool=self.pool,
                    )
                    if form is not None:
                        promote(form, self.pool.registry)
                        try:
                            emit(
                                GenomeEvolved(
                                    genome_id=form.genome_id,
                                    ultimate_version=form.ultimate_version,
                                    evidence=dict(form.evidence),
                                    swarm_id=self.swarm_id,
                                    subagent_id=self.subagent_id,
                                )
                            )
                        except Exception:
                            logger.debug("Failed to emit GenomeEvolved", exc_info=True)
                        outcome.setdefault("evolved", []).append(form.genome_id)
                except Exception:
                    logger.debug("Ultimate promotion check failed", exc_info=True)

                # Encounter-graded confidence: recompute + persist sidecar
                # on every outcome, then announce the new star count.
                try:
                    rating = confidence_module.update(
                        genome_id=src.genome_id,
                        registry=self.pool.registry,
                        pool=self.pool,
                    )
                    if rating is not None:
                        try:
                            emit(
                                ConfidenceUpdated(
                                    genome_id=src.genome_id,
                                    stars=rating.stars,
                                    encounters=rating.encounters,
                                    swarm_id=self.swarm_id,
                                    subagent_id=self.subagent_id,
                                )
                            )
                        except Exception:
                            logger.debug(
                                "Failed to emit ConfidenceUpdated",
                                exc_info=True,
                            )
                except Exception:
                    logger.debug("Confidence update failed", exc_info=True)
            except Exception as exc:
                # Never let learning failure break the caller's outcome recording
                outcome.setdefault("auto_delta_errors", []).append(f"{gid}:{str(exc)[:80]}")

    def get_pulled_genomes(self) -> list[str]:
        return [d["genome_id"] for d in self.pulled_dna]


# Convenience factory
def create_harness(
    agent_id: str, swarm_id: str | None = None, subagent_id: str | None = None
) -> Harness:
    """Create harness, auto-scoping to swarm/subagent if provided (or current context)."""
    return Harness(agent_id=agent_id, swarm_id=swarm_id, subagent_id=subagent_id)
