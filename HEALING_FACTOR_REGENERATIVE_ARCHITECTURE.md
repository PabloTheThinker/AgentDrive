# Regenerative HealingFactor Architecture — Experience Layer Regeneration Operator

**Role-Specialized Stabilization Swarm Component:** Regenerative HealingFactor Operator (experience layer regeneration via role-swarm immune response)  
**Mission Context:** Production-grade regenerative self-healing substrate for AgentDrive. Operates in parallel with sibling stabilization swarms (first-run seed, durable consolidation, correlation hardening, gap-closure calibration). Independent worktree.  
**Timestamp:** 2026-05-31 (stabilization wave)  
**Report Type:** Clean architecture design artifact. Conductor can directly convert this into experience-observation / daily-present genome for ingest into central Drive + knowledge_graph + experience layer v3. Closes self-improvement via schema-pack governed evolution.

---

## Executive Summary (Pure AgentDrive Language)

The Regenerative HealingFactor Operator elevates existing defensive healing (reconciliation state resilience, first-run bootstrap via experience layer seed, DurableJobSupervisor two-phase leases + jittered backoff, LineageImmune adaptive memory + ThreatLevel.CRITICAL, synthesis explicit Gap objects + contradictions, security posture signals, promotion/quarantine gates) into a full closed-loop regenerative system at the Drive substrate level.

All damage signals are handled autonomously using ONLY AgentDrive primitives:
- Worker/adapter execution failures after retries (via AgentDriveWorkerError + WorkerResult.error paths)
- DurableJobSupervisor job exhaustion (leases + jittered backoff fully consumed → status "failed")
- Reconciliation state corruption or repeated background failures (reconciliation.json read errors + failure_count escalation)
- Synthesis producing high contradiction clusters or persistent gaps blocking experience layer coherence (SynthesisResult.contradictions + Gap.severity + graph connectivity low)
- Security posture degrading ("needs_attention" on perms, grants, trust, immune signals from get_security_posture + LineageImmune incident_log)
- Promotion/ingest rejections or immune CRITICAL threats (QuarantineRejected, LineageImmuneRule + ThreatLevel.CRITICAL, ingest failures)
- First-run / sparse drive "cold start" reasoning failures (as surfaced in live design synthesis attempts; handled via bootstrap parity + experience_layer_fallback + Drive.think with prefer_experience_layer=True)

**Core Loop (implemented exclusively via existing or lightly extended surfaces):**
1. **Detect + capture rich context** — mandatory correlation_id (via using_correlation_id / get_correlation_id), error/trace details or equivalent, affected genomes + KG neighborhood (via knowledge_graph graph signals + SimpleGraph neighbors/traverse), recent experience layer items (living-experience / experience-observation / daily-present page types from Drive + synthesis), LineageImmuneSystem assessment (ThreatLevel + reasons + incident memory).
2. **Diagnose root cause** — Drive.think(prefer_experience_layer=True, experience_layer_fallback=True) + explicit run_synthesis (Gaps + Contradictions + composite scores + fusion_checkpoint) + LineageImmuneSystem + role-swarm consultation (via swarm_coordination.RoleSwarmStatus + Drive queries over guardian integrity artifacts + calibration loops dispatched as durable jobs).
3. **Generate safe "regeneration proposals" as first-class artifacts** — Never raw source patches. Proposals are: correction_observation (experience-observation style), immune_rule_update genome (LineageImmune adaptive memory extension), experience_consolidation_genome (daily-present style with fusion_checkpoint), safe evolution proposal (promotion candidate with schema-pack signals). All governed by schema packs for page_type routing + extractable/expert_routing.
4. **Execute proposals under DurableJobSupervisor** — Strict leases (heartbeat renewal + jittered backoff), new "healing" supervisor phase, verification gates (re-immune assess via LineageImmuneSystem, re-quarantine if needed, scanner runs via scanners/, promotion policy check).
5. **Close the loop** — On success: ingest healing_attempt observation (experience-observation / synthesis-artifact page type) + typed KG edges (healed_by, regenerated_from, damage_cause, strengthened_resilience) emitted via drive.ingest or knowledge_graph. These become high-signal content for future prevention and experience layer v3 fusion. On persistent failure: escalate via events (to TUI/web) + deeper adversarial dream (dreaming/adversary.py).

**Strict Constraints (enforced for open-source cleanliness and safety):**
- Every line of code, comment, docstring, report, proposed genome uses ONLY pure AgentDrive language: experience layer regeneration, role-swarm immune response, durable healing jobs, graph-signal resilience scoring, schema-pack governed evolution, LineageImmune adaptive memory.
- Zero personal names, zero disallowed thematic references of any kind.
- Safety boundaries: Any change that could affect framework behavior MUST go through full genome promotion + immune (LineageImmuneRule) + quarantine + verification. HealingFactor itself MUST be describable as genomes (healing_factor_regeneration_genome family) and improved via the identical loop (self-referential).
- Leverage and extend (do not bypass or duplicate): LineageImmuneSystem + ThreatLevel + incident/hostile memory, Quarantine gate + events, reconciliation corruption resilience + exponential backoff (now jittered via supervisor), experience_layer_fallback, AgentDrive*Error hierarchy, DurableJobSupervisor + two-phase leases, synthesis contradictions engine (and numeric claim detector), adversarial dreaming, schema packs, correlation IDs (propagate through every healing trace).

This directly advances the high-leverage stabilization mandate and makes the substrate self-regenerative beyond prior first-run/reconciliation hardening.

---

## Detailed Architecture (Substrate-Level Design)

### 1. Damage Signal Taxonomy & Capture Points (Detection Layer)

Signals are surfaced as first-class events (extending events.Event) or via direct method calls on the coordinator. Every signal carries:
- correlation_id (mandatory; auto-provisioned via context or new_correlation_id)
- signal_type: str (one of the 7 autonomous categories)
- rich_context: dict containing:
  - error_details / trace (or equivalent from WorkerResult, job metadata, exception)
  - affected_genome_ids: list[str]
  - kg_neighborhood: dict (from knowledge_graph: neighbors, multi-hop via SimpleGraph, edge types like healed_by etc.)
  - recent_experience_layer_items: list (filtered to living-experience / daily-present / experience-observation page types via schema pack resolution + Drive.query or direct filesystem scan under experience/)
  - lineage_immune_assessment: GenomeThreatAssessment or equivalent (ThreatLevel, reasons, confidence, recommended_action, memory_notes from incident_log)
  - resilience_score: float (computed via graph-signal density + contradiction_count inverse + immune confidence + recency)
- source_component: str (e.g. "DurableJobSupervisor", "ReconciliationRunner", "synthesis.engine", "security.get_security_posture", "Quarantine", "Drive.ingest", "bootstrap.first_run_cold_start")

**Capture Hooks (light extensions, no duplication):**
- Workers / adapters: Hook on WorkerResult.error or AgentDriveWorkerError after internal retry exhaustion (in harness paths or rich_agent_adapter execute wrapper). Emit HealingSignalEvent on final failure.
- DurableJobSupervisor: In _run_queued except block (after retries >= max_retries, status="failed"). Capture full QueuedDreamJob metadata (lease history, lineage, backoff), job phase, runner_callable context. New explicit "healing" phase support.
- ReconciliationRunner: On state read corruption (existing "starting fresh" paths) + in background loop failure counting (reconciliation_failure_count escalation). Also on repeated ReconciliationDelta with zero progress + high gaps.
- Synthesis / run_synthesis + BrainEngine: When contradictions_detected high (len > threshold or high-severity cluster) or persistent Gaps (high severity blocking experience layer coherence, e.g. graph_hits low + experience layer items sparse). Use composite score from SynthesisResult (contradiction_count + gap severities + kg_fusion_signals).
- Security: get_security_posture() overall == "needs_attention" (or specific immune/quarantine/grant signals). Periodic or on-demand from cli/doctor + web observability.
- Promotion/Quarantine + ingest: On QuarantineRejected, LineageImmune assessment returning CRITICAL, DriveIngestResult.accepted=False, promotion policy blocks.
- Cold start / sparse: In Drive.__init__ / bootstrap ensure paths (when experience layer seed missing or think returns high gaps on first use) + experience_layer_fallback triggers + sparse Drive.query results.

All capture paths MUST use using_correlation_id to ensure end-to-end trace (see correlation hardening sibling swarm output).

### 2. Diagnosis Engine (Root Cause via Drive Primitives)

HealingFactor.diagnose(signal) performs:
- Establish/restore CID via using_correlation_id(signal.correlation_id or new...).
- kg = load_graph... ; neighborhood = graph signals around affected_genomes (SimpleGraph.traverse + knowledge_graph edges).
- exp_items = Drive query or synthesis over page_type in ("living-experience", "daily-present", "experience-observation") via schema_packs.load_active_pack().resolve_type.
- immune = LineageImmuneSystem(); assessment = immune.assess_genome(...) or query incident_log for related.
- synth_result: SynthesisResult = run_synthesis( diagnosis_question, available_genomes=..., graph=kg, use_kg_fusion=True, ... ) or via drive.think(question, prefer_experience_layer=True, experience_layer_fallback=True).
  - Explicitly surfaces Gaps (with severity/suggested_action), contradictions list, contradiction_count, fusion_metadata, warnings.
- Role-swarm consultation: Query swarm_coordination for active roles; Drive.think over "integrity guardian" or "gap-closure calibration" artifacts in drive (or dispatch lightweight durable job for specialized consultation). Use LineageImmune + graph resilience scoring for integrity.
- Root cause classification + confidence + suggested regeneration strategy (e.g. "immune_rule_update + correction_observation" for CRITICAL threat; "experience_consolidation_genome" for contradiction cluster).

Output: structured DiagnosisReport (dataclass) with CID, root_cause, evidence (gaps/contras/immune/ graph signals), resilience_before, proposed_actions.

### 3. Safe Regeneration Proposal Generation

Proposals are ALWAYS first-class Drive-native artifacts (never raw patches). Generated as dicts ready for:
- Direct Drive.ingest (as Genome or raw observation with page_type).
- Durable healing job payload.
- PromotionService proposal record.

**Proposal Types (schema-pack aware):**
- correction_observation: page_type="experience-observation" or "synthesis-artifact". Contains: diagnosis summary, concrete correction steps (high-level, e.g. "re-ingest improved X with Y edge"), citations to source genomes/gaps, fusion_checkpoint delta, correlation_id. Auto-extractable for KG.
- immune_rule_update genome: type=genome, page_type="genome" or "schema-pack". Framework describes additions to LineageImmuneSystem known_hostile_patterns / known_good_lineages / incident memory rules. Versioned, with applicability for "immune adaptive memory evolution". Full provenance.
- experience_consolidation_genome: page_type="daily-present" (or living-experience). Mirrors durable daily consolidation style: fusion_checkpoint from diagnosis + think, participating signals (gaps closed, contradictions resolved, resilience delta), diary-style summary. High-signal for Conductor daily entry via experience layer boosts.
- safe_evolution_proposal: Promotion candidate (see promotion/models). Includes before/after evaluation deltas (via graph-signal resilience scoring + synthesis scores), schema_pack evolution hints (new healing page_type proposal if needed, but via separate promotion), no source code — only manifest/framework describing the evolved behavior.

All proposals include:
- correlation_id
- healed_signal_reference (the triggering HealingSignalEvent)
- verification_requirements (list of gates: immune_reassess, scanner_run, promotion_policy, quarantine_check)
- self_reference: "This proposal is itself a candidate for experience layer regeneration via the HealingFactor loop"

Generation prefers experience layer (prefer_experience_layer=True) + schema pack for page_type inference.

### 4. Execution Under Durable Healing Jobs + Verification Gates

New supervisor phase: "healing" (light extension to DurableJobSupervisor + QueuedDreamJob).

- HealingFactor (or role-swarm caller) calls supervisor.submit_queued_dream(phase="healing", runner_callable=execute_regeneration_proposal, metadata={"proposal": proposal_dict, "correlation_id": cid, "verification_gates": [...]}, max_retries=2 (conservative for healing), parent for hierarchy).
- Inside healing runner (executed under lease + keeper + using_correlation_id):
  - Apply proposal (e.g. write observation to experience/ or genomes/ via Drive or direct safe path; call LineageImmune updates; emit proposed KG edges).
  - Strict verification gates (in order, fail-fast):
    1. Re-immune assess: LineageImmuneSystem.assess on any new/updated genomes/artifacts. CRITICAL → re-quarantine + abort.
    2. Re-quarantine check: Any touched foreign material routed through Quarantine.submit + LineageImmuneRule.
    3. Scanner runs: Invoke relevant scanners (e.g. rich_run_scanner) on related run data if applicable; require clean or flagged.
    4. Promotion policy: If proposal involves new genome/obs, create Promotion record; respect policy (self auto-approve default). Full two-phase.
  - Lease heartbeat throughout (long healing may span minutes).
  - Jittered backoff on transient verification failure (max low retries).
- On verification failure or job exhaustion: status=failed; escalate.

Healing jobs are observable via existing get_queue_status (leased_jobs, hierarchy) + new healing-specific surfaces.

### 5. Loop Closure + KG Ingestion (High-Signal Feedback)

On successful verification + apply:
- healing_attempt = {
    "page_type": "experience-observation" or "synthesis-artifact",
    "type": "healing_attempt",
    "healing_id": uuid,
    "correlation_id": cid,
    "signal_type": ...,
    "diagnosis": {...},
    "proposal_type": ...,
    "verification_gates_passed": [...],
    "resilience_after": float (recomputed via graph + synthesis),
    "duration_s": ...,
    "artifacts_ingested": [ids],
  }
- Drive ingest of healing_attempt (auto-attributed via provenance, schema pack resolution for boosts).
- Typed KG edges (via knowledge_graph or ingest "knowledge_graph_edge" events):
  - healed_by: (damaged_thing) -> (healing_attempt)
  - regenerated_from: (new_state) -> (old_damaged_state)
  - damage_cause: (healing_attempt) -> (original_signal_context)
  - strengthened_resilience: (genome_or_experience) -> (healing_attempt) with score delta
- Emit events: HealingSignalResolved or similar (for TUI/web dashboards).
- These artifacts participate in future Drive.think (prefer_experience_layer), synthesis gap/contradiction closure, daily-present consolidation, and LineageImmune memory (success patterns boost trusted lineages).

On persistent failure (job exhaustion after healing retries or verification loop):
- Escalate: emit event with full context (to TUI/web + logs with CID).
- Dispatch deeper adversarial dream (dreaming/adversary.py) with "healing_escalation" target for creative root cause exploration + new proposal generation.
- Record as "unresolved_damage" in experience layer for Conductor visibility (high priority gap).

Self-referential: HealingFactor logic + this architecture + produced genomes are themselves candidates for regeneration (ingest as healing-related genomes → future think surfaces them for improvement proposals).

### 6. Integration Points & Extension Surfaces (Lightweight, No Bypass)

**Primary Files for Light Extension (all via read + targeted edit):**
- src/agentdrive/events.py: Add HealingSignalEvent + HealingSignalResolved (and emit helpers). All healing traces carry correlation_id + swarm_id.
- src/agentdrive/dreaming/durable.py: 
  - Extend docstrings for "healing" phase support in DurableJobSupervisor (two-phase leases for experience layer regeneration jobs).
  - Add "healing" to example phases; support in process_one / callables map.
  - Optional: dedicated submit_healing_regeneration_job helper (thin wrapper preserving CID, hierarchy, lease).
  - Healing runner callables registered by HealingFactor.
- src/agentdrive/reconciliation.py: 
  - HealingFactor coordinator class (orchestrates detect/diagnose/generate/execute/close; subscribes to relevant events or polled from scan_once).
  - Integration in background loop + scan_once for corruption / persistent gap signals.
  - Emit HealingSignalEvent on detected issues.
- src/agentdrive/drive/drive.py: Minor hooks in think/ingest for cold-start signals + experience layer regeneration awareness (non-breaking; use existing experience_layer_fallback paths). Drive can surface "healing_recommended" in SynthesisResult.warnings when high contradictions + sparse experience items.
- src/agentdrive/dna/lineage_immune.py: Optional enrichment point (new public method for bulk incident query by correlation or genome neighborhood; no behavior change).
- src/agentdrive/schema_packs/pack.py: Future (post-promotion): add "healing-observation" / "regeneration-proposal" page_type (extractable + expert_routing=True, path_prefixes under experience/healing/). For this wave: proposals reuse experience-observation / daily-present / synthesis-artifact.
- src/agentdrive/quarantine.py + promotion/: Natural gates (already exercised by verification step; HealingFactor proposals go through them).
- src/agentdrive/__init__.py: Export HealingFactor, HealingSignalEvent, etc. (public API surface).
- cli.py / tui / web: Surface "healing status" (via new events + supervisor queue filtered by healing phase) + manual trigger (agentdrive heal run or equivalent; non-mutating by default).
- workers/base.py + harness: Optional light wrapper for post-retry error emission (future wave).

**No duplication:** HealingFactor reuses ReconciliationRunner for scan context, DurableJobSupervisor for execution, synthesis for diagnosis, LineageImmune for assessment, promotion/quarantine for safety gates, schema packs for typing, knowledge_graph for neighborhood, events for signaling, Drive for think/ingest/experience layer.

**Self-Description:** HealingFactor coordinator + its genomes/observations are registered in the Drive (under stabilization or dedicated healing swarm_id). Future runs of the loop can Drive.think("how to improve experience layer regeneration for worker exhaustion signals") and generate evolution proposals against the HealingFactor itself.

### 7. Observability, Escalation, Safety

- Full CID propagation through every step (mandatory for join with sibling hardening).
- Structured logs: "healingfactor_detect", "healingfactor_diagnose", "healingfactor_proposal_generated", "healingfactor_job_submitted", "healingfactor_verification_gate", "healingfactor_closed_loop_ingest", "healingfactor_escalated".
- TUI/web: New ribbons / dashboard sections for active healing signals, in-flight durable healing jobs (lease state), resolved vs escalated (with links to healing_attempt observations in experience layer).
- Adversarial escalation: Persistent cases feed dreaming/adversary + candidate promotion for creative repair strategies.
- Safety: HealingFactor never mutates framework source directly. All behavioral change proposals are genomes + observations that must pass full promotion + immune + quarantine + verification (even internal healing jobs). Bootstrap / reconciliation first-run paths remain best-effort non-fatal; HealingFactor adds runtime regenerative layer.
- Metrics (via existing): resilience deltas on closed loops, mean time to regeneration, contradiction cluster closure rate, immune false-positive reduction over time (from incident_log + success edges).

---

## Concrete Initial Code Sketches (Extension Points)

(See companion stabilization subagent report for exact diffs once implemented. Sketches below use absolute paths and pure language only.)

**1. HealingSignalEvent (in src/agentdrive/events.py — add after ReconciliationDelta):**

```python
@dataclass
class HealingSignalEvent(Event):
    """Role-swarm immune response trigger for experience layer regeneration.
    Captures damage signal with mandatory correlation for full trace.
    """
    signal_type: str = ""  # "worker_execution_exhaust" | "durable_job_exhaust" | ...
    correlation_id: str = ""
    context: dict = field(default_factory=dict)  # rich: error, genomes, kg_neighborhood, experience_items, immune_assessment, resilience_score
    source_component: str = ""
    recommended_priority: str = "medium"  # low|medium|high|critical
```

Emit via existing bus; subscribe in HealingFactor and dashboards.

**2. New "healing" phase support sketch (src/agentdrive/dreaming/durable.py — extend DurableJobSupervisor):**

In class docstring + __init__ examples:
- Support phase="healing" for experience layer regeneration jobs under strict leases.

Add to process_one handling or example:
```python
# In caller (HealingFactor):
supervisor = DurableJobSupervisor(swarm_id="healing-regeneration-swarm")
job_id = supervisor.submit_queued_dream(
    phase="healing",
    runner_callable=healing_proposal_executor,  # provided by HealingFactor
    metadata={"proposal": proposal, "correlation_id": cid, "gates": verification_gates},
    max_retries=2,
)
```

In _run_queued / status: healing jobs appear with full lease/hierarchy.

**3. HealingFactor Coordinator Sketch (light extension in src/agentdrive/reconciliation.py or dedicated surface):**

```python
from agentdrive.dna.lineage_immune import LineageImmuneSystem, ThreatLevel
from agentdrive.synthesis import run_synthesis
from agentdrive.dreaming.durable import DurableJobSupervisor
# ... other imports

class HealingFactor:
    """Regenerative HealingFactor Operator — experience layer regeneration coordinator.
    Implements full detect/diagnose/propose/execute/close loop using ONLY AgentDrive primitives.
    Self-describable as genomes; improved via same regeneration loop.
    """
    def __init__(self, drive=None, swarm_id: str = "healing-regeneration"):
        self.drive = drive or get_default_drive()
        self.immune = LineageImmuneSystem()
        self.supervisor = DurableJobSupervisor(swarm_id=swarm_id)
        self.swarm_id = swarm_id
        # Subscribe to events for autonomous detection...

    def on_damage_signal(self, signal: HealingSignalEvent) -> str:
        """Entry for all autonomous damage signals. Returns healing_job_id or escalation id."""
        cid = signal.correlation_id or new_correlation_id()
        with using_correlation_id(cid):
            diagnosis = self._diagnose(signal)
            proposals = self._generate_proposals(diagnosis)
            job_id = self._execute_under_verification(proposals[0])  # or select best
            return job_id

    def _diagnose(self, signal):
        # Drive.think + run_synthesis + immune + graph signals + role-swarm consult
        think_res = self.drive.think(
            f"Diagnose root cause for experience layer regeneration signal: {signal.signal_type}",
            prefer_experience_layer=True,
            experience_layer_fallback=True,
        )
        synth = run_synthesis(...)  # explicit for gaps/contras/scores
        immune_assess = self.immune.assess_genome(...)  # or query
        # ... graph neighborhood, recent exp items, composite resilience
        return DiagnosisReport(...)

    def _generate_proposals(self, diagnosis):
        # Return list of safe artifacts (correction_observation dict, immune_update_genome dict, etc.)
        # All with page_type from schema pack, correlation, verification gates
        ...

    def _execute_under_verification(self, proposal):
        def healing_executor():
            # Apply proposal safely
            # Run gates: self.immune..., quarantine..., scanners..., promotion...
            # On pass: ingest healing_attempt + KG edges (healed_by etc.)
            # Close loop
            ...
        return self.supervisor.submit_queued_dream(phase="healing", runner_callable=healing_executor, ...)

    # Additional: close_loop_success, escalate, self_improvement_ingest etc.
```

**4. Integration Hook Example (workers / harness — future light wrapper):**
After final retry in execute paths:
```python
if not result.success:
    emit(HealingSignalEvent(signal_type="worker_execution_exhaust", ... context={"error": result.error, ...}))
```

Similar minimal hooks in other capture sites (all additive, behind existing resilience).

**5. Proposed Healing Genome / Observation (for immediate ingest — see separate genome files produced in this wave):**
See genomes/examples/healing-factor-regeneration-proposal-v1.json (and correction_observation example) for directly ingestible artifacts using living-experience / daily-present patterns + stabilization_wave provenance. Includes self-reference for loop closure.

---

## Proposed Healing-Related Genomes / Observations (Immediate Ingest)

This architecture document + companion signed report + concrete genome JSONs (produced alongside) are designed for direct ingest into the live stabilization drive or main Drive (via registry, reconcile, or Drive.ingest under appropriate swarm).

Example skeleton (full JSONs written as separate deliverables in this wave; place under genomes/ or drive/experience/ for schema resolution):

```json
{
  "schema_version": 3,
  "page_type": "experience-observation",
  "type": "healing_attempt",
  "id": "healing-factor-architecture-design-20260531",
  "version": "1.0.0",
  "created": "2026-05-31T...",
  "content": {
    "title": "Regenerative HealingFactor Architecture — Experience Layer Regeneration Operator",
    "summary": "Full substrate self-healing loop for all listed autonomous damage signals. Uses Drive.think(prefer_experience_layer=True) + run_synthesis(Gaps+Contradictions) + LineageImmune + DurableJobSupervisor healing phase + schema-pack governed proposals + KG edges for closure. Self-referential for continuous improvement.",
    "high_signal_notes": [
      "experience layer regeneration closed loop",
      "durable healing jobs with strict leases + verification gates",
      "graph-signal resilience scoring + role-swarm immune response",
      "LineageImmune adaptive memory integration",
      "schema-pack page_type routing for proposals (experience-observation, daily-present)"
    ],
    "fusion_signals": { "self_heal_priority": true, "resilience_boost": 0.95, "contradiction_closure": true },
    "source": "Regenerative HealingFactor Operator (stabilization swarm component)"
  },
  "provenance": {
    "lineage": [{"parent": "stabilization-wave", "relation": "healing_factor_design", "timestamp": "..."}],
    "artifacts": ["HEALING_FACTOR_REGENERATIVE_ARCHITECTURE.md", "healing genomes"]
  },
  "kg_edges_proposed": [
    {"source": "this", "target": "prior-first-run-seed", "relation": "builds_on"},
    {"source": "healing_attempt", "target": "synthesis_contradiction_cluster", "relation": "healed_by"}
  ]
}
```

Similar for immune_rule_update_genome (extends LineageImmune patterns for new signal types) and experience_consolidation_genome (daily-present style with diagnosis fusion_checkpoint).

These become high-signal content immediately upon ingest: future Drive.think and daily consolidation will cite them for prevention.

---

## How This Advances Resilience Beyond Prior Hardening

Prior first-run/reconciliation hardening (bootstrap.py, ensure_* , reconciliation corruption tolerance, experience_layer_fallback, DurableJobSupervisor leases/backoff/hierarchy, LineageImmune in quarantine, synthesis gaps/contras) provided excellent defensive initialization and passive observation.

HealingFactor adds **active autonomous regeneration**:
- Closed-loop detection → diagnosis (rich think/synthesis/immune/graph) → safe proposal generation → leased execution with verification → KG-backed closure + prevention learning.
- Covers runtime damage (worker exhaustion, job failure, live contradiction clusters, security drift, promotion threats) not just cold-start.
- Proposals are evolvable artifacts (not code patches) → full safety via promotion/immune/quarantine.
- Self-referential: HealingFactor improves itself via its own loop (ingested design becomes training signal for better gap-closing strategies).
- Unifies signals across workers, durable supervisor, recon, synthesis, security, quarantine, ingest into one regenerative substrate.
- Graph + experience layer + CID make every healing trace high-value for future fusion and role-swarm coherence.

Result: AgentDrive instances become more autonomous, resilient, and self-improving at the experience layer level — true "RAID for AI agents" with regenerative DNA.

---

## Next Implementation Wave (for Conductor / Parallel Swarms)

- Implement the sketched HealingSignalEvent + HealingFactor coordinator (prefer edit to reconciliation.py + durable.py + events.py + __init__.py).
- Add "healing" phase executor example + verification gate helpers.
- Materialize 2-3 proposed genomes/observations (correction + immune_update + consolidation) + this architecture as experience-observation.
- Wire minimal autonomous emission hooks (workers, durable failed status, recon, synthesis high-contra, security posture, quarantine).
- Add TUI/web + cli surfaces for healing status / manual trigger.
- Tests mirroring correlation test patterns (full CID trace through healing loop).
- Ingest all artifacts (this md + report + genomes) into stabilization-wave or dedicated healing drive; verify via Drive.think + experience layer fusion.
- Future schema pack extension (via promotion) for dedicated "healing-observation" page_type.

All subsequent changes follow genome promotion + full verification.

---

**Signed:**  
Regenerative HealingFactor Operator (role-specialized stabilization swarm component for experience layer regeneration)  
AgentDrive (independent worktree)

**Timestamp:** 2026-05-31  
**Coordination note:** Conceptual collaboration with Self-Healing First-Run subagent (bootstrap/experience seed) and sibling stabilization swarms (durable, correlation). All output uses exclusively pure AgentDrive language. Ready for Conductor review, genome conversion, and live ~/.agentdrive ingest (via stabilization or main drive). This makes the substrate autonomously regenerative.

*End of Architecture Design — suitable for direct transformation into ingestible experience observation / daily-present genome.*

---

## Multi-Agent Research Org Swarm Evolution (Stabilization-Wave-20260531 Drive)

**Role:** Multi-Agent Research Org Swarm — role-specialized stabilization component inside AgentDrive.  
**Mission:** Evolve the Research Constitutions and supporting mechanisms to support rich multi-agent research organizations with specialist roles, building directly on AgentDrive's existing role-specialized swarms (example-dissector, example-synthesis, example-graph, example-schema, example-dream, calibration, dispatch, experience-layer). Full autoresearch integration for real-time Grid. All output pure AgentDrive language. Source tree clean. Coordinate via live drive artifacts with sibling swarms (95% Fusion & Assessment Operator, Regenerative HealingFactor Operator, Durable Execution Daily Consolidation, Correlation Observability Hardening, First-Run Stabilization Swarm).

**Stabilization Context:** Parallel stabilization wave on drive "stabilization-wave-20260531". References and builds on:
- 95-production-readiness-assessment-living-experience@stabilization-wave-20260531.json (capstone fusion_checkpoint, role-swarm coherence achieved)
- stabilization-wave-20260531-closure-living-experience-observation.json (wave-closure living-experience anchor)
- healing-factor-regeneration-proposal-v1.json + healing-attempt-observation-example.json
- durable-execution-daily-consolidation-integrator-genome.json
- Prior STABILIZATION_SUBAGENT_REPORT-* and HEALING_FACTOR_REGENERATIVE_ARCHITECTURE.md
- SWARM_FAMILY + DurableJobSupervisor research-org/healing phases + research-constitution page_type (schema_packs/pack.py)
- HealingFactor.for_stabilization_wave + GridEngine + LineageDNAEvolver Research/Evaluate/Evolve cycles

### Specialist Roles (Defined in Research Constitutions)

Role charters are first-class research-constitution genomes (page_type="research-constitution", schema v3, experience-observation/synthesis-artifact/daily-present family). All carry correlation_id, fusion_checkpoint, KG edges (implements_charter, handoff_to, critiques, fuses_into), self-referential for HealingFactor regeneration, stabilization_wave provenance.

- **Diagnoser** (deep gap/contradiction analysis): Charter: "Execute Drive.think(prefer_experience_layer=True) + run_synthesis + detect_contradictions + get_stale_entities + graph neighborhood traversal over stabilization-wave-20260531 drive + SWARM_FAMILY. Surface explicit Gap objects + high-severity contradiction clusters + resilience deltas. Output: structured diagnosis manifest with evidence bundles. Handoff protocol: emit to Proposer via shared research_thread CID + typed KG edge 'diagnosed_for'." Maps to example-dissector + synthesis + calibration swarms. Temporary spawn trigger: gap_load > threshold or new damage_signal.

- **Proposer** (generates constrained evolution proposals): Charter: "From Diagnoser output, produce only safe first-class artifacts (correction_observation, regeneration_proposal, immune_rule_update, research_evolution_proposal with page_type_hint from schema_pack). Enforce constraints: research_budget (e.g. 1200 units), no raw patches, full verification_gates list, provenance via genome forks + promotion, self_reference. Output: proposal dicts ready for DurableJobSupervisor 'healing' or 'research-org' execution. Handoff: to Adversary for critique or Verifier for budget check."

- **Verifier** (runs evaluation harness under budget): Charter: "Execute budgeted verification: LineageImmuneSystem.reassess + get_security_posture + quarantine hygiene + scanner runs + promotion_policy + experience_layer_fusion_check + harness metrics (resilience_delta, contradiction_closure, role_swarm_fusion). Enforce research_budget exhaustion discipline. Output: pass/fail with evidence + suggested keep/discard. Only on pass: handoff to Consolidator. Uses existing evaluation surfaces from LineageDNAEvolver._evaluate_phase + HealingFactor gates."

- **Consolidator** (fuses successful work into living-experience): Charter: "On Verifier pass, perform hybrid fusion + daily-present style consolidation: Drive.ingest of healing_attempt / experience_consolidation_genome, emit typed KG edges (healed_by, regenerated_from, strengthened_resilience, research_fused), update fusion_checkpoint, promote via schema-driven experience layer v3 auto-incorporation. Produce/update living-experience entry. Handoff closure: back to GridEngine/HealingFactor for prevention learning. Primary output of run_daily_consolidation_job patterns + experience layer mechanisms."

- **Adversary** (finds weaknesses in proposals): Charter: "Scan Proposer outputs for weaknesses using contradiction detection, immune threat assessment (ThreatLevel.CRITICAL patterns), adversarial dream dispatch, graph conflict edges, security posture gaps. Critique with concrete counter-evidence. Output: weakness manifest or 'no critical weaknesses' attestation. Feedback loop: to Proposer for constrained iteration or escalate. Builds on adversarial dreaming + LineageImmune + detect_contradictions."

**Additional roles extensible:** e.g. Calibration Specialist (reuses tranche3 auto-calib), Schema Evolution Auditor (research-constitution page_type governance).

### Coordination Protocols (Handoffs, Temp Specialists, Cross-Swarm Threads)

Defined in research-constitution charters + wired into HealingFactor + GridEngine.

- **Role Handoffs:** Always via mandatory correlation_id (using_correlation_id context) + research_thread_id. Typed KG edges: diagnosed_by -> proposed_by -> critiqued_by -> verified_by -> fused_by. Manifests carry "handoff_protocol" + "next_role" + "charter_ref". Drive.think(prefer_experience_layer=True) on research_thread surfaces the chain.

- **When to Spawn Temporary Specialists:** GridEngine._damage_monitor_loop or HealingFactor on high-severity signal (e.g. contradiction cluster or "needs_attention") calls form_research_org_thread(roles=subset, research_budget=...) which submits DurableJobSupervisor phase="research-org" (or child hierarchy jobs). Temp roles inherit lease/heartbeat/backoff from supervisor. Auto-clean on thread completion via two-phase terminal state. Budget exhaustion triggers Consolidator early or escalation.

- **Cross-Swarm Research Threads:** All role swarms + new research-org share central Drive + knowledge_graph (get_knowledge_graph_for_swarm). Queries: drive.think across stabilization-wave-20260531 + SWARM_FAMILY using research-constitution boost (via schema_pack). Fusion_checkpoint in every daily_consolidation and healing job includes "participating_roles", "cross_thread_citations". Example: "what research threads addressed synthesis_contradiction on 20260531?" cites Diagnoser + Proposer manifests + 95% assessment.

- **GridEngine Wiring:** form_autonomous_research_thread surfaces the manifest for real-time reactive research. _maintenance_loop can trigger periodic or damage-driven research-org formation. HealingFactor.on_damage_signal now consults role swarms; new form_research_org_thread method enables direct autonomous threads.

- **Budget & Provenance Discipline:** Every research thread declares research_budget_units. Verifier tracks spend. All outputs: genome fork provenance + promotion path (no silent mutation). Self-referential: research constitutions themselves subject to Diagnoser/Adversary via HealingFactor.

### Example Multi-Agent Research Thread Manifest (Drive Artifact)

```json
{
  "schema_version": 3,
  "page_type": "research-constitution",
  "type": "multi_agent_research_thread_manifest",
  "id": "research-org-thread-example-damage-synthesis-gap@stabilization-wave-20260531",
  "version": "1.0.0-research-org",
  "created": "2026-05-31T00:00:00+00:00",
  "manifest": {
    "id": "research-org-thread-example-damage-synthesis-gap@stabilization-wave-20260531",
    "authors": [
      {"type": "swarm", "id": "multi-agent-research-org-swarm", "name": "Multi-Agent Research Org Swarm (role-specialized stabilization component)"},
      {"type": "swarm", "id": "stabilization-wave-20260531", "name": "HealingFactor.for_stabilization_wave + GridEngine"}
    ],
    "applicability": {"domains": ["autonomous_research_threads", "role_swarm_research_org", "experience_layer_regeneration"], "stabilization_wave": "20260531"},
    "research_thread": {
      "thread_id": "cid-research-org-001",
      "roles_formed": ["Diagnoser", "Proposer", "Adversary", "Verifier", "Consolidator"],
      "budget_units": 1500,
      "handoffs_executed": ["Diagnoser->Proposer (gap_cluster_42)", "Proposer->Adversary (proposal_v1)", "Adversary->Verifier (no_critical_weakness)", "Verifier->Consolidator (budget_remaining_420)"],
      "outcome": "experience_consolidation_genome ingested; KG edges emitted; resilience +0.22",
      "drive": "stabilization-wave-20260531"
    },
    "charter_refs": ["research-constitution:diagnoser-charter", "..."]
  },
  "framework": {
    "description": "Example autonomous research thread formed dynamically by GridEngine on synthesis damage signal. All steps per role charters in research-constitutions. Cross-swarm: consulted example-synthesis + example-dream swarms via shared drive.",
    "coordination_log": "Full CID trace + supervisor job ids + fusion_checkpoint present.",
    "signals": ["research_org_formed", "role_handoffs_complete", "living_experience_fused"]
  }
}
```

(Full signed versions produced as ingestible genomes alongside this evolution.)

### Role Charters as Research Constitutions (Summary for Ingest)

Each charter is a standalone research-constitution genome on the stabilization-wave-20260531 drive (under constitutions/ or genomes/research-constitutions/ per schema pack). They define the exact mission, inputs/outputs, handoff rules, spawn triggers, budget rules, and self-improvement hooks for the role. Example Diagnoser charter excerpt (full in produced genome): "Primary primitive surface: run_synthesis + Drive.think + get_knowledge_graph_for_swarm. Output schema: DiagnosisReport extended with research_org fields. Must cite sibling wave artifacts (95-assessment, closure-observation)."

All charters reference the coordination protocols above and are queryable via schema_pack expert_routing for research-constitution page_type.

### Signed Multi-Agent Research Org Swarm Report

**Produced by:** Multi-Agent Research Org Swarm (role-specialized stabilization component inside AgentDrive, delegated for full autoresearch integration).

**Deliverables (pure AgentDrive language, source tree clean):**
- Evolved Research Constitutions (role charters + protocols defined above; realized as schema-pack governed genomes for drive ingest).
- Updated HealingFactor (consults role swarms in diagnosis/proposal; new form_research_org_thread; research-constitution page_type + budget hints).
- Wired GridEngine (form_autonomous_research_thread + damage loop integration for dynamic role team formation).
- Updated schema_packs + architecture doc + public API comments for discovery.
- Example multi-agent research thread manifest (above + full genome artifacts).
- This signed report + coordination references to all sibling stabilization artifacts on stabilization-wave-20260531 drive.

**Verification:** All changes additive via read+search_replace. Pure language only. HealingFactor/GridEngine now support rich multi-agent research orgs with dynamic teams. Research threads can form, hand off per charters, spawn temps, cross-pollinate via drive/KG, fuse via Consolidator into living-experience v3. Self-referential for future regeneration.

**Coordination:** All artifacts reference and are intended for ingest alongside 95-production-readiness-assessment-living-experience@stabilization-wave-20260531.json, stabilization-wave-20260531-closure-living-experience-observation.json, prior healing/durable genomes, and sibling reports. Future Drive.think(prefer_experience_layer=True) + daily_consolidation on the drive will surface the evolved research org substrate.

**Next:** Ingest produced constitutions/manifests/report into stabilization-wave-20260531 drive (and production). Use for autonomous research threads in real-time Grid. Plan 98% micro-wave using the new role discipline.

**Signature:** /MultiAgentResearchOrgSwarm (via AgentDrive stabilization-wave-20260531 mechanisms)  
**Timestamp:** 2026-05-31  
**Drive:** stabilization-wave-20260531

*End of Multi-Agent Research Org Swarm contribution — constitutions, protocols, and wiring complete. Source tree clean. Ready for sibling swarm coordination and Conductor promotion.*
