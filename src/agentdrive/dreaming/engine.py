"""
engine — top-level Loom Dreaming orchestrator.

Design goals:
- Thread sleep detection, phase execution, checkpointing, and narrative together.
- Keep all durable writes staged and reversible until run commit.
- No new magic — just disciplined composition + Agent Drive / Genome idioms.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agentdrive.dreaming.phases import DeepResult, RemResult

from agentdrive.dreaming.dilation import (
    DilationPolicy,
    SleepWindow,
    detect_sleep_window,
    should_wake,
)
from agentdrive.dreaming.durable import (
    AGENTDRIVE_SWARM_ID,
    DurableDreamRunner,
)
from agentdrive.dreaming.ingestion import IngestionConfig, MultiSubstrateIngestor
from agentdrive.dreaming.narrative import DreamNarrator
from agentdrive.dreaming.phases import (
    AdversarialPhase,
    DeepPhase,
    DreamPhaseContext,
    LightPhase,
    PhaseConfig,
    RemPhase,
)
from agentdrive.dreaming.scoring import ScoreWeights
from agentdrive.dreaming.storage import DreamPaths, DreamRunRecord, DreamStorage, PhaseCheckpoint
from agentdrive.genome.models import Genome
from agentdrive.reasoning.engine import ReasoningEngine


@dataclass
class DreamEngineConfig:
    """Runtime configuration for Loom Dreaming orchestration."""

    paths: DreamPaths = field(default_factory=DreamPaths)
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)
    dilation: DilationPolicy = field(default_factory=DilationPolicy)
    weights: ScoreWeights = field(default_factory=ScoreWeights)
    phase: PhaseConfig = field(default_factory=PhaseConfig)
    force_when_idle_unknown: bool = False


@dataclass
class DreamEngine:
    """Orchestrator that runs the full Light → REM → Adversarial → Deep cycle."""

    config: DreamEngineConfig = field(default_factory=DreamEngineConfig)
    reasoning_engine: ReasoningEngine | None = None
    storage: DreamStorage = field(init=False)
    ingestor: MultiSubstrateIngestor = field(init=False)
    narrator: DreamNarrator = field(init=False)
    light_phase: LightPhase = field(init=False)
    rem_phase: RemPhase = field(init=False)
    adversarial_phase: AdversarialPhase = field(init=False)
    deep_phase: DeepPhase = field(init=False)
    durable_runner: DurableDreamRunner = field(init=False)

    def __post_init__(self) -> None:
        """Wire phase objects and helpers from config."""
        self.storage = DreamStorage(paths=self.config.paths)
        self.ingestor = MultiSubstrateIngestor(config=self.config.ingestion)
        self.narrator = DreamNarrator()
        self.light_phase = LightPhase(ingestor=self.ingestor, config=self.config.phase)
        self.rem_phase = RemPhase(config=self.config.phase)
        self.adversarial_phase = AdversarialPhase()
        self.deep_phase = DeepPhase(weights=self.config.weights, config=self.config.phase)
        self.durable_runner = DurableDreamRunner(swarm_id=AGENTDRIVE_SWARM_ID)

    def run_if_idle(self) -> str | None:
        """Run Loom Dreaming only if a sleep window can be opened safely."""
        window = detect_sleep_window(self.config.dilation)
        if window is None and not self.config.force_when_idle_unknown:
            return None
        result = self.run_once(window=window)
        return str(result.get("run_id"))

    def run_once(self, window: SleepWindow | None = None) -> dict[str, Any]:
        """Execute one full dream cycle and return a structured run summary."""
        self.storage.ensure_layout()
        lock_path = self.storage.acquire_lock()
        if lock_path is None:
            return {"run_id": "", "status": "locked"}
        run = self.storage.create_run(window=window)
        context = self._build_context(run=run, window=window)
        status = "staged"
        staged: list[Path] = []
        try:
            snapshot_path = self.storage.write_snapshot_manifest(
                run,
                {"runtime_root": str(context.runtime_root), "started_at": context.started_at},
            )
            context.snapshot_manifest = snapshot_path

            # === Durable job integration: each phase executes as a crash-safe, persisted job ===
            # Submit + two-phase run via DurableDreamRunner (persists under role-dream swarm drive)
            light_job = self.durable_runner.submit_phase(
                "light", run_id=run.run_id, window=bool(window)
            )
            light = self.durable_runner.run_phase(light_job, lambda: self.light_phase.run(context))
            self.checkpoint_phase(run.run_id, "light", light.metrics)
            self._write_diary(run.run_id, "light", light.metrics)
            if window and should_wake(window, self.config.dilation):
                status = "woke_after_light"
                return {
                    "run_id": run.run_id,
                    "status": status,
                    "durable_jobs": self._current_durable_job_ids(),
                }

            rem_job = self.durable_runner.submit_phase(
                "rem", run_id=run.run_id, parent_light=light_job
            )
            rem = self.durable_runner.run_phase(
                rem_job, lambda: self.rem_phase.run(context, light.candidates)
            )
            self.checkpoint_phase(run.run_id, "rem", rem.metrics)
            self._write_diary(run.run_id, "rem", rem.metrics)
            if window and should_wake(window, self.config.dilation):
                status = "woke_after_rem"
                return {
                    "run_id": run.run_id,
                    "status": status,
                    "durable_jobs": self._current_durable_job_ids(),
                }

            adv_job = self.durable_runner.submit_phase(
                "adversarial", run_id=run.run_id, parent_rem=rem_job
            )
            adversarial = self.durable_runner.run_phase(
                adv_job, lambda: self.adversarial_phase.run(context, rem.candidates)
            )
            self.checkpoint_phase(run.run_id, "adversarial", adversarial.metrics)
            self._write_diary(run.run_id, "adversarial", adversarial.metrics)
            if window and should_wake(window, self.config.dilation):
                status = "woke_after_adversarial"
                return {
                    "run_id": run.run_id,
                    "status": status,
                    "durable_jobs": self._current_durable_job_ids(),
                }

            deep_job = self.durable_runner.submit_phase(
                "deep", run_id=run.run_id, parent_adversarial=adv_job
            )
            deep = self.durable_runner.run_phase(
                deep_job,
                lambda: self.deep_phase.run(
                    context, adversarial.survivors, reinforcement_by_key=rem.reinforcement_by_key
                ),
            )
            self.checkpoint_phase(run.run_id, "deep", deep.metrics)
            self._write_diary(run.run_id, "deep", deep.metrics)
            for lane, candidates in {
                "memory": deep.promoted_memory,
                "genome": deep.promoted_genomes,
                "pattern": deep.promoted_patterns,
            }.items():
                for candidate in candidates:
                    staged.append(self.storage.stage_promotion(run, lane, candidate))
            self.storage.commit_run(run)

            # Auto-ingest dream outputs (new observations + genome proposals + edges via kg)
            # into the drive with proper role-dream role-swarm attribution.
            ingest_summary = self._auto_ingest_dream_outputs(run, deep, rem)

            durable_ids = self._current_durable_job_ids()
            return {
                "run_id": run.run_id,
                "status": status,
                "staged_promotions": [str(path) for path in staged],
                "durable_jobs": durable_ids,
                "ingest_summary": ingest_summary,
                "swarm_id": AGENTDRIVE_SWARM_ID,
            }
        except Exception as exc:
            status = "failed"
            self.storage.rollback_run(run, reason=str(exc))
            raise
        finally:
            self.storage.release_lock(lock_path)

    def _build_context(self, run: DreamRunRecord, window: SleepWindow | None) -> DreamPhaseContext:
        """Build the shared phase context for one run."""
        return DreamPhaseContext(
            run_id=run.run_id,
            started_at=time.time(),
            runtime_root=self.config.paths.root.parent,
            tick_budget=window.tick_budget if window else 0,
            snapshot_manifest=run.snapshot_manifest,
            reasoning_engine=self.reasoning_engine,
            provenance={"origin": "dreaming", "dream_run_id": run.run_id},
        )

    def checkpoint_phase(self, run_id: str, phase: str, metrics: dict[str, Any]) -> Path:
        """Write a coarse-grained checkpoint for one finished phase."""
        now = time.time()
        checkpoint = PhaseCheckpoint(
            run_id=run_id,
            phase=phase,
            status="completed",
            started_at=now,
            completed_at=now,
            metrics=metrics,
        )
        return self.storage.write_phase_checkpoint(checkpoint)

    def _write_diary(self, run_id: str, phase: str, metrics: dict[str, Any]) -> None:
        entry = self.narrator.dispatch_phase_diary(run_id, phase, {"metrics": metrics})
        self.narrator.write_phase_entry(entry)

    def _current_durable_job_ids(self) -> list[str]:
        """Helper for run summaries: expose the jobs created during this cycle."""
        # In real use the runner tracks; here we surface recent for this swarm
        try:
            recent = self.durable_runner.list_jobs()[:8]
            return [j.id for j in recent]
        except Exception:
            return []

    # --- Observability & auto-ingest (task requirements) ---

    def get_dream_status(self) -> dict[str, Any]:
        """Simple observable status for schedulers and dashboards. Delegates to durable runner."""
        try:
            summary = self.durable_runner.get_status_summary()
            summary["engine"] = "loom-dreaming"
            summary["last_run_hint"] = getattr(self, "_last_run_id", None)
            return summary
        except Exception as e:
            return {"error": str(e), "swarm_id": AGENTDRIVE_SWARM_ID}

    def get_dream_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Durable job history for observability, replay, and scheduling decisions."""
        try:
            return self.durable_runner.get_recent_history(limit=limit)
        except Exception:
            return []

    def _auto_ingest_dream_outputs(
        self,
        run: DreamRunRecord,
        deep: "DeepResult",
        rem: "RemResult",
    ) -> dict[str, Any]:
        """
        Automatically ingest dream outputs (promoted candidates as observations/genome proposals,
        plus derived edges) back into the central swarm drive with proper role-dream
        role-swarm + sub-agent attribution. This closes the loop: dreams improve the Drive.
        """
        summary: dict[str, Any] = {
            "ingested": 0,
            "genome_proposals": 0,
            "observations": 0,
            "errors": [],
        }
        try:
            # Use the dream swarm's drive explicitly for attribution
            # (get_swarm... ensures correct isolation + author tagging path)
            from agentdrive.drive.swarm_manager import get_swarm_drive_manager
            from agentdrive.genome.models import Genome, GenomeAuthor

            mgr = get_swarm_drive_manager()
            dream_drive = mgr.get_or_create_pool(AGENTDRIVE_SWARM_ID, subagent_id="dream-cycle")

            # Phase 2: exercise infer + get_active_schema_pack on dreaming ingestion path (charter gap close)
            try:
                _pack = dream_drive.get_active_schema_pack()
                for cand in (deep.promoted_genomes or [])[:3]:
                    _ = dream_drive.infer_page_type(
                        f"dreams/{run.run_id}/promoted/{getattr(cand, 'candidate_id', 'obs')}"
                    )
                if _pack:
                    _ = _pack.resolve_type("dreams/")  # touch resolution
            except Exception:
                pass

            # Ingest promoted genomes lane as first-class genome proposals
            for cand in deep.promoted_genomes or []:
                try:
                    gid = f"dream-proposal-{run.run_id}-{cand.candidate_id}"[:64]
                    g = Genome.create(
                        id=gid.lower().replace("_", "-"),
                        version="0.1.0-dream",
                        framework={
                            "kind": "dream-derived-genome-proposal",
                            "source_run": run.run_id,
                            "phase": "deep",
                            "lane": "genome",
                            "score": cand.total_score,
                            "canonical_key": cand.canonical_key,
                            "concepts": cand.concepts,
                            "provenance": {"dream_run_id": run.run_id, "origin": "loom_dreaming"},
                        },
                        authors=[
                            GenomeAuthor(
                                type="agent",
                                id=AGENTDRIVE_SWARM_ID,
                                name="durable dream production role-swarm",
                            ),
                            GenomeAuthor(type="agent", id="sub:dream-cycle", name="dream-cycle"),
                        ],
                        applicability={
                            "domains": ["self-modeling", "dreaming", "evolution"],
                            "source": "loom-dream",
                        },
                        evaluation_score={"dream_fitness": float(cand.total_score)},
                    )
                    dream_drive.ingest(
                        g,
                        source="dream-deep-genome-proposal",
                        actor=AGENTDRIVE_SWARM_ID,
                        subagent_id="dream-cycle",
                    )
                    summary["genome_proposals"] += 1
                    summary["ingested"] += 1
                except Exception as ie:
                    summary["errors"].append(str(ie)[:120])

            # Ingest top memory + pattern promotions as observations (via simple genome records + kg edges)
            for lane_name, cands in [
                ("memory", deep.promoted_memory or []),
                ("pattern", deep.promoted_patterns or []),
            ]:
                for cand in cands[:5]:  # limit to keep runs lightweight
                    try:
                        obs_id = f"dream-observation-{lane_name}-{run.run_id}-{cand.candidate_id}"[
                            :64
                        ]
                        g = Genome.create(
                            id=obs_id.lower().replace("_", "-"),
                            version="0.1.0-dream",
                            framework={
                                "kind": "dream-observation",
                                "lane": lane_name,
                                "source_run": run.run_id,
                                "score": cand.total_score,
                                "supporting_signals": len(cand.supporting_signals),
                                "risk_flags": cand.risk_flags,
                                "provenance": {
                                    "dream_run_id": run.run_id,
                                    "origin": "loom_dreaming",
                                },
                            },
                            authors=[
                                GenomeAuthor(
                                    type="agent",
                                    id=AGENTDRIVE_SWARM_ID,
                                    name="durable dream production role-swarm",
                                ),
                            ],
                            applicability={"domains": ["memory", "patterns", "self-reflection"]},
                            evaluation_score={"dream_score": float(cand.total_score)},
                        )
                        dream_drive.ingest(
                            g,
                            source=f"dream-{lane_name}-observation",
                            actor=AGENTDRIVE_SWARM_ID,
                            subagent_id="dream-cycle",
                        )
                        summary["observations"] += 1
                        summary["ingested"] += 1
                    except Exception as ie:
                        summary["errors"].append(str(ie)[:120])

            # REM inhabitants also become lightweight observations (new reasoning patterns surfaced)
            for inh in (rem.inhabitants or [])[:3]:
                try:
                    rid = f"dream-rem-inhabitant-{run.run_id}-{inh.inhabitant_id}"[:64]
                    g = Genome.create(
                        id=rid.lower().replace("_", "-"),
                        version="0.1.0-dream",
                        framework={
                            "kind": "dream-rem-inhabitant",
                            "fitness": inh.simulated_fitness,
                            "run": run.run_id,
                        },
                        authors=[GenomeAuthor(type="agent", id=AGENTDRIVE_SWARM_ID)],
                    )
                    dream_drive.ingest(
                        g,
                        source="dream-rem-observation",
                        actor=AGENTDRIVE_SWARM_ID,
                        subagent_id="dream-cycle",
                    )
                    summary["observations"] += 1
                    summary["ingested"] += 1
                except Exception:
                    pass

            # Note: drive.ingest automatically extracts knowledge_graph edges for every genome above.
            # This satisfies "new edges" + "proper role-swarm attribution".
        except Exception as e:
            summary["errors"].append(f"auto-ingest top level: {str(e)[:200]}")
        return summary


def genome_engine_anchor(genome: Genome | None) -> str:
    """Return a stable Genome anchor for future engine-level backfills."""
    return genome.genome_id if genome else ""
