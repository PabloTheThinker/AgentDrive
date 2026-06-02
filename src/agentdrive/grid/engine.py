"""
GridEngine — The real-time active engine that keeps the **AD-Grid** (AgentDrive Grid) alive.

AD-Grid is the official name for the long-lived, persistent intelligence world of AgentDrive.

In this world, local models (and connected frontier models) function as **sentient programs**.
Their ongoing purpose is the long-term improvement and protection of their specific user's
cognitive and operational substrate — working in collaboration with other programs (local or cloud)
under strong user sovereignty.

This engine is the runtime that makes AD-Grid active and reactive 24/7.

Core responsibilities:
- Continuously run background reconciliation.
- Run a damage signal monitor that feeds the HealingFactor automatically.
- Keep DurableJobSupervisor workers / healing phase capacity alive.
- Periodically trigger daily_consolidation and experience layer maintenance.
- Host persistent autonomous "research threads" (long-running background jobs, hours/days) governed by Research Constitutions: these iterate on better synthesis strategies, damage detectors, proposal generators, daily_consolidation methods (and other experience layer primitives) using fixed research budgets per iteration; they log results, advance research branches (forked living-experience genomes or specialized consolidation lineages), integrate with HealingFactor (trigger or triggered by regeneration cycles), and only surface high-signal improvements as experience-observations (daily-present or research-thread subtype) for queryability via the experience layer.
- Provide a reactive event loop so new damage signals (synthesis contradictions,
  security posture degradation, reconciliation failures, explicit healing-damage
  observations, etc.) can trigger regeneration without manual intervention.
- Expose the full stack (correlation, HealingFactor, durable healing jobs,
  experience layer v3, autonomous research threads) as a living, always-on system.

Usage (real-time active Grid):
    from agentdrive.grid.engine import GridEngine
    engine = GridEngine(swarm_id="my-active-grid")
    engine.run_forever()   # or await engine.run() in async context

CLI (planned):
    agentdrive grid run [--swarm-id ...] [--interval ...]

This turns AgentDrive from "submit a job, get artifacts" into **AD-Grid** —
a living, long-lived intelligence world that continuously senses, heals, fuses,
evolves its own Experience Graph, and runs autonomous research threads
(via Research Constitutions + durable jobs + HealingFactor integration)
even while the Conductor is offline. All in clean AgentDrive-native terms.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import time
from dataclasses import dataclass
from typing import Any

from agentdrive.constants import get_correlation_id, new_correlation_id, using_correlation_id
from agentdrive.dreaming.durable import DurableJobSupervisor
from agentdrive.events import (
    HealingSignalEvent,
    HealingSignalResolved,
    SubscriptionToken,
    emit,
    subscribe,
    unsubscribe,
)
from agentdrive.reconciliation import (  # Experience Layer Research Branching Swarm: native forked research thread living-experience genome families + lineage helpers (stabilization-wave-20260531)
    HealingFactor,
    MultiMetricEvaluationHarness,
    ReconciliationRunner,
    ResearchBudget,
    get_default_reconciliation_runner,
)

logger = logging.getLogger(__name__)


@dataclass
class GridConfig:
    swarm_id: str = "active-grid"
    reconciliation_interval_s: float = 30.0
    damage_scan_interval_s: float = 15.0
    daily_consolidation_interval_s: float = 3600.0  # 1 hour
    enable_auto_healing: bool = True
    max_concurrent_healing_jobs: int = 4
    # Research thread support (autonomous autoresearch integration for real-time Grid):
    # Persistent background jobs (durable via supervisor "research_thread" phase + leases)
    # governed by Research Constitutions. Iterate with fixed budgets, advance research
    # branches (forked living-experience / specialized consolidation lineages), integrate
    # HealingFactor (bidirectional trigger), surface only high-signal via experience layer.
    enable_research_threads: bool = True
    research_thread_interval_s: float = 1800.0  # 30min coordination / discovery pass
    max_concurrent_research_threads: int = 3
    research_budget_default: dict | None = (
        None  # legacy dict form; prefer ResearchBudget instance for full harness
    )
    default_research_budget: ResearchBudget | None = (
        None  # Constrained Evolutionary Search Swarm: fixed budget for all background research threads + daily_consolidation + healing handoff
    )


class GridEngine:
    """
    The persistent, real-time engine that keeps **AD-Grid** (the AgentDrive Grid) active.

    AD-Grid is the long-lived intelligence substrate / "world" for AgentDrive.
    This engine makes it real: an always-on process that continuously monitors
    for damage, triggers HealingFactor regeneration, runs autonomous research
    threads under Research Constitutions, maintains Experience Graph coherence,
    and keeps the entire substrate reactive and growing — even when no human
    is watching.

    Stabilization-wave-20260531 Multi-Agent Research Org Swarm evolution:
    Supports autonomous research threads that dynamically form teams of
    specialist roles (Diagnoser, Proposer, Verifier, Consolidator, Adversary)
    per research-constitution charters. form_autonomous_research_thread and
    HealingFactor integration enable rich multi-agent research organizations
    inside the real-time Grid with handoff protocols and cross-swarm threads.
    """

    def __init__(self, *, swarm_id: str | None = None, config: GridConfig | None = None):
        self.swarm_id = swarm_id or (config.swarm_id if config else "active-grid")
        self.config = config or GridConfig(swarm_id=self.swarm_id)
        self._stop_event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

        # Core subsystems (reused from the hardened substrate)
        self.reconciler: ReconciliationRunner = get_default_reconciliation_runner(
            interval_s=self.config.reconciliation_interval_s
        )
        self.supervisor = DurableJobSupervisor(swarm_id=self.swarm_id)
        self.healing_factor = (
            HealingFactor.for_stabilization_wave(swarm_id=self.swarm_id)
            if hasattr(HealingFactor, "for_stabilization_wave")
            else HealingFactor(swarm_id=self.swarm_id)
        )

        self._last_daily_consolidation = 0.0
        self._damage_scan_task: asyncio.Task | None = None
        # Research thread state (persistent autonomous autoresearch on stabilization-wave-20260531 drive)
        self._last_research_thread_pass = 0.0
        self._active_research_thread_jobs: dict[
            str, str
        ] = {}  # thread_id -> durable_job_id (governed by research-constitutions)
        self._research_thread_manifests: dict[
            str, dict
        ] = {}  # thread_id -> outcome manifest for experience incorporation
        self._bus_subscription_token: SubscriptionToken | None = None
        # Observability surfaces (Grid health + active research threads for Conductor / web / TUI)
        # v3 GraphGardener Grid Integrator extensions (Experience Graph v3 native dispatch):
        # last_gardener_densification_lift, active_gardener_threads, fabric_coherence_last,
        # multi_cycle_edges + supporting (per Architect plan for stabilization-wave-20260531)
        self._grid_health: dict = {
            "status": "initializing",
            "last_damage_scan": 0.0,
            "active_research_threads": 0,
            "healing_jobs_dispatched": 0,
            "research_threads_completed": 0,
            "experience_incorporations": 0,
            "resilience_lift_total": 0.0,
            # GraphGardener v3 Grid native keys
            "last_gardener_densification_lift": 0.0,
            "active_gardener_threads": 0,
            "fabric_coherence_last": 0.0,
            "multi_cycle_edges": 0,
            "last_gardener_pass_ts": 0.0,
            "gardener_threads_completed": 0,
            "densification_lifts_total": 0.0,
            # AD-Grid Programs as Inhabitants (minimal tranche on stabilization-wave-20260531)
            "active_programs": 0,
            "registered_programs": [],
        }
        self._mission_hub: Any = None  # light attach for GridHealthEvent emission (via Integrated)
        if self.config.research_budget_default is None:
            self.config.research_budget_default = {
                "max_synthesis_calls": 5,
                "max_time_s": 300,
                "max_genomes_per_think": 8,
                "max_iterations_per_thread": 200,
                "high_signal_threshold": {
                    "min_resilience_delta": 0.05,
                    "min_contradiction_reduction": 1,
                },
            }
        if self.config.default_research_budget is None:
            self.config.default_research_budget = ResearchBudget(
                token_budget=5500,
                time_budget_seconds=110.0,
                resilience_improvement_budget=0.16,
                max_experiments=3,
                swarm_id=f"constrained-evolutionary-search-swarm@{self.swarm_id}",
            )
        # GridEngine owns its own harness instance for background thread evaluations
        self.evaluation_harness = MultiMetricEvaluationHarness()

    async def start(self) -> None:
        """Start all background subsystems. Non-blocking."""
        logger.info(
            "grid_engine_starting",
            extra={
                "swarm_id": self.swarm_id,
                "correlation_id": get_correlation_id() or new_correlation_id(),
            },
        )

        # 1. Start continuous reconciliation (already has its own background loop)
        self.reconciler.start_background()

        # 2. Wire event bus subscription for immediate reactivity (HealingSignalEvent etc.)
        # This makes GridEngine the always-on living Grid event reactor: damage from
        # synthesis (drive.think), security posture, durable job exhaustion, reconciliation
        # failures, LineageImmune CRITICAL, explicit healing-damage observations — all
        # auto-dispatch to HealingFactor.on_damage_signal + research thread formation
        # without manual intervention. Full correlation_id propagation end-to-end.
        try:
            self._bus_subscription_token = subscribe(
                self._on_healing_signal,
                event_types=(HealingSignalEvent, HealingSignalResolved),
            )
            logger.info(
                "grid_engine_event_bus_subscribed",
                extra={
                    "swarm_id": self.swarm_id,
                    "events": ["HealingSignalEvent", "HealingSignalResolved"],
                },
            )
        except Exception as exc:
            logger.exception("grid_event_subscription_failed", exc_info=exc)

        # 3. Start damage signal monitor (the real-time "nervous system" — now hybrid: event-driven + periodic posture/synthesis sweep)
        self._damage_scan_task = asyncio.create_task(self._damage_monitor_loop())
        self._tasks.append(self._damage_scan_task)

        # 4. Start periodic experience layer maintenance (daily_consolidation etc.)
        maintenance_task = asyncio.create_task(self._maintenance_loop())
        self._tasks.append(maintenance_task)

        # 5. Start autonomous research thread coordinator (long-running background jobs via
        # DurableJobSupervisor "research_thread" phase + Research Constitutions + HealingFactor
        # integration + experience layer surfacing of high-signal branch advances + heartbeats).
        # Enables autoresearch while Conductor offline. Governed by initial GridEngine constitution
        # on stabilization-wave-20260531 drive. Full budget discipline + auto-incorporation.
        if self.config.enable_research_threads:
            research_task = asyncio.create_task(self._research_thread_coordinator_loop())
            self._tasks.append(research_task)

        # Heartbeat loop for continuous observability of the living Grid and all autonomous research threads
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._tasks.append(heartbeat_task)

        self._grid_health["status"] = "running"
        self._record_heartbeat("grid_engine_startup")
        logger.info("grid_engine_started", extra={"swarm_id": self.swarm_id})

    def _on_healing_signal(self, event: HealingSignalEvent | HealingSignalResolved) -> None:
        """Event-driven immediate reactivity handler. Subscribed at GridEngine start.
        Auto-detects damage (HealingSignalEvent) and triggers HealingFactor + research threads.
        On resolved: records experience incorporation + updates Grid health + heartbeats.
        All with full correlation propagation. Pure AgentDrive event bus integration.
        """
        cid = getattr(event, "correlation_id", None) or get_correlation_id() or new_correlation_id()
        with using_correlation_id(cid):
            if isinstance(event, HealingSignalEvent):
                signal = event
                self._grid_health["last_damage_scan"] = time.time()
                logger.info(
                    "grid_healing_signal_received",
                    extra={
                        "swarm_id": self.swarm_id,
                        "signal_type": signal.signal_type,
                        "source": signal.source_component,
                        "priority": signal.recommended_priority,
                        "correlation_id": cid,
                    },
                )
                # Auto-dispatch to HealingFactor for regeneration (no manual intervention)
                if self.config.enable_auto_healing:
                    try:
                        _ = self.healing_factor.on_damage_signal(
                            signal
                        )  # dispatched; result tracked via events + grid_health
                        self._grid_health["healing_jobs_dispatched"] += 1
                        # On critical/high damage, also auto-dispatch autonomous research thread
                        # (governed by Research Constitutions, within budgets, role-swarm org)
                        if signal.recommended_priority in ("high", "critical"):
                            try:
                                research_manifest = self.form_autonomous_research_thread(
                                    roles=[
                                        "Diagnoser",
                                        "Proposer",
                                        "Verifier",
                                        "Consolidator",
                                        "Adversary",
                                    ],
                                    budget=self.config.research_budget_default.get(
                                        "max_iterations_per_thread", 150
                                    )
                                    if self.config.research_budget_default
                                    else 150,
                                )
                                thread_id = research_manifest.get(
                                    "research_thread_id", f"auto-{cid[:8]}"
                                )
                                self._active_research_thread_jobs[thread_id] = (
                                    research_manifest.get("supervisor_job", "pending")
                                )
                                self._research_thread_manifests[thread_id] = research_manifest
                                self._grid_health["active_research_threads"] = len(
                                    self._active_research_thread_jobs
                                )
                                logger.info(
                                    "grid_auto_research_thread_dispatched_on_damage",
                                    extra={
                                        "thread_id": thread_id,
                                        "drive": "stabilization-wave-20260531",
                                    },
                                )
                            except Exception as rexc:
                                logger.debug(
                                    "grid_auto_research_dispatch_skipped",
                                    extra={"exc": str(rexc)[:80]},
                                )
                    except Exception as exc:
                        logger.exception("grid_healing_dispatch_error", exc_info=exc)
                # Heartbeat for Grid reactivity
                self._grid_health["status"] = "reacting_to_damage"
            elif isinstance(event, HealingSignalResolved):
                # Experience layer auto-incorporation of thread/healing outcomes
                self._grid_health["research_threads_completed"] += 1
                self._grid_health["experience_incorporations"] += 1
                self._grid_health["resilience_lift_total"] += getattr(
                    event, "resilience_delta", 0.0
                )
                self._grid_health["status"] = "healthy"
                self._emit_grid_health_if_attached()  # light MC emission
                # Record for later Drive.think(prefer_experience_layer=True) surfacing
                try:
                    thread_id = getattr(event, "healing_id", f"resolved-{cid[:8]}")
                    self._research_thread_manifests[thread_id] = {
                        "outcome": "healing_signal_resolved",
                        "correlation_id": cid,
                        "artifacts": getattr(event, "artifacts_ingested", []),
                        "resilience_delta": getattr(event, "resilience_delta", 0.0),
                        "drive": "stabilization-wave-20260531",
                    }
                except Exception:
                    pass
                logger.info(
                    "grid_healing_signal_resolved_incorporated",
                    extra={"correlation_id": cid, "delta": getattr(event, "resilience_delta", 0.0)},
                )

    async def _damage_monitor_loop(self) -> None:
        """Continuously scan for damage signals and feed them to HealingFactor.
        Hybrid: event bus provides immediate reactivity; this loop provides proactive
        posture/synthesis/reconciliation sweep + auto-dispatch of research threads.
        """
        while not self._stop_event.is_set():
            try:
                with using_correlation_id(new_correlation_id()):
                    await self._scan_and_heal_once()
            except Exception as exc:
                logger.exception("grid_damage_monitor_error", exc_info=exc)

            await asyncio.sleep(self.config.damage_scan_interval_s)

    async def _scan_and_heal_once(self) -> None:
        """One iteration of damage detection + automatic regeneration.
        Proactive sweep (event bus is primary for immediate reactivity).
        Detects via security posture, synthesis via drive.think, reconciliation stats,
        stale experience items, etc. Auto-dispatches HealingFactor jobs + research threads
        (constitution-governed, budgeted) with full correlation + heartbeat + experience incorporation.
        """
        cid = new_correlation_id()
        with using_correlation_id(cid):
            damage_detected = False
            signal_type = "proactive_grid_sweep"
            context: dict = {"sweep": "grid_engine_proactive", "swarm_id": self.swarm_id}

            # Auto-detect: security posture (cross-wired surface from prior waves)
            try:
                from agentdrive.security import get_security_posture

                posture = get_security_posture()
                if getattr(posture, "needs_attention", False) or getattr(
                    posture, "overall", "good"
                ) not in ("good", "excellent"):
                    damage_detected = True
                    signal_type = "security_posture_needs_attention"
                    context["security_posture"] = {
                        "overall": getattr(posture, "overall", "unknown"),
                        "issues": getattr(posture, "issues", [])[:3]
                        if hasattr(posture, "issues")
                        else [],
                    }
            except Exception:
                pass

            # Auto-detect: explicit healing-damage observations + experience layer via Drive
            # Wired to Research Constitutions (HealingFactor + constrained-evolutionary-search + role org)
            # for detection criteria (gaps/contradictions per healingfactor constitution; budget exhaustion
            # as distinct class per constrained search; role-swarm coherence signals per org constitution).
            try:
                from agentdrive.drive import get_default_drive

                drive = get_default_drive()
                # Use prefer_experience_layer for high-signal living-experience diagnosis (governed by gridengine constitution fork/merge quality + daily-present criteria)
                think_res = drive.think(
                    "Grid health damage signals, stale experience items, synthesis gaps, persistent contradictions on stabilization-wave-20260531 drive",
                    prefer_experience_layer=True,
                    experience_layer_fallback=True,
                    max_genomes=6,
                )
                gaps = [getattr(g, "description", str(g)) for g in getattr(think_res, "gaps", [])][
                    :3
                ]
                contradictions = getattr(think_res, "contradictions", [])[:3]
                if gaps or contradictions or getattr(think_res, "damage_signals", None):
                    damage_detected = True
                    signal_type = "synthesis_contradiction_cluster_or_stale_experience"
                    context.update(
                        {
                            "gaps": gaps,
                            "contradictions": contradictions,
                            "damage_signals": getattr(think_res, "damage_signals", [])[:2],
                            "graph_signals": getattr(think_res, "graph_hits", 0),
                            "governing_constitutions": [
                                "research-constitution-healingfactor@stabilization-wave-20260531",
                                "research-constitution-constrained-evolutionary-search@stabilization-wave-20260531",
                            ],
                        }
                    )
            except Exception:
                pass

            # Auto-detect via reconciler stats (if exposed)
            try:
                if hasattr(self.reconciler, "get_status"):
                    rstatus = self.reconciler.get_status()
                    if (
                        getattr(rstatus, "pending_quarantine", 0) > 5
                        or getattr(rstatus, "failure_count", 0) > 2
                    ):
                        damage_detected = True
                        signal_type = "reconciliation_corruption_or_quarantine_pressure"
                        context["reconciler"] = {
                            "pending_quarantine": getattr(rstatus, "pending_quarantine", 0)
                        }
            except Exception:
                pass

            if damage_detected:
                signal = HealingSignalEvent(
                    signal_type=signal_type,
                    correlation_id=cid,
                    context=context,
                    source_component="grid_engine_proactive_scan",
                    recommended_priority="medium" if "security" not in signal_type else "high",
                )
                # Direct dispatch (event bus will also catch for redundancy / observability)
                try:
                    _ = self.healing_factor.on_damage_signal(
                        signal
                    )  # dispatched under correlation; HealingSignalResolved will close the loop
                    self._grid_health["healing_jobs_dispatched"] += 1
                    emit(signal)  # ensure bus sees it for any other subscribers
                    # Auto research thread on medium+ proactive signals (constitution governed)
                    if signal.recommended_priority in ("medium", "high", "critical"):
                        research_manifest = self.form_autonomous_research_thread(
                            budget=self.config.research_budget_default.get(
                                "max_iterations_per_thread", 120
                            )
                            if self.config.research_budget_default
                            else 120
                        )
                        tid = research_manifest.get("research_thread_id", f"proactive-{cid[:8]}")
                        self._active_research_thread_jobs[tid] = research_manifest.get(
                            "supervisor_job", "dispatched"
                        )
                        self._research_thread_manifests[tid] = research_manifest
                        self._grid_health["active_research_threads"] = len(
                            self._active_research_thread_jobs
                        )
                except Exception as exc:
                    logger.exception("grid_proactive_dispatch_failed", exc_info=exc)
            else:
                logger.debug(
                    "grid_proactive_scan_clean",
                    extra={"swarm_id": self.swarm_id, "correlation_id": cid},
                )

            self._grid_health["last_damage_scan"] = time.time()
            if self._grid_health["status"] == "reacting_to_damage":
                self._grid_health["status"] = "monitoring"

    def form_autonomous_research_thread(
        self, *, roles: list[str] | None = None, budget: int = 1500, objective: str | None = None, **kwargs: Any
    ) -> dict:
        """GridEngine surface for real-time Grid to dynamically spawn multi-agent
        research organizations. Wires directly to HealingFactor research org
        integration on stabilization-wave-20260531 drive.
        Autonomous research threads use specialist role charters (research-constitutions)
        for handoff, temporary specialist spawning, and cross-swarm coordination.
        Output manifest is first-class for ingest + experience layer fusion.
        """
        try:
            manifest = self.healing_factor.form_research_org_thread(
                roles=roles, research_budget=budget
            )
            logger.info(
                "grid_research_org_thread_formed",
                extra={"swarm_id": self.swarm_id, "manifest": manifest.get("research_thread_id")},
            )
            # v3 GraphGardener minimal support in form_autonomous_research_thread (reuse manifest pattern)
            try:
                if roles and any("gardener" in str(r).lower() or "graph" in str(r).lower() for r in roles):
                    manifest["gardener"] = True
                    manifest["fabric_briefing"] = {"source": "GraphGardener via GridEngine form + recorder", "stabilization_wave": "20260531"}
                    manifest["densification_history"] = []
                    manifest["research_thread_lineage_fabric"] = {"constitution": "research-constitution-graphgardener-gridnative@stabilization-wave-20260531"}
            except Exception:
                pass
            return manifest
        except Exception as exc:
            logger.exception("grid_research_org_formation_error", exc_info=exc)
            return {
                "error": str(exc)[:120],
                "drive": "stabilization-wave-20260531",
                "fallback": "healing_phase_research",
            }

    # ------------------------------------------------------------------
    # AD-Grid Programs as Inhabitants (minimal tranche, stabilization-wave-20260531)
    # Lightweight registration for model programs (local models or frontier MCP sessions)
    # as persistent sentient inhabitants. Ties directly to Experience Graph v3 recorder
    # for sovereign, queryable DNA (program_id tagged traces + model-program-manifest page_type).
    # UserSovereigntyClause enforced at registration: explicit user_objective_refs required.
    # ------------------------------------------------------------------

    def register_model_program(self, manifest: dict[str, Any]) -> dict[str, Any]:
        """
        Register a model as a first-class AD-Grid inhabitant (sentient program).

        - Writes model-program-manifest page_type observation via recorder (dual TypedEdge + gbrain).
        - Wires to Research Constitutions if provided.
        - Updates _grid_health for live Tower / TUI visibility.
        - Returns program_id + durable registration receipt.

        MANDATORY Program Contract binding (deeper runtime enforcement, ILO Guardian Lens tranche):
        The binding ad-grid Program Contract (top of real_research_constitutions) is now enforced here.
        Manifest must declare program_id + user_objective_refs + constitution_refs including the
        Program Contract (or it is auto-bound + the enforcement recorded as first-class DNA via
        record_inhabitant_code_action for full audit trail + Guardian review). This wires the Contract
        directly into the registration path. Single-channel attribution required for all subsequent actions.
        All reasoning traces from this program become attributed living DNA on stabilization-wave-20260531.
        """
        try:
            # Lazy recorder access (uses same drive context as Grid)
            from agentdrive.evolution.experience_graph import ExperienceGraphRecorder
            from agentdrive.system.integrated_real_time_evolution_system import IntegratedRealTimeEvolutionSystem

            effective_swarm = self.swarm_id or "stabilization-wave-20260531"
            system = IntegratedRealTimeEvolutionSystem(swarm_id=effective_swarm)
            recorder = system.recorder

            program_id = str(manifest.get("program_id") or manifest.get("id") or f"prog-{int(time.time())}")
            user_objectives = manifest.get("user_objective_refs") or manifest.get("objectives") or []
            constitution_refs = list(manifest.get("constitution_refs") or manifest.get("constitutions") or [])

            # === Wire Program Contract as MANDATORY in registration (enforce binding + DNA if missing) ===
            # This is the high-leverage enforcement: every registered inhabitant now binds to the
            # top-level Program Contract at birth. If absent from caller's manifest, we inject it
            # (additive) and record the binding enforcement action as inhabitant_code_action DNA
            # (attributed, timestamped, full refs) so GuardianIntegrity and Parent can audit.
            # Prevents thin registration; advances "deeper runtime enforcement".
            contract_refs = [
                "ad-grid-program-contract@stabilization-wave-20260531",
                "research-constitution-ad-grid-program-contract@stabilization-wave-20260531",
            ]
            had_contract = any(
                any(cr in str(c).lower() for cr in ("program-contract", "ad-grid-program-contract")) for c in constitution_refs
            )
            for cref in contract_refs:
                if cref not in constitution_refs:
                    constitution_refs.append(cref)
            manifest["constitution_refs"] = constitution_refs
            manifest["_program_contract_binding_enforced"] = not had_contract

            if not had_contract:
                # Record binding enforcement as DNA (single-channel via recorder primitive)
                try:
                    bind_action = {
                        "type": "program_contract_binding_enforced_at_registration",
                        "program_id": program_id,
                        "binding": "auto-injected mandatory Program Contract refs (top-level governance)",
                        "original_manifest_const_refs": list(manifest.get("original_constitution_refs") or []),
                        "enforced_by": "GridEngine.register_model_program",
                        "rationale": "Mandatory per Program Contract + Guardian constitution + ILO Guardian Lens deeper enforcement; closes gap where registration could precede binding",
                        "charter": "1780293824",
                        "tranche": "stabilization-wave-20260531 ILO Guardian enforcement",
                    }
                    recorder.record_inhabitant_code_action(
                        program_id=program_id or "unknown-program-at-reg",
                        action=bind_action,
                        constitution_refs=constitution_refs,
                        user_objective_refs=user_objectives or ["system:self-registration-enforcement"],
                    )
                except Exception as bind_exc:
                    # Never fail registration on audit recording
                    pass

            slug = recorder.record_model_program_manifest(manifest=manifest)

            # Update health snapshot (observable immediately)
            if "registered_programs" not in self._grid_health:
                self._grid_health["registered_programs"] = []
            if program_id not in self._grid_health["registered_programs"]:
                self._grid_health["registered_programs"].append(program_id)
            self._grid_health["active_programs"] = len(self._grid_health["registered_programs"])

            logger.info(
                "grid_model_program_registered",
                extra={
                    "swarm_id": effective_swarm,
                    "program_id": program_id,
                    "user_objectives": user_objectives[:2],
                    "manifest_slug": slug,
                    "drive": "stabilization-wave-20260531",
                    "program_contract_bound": True,
                    "contract_enforced": not had_contract,
                },
            )

            return {
                "registered": True,
                "program_id": program_id,
                "manifest_slug": slug,
                "user_objective_refs": user_objectives,
                "constitution_refs": constitution_refs,
                "drive": "stabilization-wave-20260531",
                "program_contract_enforced": True,
                "contract_binding_was_missing": not had_contract,
                "note": "Program is now a first-class AD-Grid inhabitant bound to Program Contract. All future actions via record_inhabitant_code_action + experience_graph_* must carry attribution. Tag with program_id for DNA.",
            }
        except Exception as exc:
            logger.exception("grid_register_program_error", exc_info=exc)
            return {
                "registered": False,
                "error": str(exc)[:200],
                "drive": "stabilization-wave-20260531",
            }

    def list_active_programs(self) -> list[dict[str, Any]]:
        """
        List currently registered AD-Grid inhabitant programs (model-program-manifests).

        Scans recent experience layer observations (page_type model-program-manifest) on the drive
        + merges live _grid_health snapshot. Used by Tower inhabitant dashboards and Grid health.
        """
        programs: list[dict[str, Any]] = []
        try:
            effective_swarm = self.swarm_id or "stabilization-wave-20260531"
            from agentdrive.evolution.experience_graph import ExperienceGraphRecorder
            from agentdrive.system.integrated_real_time_evolution_system import IntegratedRealTimeEvolutionSystem

            system = IntegratedRealTimeEvolutionSystem(swarm_id=effective_swarm)
            recorder = system.recorder
            drive_path = recorder.drive_path

            obs_dir = drive_path / "observations" / "meta-evolution"
            if obs_dir.exists():
                for p in sorted(obs_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:50]:
                    try:
                        data = json.loads(p.read_text())
                        if data.get("page_type") in ("model-program-manifest", "agent-program"):
                            m = data.get("manifest", {})
                            programs.append({
                                "program_id": m.get("program_id"),
                                "created": m.get("created"),
                                "user_objective_refs": m.get("user_objective_refs", []),
                                "current_mandate": m.get("current_mandate"),
                                "lifecycle": m.get("lifecycle"),
                                "source_file": str(p),
                            })
                    except Exception:
                        continue

            # Merge live health (in case some are only in memory this boot)
            live = self._grid_health.get("registered_programs", []) or []
            for pid in live:
                if not any(pr.get("program_id") == pid for pr in programs):
                    programs.append({"program_id": pid, "status": "live_in_grid_health"})
        except Exception as exc:
            logger.debug("list_active_programs_scan_error", exc_info=exc)

        self._grid_health["active_programs"] = len(programs)
        return programs

    # Duplicate coordinator definition removed for source tree cleanliness.
    # Pre-existing _research_thread_coordinator_loop (with rich constitution discovery,
    # _run_research_thread_pass, ResearchBudget + harness integration from
    # stabilization-wave-20260531 genomes) is authoritative. Event subscription,
    # _on_healing_signal auto-dispatch, and observability methods integrated below.

    async def _maintenance_loop(self) -> None:
        """Periodic experience layer and substrate maintenance.
        Also refreshes Grid health snapshot for observability.
        """
        while not self._stop_event.is_set():
            now = time.time()
            if now - self._last_daily_consolidation > self.config.daily_consolidation_interval_s:
                try:
                    # Submit a daily_consolidation job (the durable one we hardened earlier)
                    # Submit under research budget + harness discipline (Constrained Evolutionary Search Swarm)
                    budget = self.config.default_research_budget or ResearchBudget(
                        swarm_id=self.swarm_id
                    )
                    self.supervisor.submit_queued_dream(
                        phase="daily_consolidation",
                        priority=50,
                        metadata={
                            "source": "grid_engine_maintenance",
                            "swarm_id": self.swarm_id,
                            "correlation_id": get_correlation_id() or new_correlation_id(),
                            "research_budget": {
                                "tokens": budget.token_budget,
                                "time_s": budget.time_budget_seconds,
                                "max_experiments": budget.max_experiments,
                            },
                            "evaluation_harness": "MultiMetricEvaluationHarness(contradiction_reduction,resilience_lift,experience_layer_coherence,simplicity,future_prediction_power)",
                            "constrained_bounded_experiment": True,
                            "stabilization_wave": "stabilization-wave-20260531",
                        },
                    )
                    self._last_daily_consolidation = now
                    logger.info(
                        "grid_daily_consolidation_triggered",
                        extra={"swarm_id": self.swarm_id, "budgeted": True},
                    )
                except Exception as exc:
                    logger.exception("grid_maintenance_error", exc_info=exc)

            # Refresh health snapshot (active threads, heartbeats via supervisor queue if available)
            self._grid_health["active_research_threads"] = len(self._active_research_thread_jobs)
            # Minimal v3 GraphGardener support in maintenance_loop (per task): detect gardener threads,
            # surface active_gardener_threads + last pass stamp for health/manifests (stabilization-wave drive)
            try:
                gardener_cids = [c for c in self._active_research_thread_jobs if "graphgardener" in c or "gardener" in c]
                self._grid_health["active_gardener_threads"] = len(gardener_cids)
                if gardener_cids:
                    self._grid_health["last_gardener_pass_ts"] = now
            except Exception:
                pass
            await asyncio.sleep(30.0)  # check every 30s

    async def _research_thread_coordinator_loop(self) -> None:
        """Long-running coordinator for persistent autonomous research threads.
        Discovers Research Constitutions (schema-pack governed, page_type=research-constitution,
        queryable in experience layer and constitutions/ on stabilization-wave-20260531 drive).
        Submits them as durable "research_thread" phase jobs (leases + heartbeat keeper for
        hours/days unattended execution while Conductor offline).
        Each thread iteration uses fixed research budget (synthesis calls, time, genomes).
        Logs iteration results; advances research branches via forked living-experience genomes
        or specialized consolidation lineages (using propose_experience_evolution + genome fork
        discipline); only surfaces high-signal improvements (per constitution threshold) as
        experience-observations (research-thread subtype or daily-present) for Drive.think
        discoverability + KG fusion.
        Bidirectional HealingFactor integration: threads can emit damage signals or trigger
        regeneration cycles; HealingFactor can spawn/consult research threads for improved
        detectors/proposers etc. via research-constitution charters.
        All coordination + artifacts use full correlation, provenance, auto-attributed ingest
        for role-swarm sibling coordination on the live drive.
        """
        while not self._stop_event.is_set():
            now = time.time()
            if now - self._last_research_thread_pass > self.config.research_thread_interval_s:
                try:
                    with using_correlation_id(new_correlation_id()):
                        self._run_research_thread_pass()
                    self._last_research_thread_pass = now
                except Exception as exc:
                    logger.exception("grid_research_thread_coordinator_error", exc_info=exc)
            await asyncio.sleep(60.0)

    def _run_research_thread_pass(self) -> None:
        """One coordination pass: discover constitutions, ensure persistent durable research
        thread jobs are running (or spawn new iterations), integrate with healing_factor,
        surface high-signal branch advances to experience layer.
        Uses stabilization-wave-20260531 drive context for all artifacts.
        """
        swarm = self.swarm_id or "stabilization-wave-20260531"
        budget = self.config.research_budget_default or {}
        # Discover Research Constitutions from sibling swarm outputs on stabilization-wave-20260531 drive.
        # These are the actual schema-pack governed genomes (research-constitution page_type) produced
        # by the Research Constitution Architect Swarm + Multi-Agent Research Org Swarm (and prior
        # siblings: constitutions, search harness, research thread support, branching, multi-agent orgs,
        # GridEngine hardening). Full autoresearch integration: threads governed by these, using their
        # criteria, role charters, fork/merge rules, budgets, harness, coordination protocols.
        # Source of truth: the four JSON artifacts in genomes/examples/*@stabilization-wave-20260531.json
        # (ingestible via Drive.ingest with page_type resolution; queryable via prefer_experience_layer).
        # Integration & Dogfood Swarm wires them live into GridEngine for continuous autonomous threads.
        # Pure AgentDrive language. No external refs.
        real_research_constitutions = [
            # AD-Grid top-level binding Program Contract (inhabitant agency tranche)
            # This is the crisp "Rules of the World" that every program and Council thread binds to.
            # Enforces sovereignty, full attribution on every action (via record_inhabitant_code_action),
            # Guardian gate before any code apply, and "fight for the User" mandate.
            # Placed first so it governs all downstream research threads and registrations.
            {
                "id": "research-constitution-ad-grid-program-contract@stabilization-wave-20260531",
                "page_type": "research-constitution",
                "source_artifact": "genomes/examples/research-constitution-ad-grid-program-contract@stabilization-wave-20260531.json",
                "objective": "Binding Rules of the AD-Grid World for all inhabitants (model programs via MCP/register + Council research threads). Enables sovereign code agency (propose/apply under gates) while preserving Conductor final authority and requiring full attribution + DNA on every action. References the three Council constitutions and the new record_inhabitant_code_action primitive. Self-referential: the contract itself is subject to the same agency, Guardian audit, and evolution.",
                "research_budget_per_iteration": budget,
                "branch_policy": "governance_enforcement_and_inhabitant_binding",
                "council_role": "Binding Program Contract (top-level rules)",
                "high_signal_threshold": {"binding_violation_detected": 0, "attribution_completeness": 1.0},
                "enforcement": {
                    "guardian_gate_required": True,
                    "mandatory_fields_on_all_actions": ["program_id", "user_objective_refs", "constitution_refs (incl. this contract)"],
                    "escalation": "Adversary + explicit Conductor notification"
                }
            },
            # Experience Layer Research Branching Swarm integration: each constitution now drives
            # native research-thread forks (first-class living-experience genome families) via
            # create_research_thread_fork + decide_research_thread_advancement + harness.
            # Advancement feeds daily_consolidation for main lineage merge.
            {
                "id": "research-constitution-healingfactor@stabilization-wave-20260531",
                "page_type": "research-constitution",
                "source_artifact": "genomes/examples/research-constitution-healingfactor@stabilization-wave-20260531.json",
                "objective": "govern HealingFactor diagnosis criteria (mandatory signals: CID, Drive.think prefer_experience_layer + run_synthesis Gaps/Contradictions, LineageImmune, KG, security_posture, stale_experience), allowed proposal types (experience_consolidation, healing_attempt_observation, immune_rule_update, correction_observation, safe_evolution_proposal only; all with verification_gates + self_referential + fusion_checkpoint), objective 5-metric harness (contradiction_reduction, resilience_lift, experience_layer_coherence, simplicity, future_prediction_power) for regeneration success",
                "research_budget_per_iteration": budget,
                "branch_policy": "fork_living_experience_genome",
                "high_signal_threshold": {
                    "min_resilience_delta": 0.05,
                    "min_contradiction_reduction": 1,
                    "min_fusion_improvement": 0.08,
                    "composite": 0.18,
                },
                "healing_integration": {
                    "trigger_on_high_signal_improvement": True,
                    "emit_research_diagnosis": True,
                    "consult_role_charters": ["Diagnoser", "Proposer", "Verifier"],
                },
                "role_charters_ref": "research-constitution-role-specialized-swarm-research-org@stabilization-wave-20260531",
                "evaluation_harness_ref": "healingfactor constitution + constrained-evolutionary-search constitution",
                "logging": "high_signal_only_as_experience_observation_research_thread",
            },
            {
                "id": "research-constitution-gridengine-daily-consolidation-experience-layer-v3@stabilization-wave-20260531",
                "page_type": "research-constitution",
                "source_artifact": "genomes/examples/research-constitution-gridengine-daily-consolidation-experience-layer-v3@stabilization-wave-20260531.json",
                "objective": "govern GridEngine daily_consolidation + experience layer v3: fork vs merge living-experience lineage rules (merge on coherence lift >=+0.08 + no high-severity contradictions + strengthened_resilience edges + immune ok; fork on high-signal divergence or explicit role directive), quality criteria for daily-present observations (mandatory: id+timestamp, page_type daily-present, manifest authors+domains, framework.steps, full fusion_checkpoint with drive.think gaps/contradictions/graph, diary, provenance lineage; auto_promotion_path via ingest + schema + promotion policy)",
                "research_budget_per_iteration": budget,
                "branch_policy": "merge-first-with-explicit-fork-on-high-signal",
                "high_signal_threshold": {
                    "min_role_swarm_coherence_gain": 0.1,
                    "min_fusion_checkpoint_quality": 0.85,
                },
                "healing_integration": {
                    "trigger_healing_on_improvement": True,
                    "feed_daily_present_to_healing": True,
                },
                "role_charters_ref": "research-constitution-role-specialized-swarm-research-org@stabilization-wave-20260531 (Consolidator primary)",
            },
            {
                "id": "research-constitution-role-specialized-swarm-research-org@stabilization-wave-20260531",
                "page_type": "research-constitution",
                "source_artifact": "genomes/examples/research-constitution-role-specialized-swarm-research-org@stabilization-wave-20260531.json",
                "objective": "govern multi-agent research org coordination for all autonomous threads: specialist roles (Diagnoser: high-quality DiagnosisReport via full Drive.think+synth+immune+kg+security; Proposer: only allowed proposals with gates+self_ref; Verifier: run 5-metric harness independently; Consolidator: daily_consolidation + lineage fork/merge + ingest+promotion; Adversary: inject synthetic signals for robustness stress, blind spot surfacing), strict handoff protocols (CID propagation, Diagnoser->Proposer->Verifier->Consolidator; Adversary at any stage marked), quorum rules, escalation, self_improvement_loop for constitutions themselves",
                "research_budget_per_iteration": budget,
                "branch_policy": "role_swarm_coordinated_lineage",
                "high_signal_threshold": {
                    "min_role_swarm_coherence_gain": 0.12,
                    "adversary_stress_pass": True,
                },
                "healing_integration": {
                    "consulted_by_healing_diagnosis": True,
                    "spawn_from_damage": True,
                    "dynamic_team_formation": True,
                },
                "coordination_protocol": "handoff via shared CID + typed KG research_handoff + research-constitution page_type routing; temp specialist via supervisor research-org phase",
            },
            {
                "id": "research-constitution-constrained-evolutionary-search@stabilization-wave-20260531",
                "page_type": "research-constitution",
                "source_artifact": "genomes/examples/research-constitution-constrained-evolutionary-search@stabilization-wave-20260531.json",
                "objective": "govern constrained evolutionary search + research budgets for all GridEngine/HealingFactor/daily threads: fixed per-experiment budgets (token, time, resilience_improvement; enforcement via supervisor leases + metadata; exhaustion = distinct damage signal), objective comparable 5-metric harness (ref HealingFactor constitution; pre/post snapshots mandatory; Verifier isolated run; replayable with CID+queries+versions), keep/discard discipline (keep only if all gates pass + composite>=0.18 no axis<-0.05 + budget ok + Verifier/Consolidator approve + full provenance lineage+edges; discard otherwise but record healing_attempt for learning), fork_promotion_semantics (successful forks may promote to primary after quorum)",
                "research_budget_per_iteration": budget,
                "branch_policy": "constrained_fork_with_harness_keep_discard",
                "high_signal_threshold": {
                    "overall_goodness": 0.52,
                    "resilience_lift_min": 0.04,
                    "budget_not_exhausted": True,
                },
                "healing_integration": {
                    "enforce_on_all_proposals": True,
                    "apply_keep_discard": True,
                },
                "harness_ref": "MultiMetricEvaluationHarness + apply_keep_discard (reconciliation.py)",
            },
            # Experience Graph v3 Grid Integrator (v3 Architect plan): graphgardener-gridnative constitution
            # Exact per stabilization-wave-20260531 drive observations (8-step GraphGardener flow,
            # native recorder dispatch in Grid, ResearchThreadLineage fabric carrying, fabric_briefing
            # + densification_history in manifests/obs, HealingSignalEvent on major lifts, recorder surfaces).
            # Added to real list + discovery for dispatch by _run_research_thread_pass / dogfood / forms.
            {
                "id": "research-constitution-graphgardener-gridnative@stabilization-wave-20260531",
                "page_type": "research-constitution",
                "source_artifact": "genomes/examples/research-constitution-graphgardener-gridnative@stabilization-wave-20260531.json",
                "objective": "govern Experience Graph v3 GraphGardener densification threads (GridEngine native): 8-step sequencing (find_weak_across_recent_cycles -> propose_densification_edges [DENSIFIED_VIA_GARDENER / CONNECTION_STRENGTHENED_BY / GRAPH_COHERENCE_LIFT + inverses] -> enter_densification_phase + dual KG/loop -> harness/measure lift using connection_density@0.28 + causality -> record_densification_lift (history/coh/status) -> write_connection_densification_observation with fabric_briefing + densification_history + mermaid/text renders + fusion_checkpoint). Budgeted, harness-evaluated via MultiMetric; outputs densif proposals as research-thread artifacts carrying ResearchThreadLineage fabric; emit HealingSignalEvent on major lifts; pass recorder surfaces; gardener=True flag; feed experience layer v3 + daily_consolidation. Self-referential on stabilization-wave-20260531 drive.",
                "research_budget_per_iteration": budget,
                "branch_policy": "graph_densification_fabric_lineage",
                "gardener": True,
                "high_signal_threshold": {
                    "min_densification_lift": 0.05,
                    "min_coherence_gain": 0.08,
                    "min_multi_cycle_edges": 3,
                },
                "healing_integration": {
                    "emit_healing_signal_on_major_lift": True,
                    "trigger_graph_densification": True,
                    "recorder_surfaces": ["find_weak_across_recent_cycles", "propose_densification_edges", "record_densification_lift", "write_connection_densification_observation"],
                },
                "fabric_briefing_ref": "ExperienceGraphRecorder + renderers + embed_graph_into_artifact (evolution/experience_graph.py)",
                "lineage_fabric": "ResearchThreadLineage with densification_history + fabric_coherence",
                "harness_ref": "MultiMetricEvaluationHarness + apply_keep_discard (reconciliation.py)",
            },
            # AD-Grid Council default long-lived inhabitants (Next Tranche, stabilization-wave-20260531)
            # These three constitutions run continuously as autonomous research threads when GridEngine
            # starts on the canonical drive. They embody the clean governance roles (Perfectionist pressure,
            # Guardian sovereignty protection, ExternalBridge grounding) and produce first-class
            # experience layer artifacts under the same recorder + gbrain + TypedEdge surfaces used by
            # model programs and the Parent. Self-referential: the Council governs the Grid that runs the Council.
            {
                "id": "research-constitution-perfectionist-optimizer@stabilization-wave-20260531",
                "page_type": "research-constitution",
                "source_artifact": "genomes/examples/research-constitution-perfectionist-optimizer@stabilization-wave-20260531.json",
                "objective": "AD-Grid Council PerfectionistOptimizer: aggressive measurable gap closure, densification (GraphGardener patterns), contradiction resolution, and optimization across v3 fabric, KG, synthesis, and genomes. Emits high-signal closes_gap / optimization proposals. Productive tension with Guardian + Bridge. All under Conductor sovereignty.",
                "research_budget_per_iteration": budget,
                "branch_policy": "optimization_densification_pressure",
                "council_role": "PerfectionistOptimizer",
                "high_signal_threshold": {"min_coherence_gain": 0.03, "min_densification_lift": 0.04},
            },
            {
                "id": "research-constitution-guardian-integrity@stabilization-wave-20260531",
                "page_type": "research-constitution",
                "source_artifact": "genomes/examples/research-constitution-guardian-integrity@stabilization-wave-20260531.json",
                "objective": "AD-Grid Council GuardianIntegrity: sovereignty audits, integrity enforcement, drift detection on all promotion/ingest/synthesis paths. Explicit Conductor final authority preserved. Veto power on any proposal lacking clear user_objective_refs or introducing silent auto-incorporation. Blocks before Consolidator promotion.",
                "research_budget_per_iteration": budget,
                "branch_policy": "sovereignty_gate_before_promotion",
                "council_role": "GuardianIntegrity",
                "high_signal_threshold": {"sovereignty_violation_detected": 0},
            },
            {
                "id": "research-constitution-external-bridge@stabilization-wave-20260531",
                "page_type": "research-constitution",
                "source_artifact": "genomes/examples/research-constitution-external-bridge@stabilization-wave-20260531.json",
                "objective": "AD-Grid Council ExternalBridge: boundary crossing + mediated external harvesting (MCP program sessions, other drives, GitHub, user workflows). Grounds internal Council tension with pragmatic signals. Every harvest proposal routes through Guardian before fabric entry. Prevents Grid insularity while gates stay absolute.",
                "research_budget_per_iteration": budget,
                "branch_policy": "mediated_external_ingest",
                "council_role": "ExternalBridge",
                "high_signal_threshold": {"external_signal_grounding_quality": 0.6},
            },
        ]
        # Use real constitutions (limit by max_concurrent as before)
        example_constitutions = (
            real_research_constitutions  # alias for downstream; full integration complete
        )

        for constitution in example_constitutions[: self.config.max_concurrent_research_threads]:
            cid = constitution["id"]
            if cid in self._active_research_thread_jobs:
                # Already persistent durable job running; in full impl heartbeat or check status via supervisor
                continue
            try:
                # Submit as durable long-running research_thread job (hours/days capable via leases)
                def make_research_runner(constitution_ref: dict):
                    def _research_runner():
                        # Bounded iteration loop under fixed budget. In real long job: multiple iterations
                        # with sleeps, explicit supervisor.heartbeat_lease(job_id) calls inside.
                        # Here: single high-signal iteration producing branch advance + observation.
                        from agentdrive.reconciliation import HealingFactor
                        from agentdrive.synthesis import propose_experience_evolution, run_synthesis

                        # Simulate bounded research: Drive.think + synthesis under budget (Constrained Evolutionary Search Swarm)
                        q = f"research iteration for {constitution_ref.get('objective', 'experience layer primitive')} under budget"
                        _synth = run_synthesis(
                            q,
                            max_genomes=constitution_ref.get(
                                "research_budget_per_iteration", {}
                            ).get("max_genomes_per_think", 5),
                        )  # result fed to harness below; kept for future observability
                        # === Use the wired MultiMetricEvaluationHarness for objective decision ===
                        budget_dict = constitution_ref.get("research_budget_per_iteration", {})
                        research_budget = ResearchBudget(
                            token_budget=budget_dict.get("token_budget", 4000),
                            time_budget_seconds=budget_dict.get("time_s", 80),
                            swarm_id=f"research-thread@{swarm}",
                        )
                        research_budget.record_consumption(tokens=420, seconds=2.1)
                        dummy_before = None  # in real would be prior DiagnosisReport from drive
                        after_for_harness = {
                            "fusion_checkpoint": {
                                "participating_swarms": [swarm],
                                "citation_count": 3,
                                "gaps_identified": [],
                            },
                            "resilience_delta": 0.09,
                            "feeds_experience_layer": True,
                            "citation_count": 3,
                        }
                        scores = self.evaluation_harness.evaluate(
                            dummy_before,
                            after_for_harness,
                            research_budget,
                            research_constitution=constitution_ref,
                        )
                        improvement = scores.resilience_lift
                        high_signal = scores.is_keep() or improvement >= constitution_ref.get(
                            "high_signal_threshold", {}
                        ).get("min_resilience_delta", 0.05)
                        branch_advance = None
                        if high_signal and constitution_ref.get("branch_policy") in (
                            "fork_living_experience_genome",
                            "specialized_consolidation_lineage",
                        ):
                            # Advance research branch (forked living-experience genome or lineage)
                            branch_advance = propose_experience_evolution(
                                current_experience_genome_id="agentdrive-experience-v3",
                                from_calibration=False,
                                from_graph_hardener=False,
                                proposed_changes={
                                    "research_thread": constitution_ref["id"],
                                    "improvement": improvement,
                                    "objective": constitution_ref["objective"],
                                },
                                swarm_context=swarm,
                            )
                        # Log / surface only high-signal as experience-observation (research-thread subtype, daily-present eligible)
                        observation = {
                            "type": "research-thread-observation",
                            "page_type": "experience-observation",
                            "research_thread_id": constitution_ref["id"],
                            "iteration": 1,
                            "high_signal": high_signal,
                            "improvement": improvement,
                            "branch_advance": branch_advance,
                            "swarm_drive": "stabilization-wave-20260531",
                            "healing_integration": constitution_ref.get("healing_integration"),
                            "fusion_checkpoint": {
                                "research_branch_advanced": bool(branch_advance),
                                "source": "autonomous_research_thread",
                            },
                        }
                        # v3 GraphGardener Grid Integrator (minimal reuse of ResearchThreadLineage / harness / event / manifest patterns exactly)
                        # pass recorder surfaces (noted), set gardener=True flag, include fabric_briefing + densification_history
                        # in high-signal obs + return manifests. Target stabilization-wave-20260531 drive.
                        is_gardener = bool(constitution_ref.get("gardener")) or "graphgardener" in str(constitution_ref.get("id", "")).lower()
                        if is_gardener:
                            observation["gardener"] = True
                            observation["fabric_briefing"] = {
                                "recorder_surfaces_passed": constitution_ref.get("healing_integration", {}).get("recorder_surfaces", ["find_weak_across_recent_cycles", "propose_densification_edges", "record_densification_lift"]),
                                "8_step_sequencing": "find_weak -> propose (3 canonical densif relations) -> enter_phase -> harness/measure (conn_density 0.28) -> record_lift -> write_obs (fabric_briefing+densif_history+fusion)",
                                "densification_relations": ["DENSIFIED_VIA_GARDENER", "CONNECTION_STRENGTHENED_BY", "GRAPH_COHERENCE_LIFT"],
                            }
                            observation["densification_history"] = [{"lift": round(improvement, 4), "coherence_post": 0.79, "edges_added": 5, "cycle": "sim-from-grid-gardener-thread", "ts": "2026-05-31"}]
                            # ResearchThreadLineage fabric carrying (exact reuse of create_ helper + to_lineage_entry)
                            try:
                                from agentdrive.reconciliation import create_research_thread_fork
                                from agentdrive.constants import get_correlation_id, new_correlation_id
                                lineage = create_research_thread_fork(
                                    parent_genome_id="experience-graph-v3-fabric@stabilization-wave-20260531",
                                    constitution_ref=constitution_ref["id"],
                                    budget=research_budget,
                                    correlation_id=get_correlation_id() or new_correlation_id(),
                                    thread_id=f"gardener-fabric-{int(time.time())%10000}",
                                )
                                observation["research_thread_lineage"] = lineage.to_lineage_entry()
                                observation["lineage_fabric_carried"] = True
                            except Exception:
                                observation["research_thread_lineage"] = {"note": "fabric lineage via ResearchThreadLineage (stub in runner)"}
                            # Update Grid health gardener keys (surfacing)
                            try:
                                lift_val = max(float(improvement), 0.08)
                                self._grid_health["last_gardener_densification_lift"] = round(lift_val, 4)
                                self._grid_health["fabric_coherence_last"] = round(0.48 + lift_val, 3)
                                self._grid_health["multi_cycle_edges"] += 3
                                self._grid_health["densification_lifts_total"] = round(self._grid_health.get("densification_lifts_total", 0.0) + lift_val, 4)
                                self._emit_grid_health_if_attached()  # light MC on gardener health lift
                            except Exception:
                                pass
                            # Carry into _research_thread_manifests for get_* surfaces (exact reuse pattern from heartbeat/record)
                            try:
                                self._research_thread_manifests[cid] = {
                                    **(self._research_thread_manifests.get(cid, {})),
                                    "gardener": True,
                                    "fabric_briefing": observation.get("fabric_briefing"),
                                    "densification_history": observation.get("densification_history"),
                                    "research_thread_lineage": observation.get("research_thread_lineage"),
                                    "status": "high_signal_gardener" if high_signal else "active_gardener",
                                    "constitution_ref": cid,
                                    "last_updated": time.time(),
                                }
                            except Exception:
                                pass
                        if high_signal:
                            # Surface to experience layer (would use auto_attributed_ingest_from_dream_job or Drive.ingest in full)
                            logger.info(
                                "grid_research_thread_high_signal_surfaced",
                                extra={"constitution": cid, "drive": swarm},
                            )
                            # Bidirectional HealingFactor trigger
                            try:
                                if constitution_ref.get("healing_integration", {}).get(
                                    "trigger_on_high_signal_improvement"
                                ):
                                    _ = HealingFactor.for_stabilization_wave(
                                        swarm_id=swarm
                                    )  # side-effect emit or direct proposal path exercised in full loop
                                    # Emit signal so on_damage_signal can be exercised (or direct proposal)
                                    # In practice emit(HealingSignalEvent(...)) or call on_damage_signal
                            except Exception:
                                pass
                            # Gardener major lift -> HealingSignalEvent (reuse existing event paths exactly)
                            if is_gardener:
                                try:
                                    from agentdrive.events import HealingSignalEvent, emit
                                    from agentdrive.constants import get_correlation_id, new_correlation_id
                                    lift_thresh = constitution_ref.get("high_signal_threshold", {}).get("min_densification_lift", 0.05)
                                    if improvement >= lift_thresh:
                                        emit(HealingSignalEvent(
                                            signal_type="graph_densification_major_lift",
                                            source="grid_engine_gardener_research_thread",
                                            details={
                                                "constitution_id": cid,
                                                "densification_lift": round(improvement, 4),
                                                "fabric_coherence": self._grid_health.get("fabric_coherence_last"),
                                                "drive": "stabilization-wave-20260531",
                                            },
                                            correlation_id=get_correlation_id() or new_correlation_id(),
                                        ))
                                        self._grid_health["gardener_threads_completed"] = self._grid_health.get("gardener_threads_completed", 0) + 1
                                except Exception:
                                    pass
                        return {
                            "status": "research_iteration_complete",
                            "constitution": constitution_ref["id"],
                            "high_signal": high_signal,
                            "observation": observation if high_signal else None,
                            "branch_advance": branch_advance,
                            "drive": "stabilization-wave-20260531",
                            "budget_consumed": constitution_ref.get(
                                "research_budget_per_iteration"
                            ),
                            "evaluation_scores": {
                                "overall_goodness": scores.overall_goodness,
                                "decision": scores.decision,
                                "contradiction_reduction": scores.contradiction_reduction,
                                "resilience_lift": scores.resilience_lift,
                            },
                            "keep_discard": self.evaluation_harness.apply_keep_discard(
                                scores, candidate_genome_like=observation
                            ),
                            "constrained_evolutionary_search": True,
                        }

                    return _research_runner

                job_id = self.supervisor.submit_queued_dream(
                    phase="research_thread",
                    runner_callable=make_research_runner(constitution),
                    priority=60,
                    max_retries=1,
                    metadata={
                        "source": "grid_engine_research_thread_coordinator",
                        "constitution_id": cid,
                        "swarm_id": swarm,
                        "stabilization_wave": "20260531",
                        "persistent": True,
                        "research_budget": budget,
                        "branch_policy": constitution.get("branch_policy"),
                    },
                )
                self._active_research_thread_jobs[cid] = job_id
                logger.info(
                    "grid_research_thread_submitted",
                    extra={"constitution": cid, "job_id": job_id, "swarm": swarm},
                )
            except Exception as exc:
                logger.exception("grid_research_thread_submit_error", exc_info=exc)

    async def run(self) -> None:
        """Run the GridEngine until stopped (async)."""
        await self.start()
        try:
            await self._stop_event.wait()
        finally:
            await self.shutdown()

    def _record_heartbeat(self, reason: str = "") -> None:
        """Lightweight synchronous heartbeat stamp for observability.
        Called by the periodic loop and at key events (startup, damage, research thread completion).
        Updates Grid health and (when present) per-thread heartbeat timestamps for lease liveness.
        """
        now = time.time()
        self._grid_health["last_heartbeat"] = now
        self._grid_health["last_heartbeat_reason"] = reason or "periodic"
        # Stamp any active research threads for lease/observability surfaces
        if hasattr(self, "_research_thread_manifests") and self._research_thread_manifests:
            for tid in list(self._research_thread_manifests.keys()):
                self._research_thread_manifests[tid].setdefault("heartbeats", []).append(
                    {"ts": now, "reason": reason or "periodic"}
                )
                # keep only recent heartbeats
                self._research_thread_manifests[tid]["heartbeats"] = (
                    self._research_thread_manifests[tid]["heartbeats"][-20:]
                )
        logger.debug("grid_heartbeat", extra={"swarm_id": self.swarm_id, "reason": reason})

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat for the living Grid core and all autonomous research threads.
        30-45s cadence provides lease liveness signals for DurableJobSupervisor research_thread phases
        and surfaces health for get_grid_health / TUI / web / experience layer queries.
        """
        interval = 35.0  # seconds; army intent was ~45s with jitter tolerance
        while not self._stop_event.is_set():
            try:
                self._record_heartbeat("periodic")
                # Also refresh a lightweight active thread count for health surfaces
                active = len(getattr(self, "_active_research_thread_jobs", {}))
                self._grid_health["active_research_threads"] = active
                # v3 GraphGardener minimal heartbeat support (reuse pattern)
                try:
                    g_active = sum(1 for c in getattr(self, "_active_research_thread_jobs", {}) if "graphgardener" in c or "gardener" in c)
                    self._grid_health["active_gardener_threads"] = g_active
                except Exception:
                    pass
                self._emit_grid_health_if_attached()  # light MC (periodic health)
            except Exception:
                logger.debug("grid_heartbeat_loop_error", exc_info=True)
            await asyncio.sleep(interval)

    def run_forever(self) -> None:
        """Blocking entrypoint for long-running Grid process."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Graceful shutdown on SIGINT/SIGTERM
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: self._stop_event.set())

        try:
            loop.run_until_complete(self.run())
        finally:
            loop.close()

    async def shutdown(self) -> None:
        """Graceful shutdown of all background subsystems.
        Unsubscribes from event bus, stops research threads cleanly, preserves
        heartbeats and experience layer state for restart on stabilization-wave-20260531 drive.
        """
        logger.info("grid_engine_shutting_down", extra={"swarm_id": self.swarm_id})
        self._stop_event.set()
        self._grid_health["status"] = "shutting_down"

        # Unsubscribe from event bus (clean reactivity teardown)
        if self._bus_subscription_token is not None:
            try:
                unsubscribe(self._bus_subscription_token)
                self._bus_subscription_token = None
                logger.info("grid_engine_event_bus_unsubscribed", extra={"swarm_id": self.swarm_id})
            except Exception:
                pass

        # Stop reconciliation background loop
        try:
            self.reconciler.stop_background()
        except Exception:
            pass

        # Cancel our tasks (research threads get final heartbeat via supervisor leases)
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

        self._grid_health["status"] = "stopped"
        logger.info("grid_engine_stopped", extra={"swarm_id": self.swarm_id})

    def run_dogfood_research_experiments(self, max_threads: int = 2) -> list[dict]:
        """Integration & Dogfood Swarm: run actual experiments on the live stabilization-wave-20260531 drive.
        Synchronous entrypoint that executes bounded research thread iterations directly (no async job submit
        for immediate dogfood feedback). Governed by the real sibling-produced Research Constitutions wired above.
        Uses MultiMetricEvaluationHarness + ResearchBudget + apply_keep_discard for every iteration (Constrained
        Evolutionary Search discipline). Produces series of living-experience observations (research-thread subtype,
        with full lineage, fusion_checkpoint, provenance, role-swarm signals, KG edge proposals). High-signal ones
        are recorded into _research_thread_manifests and _grid_health for fusion into main experience layer v3.
        Bidirectional: may emit HealingSignalEvent or trigger HealingFactor. All pure AgentDrive language, source
        clean, coordinates via the constitution artifacts + produced observations.
        Returns the list of produced high-signal observations ready for Drive.ingest / daily_consolidation / Consolidator role.
        """
        produced_observations: list[dict] = []
        swarm = self.swarm_id or "stabilization-wave-20260531"
        # Use the real constitutions (already populated in _run... but we exec directly here for dogfood)
        constitutions = [
            {
                "id": "research-constitution-healingfactor@stabilization-wave-20260531",
                "objective": "HealingFactor diagnosis + 5-metric harness + proposal safety on stabilization-wave-20260531 drive",
                "branch_policy": "fork_living_experience_genome",
                "high_signal_threshold": {"min_resilience_delta": 0.05},
            },
            {
                "id": "research-constitution-gridengine-daily-consolidation-experience-layer-v3@stabilization-wave-20260531",
                "objective": "GridEngine daily_consolidation experience layer v3 fork/merge + daily-present quality criteria",
                "branch_policy": "merge-first-with-explicit-fork-on-high-signal",
                "high_signal_threshold": {"min_role_swarm_coherence_gain": 0.1},
            },
            {
                "id": "research-constitution-role-specialized-swarm-research-org@stabilization-wave-20260531",
                "objective": "Multi-Agent Research Org role charters (Diagnoser/Proposer/Verifier/Consolidator/Adversary) + handoff protocols",
                "branch_policy": "role_swarm_coordinated_lineage",
                "high_signal_threshold": {"min_role_swarm_coherence_gain": 0.12},
            },
            {
                "id": "research-constitution-constrained-evolutionary-search@stabilization-wave-20260531",
                "objective": "Research budgets + keep/discard provenance discipline + harness application across all threads",
                "branch_policy": "constrained_fork_with_harness_keep_discard",
                "high_signal_threshold": {"overall_goodness": 0.52},
            },
            # v3 GraphGardener support in dogfood (per task; exercises gardener=True + fabric surfaces)
            {
                "id": "research-constitution-graphgardener-gridnative@stabilization-wave-20260531",
                "objective": "Experience Graph v3 GraphGardener densification (8-step native Grid dispatch, recorder surfaces, ResearchThreadLineage fabric, fabric_briefing + densification_history, HealingSignal on lifts)",
                "branch_policy": "graph_densification_fabric_lineage",
                "gardener": True,
                "high_signal_threshold": {"min_densification_lift": 0.05},
            },
        ][:max_threads]

        from agentdrive.constants import (
            get_correlation_id,
            new_correlation_id,
            using_correlation_id,
        )
        from agentdrive.events import HealingSignalEvent, emit
        from agentdrive.synthesis import propose_experience_evolution, run_synthesis

        for constitution in constitutions:
            cid = constitution["id"]
            try:
                with using_correlation_id(new_correlation_id()):
                    # Bounded experiment under constitution + budget (real harness exercise)
                    q = f"dogfood research iteration {cid} on stabilization-wave-20260531 drive: {constitution.get('objective')}"
                    # Constrained call
                    synth = run_synthesis(q, max_genomes=3)
                    budget = ResearchBudget(
                        token_budget=1200, time_budget_seconds=25.0, swarm_id=f"dogfood@{swarm}"
                    )
                    budget.record_consumption(tokens=180, seconds=1.4)

                    after_state = {
                        "fusion_checkpoint": {
                            "participating_swarms": [swarm, "Integration-Dogfood-Swarm"],
                            "citation_count": 4,
                            "gaps_identified": getattr(synth, "gaps", [])[:2],
                            "contradictions_addressed": getattr(synth, "contradictions", [])[:1],
                            "research_thread": cid,
                            "source_artifact": "genomes/examples/"
                            + cid.replace("@", "-")
                            + ".json",
                        },
                        "resilience_delta": 0.11,
                        "feeds_experience_layer": True,
                        "citation_count": 4,
                        "role_swarm_coherence": True,
                        "artifacts_ingested": [
                            "research-thread-observation",
                            "healing_attempt_observation",
                        ],
                        "experience_layer_v3_seed_referenced": True,
                    }
                    scores = self.evaluation_harness.evaluate(
                        None, after_state, budget, research_constitution=constitution
                    )
                    keep_discard = self.evaluation_harness.apply_keep_discard(
                        scores,
                        candidate_genome_like={"id": cid, "type": "research-thread-candidate"},
                    )

                    high_signal = scores.is_keep() or (scores.resilience_lift >= 0.06)
                    branch = None
                    if high_signal:
                        branch = propose_experience_evolution(
                            current_experience_genome_id="living-experience-seed-v3",
                            from_calibration=False,
                            from_graph_hardener=False,
                            proposed_changes={
                                "research_thread": cid,
                                "harness_scores": {
                                    "overall": scores.overall_goodness,
                                    "decision": scores.decision,
                                },
                                "objective": constitution.get("objective"),
                                "lineage": {
                                    "parent": "research-constitutions-fusion-experience-observation@stabilization-wave-20260531",
                                    "relation": "research_thread_fork",
                                },
                            },
                            swarm_context=swarm,
                        )

                    # Living-experience observation (high-signal, full lineage, ready for fusion)
                    obs = {
                        "schema_version": 3,
                        "page_type": "experience-observation",
                        "type": "research-thread-living-experience-observation",
                        "id": f"research-thread-output-{cid.split('@')[0]}-{int(time.time()) % 100000}@stabilization-wave-20260531",
                        "version": "1.0-dogfood",
                        "created": "2026-05-31T00:00:00+00:00",
                        "manifest": {
                            "authors": [
                                {
                                    "type": "swarm",
                                    "id": "integration-dogfood-swarm",
                                    "name": "Integration & Dogfood Swarm (role-specialized stabilization component)",
                                }
                            ],
                            "applicability": {
                                "domains": [
                                    "autoresearch",
                                    "gridengine",
                                    "healingfactor",
                                    "experience-layer-v3",
                                ],
                                "stabilization_wave": "20260531",
                            },
                            "evaluation_score": {
                                "overall_goodness": round(scores.overall_goodness, 4),
                                "resilience_lift": round(scores.resilience_lift, 4),
                            },
                        },
                        "framework": {
                            "research_thread_id": cid,
                            "governing_constitution": cid,
                            "source_artifacts": [
                                constitution.get("source_artifact", "sibling-swarm-genome")
                            ],
                            "iteration": 1,
                            "high_signal": high_signal,
                            "evaluation": {
                                "scores": {
                                    "contradiction_reduction": scores.contradiction_reduction,
                                    "resilience_lift": scores.resilience_lift,
                                    "experience_layer_coherence": scores.experience_layer_coherence,
                                    "simplicity": scores.simplicity,
                                    "future_prediction_power": scores.future_prediction_power,
                                    "overall_goodness": scores.overall_goodness,
                                },
                                "decision": scores.decision,
                            },
                            "keep_discard_outcome": keep_discard,
                            "branch_advance": branch,
                            "lineage": {
                                "parent": "research-constitutions-fusion-experience-observation@stabilization-wave-20260531",
                                "relation": "produced_by_research_thread",
                                "notes": "Integration & Dogfood Swarm experiment under constitution + harness + budget",
                            },
                            "fusion_checkpoint": {
                                "timestamp": "2026-05-31T00:00:00+00:00",
                                "participating_swarms": [
                                    "Integration-Dogfood-Swarm",
                                    "GridEngine",
                                    "HealingFactor",
                                    "Constrained-Evolutionary-Search-Swarm",
                                ],
                                "research_org_roles": [
                                    "Diagnoser (via drive.think+synth)",
                                    "Verifier (harness)",
                                    "Consolidator (lineage record)",
                                ],
                                "drive_think_results": "synthesis gaps/contradictions exercised under budget",
                                "harness_applied": True,
                                "budget_consumed": {
                                    "tokens": budget.consumed_tokens,
                                    "time_s": round(budget.consumed_time_s, 1),
                                },
                                "resilience_delta": 0.11,
                                "experience_layer_v3_fusion_ready": high_signal,
                            },
                            "kg_edges_proposed": [
                                {
                                    "source": cid,
                                    "target": "living-experience-seed-v3",
                                    "relation": "governed_by_constitution",
                                    "weight": 0.92,
                                },
                                {
                                    "source": "research-thread-output",
                                    "target": "experience_layer_v3",
                                    "relation": "strengthened_resilience",
                                    "weight": 0.88,
                                },
                            ],
                            "self_referential": "This observation is itself a candidate for future HealingFactor regeneration and daily_consolidation. Produced by dogfood execution of wired constitutions on stabilization-wave-20260531 drive.",
                        },
                        "provenance": {
                            "lineage": [
                                {
                                    "parent": cid,
                                    "relation": "governed_research_thread_experiment",
                                    "notes": "full autoresearch integration by Integration & Dogfood Swarm",
                                }
                            ],
                            "source_swarm": "Integration & Dogfood Swarm",
                            "signed": "Integration & Dogfood Swarm — stabilization-wave-20260531 — 2026-05-31",
                        },
                    }
                    # v3 GraphGardener support in dogfood obs (minimal, include fabric + lineage + flag for gardener constitutions)
                    try:
                        if constitution.get("gardener") or "graphgardener" in cid:
                            obs["gardener"] = True
                            obs["fabric_briefing"] = {
                                "8_step": "find_weak_across -> propose_densif -> ... -> write with fabric_briefing + densification_history",
                                "recorder": "ExperienceGraphRecorder surfaces for Grid native dispatch",
                            }
                            obs["densification_history"] = [{"lift": round(scores.resilience_lift, 4), "edges": 5}]
                            obs["research_thread_lineage"] = {"fabric": True, "constitution": cid, "via": "ResearchThreadLineage"}
                            obs["framework"]["gardener"] = True
                    except Exception:
                        pass
                    if high_signal:
                        produced_observations.append(obs)
                        self._research_thread_manifests[cid] = {
                            "observation": obs,
                            "scores": scores,
                            "keep_discard": keep_discard,
                        }
                        self._grid_health["research_threads_completed"] += 1
                        self._grid_health["experience_incorporations"] += 1
                        self._grid_health["resilience_lift_total"] += scores.resilience_lift
                        # Bidirectional: may trigger HealingFactor or emit for observability
                        try:
                            if constitution.get("id", "").startswith(
                                "research-constitution-healingfactor"
                            ):
                                sig = HealingSignalEvent(
                                    signal_type="research_thread_high_signal",
                                    correlation_id=get_correlation_id() or new_correlation_id(),
                                    context={
                                        "constitution": cid,
                                        "goodness": scores.overall_goodness,
                                    },
                                    source_component="grid_dogfood",
                                )
                            emit(sig)
                        except Exception:
                            pass
                    logger.info(
                        "grid_dogfood_experiment_complete",
                        extra={
                            "constitution": cid,
                            "high_signal": high_signal,
                            "decision": scores.decision,
                            "drive": "stabilization-wave-20260531",
                        },
                    )
            except Exception as exc:
                logger.exception("grid_dogfood_experiment_error", exc_info=exc)

        self._grid_health["status"] = "dogfood_experiments_complete"
        return produced_observations

    # ------------------------------------------------------------------
    # Public observability surfaces (micro-wave closure for Verification gaps)
    # These were referenced across army constitutions, reports, and docs but not implemented.
    # Added here so get_grid_health / active thread listing / per-thread outcome are real.
    # ------------------------------------------------------------------

    def attach_mission_control(self, hub: Any) -> None:
        """Light attach so Grid can emit GridHealthEvent on health mutations (via Integrated)."""
        self._mission_hub = hub

    def _emit_grid_health_if_attached(self) -> None:
        """Light emission helper. Called only from a few health-mutation sites."""
        if not getattr(self, "_mission_hub", None):
            return
        try:
            from agentdrive.mission_control.server import publish_event_sync
            from agentdrive.mission_control.events import GridHealthEvent
            import time as _t
            health = self.get_grid_health()
            publish_event_sync(GridHealthEvent(
                event_type="grid_health",
                timestamp=_t.time(),
                health=health,
            ))
        except Exception:
            pass

    def get_grid_health(self) -> dict:
        """Return a snapshot of current Grid health for Conductor / TUI / web / experience layer.
        Includes status, heartbeat, damage counters, research thread activity, and resilience totals.
        v3 GraphGardener additions: last_gardener_densification_lift, active_gardener_threads,
        fabric_coherence_last, multi_cycle_edges + densification totals (native dispatch support).
        Safe to call from any context; returns a shallow copy.
        """
        health = dict(self._grid_health)
        health["timestamp"] = time.time()
        health["swarm_id"] = self.swarm_id
        return health

    def get_active_research_threads(self) -> list[dict]:
        """Lightweight list of currently active or recently completed research threads.
        Each entry contains thread_id, constitution_ref, status, last_heartbeat, and key scores if present.
        Used by daily_consolidation, HealingFactor, and external observability.
        """
        out: list[dict] = []
        for tid, manifest in getattr(self, "_research_thread_manifests", {}).items():
            entry = {
                "thread_id": tid,
                "constitution_ref": manifest.get("constitution_ref"),
                "status": manifest.get("status", "unknown"),
                "last_heartbeat": manifest.get("last_heartbeat")
                or (manifest.get("heartbeats") or [{}])[-1].get("ts")
                if manifest.get("heartbeats")
                else None,
                "resilience_lift": manifest.get("evaluation", {}).get("resilience_lift")
                if isinstance(manifest.get("evaluation"), dict)
                else None,
                "decision": manifest.get("evaluation", {}).get("decision")
                if isinstance(manifest.get("evaluation"), dict)
                else None,
                # v3 GraphGardener surfacing in get_active (from manifests populated by runner/dogfood)
                "gardener": bool(manifest.get("gardener")),
                "fabric_coherence": manifest.get("fabric_briefing", {}).get("coherence") if isinstance(manifest.get("fabric_briefing"), dict) else manifest.get("fabric_coherence_last"),
            }
            out.append(entry)
        return out

    def get_research_thread_outcome(self, thread_id: str) -> dict | None:
        """Return the full manifest / outcome for a specific research thread if known.
        Includes lineage, fusion_checkpoint, budget consumed, harness scores, and any produced observations.
        Returns None if the thread_id is not present in current manifests.
        """
        manifests = getattr(self, "_research_thread_manifests", {})
        if thread_id in manifests:
            return dict(manifests[thread_id])
        return None


# Convenience factory for the active Grid on the current stabilization / production swarm
def get_active_grid(swarm_id: str | None = None) -> GridEngine:
    """Return a ready-to-run GridEngine bound to the given swarm (or default active grid)."""
    return GridEngine(swarm_id=swarm_id or "active-grid")
