# Tower Experience Layer — Parent Fabric Reasoning Traces Surface
**stabilization-wave-20260531 drive only**

**Date:** 2026-05-31  
**Charter:** Extend the Experience Layer panel (#experience-fabric-panel) in the Mission Control Tower (`src/agentdrive/mission_control/static/index.html`) to surface live `parent_fabric_reasoning` traces carried by `FabricUpdateEvent`s (and hydrated via API). Traces show what the Parent considered (elements, structural pattern, expected lift). Traces are clickable and highlight relevant edges/nodes in the fabric canvas using consistent emerald mission-panel visual language.

**Status:** Complete. High-quality, minimal surface. All changes use existing patterns (publish_event_sync, recorder as single clean point, FabricUpdateEvent + refreshExperienceFabric wiring, emerald accents, mission-panel styling).

## Files Changed (absolute paths in workspace)

- `/home/pablothethinker/agentdrive/src/agentdrive/mission_control/events.py`
- `/home/pablothethinker/agentdrive/src/agentdrive/evolution/experience_graph.py`
- `/home/pablothethinker/agentdrive/src/agentdrive/mission_control/server.py`
- `/home/pablothethinker/agentdrive/src/agentdrive/mission_control/static/index.html`
- `/home/pablothethinker/agentdrive/CHANGELOG.md` (Unreleased section)
- `/home/pablothethinker/agentdrive/docs/development/TOWER_EXPERIENCE_LAYER_PARENT_FABRIC_REASONING_SURFACE.md` (this artifact)

## Backend Changes (Minimal + Correct)

### 1. FabricUpdateEvent (events.py)
```python
@dataclass
class FabricUpdateEvent(MissionEvent):
    """..."""
    ...
    parent_fabric_reasoning: dict[str, Any] | None = None  # NEW: full trace (elements_considered, structural_pattern_matched, expected_lift_signal, decision_rationale, ...)
```
- Automatically appears in WS payloads via `_record_event_for_introspection` (uses `event.__dict__`).

### 2. Recorder Emitter + Record Path (experience_graph.py)
- `_emit_loop_or_fabric_event` now forwards `parent_fabric_reasoning=...` and `metadata=...` into `FabricUpdateEvent` ctor for fabric_update kind.
- `record_parent_fabric_reasoning(...)` now passes the full `reasoning` dict as `parent_fabric_reasoning` kwarg on its `fabric_update` emit (in addition to the existing metadata slug).
- **New method** `get_recent_parent_fabric_reasoning_traces(limit=5)`:
  - Scans `loops_dir/*.json` (durable persisted cycle artifacts of type `"parent_fabric_reasoning"`).
  - Returns normalized list with `fabric_elements_considered`, `structural_pattern_matched`, `expected_lift_signal`, `decision_rationale`, `full`, `cycle_id`, `slug`, `ts`.
  - Deduped, newest-first, used by API + Tower hydration.

### 3. API Surface (server.py)
- `/api/experience_fabric` now returns `"parent_fabric_reasoning_traces": [...]` (calls the new recorder getter if present).
- Docstring updated to document the new field for the Tower panel.

These ensure both **push** (WS live FabricUpdateEvent) and **pull** (refresh via API) paths work.

## Frontend / Tower UI Changes (static/index.html)

### State (inside `const state = { ... }`)
```js
parentReasoningTraces: [],
currentFabricHighlight: null,  // {elements, pattern, expectedLift, until, trace}
```

### New DOM Section (inside `#experience-fabric-panel`, after graphs block, emerald styling)
```html
<div class="mt-2 pt-2 border-t border-emerald-900/30">
  <div class="flex items-center justify-between mb-1 px-0.5">
    <span class="terminal-label text-emerald-400/70">PARENT FABRIC REASONING TRACES</span>
    <span class="ml-1.5 text-[9px] text-emerald-400/50">real-time • what the Parent actually considered</span>
    <button onclick="clearFabricReasoningHighlights()">CLEAR HIGHLIGHTS</button>
  </div>
  <div id="exp-parent-reasoning" class="bg-black/40 border border-emerald-900/30 rounded-xl p-2 ... max-h-[92px] ..."></div>
  <div id="exp-reasoning-detail" class="... hidden ..."></div>
</div>
```
- Positioned directly under the existing "RECENT CYCLE GRAPHS" section.
- Consistent terminal-label + emerald-400/700/900 borders + bg-black/40 + font-mono.

### Core JS Functions (added after `steerOnWeakLink`)
- `addParentFabricReasoningTrace(trace)` — deduped push + `render...`
- `renderParentFabricReasoning()` — builds clickable cards with cycle shortId, pattern, +lift, elements list, rationale preview. Uses `onclick="highlightFabricReasoningTrace(i)"` + `window._recentReasoningTraces` for safe closure.
- `highlightFabricReasoningTrace(idx)` — sets `state.currentFabricHighlight`, forces `drawFabricCanvas`, populates detail pane, temporary panel glow.
- `clearFabricReasoningHighlights()` — clears state + canvas redraw + hides detail.

### Canvas Highlighting (modifications to `drawFabricCanvas`)
- After `pruneOldGraphEdges()`: compute `hlActive` from `state.currentFabricHighlight` (with timeout check).
- **Edges**: fuzzy match (includes / substring tolerant) on source/target vs `hl.elements`. Matched edges: thick emerald-400 stroke (`rgba(52,211,153,...)`), larger head, "PARENT" label when recent.
- **Nodes**: fuzzy match on node id. Matched nodes: larger emerald glow ring, bright emerald fill (`#34d399`), "P" badge, brighter label.
- All other drawing (densif violet, continuity cyan, recency glows, force/radial) unchanged.
- Highlights auto-expire after ~16.5s or via CLEAR button. Redraws are driven by existing FabricUpdate + manual refresh paths.

### Wiring (existing handlers, per charter)
- In the central WS `onmessage` router (`else if (et.includes("fabric"))`):
  - If `d.parent_fabric_reasoning` present: call `addParentFabricReasoningTrace(...)` (immediate live update).
  - Still calls `refreshExperienceFabric()` (throttled) as before.
- In `refreshExperienceFabric()` (after fetch success):
  - If `data.parent_fabric_reasoning_traces`: merge into state (dedup), then always `renderParentFabricReasoning()`.
- Initial load + REFRESH button + all prior Fabric/ParentDecision triggers continue to work.
- Canvas redraws on highlight changes use the existing `const c = document.getElementById('fabric-canvas'); if (c) drawFabricCanvas(...)` pattern.

## Visual Result (Operator Experience)

When a live Integrated system (or static fire / grid swarm under Integrated) runs and a Parent path calls `record_parent_decision(..., fabric_reasoning={ fabric_elements_considered: ["ev-cycle-...-0042", "research-constitutions-04", ...], structural_pattern_matched: "cross_cycle_continuation_low_coh_cluster", expected_lift_signal: 0.041, decision_rationale: "..." })`:

1. Recorder creates artifact + TypedEdges + emits `FabricUpdateEvent` with the full `parent_fabric_reasoning` object.
2. Tower WS receives it → `addParentFabricReasoningTrace` → new emerald-bordered card appears instantly in the new "PARENT FABRIC REASONING TRACES" section (under the existing fabric briefing, above kanban).
3. Card shows: short cycle, pattern name, +0.041 lift, comma list of considered elements, truncated rationale.
4. **Click the card**:
   - Relevant nodes in the LIVE FABRIC OBSERVATORY canvas (the violet one next to it) glow with emerald rings + "P" badges.
   - Connecting edges between them (or to the reasoning slug) render thick bright emerald with "PARENT" callout.
   - Detail bar appears below the traces list with full elements + rationale + dismiss link.
   - Brief emerald box-shadow pulse on the whole #experience-fabric-panel.
5. 16s later (or CLEAR) everything returns to normal violet/cyan canvas without trace of the highlight.
6. Manual REFRESH or other FabricUpdateEvents keep the list populated (newest on top, max ~8).

The human operator now sees **the fabric + the Parent's live structural reasoning over specific parts of that fabric** — fulfilling the exact goal of the charter with zero new visual language or architectural deviation.

## How to Exercise (stabilization-wave-20260531)

- Run any full Integrated harness that exercises `record_parent_decision` with `fabric_reasoning` (the live swarms in ~/.agentdrive/swarms/... or `examples/mission_control/` or the 2min static fire scripts already wired).
- Or use the Wave3 command bar in Tower: `parent_decision decision.action=... fabric_reasoning=...` (server forwards it).
- Or direct Python:
  ```python
  from agentdrive.system.integrated_real_time_evolution_system import IntegratedRealTimeEvolutionSystem
  # ... attach mission control ...
  system.record_parent_decision(..., fabric_reasoning={
      "fabric_elements_considered": ["cycle-foo", "elem-bar"],
      "structural_pattern_matched": "test_pattern",
      "expected_lift_signal": 0.037,
      "decision_rationale": "High value cluster for densification."
  })
  ```
- Open `http://localhost:8080` (or whatever the mission server binds) → scroll to the emerald EXPERIENCE LAYER / v3 MULTI-CYCLE FABRIC panel → observe new traces section populate → click to highlight canvas.

## Non-Goals / Scope (Strictly Followed)
- No changes outside stabilization-wave-20260531 context.
- No new auth, no new top-level files beyond the explicit requested artifact.
- No broad refactors; only the narrow Experience Layer panel surface + the minimal supporting event/API/recorder hooks required for it to function.
- Canvas remains non-clickable for picking (only highlight driven from the new traces list).
- No TUI or other surfaces touched.

## References to Prior Work
- Builds directly on the "Experience Layer Tightening" (the #experience-fabric-panel + refresh + weak-link steering) and the "Experience Graph Parent Reasoning" tranche (the recorder hooks + fabric_reasoning arg + gbrain edges; formerly referenced as Fabric-Native Parent Reasoning for high-level consistency with v3 Experience Graph / experience_graph_* MCP tooling).
- All emission still goes exclusively through the single approved `publish_event_sync` channel.
- Visual consistency: emerald-400/700/900, mission-panel, terminal-label, font-mono, same provenance style.

## MCP Client Usage (experience_graph_* Tools)
The same Experience Graph surfaces are exposed via the AgentDrive MCP server (`src/agentdrive/adapters/mcp_server.py`) for any MCP-capable client (Claude Desktop, Cursor, etc.):

```bash
# Start the MCP server (stdio for most clients, or streamable-http)
python -m agentdrive.adapters.mcp_server
# or: agentdrive mcp serve
```

Example tool calls from an MCP client (after configuring the server in your AI tool):

- `experience_graph_get_context_pack(reasoning_style="balanced", lookback_days=7)`  
  → dense structural pack from the v3 Experience Graph (gbrain-scored elements + provenance).

- `experience_graph_find_structural_similarities(element="ev-cycle-...-0042", min_similarity=0.65)`  
  → analogical matches across cycles/edges/reasoning traces.

- `experience_graph_record_reasoning(reasoning={"fabric_elements_considered": [...], "structural_pattern_matched": "...", "expected_lift_signal": 0.041, "decision_rationale": "..."})`  
  → write explicit Parent-style reasoning trace (becomes queryable GBrain experience).

- `experience_graph_suggest_reasoning_structure()`  
  → returns exact schema + few-shot examples for high-quality payloads.

- `experience_graph_get_reasoning_traces_for_element(element=...)` and `experience_graph_get_parent_reasoning_history(lookback=10)`  
  → full history for continuity and self-reflection.

All MCP responses mirror the internal recorder (gbrain_signal_score, provenance, stabilization-wave-20260531 default swarm). Use these to let external agents directly participate in growing the Experience Graph.

This surface makes the "Parent's actual structural reasoning over it in real time" visible to the operator exactly as requested.

**Artifact produced per charter. All code changes are complete and wired.**
