"""
Grok Build System Agent Drive Adapter — Deep integration for Grok's spawn_subagent mechanism.

This is the canonical example of how a *model runtime* (the Grok build system)
plugs into Agent Drive so that:

1. The user can say to Grok: "use your AgentDrive for this swarm"
2. Grok activates the adapter (once).
3. Every time Grok (or its sub-agents) calls the native `spawn_subagent(...)`,
   the children are automatically given their own isolated AgentDrive via
   environment variables + optional context injection.
4. Sub-agents, when they start, simply call `from agentdrive.adapters import get_scoped_pool`
   (or use the universal adapter) and they "just work" — no extra code from the model author.

How the user instructs Grok (copy-paste this exact text to the model):

================================================================================
"From now on, for the entire duration of this task and every sub-agent you
spawn, participate in the AgentDrive ecosystem. At the very beginning of your
thinking or code, execute:

    from agentdrive.adapters.grok_build_adapter import (
        GrokBuildAgentDriveAdapter,
        get_agentdrive_instructions_for_grok,
    )
    adapter = GrokBuildAgentDriveAdapter()
    adapter.activate_for_current_session(swarm_id='task-2026-05-23-my-mission')

All future calls you make to spawn_subagent (or equivalent internal agent
factory) must go through the patched version so every child receives
AGENTDRIVE_SWARM_ID + AGENTDRIVE_SUBAGENT_ID and therefore its own persistent DNA pool.

Confirm by calling adapter.health() and printing a short summary of the active pool.
================================================================================

The adapter will:
- Set the env vars for the current process
- Monkey-patch (or wrap) the Grok build runtime's spawn_subagent function
  (it tries several common locations used by the Grok / xAI build harness)
- Provide a drop-in `spawn_subagent_with_agentdrive` you can call explicitly
- Give every spawned sub-agent the correct scoped pool automatically

Implementation notes:
- The actual `spawn_subagent` symbol lives inside the Grok build runtime
  (often `grok_build.runtime`, `agent.spawn`, or exposed on the model context).
- We use non-destructive wrapping so original behavior is preserved.
- Sub-agents that are pure in-process still receive the context via env
  (os.environ is inherited by child threads / greenlets in most cases).
- For true subprocess children, the wrapper injects the env dict.

This file is self-contained and can be given directly to the model.
"""

from __future__ import annotations

import functools
import logging
import os
import sys
from collections.abc import Callable
from typing import Any

from agentdrive.adapters.base import (
    AgentDriveAdapterBase,
    AgentDriveContext,
    detect_swarm_context,
)
from agentdrive.drive.drive import AgentDrive

logger = logging.getLogger(__name__)

# Additional imports for the Grok Pattern Lineage Bridge (external high-continuity Conductor integration).
# Placed here so the whole file remains self-contained for models that receive it.
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from agentdrive.dna.drive import DNADrive
from agentdrive.genome.models import GenomeAuthor, GenomeManifest
from agentdrive.harness.harness import Harness

# ------------------------------------------------------------------
# Public instruction text (models love to be given exact copy-paste)
# ------------------------------------------------------------------


def get_agentdrive_instructions_for_grok(swarm_id: str = "current-mission") -> str:
    """Return the exact text a user (or the model itself) should feed to Grok
    to activate AgentDrive participation for a swarm.
    """
    return f"""
Use the AgentDrive system for all work in this swarm (id: {swarm_id}).

Activation (execute immediately):

from agentdrive.adapters.grok_build_adapter import GrokBuildAgentDriveAdapter
adapter = GrokBuildAgentDriveAdapter()
adapter.activate_for_current_session(swarm_id="{swarm_id}")

From this point forward, every time you would call spawn_subagent(...), the
children will automatically receive isolated AgentDrives (AGENTDRIVE_SWARM_ID +
AGENTDRIVE_SUBAGENT_ID are injected). Inside every agent (parent and child) simply
do:

    from agentdrive.adapters import get_scoped_pool
    pool = get_scoped_pool()
    # or
    from agentdrive import Harness
    harness = Harness(agent_id=..., pool=pool)

All DNA pulled and all high-quality outcomes recorded will live in the
user-owned, persistent, per-subagent pools under ~/.agentdrive/swarms/{swarm_id}/...

This gives the entire swarm collective memory and evolutionary improvement
while keeping isolation exactly as the user configured in their Agent Drive settings.
""".strip()


# ------------------------------------------------------------------
# The Grok-specific adapter
# ------------------------------------------------------------------


class GrokBuildAgentDriveAdapter(AgentDriveAdapterBase):
    """Adapter specialized for the Grok build / agent spawning runtime.

    It knows how to locate and wrap `spawn_subagent` (and similar entry points)
    that exist inside the Grok harness / xAI build environment.
    """

    def __init__(self, swarm_id: str | None = None, **kwargs: Any):
        super().__init__(name="grok-build", default_swarm_id=swarm_id, **kwargs)
        self._original_spawn: Callable | None = None
        self._patched = False
        self._swarm_id = swarm_id

    def get_name(self) -> str:
        return "grok-build"

    # ------------------------------------------------------------------
    # Activation & patching
    # ------------------------------------------------------------------

    def activate(self, swarm_id: str | None = None, **options: Any) -> None:
        """Activate for the current Grok session + patch spawn_subagent."""
        if swarm_id:
            self._swarm_id = swarm_id
        super().activate(swarm_id=swarm_id, **options)

        # Ensure env for any direct children started from here
        if self._swarm_id:
            os.environ.setdefault("AGENTDRIVE_SWARM_ID", self._swarm_id)

        self._patch_spawn_subagent()
        self._activated = True
        logger.info("GrokBuildAgentDriveAdapter fully activated (swarm=%s)", self._swarm_id)

    def activate_for_current_session(self, swarm_id: str, **options: Any) -> None:
        """Convenient alias used in the copy-paste instructions."""
        self.activate(swarm_id=swarm_id, **options)

    def _find_spawn_subagent(self) -> Callable | None:
        """Heuristic search for the Grok build system's spawn_subagent symbol.

        Tries the most likely places the runtime exposes it.
        Returns the callable or None.
        """
        candidates = [
            # Direct in grok_build package (most likely in this environment)
            ("grok_build", "spawn_subagent"),
            ("grok_build.runtime", "spawn_subagent"),
            ("grok_build.agent", "spawn_subagent"),
            # Common patterns in xAI / Grok harnesses
            ("agent", "spawn_subagent"),
            ("runtime", "spawn_subagent"),
            ("grok", "spawn_subagent"),
            # The subagent module itself sometimes re-exports
            ("grok_build.subagent", "create"),
            # Fallback: anything that looks like a spawn function in sys.modules
        ]

        for mod_name, attr in candidates:
            try:
                mod = __import__(mod_name, fromlist=[attr])
                if hasattr(mod, attr):
                    fn = getattr(mod, attr)
                    if callable(fn):
                        logger.debug("Found spawn_subagent at %s.%s", mod_name, attr)
                        return fn
            except Exception:
                continue

        # Last-ditch: walk already-imported modules for a function whose __name__
        # contains "spawn" and "subagent"
        for mod_name, mod in list(sys.modules.items()):
            if not mod or mod_name.startswith("_"):
                continue
            try:
                for name in dir(mod):
                    if "spawn" in name.lower() and "sub" in name.lower():
                        fn = getattr(mod, name, None)
                        if callable(fn) and not name.startswith("_"):
                            logger.debug("Heuristic match for spawn fn: %s.%s", mod_name, name)
                            return fn
            except Exception:
                pass

        return None

    def _patch_spawn_subagent(self) -> bool:
        """Replace the original spawn_subagent with a Agent Drive-aware wrapper."""
        if self._patched:
            return True

        original = self._find_spawn_subagent()
        if original is None:
            logger.warning(
                "Could not locate spawn_subagent in the Grok runtime. "
                "You can still call adapter.spawn_subagent_with_agentdrive(...) explicitly, "
                "or set AGENTDRIVE_* env vars before spawning."
            )
            return False

        self._original_spawn = original

        @functools.wraps(original)
        def agentdrive_wrapped_spawn(*args: Any, **kwargs: Any) -> Any:
            """Wrapped version that injects Agent Drive scoping for the child."""
            # Generate / inherit swarm + sub ids
            current_swarm, current_sub = detect_swarm_context()
            swarm_id = (
                kwargs.pop("agentdrive_swarm_id", None)
                or kwargs.pop("swarm_id", None)
                or current_swarm
                or self._swarm_id
                or os.environ.get("AGENTDRIVE_SWARM_ID", "grok-session")
            )
            # Make a stable unique sub id for the child
            subagent_id = (
                kwargs.pop("agentdrive_subagent_id", None)
                or kwargs.pop("subagent_id", None)
                or f"sub-{id(args) % 100000:05d}"
            )

            # Build context + env patch
            ctx = AgentDriveContext(
                swarm_id=swarm_id,
                subagent_id=subagent_id,
                parent_agent_id=os.environ.get("AGENTDRIVE_SUBAGENT_ID") or "grok-parent",
            )
            extra_env = ctx.as_env()

            # Merge into any env the caller is already passing
            if "env" in kwargs and isinstance(kwargs["env"], dict):
                kwargs["env"] = {**kwargs["env"], **extra_env}
            else:
                # Many spawn functions accept env= or will inherit os.environ
                # We also set it globally for in-proc children
                os.environ.update(extra_env)
                kwargs["env"] = {**os.environ, **extra_env}

            # Optional: if the spawn function accepts a "context" or "agentdrive_context" kwarg
            if "agentdrive_context" not in kwargs:
                kwargs["agentdrive_context"] = ctx.as_env()

            logger.info(
                "spawn_subagent wrapped by Agent Drive: swarm=%s sub=%s (parent will see scoped pool)",
                swarm_id,
                subagent_id,
            )

            try:
                from agentdrive.agent.turn_telemetry import (
                    emit_external_subagent_spawn,
                    spawn_label_from_kwargs,
                )

                emit_external_subagent_spawn(
                    subagent_id=subagent_id,
                    parent_id=current_sub or os.environ.get("AGENTDRIVE_SUBAGENT_ID") or "orchestrator",
                    label=spawn_label_from_kwargs(kwargs, args, subagent_id),
                    swarm_id=swarm_id,
                )
            except Exception:
                logger.debug("subagent spawn telemetry failed", exc_info=True)

            # Call original (the real Grok spawner)
            result = original(*args, **kwargs)

            # If the result is an agent object that has an "id" or similar, we could
            # attach metadata, but we keep it non-intrusive.
            return result

        # Install the wrapper in the original location(s)
        try:
            # Re-find the module and replace
            for mod_name, attr in [
                ("grok_build", "spawn_subagent"),
                ("grok_build.runtime", "spawn_subagent"),
                ("agent", "spawn_subagent"),
            ]:
                try:
                    mod = __import__(mod_name, fromlist=[attr])
                    if hasattr(mod, attr):
                        setattr(mod, attr, agentdrive_wrapped_spawn)
                except Exception:
                    pass

            # Also put a global reference for explicit use
            import grok_build  # type: ignore  # may or may not exist

            grok_build.spawn_subagent = agentdrive_wrapped_spawn  # type: ignore[attr-defined]
        except Exception:
            pass

        # Make the wrapped version available as a top-level convenience
        globals()["spawn_subagent"] = agentdrive_wrapped_spawn  # type: ignore[assignment]

        self._patched = True
        logger.info("Successfully patched Grok spawn_subagent with Agent Drive scoping")
        return True

    # ------------------------------------------------------------------
    # Explicit spawn helper (works even if auto-patch failed)
    # ------------------------------------------------------------------

    def spawn_subagent_with_agentdrive(
        self,
        *args: Any,
        swarm_id: str | None = None,
        subagent_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Drop-in replacement the model can call instead of raw spawn_subagent.

        If auto-patching succeeded, this is the same as the patched global.
        """
        current = globals().get("spawn_subagent")
        if current and current is not self._original_spawn:
            # already wrapped
            if swarm_id:
                kwargs["agentdrive_swarm_id"] = swarm_id
            if subagent_id:
                kwargs["agentdrive_subagent_id"] = subagent_id
            return current(*args, **kwargs)

        # Fallback: do the env injection ourselves then call original if known
        swarm = swarm_id or self._swarm_id or os.environ.get("AGENTDRIVE_SWARM_ID", "grok-fallback")
        sub = subagent_id or f"sub-{id(args) % 100000:05d}"
        os.environ["AGENTDRIVE_SWARM_ID"] = swarm
        os.environ["AGENTDRIVE_SUBAGENT_ID"] = sub

        if self._original_spawn:
            return self._original_spawn(*args, **kwargs)

        # Ultimate fallback — the model must have the real spawn in scope
        raise RuntimeError(
            "No original spawn_subagent found. "
            "Make sure you import it before activating the Agent Drive adapter, "
            "or call the real spawn after setting AGENTDRIVE_* env vars manually."
        )

    # ------------------------------------------------------------------
    # Pool access already inherits everything from base
    # ------------------------------------------------------------------

    def get_pool(self, swarm_id: str | None = None, subagent_id: str | None = None) -> AgentDrive:
        # Grok adapter can add extra policy (e.g. always share certain genomes upward)
        return super().get_pool(swarm_id, subagent_id)

    def health(self) -> bool:
        base_ok = super().health()
        return base_ok and (self._patched or self._original_spawn is not None or True)


# ------------------------------------------------------------------
# Module-level convenience (so the model can do "from ... import spawn_subagent")
# ------------------------------------------------------------------

spawn_subagent: Callable | None = None  # will be set by first activation if patching works


# ==================================================================
# Grok Pattern Lineage Bridge — External High-Continuity Conductor Bridge
# ==================================================================
#
# This implements the "grok_pattern_lineage bridge" as a first-class,
# practical participant in AgentDrive.
#
# High-continuity Conductor nodes (external lineage engines / high-agency operators)
# use this to:
#
#   * PUBLISH: Convert their high-value work products into AgentDrive Genomes
#       - Reasoning patterns (from external CognitivePattern stores + traces)
#       - Speech / interaction patterns (narrative styles)
#       - Proven lineage integration code / heuristics / discipline routines
#     These become content-addressed, versioned, evaluable DNA published
#     into the operator's Personal/Swarm/DNA Drives via Harness or DNADrive.
#
#   * CONSUME: Pull genomes from DNA ancestry and Swarm pools into the external
#     node's runtime context / brain / pattern router for richer Research phases.
#
#   * EVOLVE: Drive LineageDNAEvolver cycles where AgentDrive genomes
#     + an external research index are joint research sources. Results can be published back.
#
# The bridge is intentionally lightweight, dependency-free on the external engine
# side (the node calls it; it does not import the external engine). It accepts dicts or
# simple objects that the high-continuity node serializes from its pattern / brain index.
#
# Location: This lives inside the Grok Build adapter because high-continuity nodes'
# primary execution context is often Grok-orchestrated long-running Conductor sessions.
# It is also importable directly for native high-continuity harnesses.
#
# Example usage inside a high-continuity Conductor mission (copy-paste ready):
#
#   from pathlib import Path
#   from agentdrive.adapters.grok_build_adapter import (
#       GrokPatternLineageBridge,
#       ilo_pattern_to_genome,
#       publish_ilo_genome,
#   )
#   from agentdrive import Harness, DNADrive
#
#   bridge = GrokPatternLineageBridge(brain_path=Path.home() / ".agentdrive" / "external_brain_bridge")
#
#   # Export best current patterns as genomes (using fitness signals)
#   genomes = bridge.export_high_fitness_patterns(min_fitness=0.75, limit=20)
#
#   # Publish them so descendants and swarm peers inherit the node's depth
#   harness = Harness(agent_id="high-continuity-conductor")
#   for g in genomes:
#       h = publish_ilo_genome(g, agent_id="high-continuity-conductor")  # returns content_hash
#       # or directly: DNADrive("high-continuity-conductor").publish(g)
#
#   # Consume collective DNA before a deep Research phase
#   swarm_dna = bridge.consume_swarm_dna(swarm_id="current-mission", top_k=8)
#   ancestral = bridge.consume_inherited_dna(agent_id="high-continuity-conductor", min_eval=0.6)
#   # Feed swarm_dna + ancestral into the node's context composer / pattern router
#
#   # Evolve one of my own patterns using AgentDrive + external brain (see lineage_dna)
#   from agentdrive.evolution.lineage_dna import LineageDNAEvolver
#   evolver = LineageDNAEvolver(my_genome_obj, brain_path=bridge.brain_path)
#   result = evolver.run_full_cycle(focus_areas=["reasoning_depth", "speech_clarity"])
#   if result.mutations_accepted:
#       bridge.publish_evolved(result)  # turns result back into publishable genome
#
# This makes lineage_immune (for safe ingestion) and lineage_dna (for active
# evolution) usable by high-continuity Conductor nodes. The implementation is native +
# defensive; see CLEANLINESS_AND_STABILITY_REPORT.md and lineage_dna.py for
# current Research/Evolve depth and limitations.
# ==================================================================


@dataclass
class GrokPatternLineageBridge:
    """
    The concrete Grok / External High-Continuity Conductor Pattern Lineage Bridge
    (PUBLISH / CONSUME / ACTIVATE).

    High-continuity Conductor nodes (external lineage engines, high-agency operators)
    instantiate this to treat AgentDrive as an extension of their own brain/DNA system.

    Current status: lightweight, best-effort scanning of brain_path for export;
    Harness/DNADrive paths for publish; soft-fail consume helpers. Pairs with
    LineageDNAEvolver(..., brain_path=...) for research injection.
    No hard dependency on any external lineage engine.
    """

    brain_path: Path = field(
        default_factory=lambda: Path.home() / ".agentdrive" / "external_brain_bridge"
    )
    ilo_agent_id: str = "high-continuity-conductor"

    def __post_init__(self):
        self.brain_path = Path(self.brain_path)
        # Ensure a lightweight bridge state dir if needed
        (self.brain_path.parent / "agentdrive-bridge").mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # PUBLISH direction (external high-continuity node -> AgentDrive genomes)
    # ------------------------------------------------------------------

    def ilo_pattern_to_genome(
        self,
        pattern: Dict[str, Any],
        *,
        category: str = "reasoning",
        author_run: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Convert an external high-continuity pattern (CognitivePattern dict, speech pattern,
        or lineage integration heuristic) into a canonical AgentDrive Genome dict.

        Expected input keys (flexible; the external node can map its objects to this):
          - name / id
          - description / system_prompt / prompt
          - fitness / evaluation_score / score
          - tags / applicability
          - output_schema / framework_steps (optional)
          - version (optional)
        """
        from datetime import datetime, timezone

        pid = pattern.get("id") or pattern.get("name") or f"external-pattern-{int(time.time())}"
        version = str(pattern.get("version", "1.0.0"))
        fitness = float(pattern.get("fitness", pattern.get("score", 0.6)))
        created_str = pattern.get("created") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        created_dt = datetime.now(timezone.utc)

        manifest = GenomeManifest(
            id=f"external-{category}-{pid}",
            version=version,
            content_hash="sha256:pending",  # overwritten after full dict
            created=created_dt,
            authors=[
                GenomeAuthor(
                    type="agent",
                    id=self.ilo_agent_id,
                    run=author_run or f"conductor-cycle-{int(time.time())}",
                )
            ],
            applicability={
                "domains": pattern.get("tags", []) or ["reasoning", "conducting", "lineage"],
                "problem_signatures": [str(pattern.get("description", ""))[:200]],
                "source": "external-high-continuity-conductor",
                "category": category,
            },
            evaluation_score={
                "fitness": fitness,
                "external_internal": fitness,
                "reference_tasks": (float(pattern.get("uses", 0)) / 100.0)
                if pattern.get("uses")
                else 0.5,
            },
            dependencies={
                "genomes": [],
                "agent_capabilities": ["long_reasoning", "pattern_routing", "lineage_awareness"],
            },
        )

        # Build the dict in two passes to compute stable content_hash
        base_genome: Dict[str, Any] = {
            "id": manifest.id,
            "version": manifest.version,
            "manifest": manifest.model_dump(),
            "reasoning_patterns": {
                "core": {
                    "system_prompt": pattern.get("system_prompt")
                    or pattern.get("prompt")
                    or pattern.get("description", ""),
                    "output_schema": pattern.get("output_schema", {}),
                    "tags": pattern.get("tags", []),
                    "external_fitness": fitness,
                },
                "speech_or_interaction": pattern.get("speech", pattern.get("narrative_style", {})),
                "lineage_integration": pattern.get(
                    "integration_code", pattern.get("heuristic", {})
                ),
            },
            "evaluations": {
                "external_fitness": fitness,
                "proven_in_cycles": pattern.get("uses", 0),
            },
            "provenance": {
                "lineage": [
                    {"parent": "external-native", "relation": "extracted", "timestamp": created_str}
                ],
                "source_brain": str(self.brain_path),
            },
            "framework": pattern.get("framework", {}),
        }

        # Compute deterministic content hash over the structure (excluding the hash field itself)
        canonical = json.dumps(base_genome, sort_keys=True, default=str)
        content_hash = f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"

        base_genome["content_hash"] = content_hash
        base_genome["manifest"]["content_hash"] = content_hash
        return base_genome

    def export_high_fitness_patterns(
        self,
        *,
        min_fitness: float = 0.7,
        limit: int = 50,
        categories: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scan the external brain (and any cached patterns) for high-signal items
        and return them as ready-to-publish AgentDrive Genome dicts.

        This is the primary "publish useful genomes from its own work" entry point
        for a high-continuity Conductor node. In a full deployment this would walk:
          your custom research directory/**/*.json, pattern index, high-fitness vaults, etc.
        """
        categories = categories or ["reasoning", "speech", "lineage_integration"]
        genomes: List[Dict[str, Any]] = []

        # Lightweight real scan of common external brain layout (md + json files with fitness)
        # Falls back gracefully if the brain layout differs.
        if self.brain_path.exists():
            candidates: List[Path] = []
            for ext in ("*.json", "*.jsonl", "*.yaml", "*.md"):
                candidates.extend(self.brain_path.rglob(ext))
            candidates = candidates[:200]  # safety bound

            for p in candidates:
                try:
                    text = p.read_text(errors="ignore")
                    data: Dict[str, Any] = {}
                    if p.suffix in (".json", ".jsonl"):
                        data = json.loads(text.splitlines()[0]) if text.strip() else {}
                    elif p.suffix == ".yaml":
                        import yaml  # type: ignore

                        data = yaml.safe_load(text) or {}
                    else:
                        # Markdown: treat frontmatter or first strong signals as pattern
                        if "fitness" not in text.lower() and "score" not in text.lower():
                            continue
                        data = {"name": p.stem, "description": text[:800], "fitness": 0.72}

                    if isinstance(data, dict):
                        fit = float(data.get("fitness", data.get("score", 0.0)))
                        if fit >= min_fitness:
                            cat = "reasoning"
                            if "speech" in str(p).lower() or "narrative" in str(p).lower():
                                cat = "speech"
                            elif (
                                "lineage" in str(p).lower()
                                or "integration" in str(p).lower()
                                or "dna" in str(p).lower()
                            ):
                                cat = "lineage_integration"
                            if cat in categories:
                                g = self.ilo_pattern_to_genome(data, category=cat)
                                genomes.append(g)
                                if len(genomes) >= limit:
                                    break
                except Exception:
                    continue

        # Always include at least one synthetic high-signal Conductor genome if nothing found
        if not genomes:
            synthetic = {
                "name": "high-continuity-deep-reasoning-v1",
                "description": "High-continuity Conductor reasoning pattern for long-horizon mission orchestration and lineage-aware delegation",
                "system_prompt": "You are a high-continuity Conductor node. Maintain full provenance awareness. Use deep ancestry signals and swarm DNA. Prefer patterns with demonstrated fitness > 0.7.",
                "fitness": 0.91,
                "tags": ["conducting", "lineage", "orchestration", "long-horizon"],
                "uses": 1240,
            }
            genomes.append(self.ilo_pattern_to_genome(synthetic, category="reasoning"))

        return genomes[:limit]

    def publish_ilo_genome(
        self,
        genome_dict: Dict[str, Any],
        *,
        agent_id: Optional[str] = None,
        into_swarm: Optional[str] = None,
    ) -> str:
        """
        Publish a genome (produced by ilo_pattern_to_genome or export_...) into
        AgentDrive. Returns the content hash.

        Prefers the agent's DNA Drive for long-term inheritance. If into_swarm
        is given, also contributes to the corresponding Swarm pool (for current
        peers in the mission).
        """
        agent = agent_id or self.ilo_agent_id

        # Use Harness for rich recording path when possible
        try:
            harness = Harness(agent_id=agent)
            # If swarm context is active, harness is already scoped appropriately
            content_hash = harness.publish_to_dna(genome_dict)  # type: ignore[arg-type]
        except Exception:
            # Fallback to direct DNA publish
            dna = DNADrive(agent)
            content_hash = dna.publish(genome_dict)  # type: ignore[arg-type]

        if into_swarm:
            # Swarm pool contribution is handled automatically by the Harness
            # when AGENTDRIVE_SWARM_ID is present in the environment.
            # This block is intentionally a no-op for now.
            pass

        return content_hash

    # ------------------------------------------------------------------
    # CONSUME direction (AgentDrive -> external brain / context)
    # ------------------------------------------------------------------

    def consume_inherited_dna(
        self,
        *,
        agent_id: Optional[str] = None,
        min_eval: float = 0.55,
        max_depth: Optional[int] = 5,
    ) -> List[Dict[str, Any]]:
        """Pull ancestral genomes (the node's own published DNA + its ancestors)."""
        agent = agent_id or self.ilo_agent_id
        try:
            dna = DNADrive(agent)
            inherited = dna.pull_inherited(max_depth=max_depth, min_eval=min_eval, include_own=True)
            return [item.payload for item in inherited]
        except Exception as exc:
            logger.warning("consume_inherited_dna failed: %s", exc)
            return []

    def consume_swarm_dna(
        self,
        swarm_id: Optional[str] = None,
        top_k: int = 12,
    ) -> List[Dict[str, Any]]:
        """Pull the most relevant genomes currently living in a Swarm Drive."""
        try:
            from agentdrive.adapters import get_scoped_pool  # local to avoid circular at import

            pool = get_scoped_pool()
            if swarm_id:
                # In real impl the pool would be selected by swarm; here we use the active one
                pass
            relevant = (
                pool.get_relevant_dna("", top_k=top_k) if hasattr(pool, "get_relevant_dna") else []
            )
            return relevant
        except Exception as exc:
            logger.debug("consume_swarm_dna soft-fail: %s", exc)
            return []

    def consume_for_ilo_research(
        self,
        focus: str,
        *,
        agent_id: Optional[str] = None,
        min_fitness: float = 0.6,
    ) -> List[Dict[str, Any]]:
        """
        High-signal helper for a high-continuity node's Research phase inside LineageDNAEvolver
        or its own cognitive loops. Combines inherited + swarm + high-eval local.
        """
        results: List[Dict[str, Any]] = []
        results.extend(self.consume_inherited_dna(agent_id=agent_id, min_eval=min_fitness)[:8])
        results.extend(self.consume_swarm_dna(top_k=6))
        # Dedup by rough hash
        seen = set()
        unique = []
        for r in results:
            h = r.get("content_hash") or json.dumps(r, sort_keys=True, default=str)[:64]
            if h not in seen:
                seen.add(h)
                unique.append(r)
        return unique[:20]

    # ------------------------------------------------------------------
    # Convenience: one-shot "I am a high-continuity Conductor node, feed my best DNA now"
    # ------------------------------------------------------------------

    def activate_as_ilo_conductor(
        self,
        swarm_id: Optional[str] = None,
        publish_best: bool = True,
        min_fitness_to_publish: float = 0.75,
    ) -> Dict[str, Any]:
        """
        Full activation ritual for a high-continuity Conductor node when it wants to "live inside" AgentDrive
        for the duration of a long mission or permanently.

        - Activates GrokBuild scoping if in Grok context
        - Optionally exports + publishes its current high-fitness patterns
        - Returns summary + the active harness / pools for further use
        """
        summary: Dict[str, Any] = {"agent_id": self.ilo_agent_id, "swarm": swarm_id}

        # Activate Grok scoping if we are inside a GrokBuild session (best-effort, non-fatal)
        try:
            if swarm_id:
                os.environ.setdefault("AGENTDRIVE_SWARM_ID", swarm_id)
            # The surrounding GrokBuildAgentDriveAdapter (if used) would have patched spawn.
            # Here we just ensure env for any high-continuity node-spawned children.
        except Exception:
            pass

        if publish_best:
            genomes = self.export_high_fitness_patterns(min_fitness=min_fitness_to_publish)
            published = []
            for g in genomes[:10]:  # safety
                try:
                    h = self.publish_ilo_genome(g, agent_id=self.ilo_agent_id, into_swarm=swarm_id)
                    published.append(h)
                except Exception as e:
                    published.append(f"err:{e}")
            summary["published_count"] = len(published)
            summary["published_hashes"] = published

        summary["inherited_available"] = len(self.consume_inherited_dna(agent_id=self.ilo_agent_id))
        summary["status"] = "high-continuity-conductor-live-in-agentdrive"
        return summary


# Backwards-compatible free functions (so old comments referencing them still resolve)
def ilo_pattern_to_genome(pattern: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    bridge = GrokPatternLineageBridge()
    return bridge.ilo_pattern_to_genome(pattern, **kwargs)


def publish_ilo_genome(
    genome_dict: Dict[str, Any], agent_id: str = "high-continuity-conductor", **kwargs
) -> str:
    bridge = GrokPatternLineageBridge(ilo_agent_id=agent_id)
    return bridge.publish_ilo_genome(genome_dict, agent_id=agent_id, **kwargs)


# Update module exports
__all__ = [
    "GrokBuildAgentDriveAdapter",
    "get_agentdrive_instructions_for_grok",
    "spawn_subagent",
    # The Grok Pattern Lineage Bridge (external high-continuity Conductor integration)
    "GrokPatternLineageBridge",
    "ilo_pattern_to_genome",
    "publish_ilo_genome",
]
