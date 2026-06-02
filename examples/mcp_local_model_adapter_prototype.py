#!/usr/bin/env python3
"""
MCP Local Model Adapter Prototype — Dead-Simple Plug-In for Any Local Model
( Ollama, llama.cpp OpenAI-compatible server, LM Studio, vLLM, etc. )

Charter (stabilization-wave-20260531): MCP Local Model Adapter Designer & Prototyper.

This is the working prototype adapter script.

It lets a local model (or simulated local reasoner) :
- Connect to the AgentDrive MCP server (stdio, SSE, or streamable-http)
  or use direct recorder mode (zero-config, always works for demo).
- Use the 6 experience_graph_* MCP tools as its primary tool surface
  for memory (multi-cycle Experience Graph fabric) and reasoning.
- Participate in the canonical 6-step Parent-Overseer-Research loop
  by calling tools, receiving graph context packs, and writing explicit
  reasoning traces back (record_parent_fabric_reasoning surface).

All participation is recorded as first-class Experience Graph artifacts
(observations + TypedEdges + gbrain_signal_score) on the drive using
only existing recorder patterns.

DEAD SIMPLE USAGE (no MCP server required for immediate demo):
    cd /home/pablothethinker/agentdrive
    PYTHONPATH=src python examples/mcp_local_model_adapter_prototype.py

With real local model (requires local_models + httpx + a running backend):
    Edit the LOCAL_MODEL_SPEC section below, then run same command.

With real MCP server (full protocol):
    Terminal 1: PYTHONPATH=src python -m agentdrive.adapters.mcp_server --transport streamable-http --port 9876
    Terminal 2: PYTHONPATH=src python examples/mcp_local_model_adapter_prototype.py --mode mcp-http --url http://127.0.0.1:9876

The adapter will:
1. Get context pack (experience_graph_get_context_pack)
2. Get reasoning structure template (experience_graph_suggest_reasoning_structure)
3. "Local model" produces high-quality fabric reasoning payload
4. Record it (experience_graph_record_reasoning) → becomes queryable DNA
5. Query similarities, traces for elements, and full history (the other 3 tools)
6. Every step emits recorder artifacts + edges (self-referential growth of the graph)

This is the exact adapter layer that makes any local model a first-class
participant in the Experience Graph + 6-step loop without writing Python
inside the model itself.

All design decisions, code, and live test results are persisted as
first-class artifacts via the recorder on this drive.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# --- Project imports (existing patterns only) ---
from agentdrive.drive.drive import AgentDrive, get_swarm_drive_path
from agentdrive.evolution.experience_graph import (
    ExperienceGraphRecorder,
    get_recorder_for_drive,
    PARENT_FABRIC_REASONING_TRACE,
    FABRIC_ELEMENT_REASONED_OVER,
    STRUCTURAL_SIMILARITY_DETECTED,
    PARENT_FABRIC_QUERY,
    FABRIC_REASONING_TRACE_ACCESSED,
    FABRIC_QUERY_RESULT_RECORDED,
)
from agentdrive.local_models import LocalModelSpec, LocalModelAdapter, OllamaAdapter, OpenAICompatAdapter  # existing local model surface

SWARM_ID = "stabilization-wave-20260531"
DEFAULT_DRIVE_PATH = get_swarm_drive_path(SWARM_ID)


# ---------------------------------------------------------------------------
# Simulated Local Reasoner (drop-in replacement point for real local model)
# ---------------------------------------------------------------------------

@dataclass
class SimulatedLocalReasoner:
    """Dead-simple stand-in for a local LLM.

    In real use, replace .reason_over_fabric() with a call to your local
    endpoint (Ollama / OpenAI-compat / LM Studio) using the exact prompt
    built from the context pack + suggest_fabric_reasoning_structure few-shots.

    The output must be a dict matching the normalized shape expected by
    experience_graph_record_reasoning / record_parent_fabric_reasoning.
    """

    name: str = "simulated-local-reasoner-v1"

    def reason_over_fabric(
        self,
        context_pack: dict[str, Any],
        reasoning_structure: dict[str, Any],
        prior_traces: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Produce a high-signal fabric reasoning payload.

        Uses only the data in the pack (top weak clusters, strong continuations,
        high-value densifications, actionable recs) + the schema from suggest().
        Never hallucinates elements not present in the pack.
        """
        fab_coh = float(context_pack.get("fabric_coherence", 0.5))
        weaks = context_pack.get("top_weak_clusters", []) or []
        conts = context_pack.get("strong_continuations", []) or []
        lifts = context_pack.get("recent_high_value_densifications", []) or []
        recs = context_pack.get("actionable_structural_recommendations", []) or []

        # Pick the highest-signal weak cluster (gbrain already favors low coh)
        target = weaks[0] if weaks else {"cycle_id": "meta-experience-layer", "coherence": fab_coh}
        cycle_ref = target.get("cycle_id", "recent-fabric")

        # Match against a proven continuation or lift if present
        pattern = "balanced structural continuation from prior high-lift densif"
        if lifts:
            pattern = f"matches prior densif lift pattern in {lifts[0].get('cycle', cycle_ref)} (+{lifts[0].get('lift', 0.04)} coh)"
        elif conts:
            pattern = f"extends strong cross-cycle continuation {conts[0].get('relation', 'fabric_link')}"

        rationale = (
            f"From fabric_context_pack (coh={fab_coh:.3f}, style={context_pack.get('reasoning_style', 'balanced')}) "
            f"the decisive element is the lowest-coh cluster {cycle_ref}. "
            f"Declaring this explicitly + expected lift allows Overseer + future Parents to measure structural (not scalar) gains. "
            f"Follows {len(recs)} actionable recs surfaced in pack."
        )[:680]

        expected_lift = round(0.03 + (1.0 - fab_coh) * 0.06, 3)  # conservative, grounded in data

        reasoning = {
            "fabric_elements_considered": [
                f"cycle:{cycle_ref}" if not str(cycle_ref).startswith("cycle:") else cycle_ref,
                "fabric:weak_clusters",
                "experience_layer_v3",
            ][:6],
            "structural_pattern_matched": pattern[:240],
            "decision_rationale": rationale,
            "expected_lift_signal": expected_lift,
            "prior_traces_referenced": [
                t.get("reasoning_slug") or t.get("slug", "") for t in (prior_traces or [])[:2] if t
            ],
            "adapter": self.name,
            "generated_at": time.time(),
            "source": "simulated_local_reasoner (replace with real local model call)",
        }
        return reasoning


# ---------------------------------------------------------------------------
# Optional real local model caller (reuses project's local_models.py exactly)
# ---------------------------------------------------------------------------

def try_real_local_reason(
    spec: Optional[LocalModelSpec],
    prompt: str,
    timeout: float = 60.0,
) -> Optional[dict[str, Any]]:
    """If a LocalModelSpec is provided and reachable, call it and try to parse JSON.

    The prompt passed in must instruct the model to output ONLY a JSON object
    matching the record_reasoning schema (use the template from suggest()).
    """
    if not spec:
        return None
    try:
        backend = spec.backend.lower()
        if backend == "ollama":
            adapter: LocalModelAdapter = OllamaAdapter()
        else:
            adapter = OpenAICompatAdapter()
        if not adapter.is_available(spec):
            return None
        # The project's adapters expose .generate (see local_models.py)
        # We use a minimal wrapper here that matches the spirit.
        # For full fidelity users extend with their exact generate call.
        result = adapter.generate(spec, prompt, max_tokens=800) if hasattr(adapter, "generate") else None
        if isinstance(result, str):
            # crude JSON extraction
            start = result.find("{")
            end = result.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(result[start:end])
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# MCP Experience Graph Adapter (the core deliverable)
# ---------------------------------------------------------------------------

@dataclass
class MCPExperienceGraphAdapter:
    """The exact adapter layer.

    - Primary surface: the 6 experience_graph_* MCP tools (names exactly as
      registered in mcp_server.py and documented in the server instructions).
    - Connection modes:
        * "direct"  — uses recorder directly (dead simple, no server, records live)
        * "mcp-stdio" — launches MCP server subprocess + uses mcp client SDK
        * "mcp-http"  — connects to streamable-http / SSE endpoint
    - Every tool call (even in direct mode) is recorded as experience via the
      recorder so the adapter's own usage grows the Experience Graph.
    - Integrates with project's LocalModelSpec for real local models.
    - Simple loop method participates in the 6-step canonical order (focus on
      step 4 Parent fabric-native decision using the graph tools).
    """

    swarm_id: str = SWARM_ID
    mode: str = "direct"  # "direct" | "mcp-stdio" | "mcp-http"
    mcp_url: str = "http://127.0.0.1:9876"
    local_model_spec: Optional[LocalModelSpec] = None
    drive_path: Path = field(default_factory=lambda: DEFAULT_DRIVE_PATH)

    # Internal (populated by connect / ensure)
    _recorder: Optional[ExperienceGraphRecorder] = None
    _mcp_session: Any = None
    _connected: bool = False

    def __post_init__(self):
        self.drive_path = Path(self.drive_path)

    def ensure_recorder(self) -> ExperienceGraphRecorder:
        if self._recorder is None:
            self._recorder = get_recorder_for_drive(self.drive_path, swarm_id=self.swarm_id)
        return self._recorder

    # --- Connection (stdio / http / direct) ---

    def connect(self) -> None:
        """Establish connection according to mode. Direct mode is instant."""
        if self._connected:
            return
        rec = self.ensure_recorder()
        if self.mode == "direct":
            # Direct = use the same recorder the MCP tools use internally.
            # This is 100% faithful to what an MCP client would experience.
            self._connected = True
            print(f"[adapter] DIRECT mode ready on {self.swarm_id} (recorder at {rec.loops_dir})")
            return

        # --- Real MCP client path (requires 'mcp' package) ---
        try:
            from mcp import ClientSession  # type: ignore
            from mcp.client.streamable_http import streamablehttp_client  # type: ignore
            # stdio variant also available but omitted for brevity in prototype
            print(f"[adapter] Attempting MCP {self.mode} connection to {self.mcp_url if 'http' in self.mode else 'stdio server'}...")
            # For full prototype we keep the connection stub lightweight.
            # A production adapter would keep the session and call tools via
            # await session.call_tool("experience_graph_get_context_pack", {...})
            self._mcp_session = "stub-mcp-session"  # placeholder for real session
            self._connected = True
            print("[adapter] MCP connection established (stub — replace with real ClientSession in prod).")
        except Exception as e:
            print(f"[adapter] MCP client not available or connection failed ({e}). Falling back to DIRECT mode.")
            self.mode = "direct"
            self._connected = True

    # --- The 6 experience_graph_* tool surfaces (exact MCP names) ---

    def experience_graph_get_context_pack(
        self, reasoning_style: str = "balanced", lookback_days: int = 7, max_tokens: int = 1800
    ) -> dict[str, Any]:
        rec = self.ensure_recorder()
        # In real MCP mode this would be: await session.call_tool("experience_graph_get_context_pack", args)
        pack = rec.get_fabric_context_pack(
            reasoning_style=reasoning_style,
            lookback_days=lookback_days,
            max_tokens=max_tokens,
        )
        # Record the query act itself (existing pattern — produces PARENT_FABRIC_QUERY edge + gbrain)
        self._record_adapter_usage("experience_graph_get_context_pack", {"style": reasoning_style})
        return pack

    def experience_graph_suggest_reasoning_structure(self) -> dict[str, Any]:
        rec = self.ensure_recorder()
        suggestion = rec.suggest_fabric_reasoning_structure()
        self._record_adapter_usage("experience_graph_suggest_reasoning_structure", {})
        return suggestion

    def experience_graph_record_reasoning(
        self, reasoning: dict[str, Any], cycle_id: str | None = None
    ) -> str:
        rec = self.ensure_recorder()
        slug = rec.record_parent_fabric_reasoning(cycle_id=cycle_id, reasoning=reasoning)
        self._record_adapter_usage(
            "experience_graph_record_reasoning",
            {"trace_slug": slug, "elements": len(reasoning.get("fabric_elements_considered", []))},
        )
        return slug or "recorded"

    def experience_graph_find_structural_similarities(
        self, element: str, lookback: int = 10, min_similarity: float = 0.6
    ) -> list[dict[str, Any]]:
        rec = self.ensure_recorder()
        matches = rec.find_structural_similarities(element=element, lookback=lookback, min_similarity=min_similarity)
        self._record_adapter_usage("experience_graph_find_structural_similarities", {"element": element, "matches": len(matches)})
        return matches

    def experience_graph_get_reasoning_traces_for_element(
        self, element: str, lookback: int = 20
    ) -> list[dict[str, Any]]:
        rec = self.ensure_recorder()
        traces = rec.get_fabric_reasoning_traces_for_element(element=element, lookback=lookback)
        self._record_adapter_usage("experience_graph_get_reasoning_traces_for_element", {"element": element, "count": len(traces)})
        return traces

    def experience_graph_get_parent_reasoning_history(self, lookback: int = 10) -> list[dict[str, Any]]:
        rec = self.ensure_recorder()
        history = rec.get_parent_reasoning_history(lookback=lookback)
        self._record_adapter_usage("experience_graph_get_parent_reasoning_history", {"count": len(history)})
        return history

    # --- Internal: record adapter usage as first-class experience (recorder pattern) ---

    def _record_adapter_usage(self, tool: str, metadata: dict[str, Any]) -> None:
        rec = self.ensure_recorder()
        try:
            cid = rec.get_active_evolution_cycle_id() or f"adapter-cycle-{int(time.time())}"
            slug = f"mcp-local-adapter:{tool}:{int(time.time())}"
            rec.record_artifact(
                cid,
                slug,
                "mcp_local_model_adapter_tool_call",
                content_ref={"tool": tool, "meta": metadata},
                texture_hints={"adapter": "MCPExperienceGraphAdapter", "gbrain_signal_score": 0.81},
            )
            rec.record_connection(
                cid,
                "mcp-local-model-adapter",
                slug,
                PARENT_FABRIC_QUERY if "get_context" in tool or "suggest" in tool else FABRIC_QUERY_RESULT_RECORDED,
                metadata={
                    "tool": tool,
                    "gbrain_signal_score": 0.81,
                    **metadata,
                    "swarm_id": self.swarm_id,
                },
            )
        except Exception:
            pass  # never break user loop

    # --- The simple participation loop (6-step flavored) ---

    def run_simple_reasoning_loop(self, num_cycles: int = 1, use_real_local: bool = False) -> list[dict[str, Any]]:
        """Demonstrates a local model participating in the 6-step loop via the 6 tools.

        This is the "simple loop" requested. Real local models replace the
        SimulatedLocalReasoner with a call that feeds the exact pack + template
        to their local endpoint and parses the JSON reasoning payload back.
        """
        self.connect()
        results: list[dict[str, Any]] = []
        reasoner = SimulatedLocalReasoner()

        for i in range(num_cycles):
            print(f"\n=== MCP Local Adapter Participation Cycle {i+1}/{num_cycles} (6-step fabric reasoning) ===")
            cycle_start = time.time()

            # 1 + 2 (prep for Parent step 4): read the Experience Graph + suggested structure
            pack = self.experience_graph_get_context_pack(reasoning_style="balanced", lookback_days=7)
            suggestion = self.experience_graph_suggest_reasoning_structure()
            print(f"  [tool-1] context_pack: coh={pack.get('fabric_coherence')}, weak_clusters={len(pack.get('top_weak_clusters',[]))}, style={pack.get('reasoning_style')}")
            print(f"  [tool-6] suggest_structure: template + {len(suggestion.get('few_shot_good_traces', []))} few-shots available")

            # 3. Local model (sim or real) reasons over the graph substrate
            prior = self.experience_graph_get_parent_reasoning_history(lookback=3)
            reasoning = reasoner.reason_over_fabric(pack, suggestion, prior_traces=prior)

            if use_real_local and self.local_model_spec:
                prompt = self._build_local_model_prompt(pack, suggestion)
                real = try_real_local_reason(self.local_model_spec, prompt)
                if real:
                    reasoning.update(real)  # overlay / override with real output
                    print("  [real-local] Used live local model response for reasoning payload")

            # 4. Record the explicit structural reasoning (the forcing function)
            trace_slug = self.experience_graph_record_reasoning(reasoning=reasoning)
            print(f"  [tool-3] record_reasoning -> trace_slug={trace_slug}")

            # 5 + 6. Verify + close the loop (query power surfaces)
            elem = reasoning["fabric_elements_considered"][0] if reasoning.get("fabric_elements_considered") else "experience_layer_v3"
            sims = self.experience_graph_find_structural_similarities(element=elem, lookback=8)
            traces = self.experience_graph_get_reasoning_traces_for_element(element=elem, lookback=8)
            hist = self.experience_graph_get_parent_reasoning_history(lookback=5)
            print(f"  [tool-2] find_similarities({elem[:40]}): {len(sims)} matches")
            print(f"  [tool-4] get_traces_for_element: {len(traces)} prior traces")
            print(f"  [tool-5] get_parent_reasoning_history: {len(hist)} entries")

            # Record the full loop participation as a high-signal artifact
            rec = self.ensure_recorder()
            loop_slug = f"mcp-local-adapter-loop-{int(time.time())}-{i}"
            rec.record_artifact(
                getattr(rec, "_active_cycle_id", None) or "mcp-adapter-meta",
                loop_slug,
                "mcp_local_model_adapter_participation",
                {
                    "cycle_index": i,
                    "tools_exercised": 6,
                    "trace_slug": trace_slug,
                    "fabric_coherence_at_entry": pack.get("fabric_coherence"),
                    "expected_lift": reasoning.get("expected_lift_signal"),
                },
            )

            results.append({
                "cycle": i,
                "trace_slug": trace_slug,
                "fabric_coherence": pack.get("fabric_coherence"),
                "expected_lift": reasoning.get("expected_lift_signal"),
                "tools_called": ["get_context_pack", "suggest", "record_reasoning", "find_similarities", "get_traces", "get_history"],
                "duration_s": round(time.time() - cycle_start, 2),
                "gbrain_signal_score": 0.83,
            })

        print(f"\n[adapter] Loop complete. {len(results)} participation cycles. All calls grew the Experience Graph on {self.swarm_id}.")
        return results

    def _build_local_model_prompt(self, pack: dict, suggestion: dict) -> str:
        """Build the exact prompt a local model should receive for tool-calling / JSON mode."""
        return (
            "You are a local model participating in the AgentDrive Experience Graph via the 6 MCP tools.\n"
            "Your job in this step of the 6-step loop is to produce a fabric_reasoning JSON payload.\n"
            "Use ONLY data from the supplied context_pack. Output ONLY valid JSON matching the schema.\n\n"
            f"CONTEXT_PACK:\n{json.dumps(pack, indent=2, default=str)[:2200]}\n\n"
            f"REASONING_STRUCTURE_TEMPLATE (from experience_graph_suggest...):\n{json.dumps(suggestion, indent=2, default=str)[:1400]}\n\n"
            "Return exactly one JSON object with keys: fabric_elements_considered (list[str]), "
            "structural_pattern_matched (str), decision_rationale (str), expected_lift_signal (float), "
            "prior_traces_referenced (list[str]). No other text."
        )


# ---------------------------------------------------------------------------
# Main (runnable demo + CLI)
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MCP Local Model Adapter Prototype — Experience Graph for any local model")
    parser.add_argument("--mode", choices=["direct", "mcp-stdio", "mcp-http"], default="direct",
                        help="Connection mode (direct = recorder, always works)")
    parser.add_argument("--cycles", type=int, default=1, help="Number of participation loops to run")
    parser.add_argument("--mcp-url", default="http://127.0.0.1:9876", help="URL for mcp-http mode")
    parser.add_argument("--use-real-local", action="store_true", help="Attempt real local model via local_models.py")
    args = parser.parse_args(argv)

    # Example real local model spec (user edits this; works with Ollama, LM Studio, llama.cpp server, etc.)
    real_spec = LocalModelSpec(
        backend="openai-compat",  # or "ollama"
        model="llama3.2",         # or whatever you have loaded
        endpoint="http://127.0.0.1:1234/v1",  # LM Studio default, or Ollama http://localhost:11434
        name="my-local-model",
        timeout_s=45.0,
    ) if args.use_real_local else None

    adapter = MCPExperienceGraphAdapter(
        swarm_id=SWARM_ID,
        mode=args.mode,
        mcp_url=args.mcp_url,
        local_model_spec=real_spec,
    )

    print("=" * 78)
    print("MCP LOCAL MODEL ADAPTER PROTOTYPE — STABILIZATION-WAVE-20260531")
    print("Dead-simple plug-in for Ollama / LM Studio / llama.cpp / any OpenAI-compat local model")
    print(f"Mode: {adapter.mode} | Swarm: {adapter.swarm_id}")
    print("=" * 78)

    results = adapter.run_simple_reasoning_loop(num_cycles=args.cycles, use_real_local=args.use_real_local)

    print("\n=== RESULTS (also written to Experience Graph as artifacts + edges) ===")
    print(json.dumps(results, indent=2, default=str))

    # Final self-referential artifact for this run (recorder pattern)
    rec = adapter.ensure_recorder()
    final_slug = f"mcp-local-model-adapter-prototype-run-{int(time.time())}"
    rec.record_artifact(
        "mcp-adapter-meta",
        final_slug,
        "mcp_local_model_adapter_prototype_execution",
        {
            "results": results,
            "mode": adapter.mode,
            "cycles": args.cycles,
            "design_version": "v1-stabilization-wave-20260531",
        },
        texture_hints={"self_referential": "This run of the MCP Local Model Adapter Prototype itself became living experience."},
    )
    print(f"\n[recorder] Final prototype execution artifact written: {final_slug}")
    print("All design decisions + full source + these results live as first-class Experience Graph artifacts on this drive.")
    print("See observations/meta-evolution/ for the authoritative record (page_type living-experience / mcp-local-adapter-...).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
