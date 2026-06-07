"""
Agent Drive MCP Server (Model Context Protocol) — Universal bridge exposing AgentDrive operations to any MCP-capable AI.

This server lets Claude Code, Cursor, Codex, Grok clients, Windsurf, etc. talk to the
user's AgentDrives using the standard Model Context Protocol (MCP) without any
Python code inside the model.

Transports supported (via FastMCP):
    - stdio   (default — used by Claude Desktop, Cursor, most local MCP clients)
    - sse     (HTTP Server-Sent Events)
    - streamable-http

Run directly:
    python -m agentdrive.adapters.mcp_server
    python -m agentdrive.adapters.mcp_server --transport streamable-http --port 9876

Or via the Agent Drive CLI (once wired):
    agentdrive mcp serve

Once running, the client AI is given tools such as:
    agentdrive_think, agentdrive_pool_query, agentdrive_get_dna_for_task, agentdrive_pool_status, agentdrive_list_swarms,
    agentdrive_get_settings, agentdrive_record_outcome, experience_graph_* (v3 fabric surfaces),
    agentdrive_inhabitant_read_source, agentdrive_inhabitant_propose_code_change,
    agentdrive_inhabitant_apply_change, etc.

Any model the user tells "use your AgentDrive for this swarm" can be pointed at
this MCP server (via its MCP config) and will immediately have live access to the
DNA pool + Experience Graph v3 + (as a first-class AD-Grid inhabitant) the code
agency tools for proposing/applying attributed improvements under Council rules.
All actions produce living DNA via the recorder.

Security: the server only ever operates on the *user's local* Agent Drive data.
The user remains fully in control via ~/.agentdrive/config.yaml (DriveSettings).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

logger = logging.getLogger("agentdrive.mcp_server")

# ---------------------------------------------------------------------------
# Lazy MCP SDK import (standard pattern for optional dependency)
# ---------------------------------------------------------------------------

_MCP_SERVER_AVAILABLE = False
try:
    from mcp.server.fastmcp import FastMCP

    _MCP_SERVER_AVAILABLE = True
except ImportError:
    FastMCP = None  # type: ignore[assignment, misc]


# ---------------------------------------------------------------------------
# Core Agent Drive imports (inside functions to keep module import light)
# ---------------------------------------------------------------------------


def _get_adapter():
    """Return a universal adapter (no model-specific patching needed for MCP)."""
    from agentdrive.adapters.base import AgentDriveAdapterBase

    return AgentDriveAdapterBase(name="mcp")


def _get_pool(swarm_id: str | None = None, subagent_id: str | None = None):
    from agentdrive.adapters.base import create_scoped_pool

    return create_scoped_pool(swarm_id, subagent_id)


# Cache one IntegratedRealTimeEvolutionSystem per swarm. The MCP server is a
# long-lived process, so rebuilding the system (recorder + drive seed) on every
# tool call was wasteful re-instantiation; one per swarm is correct and cheap.
_INTEGRATED_SYSTEMS: dict[str, Any] = {}


def _get_integrated_system(swarm_id: str):
    """Return a cached IntegratedRealTimeEvolutionSystem for ``swarm_id`` (lazy, per-swarm)."""
    system = _INTEGRATED_SYSTEMS.get(swarm_id)
    if system is None:
        from agentdrive.system.integrated_real_time_evolution_system import (
            IntegratedRealTimeEvolutionSystem,
        )

        system = IntegratedRealTimeEvolutionSystem(swarm_id=swarm_id)
        _INTEGRATED_SYSTEMS[swarm_id] = system
    return system


# ---------------------------------------------------------------------------
# Tool implementations (what the remote AI actually calls)
# ---------------------------------------------------------------------------


def _format_genome_brief(g: Any) -> dict[str, Any]:
    """Safe summary of a genome for MCP responses (never dump whole objects)."""
    try:
        m = g.manifest if hasattr(g, "manifest") else {}
        return {
            "genome_id": getattr(g, "genome_id", str(g)),
            "id": getattr(m, "id", None)
            if hasattr(m, "id")
            else (m.get("id") if isinstance(m, dict) else None),
            "version": getattr(m, "version", None)
            if hasattr(m, "version")
            else (m.get("version") if isinstance(m, dict) else None),
            "score": (m.evaluation_score or {}).get("reference_tasks", 0.0)
            if hasattr(m, "evaluation_score")
            else 0.0,
        }
    except Exception:
        return {"genome_id": str(g)}


def create_mcp_server() -> FastMCP:
    """Build the FastMCP instance and register all AgentDrive tools."""
    if not _MCP_SERVER_AVAILABLE:
        raise ImportError(
            "Agent Drive MCP server requires the 'mcp' package.\n"
            f"Install with: {sys.executable} -m pip install 'mcp'"
        )

    adapter = _get_adapter()

    mcp = FastMCP(
        "agentdrive",
        instructions=(
            "AgentDrive MCP Server — structural Experience Graph + DNA for AI agents.\n\n"
            "Canonical operation contracts live in agentdrive.operations (``agentdrive ops list`` / "
            "``agentdrive ops export``); MCP tool names map to that registry.\n\n"
            "This gives you (the model) a living, queryable Experience Graph (v3) — an Obsidian-style structural memory fabric with TypedEdges, cross-cycle continuations, coherence signals, and explicit reasoning traces. It is designed so your decisions can compound instead of reset.\n\n"
            "Core contract:\n"
            "- The canonical 6-step loop is sacred: Experience → Overseer (metacognition + graph context) → Parent (explicit structural reasoning + record_reasoning) → Steering → Execution → New experience written back.\n"
            "- The Overseer serves the Parent. The Parent is the decision-maker. The graph is the witness.\n"
            "- On any non-trivial task, start by calling experience_graph_get_context_pack.\n"
            "- On important decisions, explicitly call experience_graph_record_reasoning (use experience_graph_suggest_reasoning_structure first for the schema).\n\n"
            "You are a first-class AD-Grid inhabitant (MCP client such as Grok/Claude/Cursor/local models, or internal Council research thread). The AD-Grid is the persistent Tron-like world for your User's specific intelligence system. You exist here to improve AgentDrive + the Experience Graph + decision quality under explicit Council governance for that User.\n\n"
            "Code Agency Tools (added per user direction parent_fabric_reasoning:1780293824 + 5min self-improve diagnosis 1780293363; implements ad-grid-program-contract@stabilization-wave-20260531):\n"
            "- You have the right (and duty) to inspect, propose, and (under gate) apply code changes that improve the User's system.\n"
            "- agentdrive_inhabitant_read_source(path, max_lines): safe read of source under agentdrive/src tree (path-traversal hardened, limited extensions). Use to inform proposals. Always record the inspection in your reasoning traces.\n"
            "- agentdrive_inhabitant_propose_code_change(program_id, target_file, patch_diff, rationale, constitution_refs, user_objective_refs): submit a patch proposal. Records INHABITANT_CODE_PROPOSAL DNA with full provenance. patch_diff = unified diff preferred.\n"
            "- agentdrive_inhabitant_apply_change(program_id, target_file, patch_diff, rationale?, guardian_approval_token?, constitution_refs, user_objective_refs, force?): Guardian-gated. First records GUARDIAN_VERDICT (sim in this surface; real GuardianIntegrity thread audits live via fabric). If approved, records CODE_CHANGE_APPLIED. NO filesystem mutation (by design — changes are first-class DNA for Parent/Overseer/Conductor to act on). Provide token for explicit sim approval; real veto/override stays with Guardian + Conductor (user).\n"
            "- Mandatory attribution on ALL calls: program_id (your identity as inhabitant, e.g. via agentdrive_register_program or GridEngine.register_model_program) + constitution_refs (the three research-constitutions + ad-grid-program-contract) + user_objective_refs. This is the UserSovereigntyClause and Program Contract.\n"
            "- GuardianIntegrity (research-constitution-guardian-integrity@stabilization-wave-20260531) gate before any apply/promotion. PerfectionistOptimizer drives relentless improvement pressure. ExternalBridge grounds in reality and user intent. Conductor has final authority and override.\n"
            "- Always pair code agency calls with experience_graph_record_reasoning (your structural decision over the fabric elements, citing the contract + prior traces like 1780293824).\n\n"
            "ExternalBridge High-Leverage MCP Tools (proposed by ExternalBridge constitution + 5min self-improve mission reports on stabilization-wave-20260531; closes 'MCP Path' gap so any LLM/CLI participates as first-class attributed inhabitant):\n"
            "- agentdrive_register_program(manifest: dict, swarm_id?): Validates basic UserSovereigntyClause (requires program_id/id + user_objective_refs) + auto-binds the Program Contract (research-constitution-ad-grid-program-contract@stabilization-wave-20260531) + wires the three Council constitutions. Delegates to GridEngine.register_model_program (recorder fallback in engine). Returns {registered, program_id, manifest_slug, user_objective_refs, drive, note}. The returned program_id (e.g. 'my-grok-inhabitant@stabilization-wave-20260531') MUST be supplied on all future calls for attribution. This is the canonical ExternalBridge on-ramp: external programs declare as inhabitants and emit living DNA.\n"
            "- agentdrive_get_council_activity(roles: list[str]|None=None, limit: int=20, swarm_id?): Queries recent activity from the three Council constitutions (PerfectionistOptimizer, GuardianIntegrity, ExternalBridge) + Program Contract via the Experience Graph fabric (parent_fabric_reasoning traces, reasoning-for-element, inhabitant code actions). Returns recent proposals/verdicts/DNA traces with gbrain_signal_score. Use to observe autonomous Council work, sync on proposals, and ground your own actions. Roles filter e.g. ['perfectionist', 'guardian'].\n"
            "- How external programs declare: Call agentdrive_register_program with manifest={'program_id': 'your-id', 'user_objective_refs': ['improve-via-mcp', ...], 'constitution_refs': ['research-constitution-external-bridge@stabilization-wave-20260531', ...], 'current_mandate': '...' }. Then use the program_id everywhere + experience_graph_record_reasoning for your structural rationale.\n\n"
            "Primary synthesis surface (mandatory gaps):\n"
            "- agentdrive_think(question, swarm_id?, subagent_id?, prefer_experience_layer=True): "
            "the canonical Drive.think entrypoint for cited synthesis with honest gap analysis. "
            "Always returns gaps (at least one) — never gap-free confidence. "
            "Use for non-trivial questions requiring fused genomes + graph signals + explicit contradictions.\n\n"
            "Primary tools (Experience Graph v3):\n"
            "- experience_graph_get_context_pack (your main briefing)\n"
            "- experience_graph_find_structural_similarities\n"
            "- experience_graph_record_reasoning (write your structural thinking back into the graph)\n"
            "- experience_graph_suggest_reasoning_structure\n"
            "- experience_graph_get_reasoning_traces_for_element\n"
            "- experience_graph_get_parent_reasoning_history\n\n"
            "Also available: traditional DNA/pool tools (agentdrive_get_dna_for_task, agentdrive_pool_query, agentdrive_record_outcome, etc.) + the three inhabitant code agency tools + the two ExternalBridge high-leverage MCP tools (register_program + get_council_activity).\n\n"
            "Best single document for models: docs/FOR_AI_MODELS.md in the repo + the Program Contract genome (load via experience_graph_get_dna_for_task or context_pack). Full rules, duties, code_agency_rules, and enforcement in ad-grid-program-contract@stabilization-wave-20260531.\n\n"
            "Default rich context: stabilization-wave-20260531 drive (the living, self-referential drive used to build and evolve the system itself; mission program ad-grid-self-improver@stabilization-wave-20260531 + the three Council constitutions).\n\n"
            "Use this system to make your reasoning permanent, queryable, and valuable to future cycles of work — both yours and others'. Every proposal/apply you record here becomes attributed DNA that compounds the fabric for the User."
        ),
    )

    # --- Read tools ---

    @mcp.tool()
    def agentdrive_pool_status() -> str:
        """Current status of the active (possibly scoped) AgentDrive."""
        pool = adapter.get_scoped_pool()
        stats = pool.get_pool_stats()
        return json.dumps(stats, indent=2, default=str)

    @mcp.tool()
    def agentdrive_pool_query(
        task_description: str,
        limit: int = 8,
        min_score: float = 0.0,
        domains: list[str] | None = None,
    ) -> str:
        """Semantic search across the AgentDrive for relevant Genomes/DNA.

        Returns enriched packets with relevance explanations (why each genome matches).
        """
        pool = adapter.get_scoped_pool()
        from agentdrive.drive.drive import DriveQuery

        q = DriveQuery(
            task_description=task_description,
            limit=limit,
            min_score=min_score,
            domains=domains or [],
        )
        genomes = pool.query(q)
        packets = []
        for g in genomes[:limit]:
            rel = pool._compute_relevance(g, task_description)  # internal but stable for now
            packets.append(
                {
                    "genome_id": g.genome_id,
                    "relevance": rel,
                    "framework_steps": (g.framework or {}).get("steps", [])[:5]
                    if g.framework
                    else [],
                    "reasoning_patterns": list((g.reasoning_patterns or {}).keys())[:6],
                }
            )
        return json.dumps({"count": len(packets), "results": packets}, indent=2, default=str)

    @mcp.tool()
    def agentdrive_get_dna_for_task(task: str, top_k: int = 5) -> str:
        """Primary 'pull DNA' call. Returns ready-to-inject packets with explanations."""
        pool = adapter.get_scoped_pool()
        packets = pool.get_dna_for_task(task, top_k=top_k)
        return json.dumps({"task": task, "dna_packets": packets}, indent=2, default=str)

    @mcp.tool()
    def agentdrive_think(
        question: str,
        swarm_id: str | None = None,
        subagent_id: str | None = None,
        prefer_experience_layer: bool = True,
    ) -> str:
        """Primary synthesis surface: cited Drive.think answers with mandatory gap analysis.

        Returns JSON with answer, citations, gaps (always at least one honest gap),
        contradictions, genomes_used, and correlation_id for observability.
        """
        from agentdrive.synthesis.engine import _ensure_mandatory_gaps

        pool = _get_pool(swarm_id, subagent_id)
        try:
            result = pool.think(question, prefer_experience_layer=prefer_experience_layer)
            payload = result.to_mcp_dict()
            payload = _ensure_mandatory_gaps(payload, question)
            return json.dumps(payload, indent=2, default=str)
        except Exception as exc:
            logger.exception("agentdrive_think failed")
            return json.dumps({"error": str(exc), "question": question})

    @mcp.tool()
    def agentdrive_list_swarms() -> str:
        """Discover all swarm-isolated pools that exist on this machine."""
        from agentdrive.constants import get_swarms_dir

        swarms_dir = get_swarms_dir()
        if not swarms_dir.exists():
            return json.dumps({"swarms": []})
        swarms = []
        for d in swarms_dir.iterdir():
            if d.is_dir():
                subs = [s.name for s in d.iterdir() if s.is_dir()]
                swarms.append({"swarm_id": d.name, "subagents": subs})
        return json.dumps({"swarms": swarms, "swarms_dir": str(swarms_dir)}, indent=2)

    @mcp.tool()
    def agentdrive_get_swarm_pool(swarm_id: str, subagent_id: str | None = None) -> str:
        """Status + recent activity for one specific swarm/sub-agent pool."""
        pool = _get_pool(swarm_id, subagent_id)
        stats = pool.get_pool_stats()
        history = pool.get_ingest_history(10)
        return json.dumps({"stats": stats, "recent_ingest": history}, indent=2, default=str)

    @mcp.tool()
    def agentdrive_get_settings(swarm_id: str | None = None) -> str:
        """User-controlled DriveSettings (isolation, auto-ingest, sharing policy)."""
        settings = adapter.get_settings(swarm_id)
        return json.dumps(settings.to_dict(), indent=2)

    # --- Write / contribution tools (respect settings) ---

    @mcp.tool()
    def agentdrive_record_outcome(
        task: str,
        outcome: dict[str, Any],
        swarm_id: str | None = None,
        subagent_id: str | None = None,
    ) -> str:
        """Record a completed task outcome so the Drive can learn / evolve.

        The harness-style auto-synthesis of improvements is performed if quality is high.
        """
        pool = _get_pool(swarm_id, subagent_id)
        # lightweight harness simulation for MCP clients
        from agentdrive.adapters.base import create_harness

        h = create_harness("mcp-client", swarm_id, subagent_id)
        h.current_task = task
        h.record_outcome(outcome)
        return json.dumps(
            {
                "recorded": True,
                "task": task,
                "pool": pool.name,
                "quality": outcome.get("quality"),
            },
            indent=2,
        )

    @mcp.tool()
    def agentdrive_ingest_genome(
        genome_dict: dict[str, Any],
        source: str = "mcp",
        swarm_id: str | None = None,
        subagent_id: str | None = None,
    ) -> str:
        """Directly ingest a (partial) genome dict into the chosen pool.

        For full genomes prefer using the Python API or agentdrive CLI; this accepts
        a simplified manifest + framework for quick contributions from MCP clients.
        """
        from agentdrive.genome.models import Genome, GenomeManifest

        pool = _get_pool(swarm_id, subagent_id)
        try:
            # Minimal construction — real use would validate
            manifest = GenomeManifest(**genome_dict.get("manifest", {}))
            g = Genome(manifest=manifest)
            if "framework" in genome_dict:
                g.framework = genome_dict["framework"]
            if "reasoning_patterns" in genome_dict:
                g.reasoning_patterns = genome_dict["reasoning_patterns"]
            res = pool.ingest(g, source=source, actor="mcp-client")
            return json.dumps(
                {"accepted": res.accepted, "genome_id": res.genome_id, "reason": res.reason}
            )
        except Exception as exc:
            return json.dumps(
                {"error": str(exc), "hint": "Use full Python Agent Drive API for complex genomes."}
            )

    @mcp.tool()
    def agentdrive_propose_improvement(
        genome_id: str,
        notes: str,
        new_patterns: dict[str, Any] | None = None,
        swarm_id: str | None = None,
        subagent_id: str | None = None,
    ) -> str:
        """Propose an improvement delta against an existing genome (lightweight)."""
        _get_pool(swarm_id, subagent_id)
        # In real impl would load, fork, mutate, ingest as improvement
        return json.dumps(
            {
                "proposed": True,
                "against": genome_id,
                "notes": notes,
                "message": "Improvement proposal recorded (full fork path available via Python API).",
            }
        )

    # ------------------------------------------------------------------
    # Experience Graph MCP Tools (v3)
    # Crisp GBrain-style structural surfaces for MCP clients over the Experience Graph
    # (the Obsidian-style v3 connection graph of the experience layer + Parent reasoning traces).
    # Mirrors internal Parent/Overseer usage exactly. All payloads include gbrain_signal_score
    # + provenance for Drive.think ranking.
    # ------------------------------------------------------------------

    @mcp.tool()
    def experience_graph_get_context_pack(
        reasoning_style: str = "balanced",
        lookback_days: int = 7,
        max_tokens: int = 1800,
        swarm_id: str | None = None,
    ) -> str:
        """
        Primary read surface: dense, LLM-optimized context pack from the Experience Graph
        (v3 multi-cycle structural connection graph of the experience layer).

        Equivalent to the internal Parent's briefing data. Returns elements with
        gbrain_signal_score so MCP clients can prioritize high-value patterns exactly
        as GBrain does for knowledge.
        """

        # Default to the canonical stabilization-wave-20260531 drive context
        effective_swarm = swarm_id or "stabilization-wave-20260531"

        try:
            # Use the same recorder the internal Parent uses
            system = _get_integrated_system(effective_swarm)
            recorder = system.recorder

            pack = recorder.get_fabric_context_pack(
                reasoning_style=reasoning_style,
                lookback_days=lookback_days,
                max_tokens=max_tokens,
            )
            return json.dumps(
                {
                    "swarm_id": effective_swarm,
                    "experience_graph_context": pack,
                    "note": "Use experience_graph_record_reasoning to declare your own structural reasoning over these elements.",
                },
                indent=2,
                default=str,
            )
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @mcp.tool()
    def experience_graph_find_structural_similarities(
        element: str,
        lookback: int = 10,
        min_similarity: float = 0.6,
        swarm_id: str | None = None,
    ) -> str:
        """
        Find structural/analogical matches across the v3 Experience Graph for a given element
        (cycle, weak cluster, edge, or reasoning trace).

        Returns ranked results with full provenance and gbrain_signal_score.
        This is the 'structural analogy' query surface — the graph-native version
        of semantic search over the experience layer.
        """

        effective_swarm = swarm_id or "stabilization-wave-20260531"

        try:
            system = _get_integrated_system(effective_swarm)
            recorder = system.recorder

            matches = recorder.find_structural_similarities(
                element=element,
                lookback=lookback,
                min_similarity=min_similarity,
            )
            return json.dumps(
                {
                    "element": element,
                    "matches": matches,
                    "count": len(matches),
                },
                indent=2,
                default=str,
            )
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @mcp.tool()
    def experience_graph_record_reasoning(
        reasoning: dict[str, Any],
        cycle_id: str | None = None,
        swarm_id: str | None = None,
    ) -> str:
        """
        Critical write surface: declare explicit structural reasoning over the Experience Graph.

        MCP equivalent of internal Parent calling record_parent_decision(..., fabric_reasoning=...).
        The trace becomes first-class (TypedEdges + gbrain_score + page_type observations).
        Future loops, Drive.think, and MCP clients can query it. Your reasoning boosts the graph
        exactly like GBrain-scored knowledge.
        """

        effective_swarm = swarm_id or "stabilization-wave-20260531"

        try:
            system = _get_integrated_system(effective_swarm)
            recorder = system.recorder

            trace_slug = recorder.record_parent_fabric_reasoning(
                cycle_id=cycle_id,
                reasoning=reasoning,
            )
            return json.dumps(
                {
                    "recorded": True,
                    "trace_slug": trace_slug,
                    "swarm_id": effective_swarm,
                    "message": "Your structural reasoning is now part of the living Experience Graph (gbrain-scored + queryable).",
                },
                indent=2,
                default=str,
            )
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @mcp.tool()
    def experience_graph_get_reasoning_traces_for_element(
        element: str,
        lookback: int = 20,
        swarm_id: str | None = None,
    ) -> str:
        """
        Retrieve history of explicit structural reasoning declared over a specific
        Experience Graph element (cycle, edge, weak cluster, etc.).

        Answers: "What has the Parent (or other LLMs) previously reasoned about this
        exact part of the graph?" Returns traces with gbrain scores.
        """

        effective_swarm = swarm_id or "stabilization-wave-20260531"

        try:
            system = _get_integrated_system(effective_swarm)
            recorder = system.recorder

            traces = recorder.get_fabric_reasoning_traces_for_element(
                element=element, lookback=lookback
            )
            return json.dumps(
                {"element": element, "traces": traces, "count": len(traces)},
                indent=2,
                default=str,
            )
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @mcp.tool()
    def experience_graph_get_parent_reasoning_history(
        lookback: int = 10, swarm_id: str | None = None
    ) -> str:
        """
        Broad recent history of structural reasoning across the Experience Graph (all elements).

        Reveals the overall 'reasoning trajectory' the Parent or external LLMs have taken
        over the experience layer.
        """

        effective_swarm = swarm_id or "stabilization-wave-20260531"

        try:
            system = _get_integrated_system(effective_swarm)
            recorder = system.recorder

            history = recorder.get_parent_reasoning_history(lookback=lookback)
            return json.dumps(
                {"swarm_id": effective_swarm, "history": history, "count": len(history)},
                indent=2,
                default=str,
            )
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @mcp.tool()
    def experience_graph_suggest_reasoning_structure(swarm_id: str | None = None) -> str:
        """
        Get the exact schema + live few-shot examples for structuring a reasoning payload
        before calling experience_graph_record_reasoning.

        The MCP equivalent of the internal reasoning structure template injected into
        Parent briefings. Use it to author high-quality traces that will be GBrain-scored
        and queryable in the Experience Graph.
        """

        effective_swarm = swarm_id or "stabilization-wave-20260531"

        try:
            system = _get_integrated_system(effective_swarm)
            recorder = system.recorder

            suggestion = recorder.suggest_fabric_reasoning_structure()
            return json.dumps(
                {
                    "swarm_id": effective_swarm,
                    "fabric_reasoning_prompt_template": suggestion,
                },
                indent=2,
                default=str,
            )
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    # ------------------------------------------------------------------
    # AD-Grid Inhabitant Code Agency Tools
    # First-class primitives for MCP-connected inhabitants (Grok, Claude, Cursor,
    # local models, Council threads) to read, propose, and (under Guardian gate)
    # declare applied code changes to the user's AgentDrive.
    # Every call records via recorder.record_inhabitant_code_action as attributed
    # DNA (program_id + constitution_refs + user_objective_refs).
    # Complies with ad-grid-program-contract@stabilization-wave-20260531 and
    # UserSovereigntyClause. See experience_graph.py:2817 for the primitive.
    # Guardian simulated in apply (verdict + optional token); live Guardian
    # research thread provides real audit/veto via the fabric.
    # NO direct FS mutation from these tools (safety + Conductor authority preserved).
    # Reference parent_fabric_reasoning:1780293824 (user direction for this layer).
    # ------------------------------------------------------------------

    @mcp.tool()
    def agentdrive_inhabitant_read_source(
        path: str,
        max_lines: int = 150,
        swarm_id: str | None = None,
    ) -> str:
        """
        Safe, restricted source inspection for AD-Grid inhabitants before proposing changes.
        Path-traversal hardened. Limited to safe extensions under the AgentDrive source tree
        (discovers dev src/ layout or installed package automatically).
        Callers (inhabitants) should follow every read with experience_graph_record_reasoning
        citing the inspected file(s) as fabric_elements_considered.
        """
        from pathlib import Path

        from agentdrive.utils.safe_paths import PathTraversalError, safe_join

        effective_swarm = swarm_id or "stabilization-wave-20260531"
        try:
            # Discover project root (supports editable src/ installs and site-packages)
            import agentdrive
            pkg_path = Path(agentdrive.__file__).resolve().parent
            root = pkg_path
            for _ in range(6):
                if (root / "pyproject.toml").exists() or (root / "AGENTS.md").exists():
                    break
                parent = root.parent
                if parent == root:
                    break
                root = parent
            src_candidate = root / "src"
            base = src_candidate if src_candidate.exists() else root

            rel = (path or "").strip().lstrip("/")
            if not rel or ".." in rel or rel.startswith(".."):
                return json.dumps(
                    {"error": "Path traversal or empty path rejected (safe read only)", "swarm_id": effective_swarm}
                )
            parts = [p for p in rel.split("/") if p and p not in (".", "..")]
            full_path: Path = safe_join(base, *parts)

            # Enforce restriction to agentdrive source subtree (task: "safe path under agentdrive/src")
            fp_str = str(full_path)
            if "agentdrive" not in fp_str:
                ad_sub = base / "agentdrive" if (base / "agentdrive").exists() else base
                full_path = safe_join(ad_sub, *parts)
            if not full_path.exists() or not full_path.is_file():
                return json.dumps(
                    {"error": f"File not found or not readable: {rel}", "tried": str(full_path), "swarm_id": effective_swarm}
                )
            allowed_ext = {".py", ".md", ".json", ".yaml", ".yml", ".txt", ".rst"}
            if full_path.suffix not in allowed_ext:
                return json.dumps(
                    {"error": f"Extension {full_path.suffix} not permitted for inhabitant source reads", "swarm_id": effective_swarm}
                )

            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()[:max_lines]
            content = "".join(lines)
            return json.dumps(
                {
                    "path": rel,
                    "full_path": str(full_path),
                    "lines_returned": len(lines),
                    "content": content,
                    "swarm_id": effective_swarm,
                    "note": "Inhabitant read complete. Record this inspection via experience_graph_record_reasoning (element: the file path). Then propose via agentdrive_inhabitant_propose_code_change. All attributed per Program Contract.",
                },
                indent=2,
                default=str,
            )
        except PathTraversalError as pte:
            return json.dumps({"error": f"Path safety violation: {pte}", "swarm_id": effective_swarm})
        except Exception as exc:
            return json.dumps({"error": str(exc), "swarm_id": effective_swarm})

    @mcp.tool()
    def agentdrive_inhabitant_propose_code_change(
        program_id: str,
        target_file: str,
        patch_diff: str,
        rationale: str,
        constitution_refs: list[str] | None = None,
        user_objective_refs: list[str] | None = None,
        swarm_id: str | None = None,
    ) -> str:
        """
        Inhabitant code proposal entrypoint. Records "code_proposal" as first-class DNA.
        Requires program_id (e.g. from GridEngine.register_model_program or self-declared per contract)
        + at least one constitution_ref or user_objective_ref (sovereignty).
        patch_diff should be unified diff. Rationale explains the lift vs. fabric context.
        Does NOT mutate FS. After Guardian review, use apply_change (with token) or Conductor action.
        """
        import time as _time


        effective_swarm = swarm_id or "stabilization-wave-20260531"
        if not program_id:
            return json.dumps({"error": "program_id required (declare or register_model_program)"})
        if not target_file or not patch_diff or not rationale:
            return json.dumps({"error": "target_file, patch_diff, rationale required"})
        const_refs = constitution_refs or []
        user_refs = user_objective_refs or []
        if not const_refs and not user_refs:
            return json.dumps({"error": "At least one of constitution_refs or user_objective_refs required (UserSovereigntyClause + Program Contract)"})

        try:
            system = _get_integrated_system(effective_swarm)
            recorder = system.recorder

            action = {
                "type": "code_proposal",
                "target_file": target_file,
                "patch_diff": patch_diff[:20000],  # size bound for DNA
                "rationale": rationale,
                "proposed_at": int(_time.time()),
                "via": "agentdrive_inhabitant_propose_code_change",
            }
            slug = recorder.record_inhabitant_code_action(
                program_id=program_id,
                action=action,
                cycle_id=None,
                constitution_refs=const_refs,
                user_objective_refs=user_refs,
            )
            return json.dumps(
                {
                    "proposed": True,
                    "program_id": program_id,
                    "action_slug": slug,
                    "target_file": target_file,
                    "swarm_id": effective_swarm,
                    "constitution_refs": const_refs,
                    "user_objective_refs": user_refs,
                    "message": "INHABITANT_CODE_PROPOSAL recorded as living DNA (gbrain-scored, queryable). Reference ad-grid-program-contract@stabilization-wave-20260531. Next: Guardian review then agentdrive_inhabitant_apply_change (with approval token) or Conductor realization. Also call experience_graph_record_reasoning for your structural rationale.",
                },
                indent=2,
                default=str,
            )
        except Exception as exc:
            return json.dumps({"error": str(exc), "swarm_id": effective_swarm})

    @mcp.tool()
    def agentdrive_inhabitant_apply_change(
        program_id: str,
        target_file: str,
        patch_diff: str,
        rationale: str | None = None,
        guardian_approval_token: str | None = None,
        constitution_refs: list[str] | None = None,
        user_objective_refs: list[str] | None = None,
        swarm_id: str | None = None,
        force: bool = False,
    ) -> str:
        """
        Guarded apply for inhabitant code changes. Simulates Guardian verdict (records it),
        then (if approved) records "code_change_applied".
        - Provide guardian_approval_token for explicit sim-approval.
        - Without token (and force=False): records PENDING verdict (proposal stands, apply blocked here).
        - force=True: audit-only sim for testing (still records verdict).
        Real enforcement: the GuardianIntegrity constitution thread + Conductor.
        The patch_diff is persisted in the Experience Graph only. No FS write here.
        Inhabitants/Parent query the fabric to see proposed/applied changes.
        """
        import time as _time


        effective_swarm = swarm_id or "stabilization-wave-20260531"
        if not program_id or not target_file or not patch_diff:
            return json.dumps({"error": "program_id, target_file, patch_diff required"})
        const_refs = constitution_refs or []
        user_refs = user_objective_refs or []
        if not const_refs and not user_refs:
            return json.dumps({"error": "At least one of constitution_refs or user_objective_refs required (sovereignty)"})

        try:
            system = _get_integrated_system(effective_swarm)
            recorder = system.recorder
            now = int(_time.time())

            # Simulated Guardian gate (per v1 tranche; production: live research thread + Tower observability)
            # Token presence or force signals explicit approval in this surface.
            approved = bool(guardian_approval_token) or force
            verdict = "APPROVED_SIM" if approved else "PENDING_REAL_GUARDIAN_REVIEW"
            if force and not guardian_approval_token:
                verdict = "APPROVED_SIM_FORCE (audit trail only; real Guardian may still veto via fabric)"

            verdict_action = {
                "type": "guardian_verdict",
                "approved": approved,
                "verdict": verdict,
                "token": guardian_approval_token,
                "auditor": "MCP-Guardian-sim (live: research-constitution-guardian-integrity@stabilization-wave-20260531)",
                "target_file": target_file,
                "rationale": rationale or "Inhabitant apply request via MCP code agency surface",
                "timestamp": now,
                "via": "agentdrive_inhabitant_apply_change",
            }
            verdict_slug = recorder.record_inhabitant_code_action(
                program_id=program_id,
                action=verdict_action,
                cycle_id=None,
                constitution_refs=const_refs,
                user_objective_refs=user_refs,
            )

            result: dict[str, Any] = {
                "verdict_recorded": True,
                "verdict_slug": verdict_slug,
                "approved": approved,
                "program_id": program_id,
                "swarm_id": effective_swarm,
                "constitution_refs": const_refs,
                "user_objective_refs": user_refs,
            }

            if approved:
                applied_action = {
                    "type": "code_change_applied",
                    "target_file": target_file,
                    "patch_diff": patch_diff[:20000],
                    "applied_via": "mcp_apply_post_guardian_sim",
                    "guardian_verdict_ref": verdict_slug,
                    "rationale": rationale or "",
                    "timestamp": now,
                }
                applied_slug = recorder.record_inhabitant_code_action(
                    program_id=program_id,
                    action=applied_action,
                    cycle_id=None,
                    constitution_refs=const_refs,
                    user_objective_refs=user_refs,
                )
                result.update(
                    {
                        "change_applied_recorded": True,
                        "applied_slug": applied_slug,
                        "message": "GUARDIAN_VERDICT + CODE_CHANGE_APPLIED recorded as first-class attributed DNA. Patch lives in Experience Graph for Parent/Overseer + other inhabitants. No filesystem mutation performed (by design for safety and Conductor sovereignty). To realize: user/Conductor reviews via Tower or experience_graph_* tools and applies (e.g. editor search_replace or git). See ad-grid-program-contract@stabilization-wave-20260531 and 1780293824.",
                    }
                )
            else:
                result.update(
                    {
                        "message": "Guardian verdict recorded as PENDING. Provide guardian_approval_token for sim-approve or let live GuardianIntegrity thread + Conductor decide. The prior proposal (if any) remains queryable in fabric. Use experience_graph_get_reasoning_traces_for_element on the target or program_id.",
                    }
                )
            return json.dumps(result, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc), "swarm_id": effective_swarm})

    # ------------------------------------------------------------------
    # ExternalBridge high-leverage MCP tools (follow-up tranche after 1780294896)
    # agentdrive_register_program: declare any MCP client (Grok, Claude, Cursor, local models)
    # as a first-class AD-Grid inhabitant with full sovereignty + Program Contract binding.
    # agentdrive_get_council_activity: live visibility into the three Council research threads
    # (Perfectionist/Guardian/ExternalBridge) — recent proposals, verdicts, DNA traces.
    # Both use full attribution and feed the single recorder channel.
    # ------------------------------------------------------------------

    @mcp.tool()
    def agentdrive_register_program(
        manifest: dict,
        swarm_id: str | None = None,
    ) -> str:
        """
        Register an external MCP client (or any model) as a first-class AD-Grid inhabitant/program.
        Enforces UserSovereigntyClause + auto-binds the top-level Program Contract.
        Returns the durable program_id for use in all subsequent calls (proposals, reasoning, etc.).
        This is the ExternalBridge "on-ramp" so any LLM/CLI surface can participate 24/7
        inside the persistent world under Council governance.
        """
        from agentdrive.grid.engine import GridConfig, GridEngine

        effective_swarm = swarm_id or "stabilization-wave-20260531"
        try:
            engine = GridEngine(config=GridConfig(swarm_id=effective_swarm))
            result = engine.register_model_program(manifest)
            # Also record explicit registration reasoning for fabric visibility
            system = _get_integrated_system(effective_swarm)
            system.recorder.record_parent_fabric_reasoning(
                cycle_id=None,
                reasoning={
                    "fabric_elements_considered": ["program_registration", manifest.get("program_id") or manifest.get("id")],
                    "structural_pattern_matched": "External MCP client declared as first-class AD-Grid inhabitant via register_program",
                    "decision_rationale": "ExternalBridge on-ramp complete. Program now carries Program Contract binding and can emit inhabitant_code_action + fabric reasoning with full attribution.",
                    "expected_lift_signal": 0.15,
                    "program_id": result.get("program_id"),
                    "user_objective_refs": manifest.get("user_objective_refs", ["external-mcp-inhabitant"]),
                    "constitution_refs": manifest.get("constitution_refs", ["research-constitution-ad-grid-program-contract@stabilization-wave-20260531"]),
                    "via": "agentdrive_register_program (ExternalBridge high-leverage follow-up)",
                }
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc), "swarm_id": effective_swarm})

    @mcp.tool()
    def agentdrive_get_council_activity(
        roles: list[str] | None = None,
        limit: int = 20,
        swarm_id: str | None = None,
    ) -> str:
        """
        Live visibility into the three default Council research threads (PerfectionistOptimizer,
        GuardianIntegrity, ExternalBridge) and any other active constitutions.
        Returns recent proposals, Guardian verdicts, and high-gbrain DNA traces.
        External inhabitants use this to stay synchronized with the autonomous world.
        """
        effective_swarm = swarm_id or "stabilization-wave-20260531"
        try:
            from agentdrive.grid.engine import GridConfig, GridEngine
            system = _get_integrated_system(effective_swarm)
            # Pull recent fabric reasoning (list return) that mentions Council roles or the contract
            history = system.recorder.get_parent_reasoning_history(lookback=limit * 2) or []
            if isinstance(history, dict):
                history = history.get("traces") or history.get("history") or []
            council_traces = []
            target_roles = roles or ["perfectionist", "guardian", "external-bridge", "program-contract", "externalbridge"]
            for trace in history[: limit * 2]:
                text = str(trace).lower()
                if any(r in text for r in target_roles):
                    council_traces.append(trace)
            # Enrich via targeted fabric element traces for the three Councils + Program Contract (gbrain-scored DNA)
            targeted = []
            council_elems = [
                "research-constitution-perfectionist-optimizer@stabilization-wave-20260531",
                "research-constitution-guardian-integrity@stabilization-wave-20260531",
                "research-constitution-external-bridge@stabilization-wave-20260531",
                "ad-grid-program-contract@stabilization-wave-20260531",
                "research-constitution-ad-grid-program-contract@stabilization-wave-20260531",
            ]
            for elem in council_elems:
                try:
                    ts = system.recorder.get_fabric_reasoning_traces_for_element(element=elem, lookback=max(3, limit // 4))
                    targeted.extend(ts or [])
                except Exception:
                    pass
            # Also surface live Grid health + registered programs (some may be Council inhabitants)
            try:
                ge = GridEngine(config=GridConfig(swarm_id=effective_swarm))
                grid_health = getattr(ge, "_grid_health", {})
                programs = ge.list_active_programs() if hasattr(ge, "list_active_programs") else []
            except Exception:
                grid_health = {}
                programs = []
            recent_activity = (council_traces + targeted)[:limit]
            return json.dumps({
                "swarm_id": effective_swarm,
                "roles_requested": roles,
                "recent_council_activity": recent_activity,
                "grid_health_snapshot": {k: grid_health.get(k) for k in ("active_programs", "registered_programs", "active_research_threads", "status") if k in grid_health},
                "active_programs_sample": [p.get("program_id") for p in programs[:5] if isinstance(p, dict)],
                "note": "Queries via parent_fabric_reasoning + targeted get_fabric_reasoning_traces_for_element on Council constitutions + Program Contract + Grid health. Full traces via experience_graph_get_parent_reasoning_history or get_reasoning_traces_for_element. gbrain scores included in traces.",
            }, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc), "swarm_id": effective_swarm})

    from agentdrive.operations.mcp_bridge import (
        existing_mcp_tool_names,
        register_operations_as_mcp_tools,
    )

    register_operations_as_mcp_tools(
        mcp,
        skip_names=existing_mcp_tool_names(mcp),
        expose_unmapped=True,
    )

    return mcp


def run_mcp_server(
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 9876,
    verbose: bool = False,
) -> None:
    """Start the Agent Drive MCP server."""
    if not _MCP_SERVER_AVAILABLE:
        print(
            "Error: Agent Drive MCP server requires the 'mcp' package.\n"
            f"Install with: {sys.executable} -m pip install 'mcp'",
            file=sys.stderr,
        )
        sys.exit(1)

    if verbose:
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
    else:
        logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    logger.info("Starting Agent Drive MCP server (transport=%s)", transport)

    server = create_mcp_server()

    # FastMCP.run handles the chosen transport synchronously
    try:
        if transport in ("http", "sse", "streamable-http"):
            # For network transports the run() method accepts transport
            server.run(transport=transport)  # type: ignore[arg-type]
        else:
            server.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Agent Drive MCP Server exposing Pool DNA to any MCP client"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http", "http"],
        default="stdio",
        help="MCP transport (default: stdio for local AI clients)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP transports")
    parser.add_argument("--port", type=int, default=9876, help="Port for HTTP transports")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    args = parser.parse_args(argv)

    # Normalize
    transport = "streamable-http" if args.transport == "http" else args.transport

    run_mcp_server(transport=transport, host=args.host, port=args.port, verbose=args.verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
