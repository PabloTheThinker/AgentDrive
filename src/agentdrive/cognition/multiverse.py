"""
Multiverse Cognition — parallel timeline superposition for Parent decisions.

Holds competing futures in superposition, extracts cross-branch invariants,
stress-tests via Adversary lens, collapses to one governed path, and records
everything as first-class Experience Graph v3 DNA.

Integrates with:
- ExperienceGraphRecorder (TypedEdges + page_type observations)
- IntegratedRealTimeEvolutionSystem.record_parent_decision (fabric_reasoning)
- AD-Grid Council (Adversary stress-test, Guardian veto hook)
- Cognitive Agent Team roles (branch generators)

See docs/MULTIVERSE_COGNITION.md for the full architecture.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from agentdrive.evolution.experience_graph import ExperienceGraphRecorder
    from agentdrive.cognition.store import MultiverseSessionStore

# ------------------------------------------------------------------
# TypedEdge relations (dual-written via recorder.record_connection)
# ------------------------------------------------------------------

MULTIVERSE_SESSION = "multiverse_session"
BRANCH_SPAWNED = "branch_spawned"
BRANCH_SIMULATED_FORWARD = "branch_simulated_forward"
INVARIANT_EXTRACTED = "invariant_extracted"
CONVERGENCE_DETECTED = "convergence_detected"
DIVERGENCE_DETECTED = "divergence_detected"
PATH_COLLAPSED = "path_collapsed"
BRANCH_STRESS_TESTED = "branch_stress_tested"
MULTIVERSE_INFORMED_DECISION = "multiverse_informed_decision"

MULTIVERSE_RELATIONS: dict[str, str] = {
    MULTIVERSE_SESSION: "session_contains_multiverse",
    BRANCH_SPAWNED: "spawned_in_multiverse",
    BRANCH_SIMULATED_FORWARD: "forward_simulation_of_branch",
    INVARIANT_EXTRACTED: "invariant_of_multiverse",
    CONVERGENCE_DETECTED: "converges_via_multiverse",
    DIVERGENCE_DETECTED: "diverges_at_multiverse_point",
    PATH_COLLAPSED: "collapsed_from_multiverse",
    BRANCH_STRESS_TESTED: "stress_test_on_branch",
    MULTIVERSE_INFORMED_DECISION: "decision_informed_by_multiverse",
}

# Cognitive Agent Team roles → branch generators
COGNITIVE_ROLES: tuple[str, ...] = (
    "architect",
    "adversary",
    "scout",
    "operator",
    "surgeon",
    "beacon",
    "watchdog",
)

DIVERGENCE_AXES: tuple[str, ...] = (
    "risk",
    "speed",
    "reversibility",
    "cost",
    "dependency_order",
)

ROLE_PATH_TEMPLATES: dict[str, str] = {
    "architect": "Structural path: map whole system first, then locate intervention point",
    "adversary": "Failure path: assume optimistic plan breaks at weakest assumption",
    "scout": "Intelligence path: gather unknowns before committing resources",
    "operator": "Velocity path: smallest shippable slice with momentum preservation",
    "surgeon": "Precision path: minimal cut at highest-leverage intervention point",
    "beacon": "Signal path: optimize for discoverability and audience propagation",
    "watchdog": "Defense path: trace attack surfaces and anomaly blast radius",
}


class CollapsePolicy(str, Enum):
    PATTERN_CRYSTALLIZED = "pattern_crystallized"
    ADVERSARY_CLEAR = "adversary_clear"
    HARNESS_SCORE = "harness_score"
    CONDUCTOR_OVERRIDE = "conductor_override"
    BUDGET_EXHAUSTED = "budget_exhausted"
    EXTERNAL_PARENT = "external_parent"


class InvariantKind(str, Enum):
    ROBUST = "robust"
    FRAGILE = "fragile"
    CONVERGENCE = "convergence"
    DIVERGENCE = "divergence"


class SessionStatus(str, Enum):
    OPEN = "open"
    COLLAPSED = "collapsed"
    REOPENED = "reopened"


@dataclass
class ForwardStep:
    step_index: int
    description: str
    confidence: float = 0.7


@dataclass
class AdversaryVerdict:
    passed: bool
    fatal_flaws: list[str] = field(default_factory=list)
    mitigations: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass
class Branch:
    branch_id: str
    role: str
    path_summary: str
    assumptions: list[str] = field(default_factory=list)
    divergence_axes: list[str] = field(default_factory=list)
    forward_steps: list[ForwardStep] = field(default_factory=list)
    robustness_score: float = 0.0
    fragility_flags: list[str] = field(default_factory=list)
    stress_test: AdversaryVerdict | None = None


@dataclass
class Invariant:
    statement: str
    branch_coverage: float
    kind: InvariantKind
    source_branches: list[str] = field(default_factory=list)


@dataclass
class MultiverseSession:
    session_id: str
    trigger: str
    cycle_id: str
    correlation_id: str
    branches: list[Branch] = field(default_factory=list)
    invariants: list[Invariant] = field(default_factory=list)
    convergence_points: list[str] = field(default_factory=list)
    divergence_points: list[str] = field(default_factory=list)
    status: SessionStatus = SessionStatus.OPEN
    collapsed_branch_id: str | None = None
    collapse_reason: str | None = None
    collapse_policy: CollapsePolicy | None = None
    program_id: str | None = None
    constitution_refs: list[str] = field(default_factory=list)
    user_objective_refs: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    # Set when an MCP-connected frontier/local chat model supplies branches (Grok, Claude, Codex, etc.)
    reasoning_provider: str | None = None
    llm_mode: str = "heuristic"  # heuristic | llm | external
    external_fabric_reasoning: dict[str, Any] | None = None


class MultiverseEngine:
    """
    Orchestrates multiverse cognition sessions against a live Experience Graph recorder.

    Tier 0 implementation: heuristic branch spawning + forward simulation.
    Swap ``branch_generator`` / ``forward_simulator`` callables for LLM-backed tiers.
    """

    def __init__(
        self,
        recorder: ExperienceGraphRecorder,
        *,
        program_id: str | None = None,
        constitution_refs: list[str] | None = None,
        user_objective_refs: list[str] | None = None,
        default_forward_steps: int = 3,
        robust_threshold: float = 0.7,
        use_llm: bool = True,
    ) -> None:
        self.recorder = recorder
        self.program_id = program_id
        self.constitution_refs = constitution_refs or [
            "research-constitution-multiverse-cognition@stabilization-wave-20260531"
        ]
        self.user_objective_refs = user_objective_refs or ["multiverse-cognition-integration"]
        self.default_forward_steps = default_forward_steps
        self.robust_threshold = robust_threshold
        self.use_llm = use_llm
        self._llm_spawner: Any | None = None
        self._sessions: dict[str, MultiverseSession] = {}
        drive_path = getattr(recorder, "drive_path", None)
        self._store: MultiverseSessionStore | None = None
        if drive_path:
            from agentdrive.cognition.store import MultiverseSessionStore

            self._store = MultiverseSessionStore(Path(drive_path))
        if self._store:
            for session in self._store.list_recent(limit=20):
                self._sessions[session.session_id] = session

    def _get_llm_spawner(self, trigger: str) -> Any | None:
        if not self.use_llm:
            return None
        if self._llm_spawner is not None:
            return self._llm_spawner
        try:
            from agentdrive.cognition.llm_spawner import LLMBranchSpawner

            fabric_context: dict[str, Any] = {}
            if hasattr(self.recorder, "get_fabric_context_pack"):
                try:
                    fabric_context = self.recorder.get_fabric_context_pack(max_tokens=800)
                except Exception:
                    pass
            spawner = LLMBranchSpawner(
                agent_id=self.program_id or "multiverse-llm",
                harness_task=trigger,
                fabric_context=fabric_context,
            )
            if spawner.llm_available:
                self._llm_spawner = spawner
                return spawner
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def spawn_session(
        self,
        trigger: str,
        *,
        cycle_id: str | None = None,
        correlation_id: str | None = None,
        n_branches: int = 7,
        roles: list[str] | None = None,
        durable: bool = False,
    ) -> MultiverseSession:
        """Open a new superposition session and spawn orthogonal branches."""
        ts = int(time.time())
        if not cycle_id:
            cycle_id = self.recorder.start_cycle(
                str(ts), {"source": "multiverse_spawn_session", "trigger": trigger[:120]}
            )
        session_id = f"multiverse-session:{ts}"
        correlation_id = correlation_id or f"multiverse-corr:{uuid.uuid4().hex[:12]}"

        session = MultiverseSession(
            session_id=session_id,
            trigger=trigger,
            cycle_id=cycle_id,
            correlation_id=correlation_id,
            program_id=self.program_id,
            constitution_refs=list(self.constitution_refs),
            user_objective_refs=list(self.user_objective_refs),
        )

        active_roles = roles or list(COGNITIVE_ROLES[: max(1, n_branches)])
        for i in range(n_branches):
            role = active_roles[i % len(active_roles)]
            axis = DIVERGENCE_AXES[i % len(DIVERGENCE_AXES)]
            branch = self._spawn_branch(session, role, axis, index=i)
            session.branches.append(branch)

        self._sessions[session_id] = session
        self._persist_session_observation(session, page_type="multiverse-session")
        self._record_session_edges(session, event="spawned")
        if durable:
            self._mark_durable(session)
        self._publish_multiverse_event(session, phase="spawned")
        self._save_session(session)
        return session

    def simulate_branches(
        self,
        session_id: str,
        *,
        forward_steps: int | None = None,
    ) -> MultiverseSession:
        """Roll each branch forward N steps."""
        session = self._require_session(session_id)
        steps = forward_steps or self.default_forward_steps

        for branch in session.branches:
            branch.forward_steps = self._simulate_forward(session.trigger, branch, steps)
            self._persist_branch_observation(session, branch)
            self._record_branch_edge(session, branch, BRANCH_SIMULATED_FORWARD)

        self._save_session(session)
        return session

    def extract_invariants(self, session_id: str) -> MultiverseSession:
        """Compute robust/fragile/convergence/divergence across branches."""
        session = self._require_session(session_id)
        session.invariants = self._compute_invariants(session.branches)
        session.convergence_points = self._find_convergence_points(session.branches)
        session.divergence_points = self._find_divergence_points(session.branches)

        for inv in session.invariants:
            rel = INVARIANT_EXTRACTED
            if inv.kind == InvariantKind.CONVERGENCE:
                rel = CONVERGENCE_DETECTED
            elif inv.kind == InvariantKind.DIVERGENCE:
                rel = DIVERGENCE_DETECTED
            self.recorder.record_connection(
                session.cycle_id,
                session.session_id,
                f"invariant:{hash(inv.statement) & 0xFFFFFF:06x}",
                rel,
                metadata={
                    "statement": inv.statement,
                    "branch_coverage": inv.branch_coverage,
                    "kind": inv.kind.value,
                    "gbrain_signal_score": round(0.4 + inv.branch_coverage * 0.5, 3),
                    "program_id": self.program_id,
                },
            )

        self._persist_session_observation(session, page_type="multiverse-invariants")
        self._save_session(session)
        return session

    def densify_invariant_clusters(self, session_id: str) -> dict[str, Any]:
        """M3: strengthen robust invariant edges in the Experience Graph (GraphGardener hook)."""
        session = self._require_session(session_id)
        densified = 0
        try:
            from agentdrive.evolution.experience_graph import DENSIFIED_VIA_GARDENER
        except ImportError:
            DENSIFIED_VIA_GARDENER = "densified_via_gardener"

        for inv in session.invariants:
            if inv.kind != InvariantKind.ROBUST:
                continue
            inv_slug = f"invariant:{hash(inv.statement) & 0xFFFFFF:06x}"
            try:
                self.recorder.record_connection(
                    session.cycle_id,
                    session.session_id,
                    inv_slug,
                    DENSIFIED_VIA_GARDENER,
                    metadata={
                        "statement": inv.statement[:200],
                        "branch_coverage": inv.branch_coverage,
                        "multiverse_densification": True,
                        "gbrain_signal_score": round(0.5 + inv.branch_coverage * 0.35, 3),
                    },
                )
                densified += 1
            except Exception:
                pass

        result = {"session_id": session_id, "densified_invariants": densified}
        if densified and hasattr(self.recorder, "compute_cycle_density"):
            try:
                result["cycle_density"] = self.recorder.compute_cycle_density(session.cycle_id)
            except Exception:
                pass
        self._write_observation(
            f"multiverse-densify-{session_id}",
            "multiverse-invariant-densification",
            result,
        )
        return result

    def reopen_stale_sessions(self, *, max_age_hours: float = 24.0) -> list[str]:
        """M4: mark stale open superposition sessions as reopened."""
        drive_path = getattr(self.recorder, "drive_path", None)
        if not drive_path:
            return []
        from agentdrive.cognition.research_thread import find_stale_open_sessions

        reopened: list[str] = []
        for sid in find_stale_open_sessions(Path(drive_path), max_age_hours=max_age_hours):
            session = self.get_session(sid)
            if not session or session.status != SessionStatus.OPEN:
                continue
            session.status = SessionStatus.REOPENED
            self._save_session(session)
            self._publish_multiverse_event(session, phase="reopened")
            reopened.append(sid)
        return reopened

    def stress_test_branch(
        self,
        session_id: str,
        branch_id: str,
        *,
        adversary_rationale: str | None = None,
    ) -> AdversaryVerdict:
        """Adversary pre-mortem on a candidate branch (LLM when available, else heuristic)."""
        session = self._require_session(session_id)
        branch = self._require_branch(session, branch_id)

        spawner = self._get_llm_spawner(session.trigger)
        if spawner:
            llm_verdict = spawner.adversary_stress_test(branch)
            if llm_verdict:
                branch.stress_test = llm_verdict
                self._record_stress_test_edges(session, branch, llm_verdict)
                return llm_verdict

        fatal: list[str] = []
        for assumption in branch.assumptions:
            if any(w in assumption.lower() for w in ("always", "never", "guaranteed", "zero risk")):
                fatal.append(f"Overconfident assumption: {assumption}")

        if branch.role == "adversary":
            fatal.append("Branch is already adversarial — double-counting risk")

        passed = len(fatal) == 0
        verdict = AdversaryVerdict(
            passed=passed,
            fatal_flaws=fatal if not passed else [],
            mitigations=["Add reversible gate", "Run probe before full commit"] if not passed else [],
            rationale=adversary_rationale or f"Adversary stress-test on {branch_id}",
        )
        branch.stress_test = verdict
        self._record_stress_test_edges(session, branch, verdict)
        return verdict

    def collapse(
        self,
        session_id: str,
        *,
        branch_id: str | None = None,
        policy: CollapsePolicy | None = None,
        reason: str | None = None,
    ) -> MultiverseSession:
        """Collapse superposition to one committed path."""
        session = self._require_session(session_id)

        if branch_id is None:
            branch_id, policy, reason = self._auto_select_collapse(session)

        branch = self._require_branch(session, branch_id)
        session.collapsed_branch_id = branch_id
        session.collapse_policy = policy or CollapsePolicy.PATTERN_CRYSTALLIZED
        session.collapse_reason = reason or f"Collapsed to {branch.role} path"
        session.status = SessionStatus.COLLAPSED

        self.recorder.record_connection(
            session.cycle_id,
            session.session_id,
            branch_id,
            PATH_COLLAPSED,
            metadata={
                "collapse_policy": session.collapse_policy.value,
                "collapse_reason": session.collapse_reason,
                "robustness_score": branch.robustness_score,
                "gbrain_signal_score": round(0.5 + branch.robustness_score * 0.4, 3),
                "program_id": self.program_id,
            },
        )
        self._write_observation(
            f"multiverse-collapse-{session.session_id}",
            "multiverse-collapse",
            {
                "session_id": session_id,
                "collapsed_branch_id": branch_id,
                "policy": session.collapse_policy.value,
                "reason": session.collapse_reason,
                "invariants": [asdict(i) for i in session.invariants],
            },
        )
        self._publish_multiverse_event(session, phase="collapsed")
        self._save_session(session)
        return session

    def run_full(
        self,
        trigger: str,
        *,
        n_branches: int = 7,
        forward_steps: int | None = None,
        stress_test_top_n: int = 2,
        durable: bool = False,
        densify_invariants: bool = True,
    ) -> MultiverseSession:
        """One-shot: spawn → simulate → invariants → stress-test → collapse."""
        session = self.spawn_session(trigger, n_branches=n_branches, durable=durable)
        self.simulate_branches(session.session_id, forward_steps=forward_steps)
        self.extract_invariants(session.session_id)
        if densify_invariants:
            self.densify_invariant_clusters(session.session_id)

        ranked = sorted(session.branches, key=lambda b: b.robustness_score, reverse=True)
        for branch in ranked[:stress_test_top_n]:
            self.stress_test_branch(session.session_id, branch.branch_id)

        return self.collapse(session.session_id)

    def resolve_llm_mode(self, trigger: str | None = None) -> str:
        """Return how branches were produced: local llm, heuristic fallback, or external MCP parent."""
        if self._get_llm_spawner(trigger or "") and self._llm_spawner:
            return "llm"
        return "heuristic"

    def ingest_external_parent_decision(
        self,
        trigger: str,
        branches: list[dict[str, Any]],
        *,
        collapsed_branch_id: str,
        invariants: list[dict[str, Any]] | None = None,
        collapse_reason: str = "",
        collapse_policy: str | CollapsePolicy | None = None,
        reasoning_provider: str = "mcp-external",
        convergence_points: list[str] | None = None,
        divergence_points: list[str] | None = None,
        fabric_reasoning: dict[str, Any] | None = None,
        program_id: str | None = None,
        user_objective_refs: list[str] | None = None,
        densify_invariants: bool = True,
    ) -> MultiverseSession:
        """
        Record a full multiverse collapse supplied by an external MCP client (Grok, Claude, Codex, etc.).

        The connected model performs branch reasoning in its own context, then submits structured
        branches + collapse here. AgentDrive persists session DNA and wires record_parent_decision.
        """
        if not branches:
            raise ValueError("branches must be a non-empty list")
        if not collapsed_branch_id:
            raise ValueError("collapsed_branch_id is required")

        ts = int(time.time())
        cycle_id = self.recorder.start_cycle(
            str(ts),
            {
                "source": "external_parent_decision",
                "trigger": trigger[:120],
                "reasoning_provider": reasoning_provider,
            },
        )
        session_id = f"multiverse-session:{ts}"
        correlation_id = f"multiverse-corr:{uuid.uuid4().hex[:12]}"

        if program_id:
            self.program_id = program_id
        if user_objective_refs:
            self.user_objective_refs = list(user_objective_refs)

        parsed_branches = [self._branch_from_external_dict(b, index=i) for i, b in enumerate(branches)]
        branch_ids = {b.branch_id for b in parsed_branches}
        if collapsed_branch_id not in branch_ids:
            raise ValueError(
                f"collapsed_branch_id {collapsed_branch_id!r} not found in branches "
                f"({sorted(branch_ids)})"
            )

        policy = CollapsePolicy.EXTERNAL_PARENT
        if collapse_policy is not None:
            policy = (
                collapse_policy
                if isinstance(collapse_policy, CollapsePolicy)
                else CollapsePolicy(str(collapse_policy))
            )

        session = MultiverseSession(
            session_id=session_id,
            trigger=trigger,
            cycle_id=cycle_id,
            correlation_id=correlation_id,
            branches=parsed_branches,
            invariants=self._invariants_from_external(invariants or [], parsed_branches),
            convergence_points=list(convergence_points or []),
            divergence_points=list(divergence_points or []),
            status=SessionStatus.COLLAPSED,
            collapsed_branch_id=collapsed_branch_id,
            collapse_reason=collapse_reason or f"External parent ({reasoning_provider}) collapsed path",
            collapse_policy=policy,
            program_id=self.program_id,
            constitution_refs=list(self.constitution_refs),
            user_objective_refs=list(self.user_objective_refs),
            reasoning_provider=reasoning_provider,
            llm_mode="external",
            external_fabric_reasoning=dict(fabric_reasoning) if fabric_reasoning else None,
        )

        self._sessions[session_id] = session
        self._persist_session_observation(session, page_type="multiverse-session-external")
        self._record_session_edges(session, event="spawned")
        for branch in session.branches:
            self._persist_branch_observation(session, branch)
            self._record_branch_edge(session, branch, BRANCH_SPAWNED)
            if branch.forward_steps:
                self._record_branch_edge(session, branch, BRANCH_SIMULATED_FORWARD)
        for inv in session.invariants:
            rel = INVARIANT_EXTRACTED
            if inv.kind == InvariantKind.CONVERGENCE:
                rel = CONVERGENCE_DETECTED
            elif inv.kind == InvariantKind.DIVERGENCE:
                rel = DIVERGENCE_DETECTED
            self.recorder.record_connection(
                session.cycle_id,
                session.session_id,
                f"invariant:{hash(inv.statement) & 0xFFFFFF:06x}",
                rel,
                metadata={
                    "statement": inv.statement,
                    "branch_coverage": inv.branch_coverage,
                    "kind": inv.kind.value,
                    "external_parent": True,
                    "reasoning_provider": reasoning_provider,
                    "gbrain_signal_score": round(0.45 + inv.branch_coverage * 0.45, 3),
                    "program_id": self.program_id,
                },
            )

        collapsed = self._require_branch(session, collapsed_branch_id)
        self.recorder.record_connection(
            session.cycle_id,
            session.session_id,
            collapsed_branch_id,
            PATH_COLLAPSED,
            metadata={
                "collapse_policy": session.collapse_policy.value,
                "collapse_reason": session.collapse_reason,
                "robustness_score": collapsed.robustness_score,
                "reasoning_provider": reasoning_provider,
                "llm_mode": "external",
                "gbrain_signal_score": round(0.55 + collapsed.robustness_score * 0.35, 3),
                "program_id": self.program_id,
            },
        )
        self._write_observation(
            f"multiverse-collapse-{session.session_id}",
            "multiverse-collapse-external",
            {
                "session_id": session_id,
                "collapsed_branch_id": collapsed_branch_id,
                "policy": session.collapse_policy.value,
                "reason": session.collapse_reason,
                "reasoning_provider": reasoning_provider,
                "invariants": [asdict(i) for i in session.invariants],
            },
        )
        self._publish_multiverse_event(session, phase="collapsed")
        self._save_session(session)
        if densify_invariants:
            self.densify_invariant_clusters(session.session_id)
        return session

    def to_fabric_reasoning(self, session: MultiverseSession) -> dict[str, Any]:
        """Produce fabric_reasoning payload for record_parent_fabric_reasoning / record_parent_decision."""
        if session.external_fabric_reasoning:
            payload = dict(session.external_fabric_reasoning)
            payload.setdefault("multiverse_session_id", session.session_id)
            payload.setdefault("program_id", self.program_id)
            payload.setdefault("constitution_refs", self.constitution_refs)
            payload.setdefault("user_objective_refs", self.user_objective_refs)
            payload.setdefault(
                "collapse_policy",
                session.collapse_policy.value if session.collapse_policy else None,
            )
            payload.setdefault("reasoning_provider", session.reasoning_provider)
            payload.setdefault("llm_mode", session.llm_mode)
            return payload

        collapsed = (
            self._require_branch(session, session.collapsed_branch_id)
            if session.collapsed_branch_id
            else None
        )
        robust_invariants = [
            inv.statement for inv in session.invariants if inv.kind == InvariantKind.ROBUST
        ]

        elements = [session.session_id]
        elements.extend(f"branch:{b.branch_id}" for b in session.branches[:4])
        elements.extend(f"invariant:{inv.statement[:48]}" for inv in session.invariants[:3])

        coverage = (
            sum(i.branch_coverage for i in session.invariants) / len(session.invariants)
            if session.invariants
            else 0.5
        )

        return {
            "fabric_elements_considered": elements,
            "structural_pattern_matched": (
                f"multiverse_cognition:robust_invariant_coverage_{coverage:.2f}"
            ),
            "decision_rationale": (
                f"Collapsed to {collapsed.role if collapsed else 'unknown'} path "
                f"({session.collapse_reason}). "
                f"Robust invariants: {robust_invariants[:2]}"
            ),
            "expected_lift_signal": round(0.03 + coverage * 0.05, 3),
            "multiverse_session_id": session.session_id,
            "invariants": robust_invariants,
            "collapse_policy": (
                session.collapse_policy.value if session.collapse_policy else None
            ),
            "program_id": self.program_id,
            "constitution_refs": self.constitution_refs,
            "user_objective_refs": self.user_objective_refs,
            "reasoning_provider": session.reasoning_provider,
            "llm_mode": session.llm_mode,
        }

    def get_session(self, session_id: str) -> MultiverseSession | None:
        if session_id in self._sessions:
            return self._sessions[session_id]
        if self._store:
            loaded = self._store.load(session_id)
            if loaded:
                self._sessions[session_id] = loaded
                return loaded
        return None

    def list_sessions(self, *, limit: int = 10) -> list[MultiverseSession]:
        if self._store:
            sessions = self._store.list_recent(limit=limit)
            for s in sessions:
                self._sessions[s.session_id] = s
            return sessions
        return list(self._sessions.values())[:limit]

    def briefing_context(self, *, limit: int = 5) -> dict[str, Any]:
        if self._store:
            return self._store.briefing_context(limit=limit)
        return {"session_count_recent": len(self._sessions)}

    def record_parent_decision(
        self,
        session: MultiverseSession,
        *,
        integrated: Any | None = None,
        actions_taken: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Wire collapsed multiverse session into the canonical Parent decision path.

        Calls IntegratedRealTimeEvolutionSystem.record_parent_decision when
        ``integrated`` is provided; otherwise only returns the decision payload.
        """
        collapsed = (
            self._require_branch(session, session.collapsed_branch_id)
            if session.collapsed_branch_id
            else None
        )
        fabric_reasoning = self.to_fabric_reasoning(session)
        decision = {
            "directive": collapsed.path_summary if collapsed else session.trigger,
            "multiverse_session_id": session.session_id,
            "collapsed_branch_id": session.collapsed_branch_id,
            "collapse_policy": (
                session.collapse_policy.value if session.collapse_policy else None
            ),
        }

        result: dict[str, Any] = {
            "decision": decision,
            "fabric_reasoning": fabric_reasoning,
            "cycle_id": session.cycle_id,
        }

        if integrated is not None and hasattr(integrated, "record_parent_decision"):
            slug = integrated.record_parent_decision(
                session.cycle_id,
                decision,
                actions_taken=actions_taken
                or [f"multiverse_collapse:{session.collapsed_branch_id}"],
                fabric_reasoning=fabric_reasoning,
            )
            result["parent_decision_slug"] = slug
            if hasattr(self.recorder, "record_connection"):
                self.recorder.record_connection(
                    session.cycle_id,
                    session.session_id,
                    slug or f"parent_decision:{session.session_id}",
                    MULTIVERSE_INFORMED_DECISION,
                    metadata={
                        "collapse_policy": session.collapse_policy.value
                        if session.collapse_policy
                        else None,
                        "gbrain_signal_score": 0.74,
                        "program_id": self.program_id,
                    },
                )

        return result

    def to_mcp_dict(self, session: MultiverseSession) -> dict[str, Any]:
        """Serialize session for MCP tool responses."""
        return {
            "session_id": session.session_id,
            "trigger": session.trigger,
            "status": session.status.value,
            "branch_count": len(session.branches),
            "branches": [
                {
                    "branch_id": b.branch_id,
                    "role": b.role,
                    "path_summary": b.path_summary,
                    "robustness_score": b.robustness_score,
                    "forward_steps": [asdict(s) for s in b.forward_steps],
                    "stress_test_passed": (
                        b.stress_test.passed if b.stress_test else None
                    ),
                }
                for b in session.branches
            ],
            "invariants": [asdict(i) for i in session.invariants],
            "convergence_points": session.convergence_points,
            "divergence_points": session.divergence_points,
            "collapsed_branch_id": session.collapsed_branch_id,
            "collapse_policy": (
                session.collapse_policy.value if session.collapse_policy else None
            ),
            "collapse_reason": session.collapse_reason,
            "fabric_reasoning": self.to_fabric_reasoning(session),
            "reasoning_provider": session.reasoning_provider,
            "llm_mode": session.llm_mode,
        }

    # ------------------------------------------------------------------
    # Internal: branch spawning & simulation (Tier 0 heuristics)
    # ------------------------------------------------------------------

    def _branch_from_external_dict(self, raw: dict[str, Any], *, index: int) -> Branch:
        branch_id = str(raw.get("branch_id") or f"branch:{raw.get('role', 'branch')}-{index}")
        steps_raw = raw.get("forward_steps") or []
        steps: list[ForwardStep] = []
        for i, step in enumerate(steps_raw):
            if isinstance(step, dict):
                steps.append(
                    ForwardStep(
                        step_index=int(step.get("step_index", i + 1)),
                        description=str(step.get("description", "")),
                        confidence=float(step.get("confidence", 0.7)),
                    )
                )
        st = raw.get("stress_test")
        stress: AdversaryVerdict | None = None
        if isinstance(st, dict):
            stress = AdversaryVerdict(
                passed=bool(st.get("passed", st.get("stress_test_passed", True))),
                fatal_flaws=list(st.get("fatal_flaws", [])),
                mitigations=list(st.get("mitigations", [])),
                rationale=str(st.get("rationale", "")),
            )
        elif "stress_test_passed" in raw:
            passed = bool(raw.get("stress_test_passed"))
            stress = AdversaryVerdict(
                passed=passed,
                fatal_flaws=list(raw.get("fatal_flaws", [])) if not passed else [],
                mitigations=list(raw.get("mitigations", [])),
                rationale=str(raw.get("stress_rationale", "")),
            )
        return Branch(
            branch_id=branch_id,
            role=str(raw.get("role", COGNITIVE_ROLES[index % len(COGNITIVE_ROLES)])),
            path_summary=str(raw.get("path_summary", "")),
            assumptions=[str(a) for a in raw.get("assumptions", [])],
            divergence_axes=[str(a) for a in raw.get("divergence_axes", [])],
            forward_steps=steps,
            robustness_score=float(raw.get("robustness_score", 0.0)),
            fragility_flags=[str(f) for f in raw.get("fragility_flags", [])],
            stress_test=stress,
        )

    def _invariants_from_external(
        self,
        raw_invariants: list[dict[str, Any]],
        branches: list[Branch],
    ) -> list[Invariant]:
        if not raw_invariants:
            return self._compute_invariants(branches)
        parsed: list[Invariant] = []
        for raw in raw_invariants:
            kind = raw.get("kind", InvariantKind.ROBUST)
            if isinstance(kind, str):
                kind = InvariantKind(kind)
            parsed.append(
                Invariant(
                    statement=str(raw.get("statement", "")),
                    branch_coverage=float(raw.get("branch_coverage", 0.0)),
                    kind=kind,
                    source_branches=[str(s) for s in raw.get("source_branches", [])],
                )
            )
        return parsed

    def _spawn_branch(
        self,
        session: MultiverseSession,
        role: str,
        axis: str,
        *,
        index: int,
    ) -> Branch:
        spawner = self._get_llm_spawner(session.trigger)
        if spawner:
            llm_branch = spawner.spawn_branch(session.trigger, role, axis, index=index)
            if llm_branch:
                self._persist_branch_observation(session, llm_branch)
                self._record_branch_edge(session, llm_branch, BRANCH_SPAWNED)
                return llm_branch

        template = ROLE_PATH_TEMPLATES.get(role, "Custom path")
        branch_id = f"branch:{role}-{index}"
        path_summary = f"[{axis}] {template} — for: {session.trigger[:80]}"

        assumptions = [
            f"{axis} is the primary divergence axis",
            f"{role} lens reveals non-obvious structure",
        ]
        if role == "adversary":
            assumptions.append("At least one optimistic assumption fails")
        if role == "operator":
            assumptions.append("Smallest shippable slice is sufficient to learn")

        branch = Branch(
            branch_id=branch_id,
            role=role,
            path_summary=path_summary,
            assumptions=assumptions,
            divergence_axes=[axis],
        )
        self._persist_branch_observation(session, branch)
        self._record_branch_edge(session, branch, BRANCH_SPAWNED)
        return branch

    def _simulate_forward(
        self,
        trigger: str,
        branch: Branch,
        steps: int,
    ) -> list[ForwardStep]:
        spawner = self._get_llm_spawner(trigger)
        if spawner:
            llm_steps = spawner.simulate_forward(trigger, branch, steps)
            if llm_steps:
                return llm_steps

        axis = branch.divergence_axes[0] if branch.divergence_axes else "risk"
        projections = [
            f"Immediate: apply {branch.role} lens on '{trigger[:60]}' via {axis} axis",
            f"Second-order: dependencies shift; {branch.role} assumptions stress-tested",
            f"Equilibrium: path {'stabilizes' if branch.role != 'adversary' else 'exposes fatal flaw'}",
        ]
        return [
            ForwardStep(step_index=i + 1, description=projections[i], confidence=0.65 + i * 0.05)
            for i in range(min(steps, len(projections)))
        ]

    def _compute_invariants(self, branches: list[Branch]) -> list[Invariant]:
        if not branches:
            return []

        n = len(branches)
        # Tier 0: shared role/axis patterns as synthetic invariants
        axis_counts: dict[str, int] = {}
        role_endings: dict[str, list[str]] = {}

        for b in branches:
            for axis in b.divergence_axes:
                axis_counts[axis] = axis_counts.get(axis, 0) + 1
            ending = b.forward_steps[-1].description if b.forward_steps else ""
            role_endings.setdefault(b.role, []).append(ending)

        invariants: list[Invariant] = []

        invariants.append(
            Invariant(
                statement="Every path requires explicit assumption naming before execution",
                branch_coverage=min(1.0, len(branches) / n),
                kind=InvariantKind.ROBUST,
                source_branches=[b.branch_id for b in branches],
            )
        )

        for axis, count in axis_counts.items():
            coverage = count / n
            kind = InvariantKind.ROBUST if coverage >= self.robust_threshold else InvariantKind.FRAGILE
            invariants.append(
                Invariant(
                    statement=f"Divergence axis '{axis}' shapes distinct outcome class",
                    branch_coverage=coverage,
                    kind=kind,
                    source_branches=[b.branch_id for b in branches if axis in b.divergence_axes],
                )
            )

        for branch in branches:
            branch.robustness_score = round(
                sum(1 for inv in invariants if inv.kind == InvariantKind.ROBUST) / max(len(invariants), 1),
                3,
            )

        return invariants

    def _find_convergence_points(self, branches: list[Branch]) -> list[str]:
        if len(branches) < 2:
            return []
        return ["All paths require fabric DNA recording before execution"]

    def _find_divergence_points(self, branches: list[Branch]) -> list[str]:
        axes = {b.divergence_axes[0] for b in branches if b.divergence_axes}
        return [f"Axis '{a}' produces incompatible commitment timing" for a in sorted(axes)[:3]]

    def _auto_select_collapse(
        self,
        session: MultiverseSession,
    ) -> tuple[str, CollapsePolicy, str]:
        ranked = sorted(session.branches, key=lambda b: b.robustness_score, reverse=True)
        top = ranked[0]

        for branch in ranked[:2]:
            if branch.stress_test is None:
                self.stress_test_branch(session.session_id, branch.branch_id)

        if top.stress_test and not top.stress_test.passed:
            for alt in ranked[1:]:
                if alt.stress_test and alt.stress_test.passed:
                    return (
                        alt.branch_id,
                        CollapsePolicy.ADVERSARY_CLEAR,
                        f"Top branch failed stress-test; {alt.role} path is adversary-clear",
                    )

        if top.robustness_score >= 0.75:
            return (
                top.branch_id,
                CollapsePolicy.PATTERN_CRYSTALLIZED,
                f"Pattern crystallized on {top.role} path (robustness={top.robustness_score})",
            )

        return (
            top.branch_id,
            CollapsePolicy.BUDGET_EXHAUSTED,
            f"Highest robustness {top.role} path selected (score={top.robustness_score})",
        )

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _record_session_edges(self, session: MultiverseSession, *, event: str) -> None:
        self.recorder.record_connection(
            session.cycle_id,
            session.cycle_id,
            session.session_id,
            MULTIVERSE_SESSION,
            metadata={
                "event": event,
                "trigger": session.trigger[:200],
                "correlation_id": session.correlation_id,
                "gbrain_signal_score": 0.72,
                "program_id": self.program_id,
                "constitution_refs": self.constitution_refs,
            },
        )

    def _record_branch_edge(self, session: MultiverseSession, branch: Branch, relation: str) -> None:
        self.recorder.record_connection(
            session.cycle_id,
            session.session_id,
            branch.branch_id,
            relation,
            metadata={
                "role": branch.role,
                "divergence_axes": branch.divergence_axes,
                "gbrain_signal_score": 0.6,
                "program_id": self.program_id,
            },
        )

    def _persist_session_observation(self, session: MultiverseSession, *, page_type: str) -> None:
        self._write_observation(
            session.session_id,
            page_type,
            {
                "session": asdict(session),
                "branches": [asdict(b) for b in session.branches],
            },
        )

    def _persist_branch_observation(self, session: MultiverseSession, branch: Branch) -> None:
        self._write_observation(
            branch.branch_id,
            "multiverse-branch",
            {"session_id": session.session_id, "branch": asdict(branch)},
        )

    def _write_observation(self, slug: str, page_type: str, content: dict[str, Any]) -> Path | None:
        drive_path = getattr(self.recorder, "drive_path", None)
        if not drive_path:
            return None
        obs_dir = Path(drive_path) / "observations" / "meta-evolution" / "multiverse"
        obs_dir.mkdir(parents=True, exist_ok=True)
        safe_slug = "".join(c if c.isalnum() or c in "-_:" else "_" for c in slug)[:120]
        path = obs_dir / f"{safe_slug}.json"
        payload = {
            "page_type": page_type,
            "slug": slug,
            "timestamp": time.time(),
            "program_id": self.program_id,
            "constitution_refs": self.constitution_refs,
            "content": content,
        }
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return path

    def _record_stress_test_edges(
        self,
        session: MultiverseSession,
        branch: Branch,
        verdict: AdversaryVerdict,
    ) -> None:
        self.recorder.record_connection(
            session.cycle_id,
            session.session_id,
            branch.branch_id,
            BRANCH_STRESS_TESTED,
            metadata={
                "passed": verdict.passed,
                "fatal_flaws": verdict.fatal_flaws,
                "gbrain_signal_score": 0.65 if verdict.passed else 0.35,
                "program_id": self.program_id,
            },
        )
        self._write_observation(
            f"multiverse-council-verdict-{branch.branch_id}",
            "multiverse-council-verdict",
            {
                "session_id": session.session_id,
                "branch_id": branch.branch_id,
                "verdict": asdict(verdict),
            },
        )

    def _mark_durable(self, session: MultiverseSession) -> None:
        drive_path = getattr(self.recorder, "drive_path", None)
        if not drive_path:
            return
        from agentdrive.cognition.research_thread import write_durable_research_thread_manifest

        write_durable_research_thread_manifest(Path(drive_path), session)
        self.recorder.record_connection(
            session.cycle_id,
            session.session_id,
            f"research-thread:{session.session_id}",
            MULTIVERSE_SESSION,
            metadata={"durable": True, "gbrain_signal_score": 0.68},
        )

    def _publish_multiverse_event(self, session: MultiverseSession, *, phase: str) -> None:
        try:
            from agentdrive.mission_control.events import MultiverseUpdateEvent
            from agentdrive.mission_control.server import publish_event_sync

            publish_event_sync(
                MultiverseUpdateEvent(
                    event_type="multiverse_update",
                    timestamp=time.time(),
                    cycle_id=session.cycle_id,
                    correlation_id=session.correlation_id,
                    session_id=session.session_id,
                    phase=phase,
                    status=session.status.value,
                    branch_count=len(session.branches),
                    collapsed_branch_id=session.collapsed_branch_id,
                    invariants=[inv.statement for inv in session.invariants[:5]],
                    branches_summary=[
                        {"id": b.branch_id, "role": b.role, "robustness": b.robustness_score}
                        for b in session.branches[:8]
                    ],
                )
            )
        except Exception:
            pass

    def _save_session(self, session: MultiverseSession) -> None:
        self._sessions[session.session_id] = session
        if self._store:
            self._store.save(session)

    def _require_session(self, session_id: str) -> MultiverseSession:
        session = self.get_session(session_id)
        if not session:
            raise KeyError(f"Unknown multiverse session: {session_id}")
        return session

    def _require_branch(self, session: MultiverseSession, branch_id: str) -> Branch:
        for branch in session.branches:
            if branch.branch_id == branch_id:
                return branch
        raise KeyError(f"Unknown branch {branch_id} in session {session.session_id}")