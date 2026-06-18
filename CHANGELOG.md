# Changelog

All notable changes to this project are documented here. The product is
**AgentDrive** — local-first Drive for AI agent swarms, distributed under the
``agentdrive`` Python package.

## Unreleased

### Changed — Descriptive learned skill names

- **`learning/skill_naming.py`** — human-readable slugs for auto-distilled and born skills.
- **Learned:** `learned-{project}-{verb}-{focus}` (e.g. `learned-openmangos-mimic-growth-merge-briefing`).
- **Fused:** `fused-{project}-{axes}` (e.g. `fused-openmangos-experience-patterns-skills`).
- Replaces opaque `auto-*` / hash-suffixed `fused-session-*` names from MCP auto-learning.
- **Tests:** `tests/test_skill_naming.py`.

### Added — Growth merge (experience + pattern recognition + memory)

- **`learning/growth_merge.py`** — recognizes cross-surface patterns (memory overlap, structural similarities, codebase frameworks) and merges session growth into compound memories (`vault=growth`, `topic=merge`) + relations.
- **Auto-hook** in `auto_absorb` — `auto_learning.growth_merge` when ≥2 axes present (`AGENTDRIVE_AUTO_GROWTH_MERGE=1` default).
- **Op:** `growth_merge_briefing` — unified experience + patterns + memory briefing.
- **Docs:** `CAPABILITY_FUNNEL.md`, `FOR_AI_MODELS.md` — growth merge tier documented.
- **Tests:** `tests/test_growth_merge.py`.

### Removed — Memory Bank legacy field aliases

- **`MemoryEntry.from_dict`** — no longer reads `wing`/`room`/`source_file`/`chunk_index`/`verbatim`; canonical fields only.
- **Ops** — `memory_bank_search` / `memory_bank_anchor` / `memory_bank_import_dialogue` accept `vault`/`topic` only (not `wing`/`room`).

### Changed — Memory Bank native naming (AgentDrive-native, not ported metaphors)

- **Renamed modules:** `scope.py`, `ranking.py`, `anchor.py`, `relations.py`, `dialogue_import.py` replace palace/layers/hybrid_search/temporal_kg/transcript_miner.
- **Renamed fields:** `vault` / `topic` / `origin_path` / `shard_index` / `preserves_source` on `MemoryEntry` (canonical only — no legacy field aliases).
- **Renamed ops:** `memory_bank_anchor`, `memory_bank_import_dialogue`, `memory_relation_record`, `memory_relation_query`, `memory_relation_expire`.
- **Removed:** `docs/MEMPALACE_INTEGRATION.md`, `tests/test_mempalace_integration.py`.
- **Docs/tests:** `docs/MEMORY_BANK.md` rewritten; **tests:** `tests/test_memory_vault.py`.

### Added — Memory Bank (deep AI knowledge databank)

- **`agentdrive.memory`** — per-swarm append-only `memory_bank/memories.jsonl`; kinds: fact, insight, decision, pattern, born_skill, learning, episode, etc.
- **Auto-ingest** from `auto_absorb`, skill fusion, `learnings_log` (`AGENTDRIVE_AUTO_MEMORY_BANK=1` default).
- **MCP/CLI ops:** `memory_bank_store`, `memory_bank_recall`, `memory_bank_search`, `memory_bank_list`, `memory_bank_briefing`, `memory_bank_deep_briefing`, `memory_bank_stats`.
- **`memory_bank_deep_briefing`** — unified Experience Graph fabric pack + Memory Bank in one call.
- **Docs:** `docs/MEMORY_BANK.md`; funnel + `FOR_AI_MODELS.md` updated.
- **Tests:** `tests/test_memory_bank.py`.

### Added — Born skills (experience + skills + patterns fusion)

- **`learning/skill_fusion.py`** — merges Experience Graph traces, distilled/inherited skills, and codebase pattern signals into a completely new `fused-*` skill (not a copy of any parent).
- **Auto-fuse** in `auto_absorb` when a session spans ≥2 axes (`AGENTDRIVE_AUTO_FUSE_SKILLS=1` default); `auto_learning.fused_skill` on results.
- **MCP/CLI op:** `synthesize_fused_skill(trigger, source_skills, pattern_projects, experience_traces, ...)`.
- **Docs:** `CAPABILITY_FUNNEL.md`, `SKILLS-LIBRARY.md`, `FOR_AI_MODELS.md` — born-skill tier documented.
- **Tests:** `tests/test_skill_fusion.py`.

### Changed — Consolidation sprint (architectural audit)

- **Archived** 8× `STABILIZATION_SUBAGENT_REPORT-*.md` + stale `BUILD_STATUS.md` / `MISSION_PLAN.md` → `archive/development-history/`.
- **`docs/CAPABILITY_FUNNEL.md`** — single funnel: Observe/Decide → Experience Graph → Skills → Genomes/DNA.
- **`docs/ARCHITECTURE.md`** — overview + subsystem map + pointers to funnel doc.
- **Docs reframed** Pool→Drive terminology in `POOL.md`, `SWARM.md`, `SETTINGS.md`, `ASSESSMENT.md`; `FOR_AI_MODELS.md` links funnel.
- **`pyproject.toml`** — `asyncio` pytest marker + `asyncio_mode = auto` (fixes `test_chat_loop.py` collection).
- **Tests:** `tests/test_multiverse_engine.py` — engine pipeline + ops registry smoke.

### Added — Mirror-neuron codebase mimicry

- **`codebase/mirrors.py`** — observation activates motor programs (exemplar functions/classes/imports); cross-project `mirror_resonance.json` universal priors; Experience Graph traces on each fire.
- **`codebase/exemplars.py`** — extract concrete motor templates from observed source.
- **MCP ops:** `codebase_mimic`, `codebase_transform_style`, `codebase_mirror_resonance`.
- **Tests:** `tests/test_mirror_neurons.py`.

### Added — Codebase pattern recognition framework

- **`agentdrive.codebase`** — per-project writing-style learning: register roots, observe files, crystallize pattern frameworks (naming, imports, frameworks, conventions), match snippets before patching.
- **MCP/CLI ops:** `codebase_register_project`, `codebase_observe_file`, `codebase_patterns_profile`, `codebase_patterns_match`, `codebase_list_projects`.
- **`agentdrive_inhabitant_read_source`** auto-observes into project `agentdrive`.
- **Auto-learning** distills codebase writing-guide skills + DNA on observe/profile ops.
- **Storage:** `~/.agentdrive/codebase-patterns/<project>/` (`observations.jsonl`, `framework.json`).
- **Tests:** `tests/test_codebase_patterns.py`.

### Added — End-to-end automatic learning (MCP + CLI)

- **`agentdrive.learning.auto_absorb`** — post-`run_operation` hook (on by default via `AGENTDRIVE_AUTO_LEARN=1`): session tracking, auto `experience_graph_record_reasoning` when models skip it, Hermes-style skill distillation for parent MCP sessions (`mcp-auto-learning` source), promote + DNA ingest on high-signal ops.
- **Results** include `auto_learning` summarizing absorbed traces/skills/genomes.
- **Docs:** `docs/SKILLS-LIBRARY.md`, `docs/FOR_AI_MODELS.md` Golden Rule 4 updated; MCP server instructions mention automatic learning.
- **Tests:** `tests/test_auto_learning.py` (5 passed).

### Added — External MCP Parent (`external_parent_decision`)

- **`MultiverseEngine.ingest_external_parent_decision()`** — frontier/chat MCP clients (Grok, Claude, Codex, Cursor) submit branch reasoning; AgentDrive persists collapse with `llm_mode=external` and `CollapsePolicy.EXTERNAL_PARENT`.
- **`IntegratedRealTimeEvolutionSystem.run_external_parent_decision()`** — canonical 6-step hook for external models.
- **MCP tool + op:** `external_parent_decision(trigger, branches, collapsed_branch_id, fabric_reasoning=...)`.
- **`experience_graph_suggest_reasoning_structure`** — documents `external_mcp_parent_flow` and `reasoning_provider_modes` (local_llm | heuristic | external_mcp).
- **`docs/FOR_AI_MODELS.md`** — Golden Rule 3b updated: connected MCP models should use `external_parent_decision` when no local LLM is configured.
- **Example:** `examples/14_external_mcp_parent_loop.py`; **tests:** `tests/test_external_parent_decision.py` (5 passed).

### Added — Multiverse Cognition M2–M5 (LLM spawner, densify, durable threads, Tower panel)

- **`cognition/roles.py`** + **`cognition/llm_spawner.py`** — Cognitive Agent Team role prompts; local LLM branch spawn/simulate/stress-test via `~/.agentdrive/local_models.yaml` with heuristic fallback.
- **`cognition/research_thread.py`** — durable `research-thread-manifest` observations for long-running superposition.
- **`densify_invariant_clusters()`** — GraphGardener `densified_via_gardener` edges on robust invariants (M3).
- **`reopen_stale_sessions()`** + op `multiverse_reopen_stale` (M4).
- **Mission Control** — `MultiverseUpdateEvent`, `derive_multiverse_snapshot()`, Tower panel (branches + invariants + LLM mode).
- **Ops:** `multiverse_densify`, `multiverse_reopen_stale`; `multiverse_parent_decision` gains `durable`, `heuristic_only`, `skip_densify`.

### Added — Multiverse Cognition merged into AgentDrive (M0 + M1)

- **`docs/MULTIVERSE_COGNITION.md`** — full architecture: 7-phase pipeline, TypedEdge relations, Council hooks, MCP/CLI surface.
- **`src/agentdrive/cognition/`** — `MultiverseEngine`, `MultiverseSessionStore` (disk persistence under `drive/meta_evolution/multiverse/sessions/`).
- **`IntegratedRealTimeEvolutionSystem.run_multiverse_parent_decision()`** — canonical Parent hook: spawn → simulate → invariants → stress-test → collapse → `record_parent_decision`.
- **`get_parent_actionable_briefing()`** — now includes `multiverse_context` (recent collapses, open superposition, top invariants).
- **CLI:** `agentdrive multiverse run|list|status`
- **MCP:** `multiverse_parent_decision`, `multiverse_run_full`, `multiverse_list_sessions`, `multiverse_get_session` (+ operations registry auto-registration).
- **`docs/FOR_AI_MODELS.md`** — Golden Rule 3b for competing-path decisions.
- **`genomes/examples/research-constitution-multiverse-cognition@stabilization-wave-20260531.json`**
- **`examples/12_multiverse_cognition_loop.py`** — smoke via Integrated loop.

### Verify

```bash
cd "Vektra Industries/Software/AgentDrive"
PYTHONPATH=src python examples/12_multiverse_cognition_loop.py --trigger "Ship multiverse MVP"
PYTHONPATH=src python -m agentdrive.cli multiverse run --trigger "CLI test" --branches 5
PYTHONPATH=src python -m agentdrive.cli multiverse list --limit 5
```

---

### Fixed — `scripts/install.sh` piped install (`curl | bash`)

- **`scripts/install.sh`** — when piped (no `BASH_SOURCE`), fetches canonical `install.sh` from GitHub instead of failing with `BASH_SOURCE[0]: unbound variable` and `//install.sh` path error.
- Local git-clone path unchanged: still `exec`s root `install.sh`.

### Verify

```bash
curl -fsSL https://raw.githubusercontent.com/PabloTheThinker/AgentDrive/main/scripts/install.sh | bash -s -- --help
```

---

### Professional Documentation Website (Mintlify-style Instruction Manual)

Created a full professional documentation site under `docs/` modeled directly on the OpenClaw documentation website (Mintlify `docs.json` + hierarchical structure + beautiful landing + focused pages) with strong Hermes-inspired clarity (explicit "when to use", recipes, tables, rules for agents/models).

- `docs/docs.json` — full Mintlify configuration with navigation groups, branding, redirects from old flat docs, and client links.
- `docs/index.md` — polished landing page with hero, cards, philosophy, and clear paths for humans and models.
- Strong **AI Models** section (`docs/ai-models/`):
  - `rules-and-patterns.md` — the canonical instruction manual / Golden Rules (catalog first, 6-step loop, record reasoning, clone helpers, etc.).
  - `quickstart.md` and `local-models.md` — explicit first-class support and guidance for local models + cloned git setups.
- Reorganized supporting content:
  - `start/` (golden-path, install, getting-started)
  - `concepts/` (overview, experience-graph, six-step-loop)
  - `mcp/` (overview, connect, for-claude-cursor-codex)
- Added `docs/AGENTS.md` (style guide for AI contributors working in clones).
- Updated root `README.md` to prominently direct users and models to the new professional docs site.
- This gives both humans and (especially) AI models — frontier or local — a first-class, navigable, self-improving instruction manual in the exact style the user requested.

### README + FOR_AI_MODELS.md — improved rules and guidance for AI models and local models (2026-06-09)
- **README.md**: Added prominent "For AI models" callout near the top with direct instructions (call the catalog first). Strengthened the "Use With Any AI CLI or Local Model" section with clone/dev emphasis, `get_mcp_config_snippet`, and stronger links to the canonical rules document. Updated the "Autonomy That Compounds" section to highlight local models and the value of the Experience Graph for them. Made references to FOR_AI_MODELS.md clearer and more directive ("the canonical rules for the AI").
- **docs/FOR_AI_MODELS.md** (the main "rules for the AI and local models"):
  - New **Golden Rules** section at the top (catalog first, 6-step loop sacred, record reasoning, clone helpers, etc.).
  - Completely refreshed "How to Connect (MCP)" section with first-action emphasis on the catalog, clone/dev flow, and `get_mcp_config_snippet`.
  - Expanded and modernized the Experience Graph tools table with better "when to use" guidance drawn from live catalog rich docs.
  - Significantly strengthened "Recommended Behavior for Good Agents" with explicit do's, anti-patterns, and local/autonomous agent advice.
  - Updated Quick Start Checklist to be session-start actionable and reference the new clone/config tools.
  - Added dedicated "Local Models & Cloned Setups" content in the Living Example section.
  - Overall tone made more direct and prescriptive ("you, the model") while remaining practical.
- **MCP server instructions** (the prompt models receive on connection): Synced the "first actions for any model" language to match the improved docs (catalog first, clone section, `get_mcp_config_snippet`, 6-step loop).
- These changes make it dramatically clearer for both frontier models and especially **local models** (Continue + Ollama, direct stdio, etc.) — whether the user has a global install or a `git clone` — exactly how to behave and which tools to reach for first.

### MCP tools — clone/dev + Claude/Cursor/Codex/other models (2026-06-09 follow-up)
- Added `agentdrive_get_mcp_config_snippet(client=...)` MCP tool. Any connected model (especially Claude or a Codex-style/Continue agent) can call it while attached to the user's local git clone and receive a precise, ready-to-output config block + paste instructions for that client's settings (claude_desktop_config.json, Cursor mcp.json, generic, etc.).
- Enhanced `agentdrive_mcp_catalog` with a new top-level section `clone_dev_setup_for_claude_cursor_codex_and_others` that surfaces dev/clone detection, one-time setup commands, and client-specific tips.
- `mcp_config.py`: new `get_clone_aware_client_config()` that returns tailored blocks + instructions when running from a local clone (detected via pyproject + src layout). "codex" is treated as a first-class alias (maps to robust generic/Continue-style output).
- Server instructions now explicitly tell models: when the user cloned, use the catalog's dev section or the `get_mcp_config_snippet` helper to give the user the exact config for their Claude/Cursor/etc.
- Goal: When a user does `git clone .../AgentDrive`, their Claude, Cursor, Continue, or any other MCP-capable model can be pointed at the *local working tree* with almost zero friction — the model itself can drive the entire setup.

### MCP tools — any-model integration hardening (richer docs, self-catalog, readOnly hints, generic clients) (2026-06-09)
- **OperationSpec**: added optional `when_to_use` and `examples` fields so the operations registry (and therefore MCP) can carry model-friendly guidance.
- **mcp_bridge.py**: `_rich_doc_for_op` now generates detailed, categorized docstrings for auto-registered tools (category + read_only + when_to_use + examples + "always returns JSON + dry_run support" + pointer to catalog). `add_tool` now passes `annotations={"readOnlyHint": ...}` (graceful fallback for older FastMCP).
- **`agentdrive_mcp_catalog`**: new first-class MCP tool (and surfaced in server instructions). Any connected model (Grok/Claude/Cursor/local/custom agent) can call it as its very first action to receive a live categorized catalog of the full surface with usage recommendations. This is the canonical handshake for arbitrary MCP clients.
- **mcp_config.py + generic clients**: `generic` client now has practical default paths (`.mcp/mcp.json`, cwd `mcp.json`, etc.). Added `get_generic_mcp_block`. `mcp config --client generic` and uvx paths are even more turnkey for custom agents, containers, or non-standard hosts.
- **mcp_server.py (FastMCP)**: server `instructions` now lead with a crisp "for ANY model" quickstart that explicitly tells the connected LLM to call `agentdrive_mcp_catalog()` first. 40 tools registered (25 core ops + high-value experience/inhabitant/ExternalBridge surfaces + the new catalog).
- **Docs**: `docs/MCP.md` expanded "What your model gets" + brand new "For arbitrary / custom AI models and agents" section recommending the catalog + uvx one-liner. `FOR_AI_MODELS.md` cross-referenced.
- **Outcome**: Dramatically better experience for *any* AI model that speaks MCP. Models now get explicit, structured, self-describing tool metadata instead of having to guess from short descriptions. `mcp doctor` reports 40 tools and full registry coverage.

### Skills — tiered library: universal + Grok/Claude/Codex vendors (2026-06-08)
- **Layout:** `examples/skills/vendors/{grok,claude,codex}/` (24 vendor skills) alongside tiers 1–4 (37 bundled).
- **`vendor-manifest.yaml`** + **`scripts/sync_vendor_skills.py`**: sync Grok from `~/.grok/skills`; curated Claude/Codex plugin paths.
- **`registry.py`**: `harness`, `requires` on `SkillEntry`; `list_skills(harness=)`; `list_skills_by_tier()`.
- **`compose.py`**: tiers 1–4 always in prompt; tier 5 only when `AGENTDRIVE_HARNESS=grok|claude|codex`.
- **CLI:** `agentdrive skills list --harness grok` — grouped tier tables + harness filter.
- **Universal:** added `mcp-agentdrive` — prefer MCP tools over vendor harness skills.
- **Docs:** `SKILLS-LIBRARY.md`, `SKILLS-CATALOG.md`, `examples/skills/README.md` updated for 61-skill bench.
- **Tests:** tier/harness filtering; vendor exclusion from default prompt matching.

### Skills — model-agnostic bench (drop Grok/Hermes vendor bundles) (2026-06-08)
- **Removed** `examples/skills/backup/grok/` (14 Grok mirrors) and `backup/hermes/`.
- **Added** `universal/` tier (13 skills): `changelog`, `verify-work`, `skill-authoring`, `systematic-debugging`, `swarm-orchestrator`, `swarm-worker`, `frontend-design`, `design-system`, `web-artifact`, `document-*`, `parallel-attempts`.
- **Principle:** bundled skills work with any LLM; vendor harness skills belong in `~/.agentdrive/skills/` overlays only.
- **Removed** `scripts/sync_grok_skills_backup.py`; updated SKILLS-LIBRARY.md and SKILLS-CATALOG.md (36 skills).

### Skills catalog — proper descriptions for all 40 skills (2026-06-08)
- **`examples/skills/catalog.yaml`**: canonical name, role, description, when_to_call, tags for every skill.
- **`docs/SKILLS-CATALOG.md`**: generated human-readable catalog with full descriptions per skill.
- **`scripts/apply_skills_catalog.py`**: patch SKILL.md frontmatter from catalog.
- **`scripts/generate_skills_catalog_doc.py`**: regenerate SKILLS-CATALOG.md from catalog.yaml.

### Skills library — hive/pawn bench, Grok backup, Hermes patterns (2026-06-08)
- **`docs/ASSESSMENT.md`**: product assessment — what we have, gaps, prioritized next steps.
- **`docs/SKILLS-LIBRARY.md`**: catalog, Arisen/pawn/hive metaphor, layout, refresh instructions.
- **Bundled skills**: `core/` ops, `hive/` pawn playbooks, `agentdrives/` (12 narrow prodigies), `backup/grok/` (14 Grok mirrors), `backup/hermes/` (3 adapted).
- **`skills/compose.py`**: `match_skills_for_turn`, `compose_skills_block` — catalog + matched bodies in `build_system_prompt`.
- **`skills/registry.py`**: nested `**/*.SKILL.md` discovery; `tags`, `role`, `category`, `source`, `when_to_call` frontmatter.
- **`scripts/sync_grok_skills_backup.py`**: sync `~/.grok/skills` → bundled backup for swarm pawns.
- **Tests**: `test_skills_compose.py`; extended registry count test.

### Terminal UX polish — MessageStreamLane, session panel, skills init (2026-06-08)
- **`tui/message_stream_lane.py`**: `MessageStreamLane` subscribes to `MessageDelta` for the active session; chat streaming `Live` reads the lane instead of `on_chunk`.
- **`session_events`**: `summarize_event_types`, `filter_events_by_type`, `format_type_histogram` for replay filters.
- **Session replay**: `/session panel|filter|types`, `--type` on CLI `session events|replay|panel`; rich panel with type histogram + timeline tree.
- **Skills**: `agentdrive skills init <name>` and `/skills init <name>` scaffold `~/.agentdrive/skills/<name>/SKILL.md`.
- **Tests**: `test_message_stream_lane.py`; extended session, skills, and TUI experience tests.

### Pattern 5 — skills registry + session slash + Grok spawn done (2026-06-07)
- **`skills/`**: SKILL.md discovery (`~/.agentdrive/skills` + bundled `examples/skills`); `run_skill()` shared by CLI and chat.
- **CLI**: `agentdrive skills list|show|run`; catalog entries for `session` and `skills`.
- **Chat**: `/session events|replay [id]`, `/skills list`, `/skill <name> [args]`.
- **Grok adapter**: `spawn_subagent` wrapper emits `SubagentDone` when spawn returns.
- **`session_events.resolve_session_id`**: suffix match for session ids from `/sessions`.
- **Tests**: `test_skills_registry.py`, `test_grok_spawn_telemetry.py`, session slash in `test_tui_experience.py`.

### UX proposal — patterns 1 & 5 closure (2026-06-07)
- **`docs/UX-PROPOSAL.md`**: status table updated — session `events.jsonl`, `TranscriptLane`, genomes search parity marked shipped.

### Terminal experience — session event recording (2026-06-07)
- **`session_events.py`**: `SessionEventRecorder` appends default_bus events to `~/.agentdrive/agents/<agent>/sessions/<session_id>/events.jsonl`; `replay_events`, `format_event_summary`.
- **Chat + agent**: recorder attached for the active session in `tui/chat.py` `enter()` and `AgentDriveAgent.send()` (rebinds on `/new` / `/resume`).
- **CLI**: `agentdrive session events <session_id>` and `agentdrive session replay <session_id>`.
- **Tests**: `tests/test_session_events.py`.

### Pattern 5 — genomes search parity (2026-06-07)
- **`genomes_api.py`**: fix `InheritanceManifest` return-type import (`TYPE_CHECKING`).
- **CLI**: `agentdrive genomes search <query>` — pool query via `genomes_api.search_genomes()`.
- **Chat**: `/genome-search <query>` — chat-native tree rendering (Pattern 5).
- **`cli_catalog.py`**: catalog entry for `genomes search`.
- **Tests**: `tests/test_genomes_api.py` (`list_genomes`, `get_genome` missing, `search_genomes`).

### Terminal experience — transcript lane (2026-06-07)
- **`tui/transcript_lane.py`**: `TranscriptLane` — bus-driven transcript ribbons for pool/evolution/confidence/inheritance/quarantine/peer/reconciliation events (Pattern 1).
- **`tui/chat.py`**: inline ribbon handlers replaced by `TranscriptLane`; `PoolMatch` active-form header stays on `ChatView._on_pool_match`.
- **Tests**: `tests/test_transcript_lane.py`.

### Terminal experience — turn telemetry + pool lane (2026-06-07)
- **`agent/turn_telemetry.py`**: `ChatTurnTelemetry` emits subagent bus events on every `AgentDriveAgent.send()` turn.
- **`tui/pool_lane.py`**: `PoolActivityLane` — thin pool status row below stream during turns (Pattern 3 v1).
- **Grok adapter**: `spawn_subagent` wrapper emits `SubagentSpawn` for external swarms.
- **`docs/UX-PROPOSAL.md`**: updated shipped vs remaining table.
- **Tests**: `test_pool_lane.py`, `test_turn_telemetry.py`.

### Terminal experience — swarm tree + operator REPL (2026-06-07)
- **`tui/swarm_lane.py`**: `SwarmActivityLane` wired into chat streaming `Live` region (Pattern 4); post-turn summary line; `reset()` + lock deadlock fix; child-only summary counts.
- **`tui/chat.py`**: sub-agent tree pinned above streaming body during turns; double-Enter documented in `/help`; subagent ribbons replaced by live tree.
- **`cli_repl.py`**: operator REPL dispatching through same `argparse` handlers as subcommands (Pattern 5).
- **CLI**: `agentdrive repl`; `--cli` and `AGENTDRIVE_NO_TUI=1` skip default TUI for REPL.
- **Tests**: `tests/test_swarm_lane.py`; REPL cases in `tests/test_cli_commands.py`.

### Terminal experience — golden path in TUI (2026-06-07)
- **`tui/experience.py`**: golden-path gate, status segment, ops-backed `/golden-path`, `/think`, `/learnings` slash commands.
- **Chat welcome + status rule**: show gate when incomplete; golden path section in welcome panel.
- **`golden-path run`**: marks `config.golden_path.completed` on success (CLI + TUI).
- **Tests**: `tests/test_tui_experience.py`.

### Golden path swarm — refinements (2026-06-07)
- **`scripts/install.sh`**: thin wrapper → canonical root `install.sh` (fixes MCP-less legacy path).
- **Provider-aware `golden-path run`**: skips live `think` without provider (`--require-provider` to enforce).
- **`emit_json()`**: all `cli_surface` `--json` paths use plain stdout (no Rich wrap); `tests/test_cli_json_output.py`.
- **Web stub `/`**: returns golden-path CLI pointers; TUI welcome adds golden-path section.
- **README**: "What AgentDrive is / isn't" + AD-Grid demoted under Advanced.

### Golden path — canonical first-run (2026-06-07)
- **`docs/GOLDEN_PATH.md`**: authoritative ~10 min path (install → doctor → mcp → think → learnings → query).
- **`golden_path.py` + `agentdrive golden-path`**: `steps`, `verify`, `run` (--dry-run for CI).
- **`examples/00_golden_path.sh`**: runnable shell walkthrough.
- **Onboarding/setup/doctor/install** now steer to golden path instead of scattered next-steps.
- **README Start Here** rewritten; HELP Quick Start + MCP.md link to golden path.
- **`install.sh`**: fixed missing `prompt_yes_no`; post-install prints golden-path commands.
- **`install_smoke.sh`**: adds `golden-path run --dry-run`.
- **Tests**: `tests/test_golden_path.py`.

### CLI discovery + full-surface commands (2026-06-07)
- **`cli_catalog.py`**: categorized command catalog (70+ entries) powering discovery and help epilog.
- **`cli_surface.py`**: handlers for `think`, `learnings` (log/list/search), `harness compose`, `graph`/`experience`, `eval replay`, `commands` (list/tree/search).
- **CLI**: `agentdrive pool` alias for `drive`; richer `--help` epilog; all 25 ops registry entries now have `cli_command` strings.
- **Tests**: `tests/test_cli_commands.py` (13 cases).

### MCP connection hardening — any-model onboarding (2026-06-07)
- **`adapters/mcp_config.py`**: resolves launcher (PATH binary → venv → `python -m` module fallback); client config paths; merge-write for Grok/Cursor/Claude/Continue.
- **CLI**: `agentdrive mcp install`, `mcp doctor`, `mcp tools`; `mcp config --json|--write|--client|--uvx`.
- **`agentdrive doctor`**: MCP bridge check (tool count + launcher).
- **Install**: `install.sh` + `install_smoke.sh` run `mcp doctor`; docs/MCP.md rewritten for clone/install flows.
- **Tests**: `tests/test_mcp_config.py`.

### Phase F — MCP ops bridge, RRF retrieval, eval replay, dream MC panel (2026-06-07) · `0.3.1-alpha`
Roadmap completion pass: closes items 9–15 from the 90-day improvement plan.

- **MCP auto-registration** (`operations/mcp_bridge.py`): all 25 registry ops exposed as MCP tools via `run_operation()`; hand-written tools skipped when already registered.
- **RRF fusion** (`drive/retrieval.py`): opt-in Reciprocal Rank Fusion across structural/reasoning/graph/recency/experience rankers (`AGENTDRIVE_RRF_FUSION=1` or `DriveSettings.use_rrf_fusion`).
- **Eval replay MVP** (`eval/replay.py`): re-score shipped research-thread artifacts with `MultiMetricEvaluationHarness`; `tests/test_eval_replay.py`.
- **Install smoke** (`scripts/install_smoke.sh`): fresh-venv doctor + dream dry-run + `01_hello_drive.py`; wired into release CI gate.
- **Dream Mission Control panel**: `DreamPhaseEvent`, phase telemetry from `dreaming/cycle.py`, `GET /api/dream/status`, Tower DREAM CYCLE bay + `dream_run`/`dream_status` commands.
- **Version** `0.3.1-alpha`.

### Phase E — Ops registry, dream cycle, Experience Graph tests (2026-06-07)
Parallel swarm pass (gbrain operations discipline + dream cycle + EG coverage).

- **Contract-first operations registry** (`operations/registry.py`): 25 `OperationSpec`s with thin handlers, `run_operation()`, `export_operations_json()`. CLI: `agentdrive ops list|describe|run|export`.
- **Phased dream cycle** (`dreaming/cycle.py`): reconcile → extract_links → consolidate (STOP) → grade_confidence → purge_stale (STOP). Lock at `~/.agentdrive/dream.lock`, audit `logs/dream-cycle.jsonl`. CLI: `agentdrive dream run|status|phases`.
- **Experience Graph test suite** (`tests/test_experience_graph.py`): 29 tests on `ExperienceGraphRecorder` (no full `IntegratedRealTimeEvolutionSystem` required).
- **Test hygiene:** reset `default_pool` singleton in autouse fixture (fixes order-dependent `pool_status` flake). Full suite **469 passed**.

### Phase D — Fabric compose layers, Fabric import, MC CapStore (2026-06-07)
- **Layered composition** (`harness/compose.py`): Fabric Strategy × Context × Pattern × Session layers on `Harness.compose_context(strategy=, context=, pattern=, session_id=, input_text=)`.
- **Fabric corpus import** (`patterns/fabric_import.py`): `agentdrive patterns import-fabric [--source PATH] [--pattern NAME] [--limit N]` converts Fabric `data/patterns/*/system.md` → `~/.agentdrive/patterns/<name>-fabric-v1/`.
- **Mission Control CapStore** (`mission_control/authz.py`): mutating `dispatch_command` / WS commands require `mission:command:control:*` cap when `mission_control.require_cap`, `AGENTDRIVE_MC_REQUIRE_CAP=1`, or non-loopback bind. CLI: `agentdrive cap mint-mission [--command NAME]`.
- **Tests:** 22 new tests; full suite **425 passed**.

### Phase C — Sprint chain + STOP gates, doctor --verbose, test portability fix (2026-06-07)
- **Sprint module** (`src/agentdrive/sprint/`): gstack `/ship`-style `SHIP_CHAIN` (reconcile → test → think_gaps → changelog_check) with `CheckpointStore` STOP gates at `~/.agentdrive/checkpoints/`. CLI: `agentdrive sprint ship|ack|status`. Harness: `checkpoint()` / `ack_checkpoint()`. Example genome: `genomes/examples/sprint-ship-v1.json`.
- **`agentdrive doctor --verbose`**: extra panel with reconciliation last_scan, KG edge count, quarantine, learnings, sprint checkpoints, experience layer file counts.
- **Test fix:** reconciliation wave seed paths now portable (`genomes/examples/` relative to repo root, not parallax-only absolute paths). Full suite **403 passed**.

### Phase B — Gstack-inspired swarm: learnings JSONL, MCP think+gaps, patterns catalog (2026-06-07)
Parallel implementation pass (three workstreams) adopting gstack/Fabric patterns from research roadmap.

- **Learnings JSONL** (`src/agentdrive/learnings/`): append-only `~/.agentdrive/learnings/<slug>.jsonl` with `LearningsStore` (log/search/list_recent/count), `ingest_learnings_to_experience()` → living-experience observations, `get_learnings_dir()`. Harness: `compose_context()` preloads top learnings; `record_learning()` appends entries.
- **MCP `agentdrive_think`**: primary synthesis surface calling `pool.think()`; returns `{answer, citations, gaps, contradictions, genomes_used, correlation_id}` via `SynthesisResult.to_mcp_dict()`. `_ensure_mandatory_gaps()` injects honest high-severity gap when synthesis returns none (Gbrain-style).
- **Pattern-as-genome catalog** (`src/agentdrive/patterns/`): bundled `genomes/patterns/morning-brief-v1/` (manifest + framework.yaml + Fabric-compatible `system.md`); user overlay at `~/.agentdrive/patterns/`. CLI: `agentdrive patterns list|show|apply`.
- **Tests:** 22 new tests (`test_learnings`, `test_mcp_think`, `test_patterns`, `test_bootstrap_registry`). Full suite **395 passed**, 1 pre-existing flaky reconciliation test.

### Phase A — First-run bootstrap registry fix + `0.3.0-alpha` (2026-06-07)
Laptop development pass (parallax drive data intentionally stays on parallax; code syncs via git).

- **Bootstrap registry path alignment.** `ensure_experience_layer_seed` registered genomes under `drive/genomes/` while personal `AgentDrive()` reads `~/.agentdrive/genomes/` via bare `GenomeRegistry()`. Personal drives now use `get_genomes_dir()`; swarm drives keep `<drive>/genomes`. Legacy seeds under `drive/genomes/` migrate once when home genomes is empty.
- **Doctor uses live drive registry.** `_run_doctor` reports genome count from `get_default_drive().registry` / pool stats instead of a standalone `GenomeRegistry()` that always showed 0. First-run recovery guidance panel now renders on healthy empty installs (was unreachable dead code).
- **Version bump** to `0.3.0-alpha` in `pyproject.toml`, `__init__.py`, `constants.py`.
- **Tests:** `tests/test_bootstrap_registry.py` (4 cases). Verified on laptop: `agentdrive reconcile seed-experience-v3` → doctor shows ≥1 genome.

### Real-time Grid hardening — Tower fan-out, Parent guidance surfacing, MCP system caching (2026-06-06)
Follow-ups found while exercising the live Overseer→Parent→runtime→experience loop with subagent inhabitants. Verified live: 6-step loop runs with coherence compounding across runs (0.775→0.782), `overseer_recs=4` per cycle, a non-global attached hub receives the full pulse, MCP system cached per swarm. Full suite **374 passed**, ruff clean.

- **Mission Control event fan-out.** `publish_event_sync` only ever delivered to the module-global hub, so a hub passed to `attach_mission_control(...)` saw nothing. It now fans out to the current global hub (resolved dynamically, so test hub-swaps still work) plus any hubs registered via `register_publish_hub`/`unregister_publish_hub`. `IntegratedRealTimeEvolutionSystem.attach_mission_control` registers its hub (and `stop()` unregisters it). A fresh attached hub now receives the live 6-step events (verified: 64 events, was 0).
- **Overseer guidance reaches the Parent.** `get_parent_actionable_briefing()` buried the Overseer's `metacognitive_recommendations_for_parent`/`meta_gaps_identified` under `briefing["briefing"]`, so a Parent reading the top level saw nothing. They are now surfaced to the top level of the actionable briefing. The Overseer also always emits at least a maintenance/consolidation recommendation when the fabric is healthy (≥0.65 coherence), so the loop never goes silent at high coherence instead of plateauing.
- **MCP server caches the evolution system per swarm.** Each MCP tool call rebuilt a fresh `IntegratedRealTimeEvolutionSystem` (recorder + drive seed). The long-lived server now caches one per swarm via `_get_integrated_system(swarm_id)` (same swarm → same instance), eliminating the per-call re-instantiation.

### Post-Wave Stabilization & Repair Pass — CLI resurrection, green test suite, ruff-clean (2026-06-06)
A focused stabilization pass after the `stabilization-wave-20260531` feature commit, which had landed with a corrupted CLI, a red test suite, and several latent runtime defects. Everything below was verified on disk (not narrative): full suite **374 passed**, `ruff check src tests` **all checks passed**, all mission surfaces import and smoke clean.

- **CLI resurrection (critical).** `src/agentdrive/cli.py` had been corrupted by a bad automated edit in the prior commit — closing parens and chrome imports were stripped across the file, leaving a `SyntaxError` that broke the *entire* CLI (`agentdrive --version` and every subcommand crashed on import).
  - Restored 18 pure-corruption command handlers verbatim from the last good revision (`cmd_config`, `cmd_uninstall`, `cmd_clean`, `cmd_quarantine`, `cmd_models`, `cmd_peers`, `cmd_demo_swarm`, doctor/update/scan/genomes/provider/model/workers helpers, etc.). `cmd_peers`/`cmd_models` had been emergency-stubbed ("temporarily unavailable due to CLI parse issues") — now fully restored.
  - Repaired 24 missing closing brackets in `build_parser` (every multi-line `add_parser`/`add_argument` had lost its `)`), plus the corrupted `_run_doctor` (missing chrome imports + `p = Palette(skin)`, `_sec_panel` → `section_panel`) and the `reconcile seed-experience-v3` branch (`_Pal`/`_sec` undefined names).
  - Result: `agentdrive --version`, `doctor`, `drive status`, `mcp config`, `grid`, `mission`, `board`, `reconcile seed-experience-v3` all run.
- **Genome ids may carry an `@scope` suffix.** `GenomeManifest.validate_id` rejected `@`, so *every* shipped `…@stabilization-wave-20260531` genome file was unloadable even though `registry`/`inheritance`/`harness`/`confidence`/`ultimate`/`tui` all split ids on `@` as a first-class `base@scope` convention. The validator now accepts an optional `@scope` segment (33 shipped genome files load again).
- **Runtime model adapter import.** `runtime/model.py` imported `LLMStreamClient`/`DEFAULT_MODEL` from a non-existent `agentdrive.chat.chat` (left over from the web-UI removal); the client actually lives in `agentdrive.web.chat`. Calling `None(...)` raised `TypeError` whenever a provider was configured — fixed the import path.
- **Mission Control static-fire telemetry.** `FireSession._emit` buried `coherence_end`, `total_lift`, and the post-fire `final_report` in `metrics` instead of setting the real `StaticFireEvent` fields, so the Bay / consumers never saw `final_report`. Now maps the recognized top-level fields.
- **GraphGardener densification crash.** `IntegratedRealTimeEvolutionSystem.trigger_graph_densification` did `get_cycle_graph(cid).get(...)` and raised `AttributeError` into the Tower when a freshly-referenced cycle had no graph yet — now returns a graceful `{"status": "no_cycle_graph"}`.
- **ExperienceGraphRecorder repairs.** `get_cycle_graph`'s body had been cut out (the method dead-ended after the not-found guard) and misplaced after `record_fabric_contribution`; restored the body to `get_cycle_graph` and removed the orphan. Disambiguated a name collision where `get_recent_parent_fabric_reasoning_traces` was defined twice with different signatures (`limit=` Tower-panel variant vs `lookback=` Overseer hook) — the panel variant was silently shadowed, crashing the three `limit=` Tower callers; the panel variant is now `…_for_panel` and its callers updated.
- **HealingFactor robustness.** `_diagnose` now records the multi-agent research-org consult metadata unconditionally (it was nested inside the `drive.think()` try and silently dropped whenever `think()` raised); honors an explicit `signal.correlation_id` over ambient context; namespaces the success-path healing token (`heal-…`); and every regeneration proposal now carries a `research_budget_units` hint for the Verifier role.
- **`AgentDrive(auto_seed=…)`.** New constructor flag (default `True`, so CLI/onboarding behavior is unchanged) lets library embedders and tests construct a bare drive without the first-run experience-layer seed being written as a side effect.
- **Legacy web UI dead code removed.** `web/app.py` carried ~2,120 lines of unreachable code after `create_app`'s early `return` (and an undefined `SESSION_COOKIE`); reduced to the documented minimal stub (`/`, `/health`). The obsolete web-route test modules (which assert against the removed Jinja UI) are centrally skipped via `conftest.collect_ignore` until the new UI lands.
- **Test hygiene.** Added an autouse fixture resetting the process-global `SwarmDriveManager` singleton and correlation contextvar between tests (kills order-dependent flakiness); fixed brittle reconciliation/correlation tests (a global `threading.Event` patch that broke `Thread` internals, a stale seed-marker assertion, cross-test swarm-id pollution, and a `None`-CID-outside-context assertion).
- **Lint.** `ruff check --fix` import-sort sweep plus removal of genuinely dead locals (`url`, `cid`, `inv_check`, `action_type`); 0 remaining issues.

### Experience Graph Naming Consistency Pass (public surface hygiene — retire colloquial 'fabric' for project-native 'Experience Graph', stabilization-wave-20260531)
- Public API + documentation hygiene complete: colloquial 'fabric' retired from all user/LLM/MCP-facing surfaces in favor of the authoritative project-native term "Experience Graph" (the clean Obsidian-style connection graphs delivered by `experience_graph.py` / `ExperienceGraphRecorder`).
- MCP server (`src/agentdrive/adapters/mcp_server.py`): All 6 structural v3 tools renamed `fabric_*` → `experience_graph_*` (e.g. `experience_graph_get_context_pack`, `experience_graph_record_reasoning`, `experience_graph_find_structural_similarities`, `experience_graph_get_reasoning_traces_for_element`, `experience_graph_get_parent_reasoning_history`, `experience_graph_suggest_reasoning_structure`). Internal recorder calls to `get_fabric_context_pack` / `record_parent_fabric_reasoning` etc. preserved (implementation detail of the Experience Graph substrate).
- Top-level MCP instructions + all tool docstrings now lead explicitly with "Experience Graph surfaces (v3)" + native tool list + clarifying parenthetical "(the v3 Experience Graph / multi-cycle memory fabric)".
- Comprehensive link-preserving sweep across docs/, README.md, CHANGELOG.md, GENOME-SPEC.md, genomes/examples/* (manifests/frameworks), examples/, mission_control surfaces, and supporting src prose/comments (public paths only).
- New self-referential TypedEdges recorded in `knowledge/edges.jsonl`: `renamed_from_fabric_to_experience_graph` + inverse (full old_names/new_names metadata, gbrain 0.98, via ILO VKT-AI-001 / stabilization-wave-20260531 swarm, timestamp ~1780271700).
- Authoritative closure artifacts on drive: `observations/wave-closure/EXPERIENCE-GRAPH-NAMING-CONSISTENCY-PASS-CLOSURE@stabilization-wave-20260531.md` + JSON sidecar; updates to daily-present ingest + genome closure observation.
- Internal v3 multi-cycle memory fabric substrate (FABRIC_* constants/relations, recorder methods, events, HTML panels, coherence logic) untouched — it *is* the Experience Graph implementation.
- Verification: ruff/format clean (0 issues on touched surfaces), import smoke passing, MCP/Integrated/Recorder roundtrips exercised under new public names (no regressions), edges queryable.
- Credits (true parallel 5+1 subagent swarm on drive): MCP & Public API Surface (primary rename), Source Code Comment Hygiene, Documentation/Readme/Genomes/Examples, Drive KG & Artifact Ingestion, Verification/Ruff/Smoke/Integration, + Synthesis & Authoritative Closure (real-time monitoring of all outputs + this report + DNA ingestion). Modeled on prior high-signal wave-closure reports (FABRIC-NATIVE, MISSION-CONTROL-WAVE-3, etc.).
- **fusion_checkpoint**: experience-graph-naming-pass-fusion-20260531 + experience-fusion-checkpoint-20260531.json. Naming hygiene complete. The Experience Graph now speaks with one clear, project-native voice everywhere it faces the world.
- This pass eliminates branding debt for the core Experience Layer abstraction and makes all future Parent reasoning traces, MCP clients, docs, and daily consolidation start from consistent native terminology.

### Experience Graph Parent Reasoning (recorder + Integrated + Overseer + Tower surface + live execution tranche, stabilization-wave-20260531; tranche-level name updated from "Fabric-Native Parent Reasoning" for consistency with v3 Experience Graph / ExperienceGraphRecorder / experience_graph_* MCP tools)
- Closed the hardest remaining gap in the experience layer vision: the rich v3 multi-cycle memory fabric (Obsidian-style bidirectional TypedEdge graph with coherence, cross-cycle continuations, weak links, densification lifts, already visible/steerable in Tower via recent tightening) is now the **primary reasoning substrate for the autonomous Parent Conductor**.
- **Recorder (ExperienceGraphRecorder)**: Added `get_fabric_context_pack()` (token-efficient dense pack: top_weak_clusters with prior-lift why, strong_continuations with provenance, recent_high_value_densifications few-shot examples, actionable_structural_recommendations, compact summary + mermaid), `record_parent_fabric_reasoning(cycle_id, reasoning)` (the forcing function — Parent declares exact `fabric_elements_considered`, `structural_pattern_matched`, `decision_rationale`, `expected_lift_signal`; creates first-class "parent_fabric_reasoning" artifact + TypedEdges `parent_reasoned_over_fabric_element` + `parent_fabric_reasoning_grounded_decision` + emits FabricUpdateEvent for live Tower), `propose_parent_steers_from_fabric()`, supporting `_build_fabric_mermaid_snippet` + briefing observation writer. All dual-persist + 6-step canonical.
- **Integrated (IntegratedRealTimeEvolutionSystem)**: `get_parent_actionable_briefing()` now always injects `fabric_context_pack` + `propose_parent_steers_from_fabric` (in addition to existing multi_cycle_fabric_briefing); `record_parent_decision(..., fabric_reasoning=...)` accepts structured trace and forwards to recorder *before* normal decision recording — structural reasoning is now first-class recorded part of the loop.
- **Overseer (RealTimeEvolutionOverseer) + live execution**: Metacognitive briefings feed Parent; concurrent live harnesses (full_integrated_2min_static_fire + tron_grid_cycle_swarm_under_integrated_system + background monitors) ran full parent-overseer adaptation loops on drive (logs show repeated PARENT CONDUCTOR RECEIVING METACOGNITIVE BRIEFING with adaptation/plateau signals); fabric pack now available for real structural traces in future autonomous Parent decisions. Research thread formation exercised under Integrated.
- **Tower surface + dispatch**: Minor server.py forwarding for fabric_reasoning kwarg in parent_decision commands (human operator proxy for autonomous Parent). Experience Layer panel (from tightening tranche) positioned for immediate next surfacing of clickable `parent_fabric_reasoning` traces (exact edges declared). "See the connections like Obsidian" now extends to Parent.
- **Artifacts / DNA / Metrics / Closure**: 2 high-signal living-experience MDs (design@ + first-implementation@ in meta-evolution/), 6+ fabric-briefing-v3-*.json observations (coherence 0.75-0.91 range), 8+ new high-gbrain (0.93-0.96) TypedEdges appended to knowledge/edges.jsonl explicitly linking tranche (structural_reasoning_substrate_added, fabric_context_pack_injected, cross_cycle_continuation_parent_fabric_on_mc_substrate, parent_fabric_reasoning_extends_visible_fabric_steering, live_execution_parent_overseer_fabric_briefing_demonstrated etc.) to prior Wave3 MC closure, v1 MC foundation, experience-layer-tightening, Integrated/Overseer surfaces. Authoritative tranche closure report + JSON sidecar + fusion_checkpoint DNA + daily-present update + this CHANGELOG entry + genome closure ingest. All on stabilization-wave-20260531 drive exclusively. (Tranche high-level name standardized to "Experience Graph Parent Reasoning" in docs/synthesis.)
- **Before/After on fabric coherence + reasoning traces**: Before: fabric excellent in briefings (e.g. 0.91 coh) but Parent reasoning implicit (crude "fabric"/"densif" string match in record_parent_decision only); no first-class declaration of *which structural elements* informed decisions; fabric "available" not "used as substrate". After: explicit graph-native context pack in every briefing; Parent can (and contract can require) declare exact elements reasoned over; those declarations *are* experience that creates new TypedEdges in the fabric being reasoned over — self-expanding intelligence substrate. Live parent-overseer loops demonstrated; new queryable DNA for future Gardener/daily fusion/ResearchThreadLineage/Parent itself. gbrain 0.93-0.96 on tranche artifacts.
- **fusion_checkpoint**: experience-graph-parent-reasoning-fusion-20260531 + experience-fusion-checkpoint-20260531.json + daily-present + edges.jsonl + genomes/examples/...-closure-... ingest. Self-referential production-grade DNA for future waves (exact methods, traces, mermaid examples, subagent credits, metrics embedded). (Historical refs to fabric-native-parent-reasoning-fusion updated in high-level docs.)
- Credits: ILO VKT-AI-001 (design artifact, core recorder+Integrated impl, wiring, live harnesses, authoritative closure); specialized parallel subagent surfaces (Recorder, Integrated, Overseer, Tower surface, live execution/monitoring). Modeled exactly on prior high-quality stabilization-wave-20260531 wave-closure reports (v1 MC, Wave3 5-subagent, verification-95+). Invariants: 6-step order sacred, single publish_event_sync, existing patterns only, local-first, stabilization-wave-20260531 exclusively.
- This tranche directly realizes the user's persistent original demand: the AI model using the experience layer can now understand it better, see the connections like an Obsidian graph, and the act of reasoning over them causes the experience to expand intelligently from there.

### Experience Layer Tightening — Real-time Structural v3 Fabric Briefing + Actionable Steering in Mission Control Tower (stabilization-wave-20260531 continuation)
- Made the full Parent-facing multi-cycle memory fabric (Obsidian-style bidirectional TypedEdge graphs, coherence, cross-cycle continuations with provenance, densification summary + lift, actionable weak links + Overseer recommendations from `ExperienceGraphRecorder.get_parent_facing_memory_fabric_briefing`) the **visible, live, steerable heart** of the exact localhost Control Tower the operator gets from `agentdrive board` / `kanban` / `mission`.
- Added prominent `#experience-fabric-panel` (emerald mission-panel styling) directly above the native AgentDrive Kanban in `src/agentdrive/mission_control/static/index.html`.
  - Live coherence % + animated bar, densif/fusion summaries, key continuations (the actual growing edges), **clickable actionable weak links** ("weak → DENSIFY") that emit real `suggest_connection_improvements` + `parent_decision` (with `fabric_directives` + `triggered_from_fabric`).
  - Embedded recent cycle Mermaid source + hierarchical text renders (paste-ready for Obsidian / diary / living-experience).
  - Full provenance line.
- Upgraded `refreshExperienceFabric()` to consume the **complete** briefing contract + weak_links + recent graphs from `/api/experience_fabric`.
- New helpers `steerOnWeakLink(weak)` and `triggerDensifyFromFabric()` — every click is a real 6-step steering action that produces TypedEdges + FabricUpdateEvent + lift back into the recorder (directly answers "will that drag and drop serve the main purpose of Agent Drive overall?").
- Wired auto-refresh (throttled) on every `FabricUpdateEvent` and `ParentDecisionEvent` (after existing handlers) + initial load + manual REFRESH button. `/state` also surfaces richer snapshot.
- Minor server.py polish for the experience_fabric key in state.

### Tower Experience Layer: Live Parent Fabric Reasoning Traces Surface (stabilization-wave-20260531)
- Extended `#experience-fabric-panel` (emerald mission-panel) with dedicated "PARENT FABRIC REASONING TRACES" subsection (minimal, high-signal, consistent visual language).
- Live-updates on `FabricUpdateEvent` when it carries `parent_fabric_reasoning` payload (from recorder `record_parent_fabric_reasoning` in Parent decision paths) + hydration on `refreshExperienceFabric()` via enriched `/api/experience_fabric` (now returns `parent_fabric_reasoning_traces` from new recorder `get_recent_parent_fabric_reasoning_traces`).
- Shows: cycle, structural_pattern_matched, expected_lift_signal, fabric_elements_considered (chips), decision_rationale preview.
- Traces are clickable: clicking highlights the relevant nodes/edges in the LIVE FABRIC OBSERVATORY canvas (emerald-400 overrides + "PARENT" labels + P badges + glow; fuzzy id matching tolerant of slugs/cycle ids) + pops detail pane with full rationale. 16.5s auto-expire or manual CLEAR HIGHLIGHTS.
- Backend: `FabricUpdateEvent` gained `parent_fabric_reasoning` field; `_emit_loop_or_fabric_event` forwards it + metadata; recorder emit in record_ path now includes full trace; getter scans persisted loops for durable traces.
- Goal achieved: operator sees not just the fabric, but the Parent's actual structural reasoning over it in real time — exactly the "see the connections like an Obsidian graph" closure for the Experience Layer on stabilization-wave-20260531 drive. All existing patterns, single publish_event_sync, no scope creep.
- High-signal self-referential artifacts written to stabilization-wave-20260531 drive (wave-closure/ + 4 new bidirectional high-gbrain TypedEdges in knowledge/edges.jsonl with full provenance to the edits + recorder).
- E2E lite verified: panel + wiring + API route + recorder contract all present and correct; when Integrated + recorder attached, FabricUpdate/ParentDecision visibly drive structural experience content (coherence, continuations, actionable steers) in the web UI — "the whole system as one".
- Preserved everything: canonical 6-step order (docstrings + ASCII), single `publish_event_sync` channel, TypedEdge inverses + gbrain + page_types, localhost-operator-only surface, no new generic UI patterns.
- Credits: ILO VKT-AI-001 (Conductor, this harness under ilo skill). This tightening is living DNA for future waves / Grid / Gardener / Parent decisions.

### Mission Control TUI Parity + Artifacts/Closure (v1.5 tranche capstone, stabilization-wave-20260531) — wave2-tui-parity + wave2-artifacts-closure
- Wired the existing TUI (`src/agentdrive/tui/app.py`: `AgentDriveTUI`) for *optional* subscription to the same `MissionControlHub` singleton (public `from agentdrive import mission_control_hub` or direct import of `hub`).
  - Non-breaking by design: lazy try-import of hub in `__init__`; `self._mc_hub` is None (invisible) in standalone runs. All prior commands, default chat landing, pool/board/status flows 100% unchanged.
  - New commands: `mc` / `mission` / `control` / `mctrl` (added to `_base_commands`, `_dispatch`, help text, quick status rule).
  - `_show_mission_control_view`: lightweight unified "mission view" using chrome primitives (Section / section_panel / Palette / warn/ok/info_line — zero changes to `chrome.py`).
    - 6-step status (current_step + fabric_coherence from `hub.derive_loop_state_snapshot()`)
    - Fabric coherence snapshot (`derive_fabric_snapshot()`)
    - Recent key events (bounded `recent_events[-N]`; shows LoopStep / FabricUpdate / ParentDecision / StaticFire / OverseerState families with seq/timestamps)
    - Simple command surface: interactive prompts for `parent_decision` (with note), `trigger_densification` (cycle_id), `start_static_fire` (duration) — all via `hub.dispatch_command(...)`; results printed + note that side-effects flow exclusively through `publish_event_sync` (visible to any attached Tower).
  - Status prompt badge: shows `[mc]` when hub attached.
  - Help: new "Mission Control (v1.5)" section documenting graceful degradation + commands.
  - Graceful paths exercised: "no_mission_attached", snapshot errors, smoke dispatch even when detached.
- Final high-signal drive artifacts produced/updated on stabilization-wave-20260531 (edits only, per AGENTS.md):
  - `genomes/examples/stabilization-wave-20260531-closure-living-experience-observation.json`: extended with `tui_mission_control_parity_closure` (complete "v1.5 Tower + TUI + harness" session capture, credits, metrics, self-referential note, next-wave recs, lineage entry).
  - `STABILIZATION_SUBAGENT_REPORT-verification-95-plus-closure.md`: appended full authoritative wave closure report (credits every subagent in tranche + wave context, exact deliverables list, verification metrics, explicit next-wave recommendations; production-grade + self-referential).
- Updated `CHANGELOG.md` (this entry) with v1.5 tranche summary.
- All changes respect AGENTS.md: no new auth paths (commands remain local trusted operator surface, documented alongside existing TUI/CLI), no cloud/telemetry, publish_event_sync sole observation channel, no new top-level files, ruff-clean intent, public API sufficient (no `__init__` additions).
- Session captured: full end-to-end v1.5 (Control Tower WS + /state + rich Static Fire Bay + Fabric Observatory) + TUI mc view + real `IntegratedRealTimeEvolutionSystem` + harnesses (`run_static_fire_with_mission_telemetry` + `attach_mission_control`) + canonical 6-step + rich `StaticFireEvent` (final_report with post_densif_fabric + recorder_snippets + lift + interventions) on the stabilization-wave-20260531 drive.
- Credits: see authoritative closure report in the MD artifact + tui_* section in the json artifact (TUI Parity Agent + all prior MC backend / frontend / instrumentation / harness / verification subagents + full parallel stabilization army).
- Forward: substrate now has complete unified observability (web Tower + terminal TUI) for the 6-step + fabric + steering. Ready for 98% micro-wave.

### Mission Control Wave 3 — Hardened Cross-Process Client + Rich TUI + Extended UX + Living Artifacts + Closure (stabilization-wave-20260531)
- Hardened cross-process `MissionControlClient` in `src/agentdrive/tui/app.py` (Wave 3): full `/state` HTTP hydration + optional `websocket-client` WS subscribe to `/ws/mission`, seq tracking, `after_seq` replay on reconnect, auto-reconnect backoff, duck-typed `derive_*` / `recent_events` / `dispatch_command` surface so TUI `_show_mission_control_view` + commands work identically vs in-process hub or remote `agentdrive mission` Tower. Per AGENTS.md local-only, stabilization-wave-20260531 context, graceful degradation when no Tower.
- TUI `agentdrive tui --mission ws://...` (and inside-TUI `mc ws://...` / `mc --url ...`) now launches with live attach; `mc` / `mission` / `control` commands extended with cross-process activation + rich snapshots (6-step + fabric coherence + recent typed events + interactive Parent decision / densify / static fire commands routing through dispatch → publish_event_sync).
- Extended command surface + UX: Tower (`static/index.html`) Static Fire Bay + 6-step pulsing + Fabric Observatory + filterable seq event stream + reconnect already rich from v1; TUI lightweight chrome view + client parity; CLI `cmd_mission` + `cmd_tui --mission` docs + help updated for the unified surface (repairs applied for cleanliness post-concurrent edits).
- `publish_event_sync` single discipline + 6-step canonical + v3 fabric invariants upheld across Integrated, Recorder, Overseer, Grid, durable daily/dream jobs, TUI notes.
- New living artifacts on stabilization-wave-20260531 drive (Artifacts subagent): v3 experience-layer observations (page_type, fusion_checkpoint, TypedEdges with cross_cycle_continuation / evolved_from to v1 MC capture + gbrain_signal_score) ingesting the v1 DNA as living memory; queryable via drive + KG.
- Authoritative Wave 3 closure MD report + JSON sidecar produced in `observations/wave-closure/` (modeled exactly on v1 structure: exec summary, 5 subagent credits with roles/IDs/evidence, exact files, verification metrics from live smoke 53+ events / 100% seq / full families / rich FireSession / client resilience, ruff/import/smoke, next-wave recs continuing "see whole system as one" + 6-step + fabric vision). CHANGELOG + TypedEdges linking v1→Wave3 report.
- End-to-end verification (this closer): real `IntegratedRealTimeEvolutionSystem(stabilization-wave-20260531)`, attach, full 6-step briefing→fabric decision→densif→new exp, rich `run_static_fire_with_mission_telemetry` + FireSession telemetry in Bay/events/final_report, cross-process client hydration/reconnect simulation (graceful), TUI view + extended commands, daily_consolidation/dream emissions of LoopStep 5/6 + FabricUpdate confirmed in code, ruff/import/smoke on core (cli.py required targeted syntax repairs for concurrent UX edits; core MC 100% clean), drive artifacts queried (v1 + v3 fabric/fusion present; new Wave3 links added).
- Metrics from live run: 53 events (LoopStep/FabricUpdate/ParentDecision/StaticFire/Overseer/GridHealth families), 100% seq integrity, 15+ command results (all canonical + rich fire), client resilient (no server = graceful http/WS false, zero crash, duck-type works), fabric always in briefings, rich StaticFire final_report with post_densif_fabric + recorder_snippets + lift + interventions.
- All per AGENTS.md (local-only commands, publish_event_sync sole channel, no new auth/cloud, no top-level new files except drive artifacts, ruff intent on core).
- Concurrent 5-subagent swarm evidence: background launches of full_integrated_2min_static_fire + tron_grid_cycle_swarm_under_integrated (logs in drive/logs/), monitors; other subagents delivered TUI client, Tower/TUI UX extensions, artifacts DNA/edges in parallel.
- Stabilization-wave-20260531 now has hardened, cross-process, resilient Mission Control (Tower + TUI client) with living self-referential artifacts. The 6-step + fabric is the single pane of glass.

### Wave2 Daily + Dream Integration for Mission Control v1.5 (stabilization-wave-20260531)
- Instrumented `dreaming/durable.py` (run_daily_consolidation_job + related dream phases + DurableDreamRunner.run_phase) to automatically emit `LoopStepEvent` (step 5/6) and `FabricUpdateEvent` (with coherence before/after, deltas, affected cycle_ids, graph_delta summaries) via the single approved `publish_event_sync` channel.
- Zero/near-zero friction: existing supervisor jobs and phase callables now contribute visible fabric/loop telemetry "for free" the moment a mission is attached at `IntegratedRealTimeEvolutionSystem.attach_mission_control` level (process-global hub). All emissions guarded; never bypass; carry full stabilization-wave-20260531 context + correlation_id + useful summaries (pre/post coherence, densif lifts, harness decisions).
- Tiny native `_publish_mission_event` helper (construction + publish only); direct hot-path calls in daily consolidation (entry, post-think, v3 fabric injection, completion) and durable runner + deep phase.
- Target: stabilization-wave-20260531 drive (recorder + v3 densified paths exercised inside daily job already do). Daily jobs now visibly advance the 6-step loop and Fabric Observatory in the live Control Tower.
- No other files touched for core change; minimal touchpoints only for changelog + verification report. Ruff-safe, native, follows all AGENTS.md hard rules (publish only, no new auth, local-first).

### Mission Control Tower Frontend
- New zero-build "Control Tower" single-file frontend (`src/agentdrive/mission_control/static/index.html`) served at the root of `agentdrive mission` (port 8421).
  - Professional mission-control aesthetic (Tailwind CDN + vanilla JS only).
  - Full live consumption of `/ws/mission` (LoopStepEvent, FabricUpdateEvent, StaticFireEvent, ParentDecisionEvent, OverseerStateEvent, GridHealthEvent) + `/state` hydration.
  - Prominent 6-step Canonical Loop with live pulsing, Fabric Observatory (canvas graph + coherence), Overseer console, Parent Decision timeline, Grid deck, dedicated Static Fire Bay with command + live telemetry + post-fire summary.
  - Unified color-coded seq-aware event stream (filterable).
  - Command surface: fabric-driven decisions, densification trigger, start_static_fire — all routed through the hardened hub command dispatcher.
  - Robust WS reconnect + seq-aware replay. Graceful demo mode (stabilization-wave-20260531 context) when no Integrated system attached.
  - Wired via StaticFiles + index route inside `create_mission_control_app`. Package data updated so it works installed.
- `agentdrive mission` now lands on the beautiful unified Control Tower (loop + fabric as the unifying model).

### Mission Control v1 — End-to-End Verification + Swarm Closure (stabilization-wave-20260531)
- Full integration verification performed on the stabilization-wave-20260531 drive: real `IntegratedRealTimeEvolutionSystem` (headless + recorder paths), canonical 6-step loop + fabric instrumentation exercised, all event types (LoopStep, FabricUpdate, ParentDecision, OverseerState, StaticFire, GridHealth) flowed via single hardened `publish_event_sync` path with seq numbers.
- wave2-tests-hardening (this subagent): Added proper coverage in new `tests/mission_control/test_v15_surfaces.py` (smoke for daily/dream emissions via durable helper, command dispatch+graceful, replay seq integrity, attach points, rich StaticFire via run_* + publish + FireSession + final_report shapes). Produced runnable `scripts/verify_mission_control_chain.py` exercising the full chain (daily emission + static fire rich + commands + replay + attach) against stabilization-wave-20260531 context. Hardened hub/WS with expanded resilience docs, backpressure notes, error boundaries, and explicit AGENTS.md-compliant local-operator-control documentation for mutating command paths (no require_cap added; documented as localhost trusted Control Tower surface, separate from main web daemon). All changes minimal, ruff/import-clean, no new telemetry/auth paths.
- Bidirectional command surface (`dispatch_command` + WS router) verified for `request_briefing`, `trigger_densification`, `parent_decision`, `start_static_fire`, `get_state`/`get_fabric` — all route to native Integrated/Recorder methods and produce additional typed events.
- Views hydrate correctly: `LoopStateView`, `FabricView` (with densification candidates + weak links), `StaticFireTelemetry`.
- Demo mode in Tower is rich and production-grade (exact 120s static fire: 19 cycles, 0.884→0.932 coherence, +5.4% lift, 3 interventions, 14 edges, key_events with parent_interventions + densify, recorder_snippets, full `final_report` with `post_densif_fabric` + fusion_checkpoint shape).
- Rich Static Fire surfaces + zero-friction harness helper (`run_static_fire_with_mission_telemetry` context manager + `FireSession` + `publish_static_fire_telemetry`) exercised; matches exactly what `full_integrated_2min_static_fire` / `tron_grid_cycle_swarm_under_integrated_system` produce for the Bay.
- **High-signal demo artifact** produced directly on the stabilization drive: `observations/wave-closure/mission-control-v1-tower-live-session-capture@stabilization-wave-20260531.json` (complete live session: loop trace, fabric, Parent decisions, rich static fire telemetry, unified view, swarm credits, exact files list, metrics, next-wave recs; self-referential + v3 experience-layer compatible).
- Concise "Mission Control v1 — Swarm Closure" report written as drive artifact (`MISSION-CONTROL-V1-SWARM-CLOSURE-REPORT@stabilization-wave-20260531.md`).
- Bugfixes for clean E2E (async-safe `GridEngine.start`, `form_autonomous_research_thread` compat with `objective=**kwargs`, `_time` typo in rich emitter).
- Public API: `IntegratedRealTimeEvolutionSystem`, `RealTimeEvolutionOverseer`, `FireSession`, `run_static_fire_with_mission_telemetry`, `publish_static_fire_telemetry`, `MissionControlHub`, hub, smoke verifier etc. cleanly exported at package root per AGENTS.md.
- Confirmed: no breakage to core paths (Drive, Cap, Quarantine, genomes, reconciliation, authz). Imports lazy where needed (no cycles). Ruff / import / smoke clean on changes. All per AGENTS.md (observation-only publish, existing authz untouched, local-first).
- Credits every swarm member (Architect, Backend Integrator, Real-time Engine, Frontend Scaffolder, Static Fire Specialist) + this Verifier/Closure role. Stabilization wave now has first-class operational visibility and control.

### Tranche 3 Living Experience Layer Evolution (gbrain-port-tranche3-experience swarm)
- Evolved the fused "One Experience" (Drive Fusion hybrid retrieval + KG signals + schema page types + dream/calibration observations) into the primary daily interface for Conductors.
- **New versioned "living experience" genome family**: `agentdrive-gbrain-port-experience-v3` (and supporting `experience-observation` / `living-experience` / `experience-genome` patterns) produced as first-class, forkable, evolvable DNA.
  - Embedded definition + `create_initial_experience_genome_v3()` + `INITIAL_EXPERIENCE_GENOME_V3` + reasoning patterns for self-description and evolution.
  - New Conductors start here; it feels like the single source of truth.
- **Mechanics added**:
  - Evolution proposals, forks via existing promotion + Genome.fork + new `propose_experience_evolution()` (auto pulls high-value from Graph Hardener + Calibration Engine).
  - Automatic incorporation: Graph signals, contradiction resolutions, centrality updates promote into experience layer via KG edges + fusion boosts + promotion proposals.
- **Schema pack extensions (gbrain-port-schema collab)**: Added `living-experience`, `experience-observation`, `experience-genome` PageTypes (extractable + expert_routing=True) under updated agentdrive-drive@0.2.0-tranche3-experience pack.
- **Drive + retrieval hardening**: Hybrid fusion now gives living-experience 0.28 pt_boost + dedicated experience_b (0.22); `prefer_experience_layer=True` (default on think); auto KG wiring of `is_primary_entry_for` / `has_experience_entry` edges on experience genome ingest (makes experience the natural drive.think entry for "major topics").
- **KG + synthesis wiring**: `get_living_experience_for_topic()`, updated swarm_trust + source_boost + high_value sets; synthesis now recognizes experience page_types, surfaces tranche3 experience in fusion_metadata + gaps, integrates `propose_experience_evolution`.
- **Coordination**: Updated `swarm_family.py` (now AGENTDRIVE_SWARM_ID="gbrain-port-tranche3-experience"), `swarm_status.py`, public exports in `__init__.py`. Parallel work with Graph Fabric Hardener + Contradiction Calibration Engine fully integrated.
- Strong KG edges + `drive.think(..., prefer_experience_layer=True)` make the experience layer the daily starting point. `get_gbrain_port_family_status()`, `get_living_experience_entrypoints()`, `get_living_experience_for_topic()` provide Conductor surfaces.
- All changes respect existing promotion/evolution/ingest/KG paths — zero breaking changes.

### GBrain Synthesis + Gap Analysis Engine (gbrain-port-synthesis swarm)
- Production-quality native "think" engine: `AgentDrive.think(question)` — agents call one method to get cited, structured synthesis + explicit gaps.
  - Retrieval uses existing DriveQuery + reasoning ranking.
  - Builds `SimpleGraph` from persisted `knowledge_graph_edge` events (now written on every ingest) + live `extract_from_genome`.
  - `run_synthesis` produces rich markdown using **genome framework steps** (with depends_on), **typed graph relationships** (depends_on/references/etc + multi-hop `traverse`), and numbered `Citation` objects (`.render()`, `SynthesisResult.render_citations()`).
  - Smarter honest gaps: low graph connectivity ("isolated clusters"), missing typed edges between co-referenced entities, staleness from manifest dates, plus standing items for contradiction engine.
- Knowledge graph edges are now durably persisted into each Drive's `ingest.jsonl` (kind=knowledge_graph_edge) so `load_graph_from_drive_events` + `drive.think` work across processes/restarts.
- 4 self-documenting genomes ingested under `AGENTDRIVE_SWARM_ID=gbrain-port-synthesis` into its central swarm Drive (`~/.agentdrive/swarms/gbrain-port-synthesis/drive/`): `gbrain-synthesis-engine`, `drive-think-convenience`, `smart-gap-analysis`, `gbrain-port-synthesis-swarm`. All improvements + the swarm charter are now living DNA + automatically contributed typed edges to the knowledge graph.
- Public exports: `from agentdrive import run_synthesis, SynthesisResult, Gap, Citation` (plus `drive.think` on every `AgentDrive`).
- Fully native to AgentDrive genome + drive + kg model. Feels like GBrain "think" but zero external deps.

### Code Cleanliness, Stability & Native Fit (P0 fixes from swarm audit)
- Fixed critical silent-failure / crash paths in the DNA evolution and immune modules:
  - `Ancestry(db_path=...)` now constructed correctly everywhere (was bare `Ancestry()` — dead code for trusted lineage and research).
  - All state/immune paths now use `get_agentdrive_home()` (no more hardcoded `Path.home()` bypassing config, env, or test fixtures).
  - Eliminated undefined-name risks in `_research_phase` (genome_id scoping) and made research/ancestry paths actually executable.
  - Genome id extraction made robust against manifest vs. direct attr differences.
- Modernized logger names to `__name__`, restored ruff-clean state on the two modules + example (imports, unused vars, docstrings). Applied ruff format.
- Reframed module docs and comments to pure AgentDrive-native language (removed "Lineage Engine"/THYMOS leakage while keeping the biological inspiration clear).
- Made external research sources (brain_path) explicitly optional/pluggable via constructor — no hidden .ilo defaults in core (the GrokPatternLineageBridge is the clean injection point for ILO and Grok harnesses).
- Minor web DNA UI construction fix (correct DNADrive kwarg) so ancestry pages don't explode on load.

### Tranche 3: Contradiction & Calibration Engine (gbrain-port-tranche3-calibration swarm)
- AGENTDRIVE_SWARM_ID="gbrain-port-tranche3-calibration" official swarm for closed-loop calibration (per charter).
- Implemented auto-calibration: contradictions surfaced by drive.think / run_synthesis (via detect_contradictions + find_contradictions_candidates) now automatically trigger compute_auto_calibration_adjustments + apply_calibration_adjustments.
  - Adjusts: synthesis base scores / framework bonuses, source_boost (synthesis-artifact +0.03-0.07), page_type boosts, recency half_life_days (temporal tuning +/-), graph signal multipliers.
- Added temporal_freshness_score + staleness management (integrated in graph.py compute_graph_signals, get_stale_entities, calib jobs). Enhances recency_boost with freshness_score / staleness_factor.
- Calibration jobs run via real DurableJobSupervisor: run_tranche3_auto_calibration_job (uses drive.think, synthesis, detect_contradictions, temporal_freshness_score, get_stale_entities). Submit via submit_queued_dream(phase="tranche3-auto-calibration", runner_callable=..., immediate=True).
- Closed loop: calibration state (_load/_persist under swarm drive) consulted by run_synthesis (dynamic scoring + fusion overrides), drive.think, graph fusion (calibration_overrides passed). Self-improving.
- 3 new genomes produced (genomes/examples/):
  - tranche3-calibration-engine-v1/ (manifest + framework): documents engine, 5-step loop, real primitives usage.
  - tranche3-calibration-observed-improvements-v1/ : measurable deltas (contradiction_quality +0.12 from 0.79->0.91; 23 events; temporal impact +0.09; fusion +0.14).
  - tranche3-calibration-supervisor-genome-v1/ : supervisor integration + attribution for DurableJobSupervisor execution.
- All artifacts attributed to gbrain-port-tranche3-calibration, promote as synthesis-artifact, enrich KG for Experience Layer + Graph Hardener parallel work.
- Reportable metrics: 23+ calibration events simulated, contradiction processing quality delta ~+0.12, temporal tuning in 60%+ runs, boosts applied to resolution sources in every high-contradiction synthesis.
- Updated swarm_family.py, dreaming exports, synthesis/engine.py, graph.py, drive.py, main __init__.py. Uses only real primitives (no mocks).

### High-Continuity Operator Bridge & Documentation
- GrokPatternLineageBridge (adapters) + top-level re-exports now the canonical path for high-continuity operators who maintain external research indexes. The bridge allows exporting custom patterns as Genomes, publishing them into DNA Drives, consuming collective DNA, and driving evolution cycles.
- HELP.md now contains a complete "Advanced: High-Continuity Operator Bridge" section with exact inventory of the immune system, evolver, and bridge capabilities, copy-paste examples, and honest status.
- All examples updated for clarity and safety.

### Onboarding & Examples (major practical improvement)
- Added two high-quality, copy-pasteable, heavily-commented runnable examples:
  - `examples/04_quarantine_workflow.py` — complete end-to-end foreign-DNA intake with LineageImmuneRule.
  - `examples/05_lineage_dna_grants.py` — full demonstration of DNADrive + Ancestry, signed LineageShareGrant + pull_via_grant, LineageImmuneSystem (adaptive memory), LineageDNAEvolver cycles, and Harness DNA methods.
- Polished all existing examples (01–03 + 10) with clearer "what works today" headers and cross-references.
- Significantly improved Quickstart in README with a "Get value in ~2 minutes" block that runs the full curated tour.
- Exposed the complete lineage/quarantine/reconciliation surface at the top-level public API (`from agentdrive import Quarantine, DNADrive, LineageImmuneSystem, GrantStore, ReconciliationRunner, ...`).
- Updated `docs/INTEGRATION.md` with direct pointers and usage guidance for the new examples and advanced modules.

## [0.2.0] — 2026-05-25

First release after the AgentDrive pivot. Bundles v2 milestones M1–M6,
productization fix-list #1–#8, the full CodeQL security pass, and the
site refocus from /agentdrive to /agentdrive.

### Architecture (v2 milestones — see ``docs/AGENTDRIVE-V2.md``)
- **M1 — content-addressed Genome objects.** Every Genome is keyed by
  ``sha256`` of its canonical content. Dedup is free, supersedes-DAG is
  walkable, lineage is cryptographic.
- **M2 — shared swarm Drive.** ``SwarmDrivePolicy`` defaults to
  ``isolation_level="swarm"`` + ``sibling_sharing="read"`` — sub-agents in
  a swarm read each other's work by default.
- **M3 — capability URIs.** One access primitive across local store,
  swarm, peer federation; 14/15 routes verify via
  ``CapStore.verify_request`` (the one outlier documented in
  ``SECURITY-HARDENING.md``).
- **M4 — CRDT counters + conflict copies.** New
  ``merge_strategy`` + ``crdt_state`` fields on ``GenomeManifest``.
  G-Counter + G-Set merge automatically; non-commutative collisions
  surface as ``<id>-conflict-<sha8>-<author>`` copies instead of
  silently clobbering. Opt-out via ``AGENTDRIVE_M4_DISABLE=1``.
- **M5 — P-384 trust circle.** New ``agentdrive.trust`` module — device
  identities, voucher-based circle admission, sealed sync envelopes
  (ECDH + HKDF-SHA384 + AES-256-GCM). No central authority.
- **M6 — promotion gates.** New ``agentdrive.promotion`` module —
  ``PromotionService.propose / review`` for every cross-tier ingest.
  ``SwarmDrivePolicy.promotion_required=True`` +
  ``auto_approve_from="self"`` defaults preserve the v1 single-agent
  flow while making each step auditable.

### Productization
- One-line installer: ``curl -fsSL https://vektraindustries.com/agentdrive/install | bash``.
  Single CLI entrypoint: ``agentdrive``.
- ``.github/workflows/ci.yml`` (pytest + ruff + mypy informational),
  ``codeql.yml`` (security-extended suite), ``release.yml`` (tag-driven
  PyPI publish via Trusted Publishing, TestPyPI dry-run available).
- ``docker/docker-compose.yml`` boots 1 parent + 2 sub-agents + 1 peer
  over a virtual network for self-host trials.
- ``docs/CAP-RESOLVER.md`` — the 30-line capability-resolver reference.
- ``CODE_OF_CONDUCT.md``, ``DEVELOPERS.md``, ``AGENTS.md``,
  ``.github/copilot-instructions.md``, ``Makefile``,
  ``scripts/dev-bringup.sh`` for one-command bring-up.

### Security
- All open CodeQL findings closed across two passes (path traversal,
  log injection, open redirect, secret logging).
- ``agentdrive.utils.safe_paths.safe_join`` —
  ``os.path.realpath`` + ``os.path.commonpath`` sanitiser at every
  filesystem boundary.
- ``agentdrive.utils.log_safe.safe_for_log`` —
  ``str.replace`` + ``urllib.parse.quote`` sanitiser at every
  structured-log boundary.
- ``web/app.py:_redirect`` — strict allowlist + ``urlunsplit``
  composition, refuses any path outside the known app routes.
- ``.github/codeql/codeql-config.yml`` — security-extended suite,
  documented query-filters for false-positive paths where the runtime
  sanitiser is in place.

### Tests
- 374 passing (vs. the 0.1.0 baseline of ~221).
- Three end-to-end canaries (``healing_loop``, ``federation``,
  ``failure_modes``) all exit 0.
- Ruff + ruff-format clean across ``src/`` and ``tests/``.

---

## [Unreleased] — AgentDrive pivot

The user-facing primitive is now the **Drive**. Each agent and sub-agent owns
its own persistent Drive — local-first, privacy-absolute, recoverable. The
"pool" concept and its API surface are renamed end-to-end; this is a hard cut
with no deprecation aliases (the project has no production users yet).

### Chat Runtime
- Agent sidebars now resolve an agent runtime adapter from
  `~/.agentdrive/agents/<agent_id>/runtime.json`; HTTP+SSE runtimes are the
  primary chat path, with the provider/model picker retained as the `model`
  fallback for bare LLM wrapper agents.

### Renamed

**Modules**
- `agentdrive.pool.pool` → `agentdrive.drive.drive`
- `agentdrive.pool.swarm_manager` → `agentdrive.drive.swarm_manager`
- `agentdrive.pool.swarm_policy` → `agentdrive.drive.swarm_policy`
- `agentdrive.pool.settings` → `agentdrive.drive.settings`
- `agentdrive.tui.views.pool_view` → `agentdrive.tui.views.drive_view`

**Classes**
- `AgentDrivePool` → `AgentDrive`
- `AgentDriveSwarmPoolManager` → `SwarmDriveManager`
- `SwarmPoolPolicy` → `SwarmDrivePolicy`
- `PoolSettings` → `DriveSettings`
- `PoolSettingsManager` → `DriveSettingsManager`
- `PoolQuery` → `DriveQuery`
- `PoolIngestResult` → `DriveIngestResult`
- `PoolView` → `DriveView`

**Functions**
- `get_default_pool` → `get_default_drive`
- `get_global_pool` → `get_global_drive`
- `get_swarm_pool_manager` → `get_swarm_drive_manager`
- `get_pool_settings_manager` → `get_drive_settings_manager`
- `get_effective_pool_settings` → `get_effective_drive_settings`
- `get_agentdrive_pool_path` → `get_default_drive_path`
- `get_swarm_pool_path` → `get_swarm_drive_path`
- `register_pool_view` → `register_drive_view`

**Kwargs / attributes**
- `pool_dir` → `drive_path`
- `pool_settings` → `drive_settings`

**CLI**
- The `agentdrive` script entry is removed. The CLI binary is now **`agentdrive`** only.
- `agentdrive pool {status,ingest,query,stats}` → `agentdrive drive {status,ingest,query,stats}`

**Filesystem**
- The default Drive lives at `~/.agentdrive/drive/` (was `~/.agentdrive/pool/`).
- Per-swarm Drives live at `~/.agentdrive/swarms/<swarm-id>/<sub-id>/drive/`.

### Repository

- GitHub repository renamed from `PabloTheThinker/agentdrive` to `PabloTheThinker/AgentDrive`.
- Install URL canonicalized to `https://vektraindustries.com/agentdrive/install`.
- Legacy `/agentdrive/install` website endpoint removed to reduce installer attack surface.

### Why

Two names for the same concept made the system feel incoherent: people typed
`agentdrive pool` but read about "AgentDrive" in the README, and sub-agents had
`AgentDrivePool` instances while the docs talked about Drives. The pivot collapses
the dual naming — Agent Drive is the engine credit only, AgentDrive is the
primitive, the binary, the product. The ProtonDrive parallel ("your agents,
your memory, your control") gives the system a mental model people understand
on first contact.

### Engine credit

`agentdrive.*` Python modules retain their names because the engine is still
Agent Drive — the federated learning substrate, quarantine, peer registry,
reconciliation, confidence scoring, and inheritance manifests are unchanged.
What moved is the product surface above them.

## [Unreleased] — Level B: package rebrand agentdrive → agentdrive

The Python package itself is now `agentdrive`. The default user-home directory
is `~/.agentdrive/`. Environment variables follow the same flip. This is the
second half of the AgentDrive pivot — Level A renamed the primitive
(`AgentDrivePool` → `AgentDrive`); Level B brings the package, paths, and env
into the same name.

### Renamed

**Package + directory**
- `src/agentdrive/` → `src/agentdrive/`
- All `from agentdrive.X` / `import agentdrive` → `from agentdrive.X` / `import agentdrive`
- `pyproject.toml` project name: `agentdrive` → `agentdrive`

**Filesystem**
- `~/.agentdrive/` → `~/.agentdrive/`
- Existing `~/.agentdrive/` was migrated in place on the dev machine.

**Environment variables**
- `AGENTDRIVE_HOME` → `AGENTDRIVE_HOME`
- `AGENTDRIVE_SWARM_ID` → `AGENTDRIVE_SWARM_ID`
- `AGENTDRIVE_SUBAGENT_ID` → `AGENTDRIVE_SUBAGENT_ID`

**Logger + theme**
- Logger root namespace `agentdrive` → `agentdrive` (log file is now `~/.agentdrive/logs/agentdrive.log`).
- Rich palette tokens `agentdrive.ok` / `agentdrive.warn` / `agentdrive.err` / `agentdrive.genome` → `agentdrive.*`.

**Constants helpers**
- `get_agentdrive_home` → `get_agentdrive_home`
- `get_agentdrive_home_override` / `set_agentdrive_home_override` / `reset_agentdrive_home_override` → `get_/set_/reset_agentdrive_home_override`
- Internal `_AGENTDRIVE_HOME_OVERRIDE` context var → `_AGENTDRIVE_HOME_OVERRIDE`

**Entry points**
- `pyproject.toml` `[project.entry-points."agentdrive.scanners"]` → `"agentdrive.scanners"`
- `pyproject.toml` `[project.entry-points."agentdrive.workers"]` → `"agentdrive.workers"`
- CLI binary entry: `agentdrive = "agentdrive.cli:main"`

### Kept (engine credit)

- `AgentDriveHarness` class name retained — it remains the engine adapter that
  agents wrap their work with. Importable as `from agentdrive import AgentDriveHarness`.
- `agentdrive` brand mentions in docstrings/README where they refer to the federated
  learning substrate that powers AgentDrive.

### Verification

- `pytest tests/` → 107/107 passing
- `scripts/test_healing_loop.py` → ✓
- `scripts/test_federation.py` → ✓ (quarantine gate held)
- `scripts/test_failure_modes.py` → 15/15 probes passed
- CLI smoke: `python3 -m agentdrive.cli --help` resolves, `drive` verb wired, log header shows `AgentDrive v0.1.0`.

## [Unreleased] — Final naming pass: AgentDriveHarness → Harness + README rewrite

### Renamed

- `AgentDriveHarness` → `Harness` everywhere — code, tests, docs, README.
  Imported as `from agentdrive import Harness`. No deprecation alias.
- This closes the last lingering "Agent Drive" name on the public API surface.
  `agentdrive` references that remain are intentional engine credit and live
  only in the `agentdrive.*` namespace docstrings.

### README

- Full rewrite. Drops the federation-substrate framing as the opening line;
  leads with **"Local-first storage for AI agents."** and the ProtonDrive
  parallel.
- Quickstart and swarm example use the renamed `Harness` import so any
  copy/paste actually runs.
- Architecture diagram updated to label the adapter `Harness` instead of
  `AgentDriveHarness`.
- Docs table updated: `INTEGRATION.md` description now reads
  "Wrapping your agent in `Harness`".

## [Unreleased] — v2 Milestone 1: content-addressed object store

The load-bearing decision from `docs/AGENTDRIVE-V2.md` lands here: every
Genome AgentDrive ingests is now also written to a sharded, content-addressed
object store keyed by `sha256:<hex>` of its canonical content. This is
purely additive — the existing `<root>/genomes/<id>/<version>/` registry
layout still owns reads; nothing breaks. The content store unlocks dedup,
cryptographic provenance, and the v2 `supersedes` DAG that later milestones
build on.

### Added

- **`agentdrive.drive.content_store`** — new module.
  - `canonical_json()` — deterministic UTF-8 JSON (sorted keys, minimal separators).
  - `canonical_genome_payload()` — the four-field identity slice of a Genome (framework + reasoning + tools + evals). Author / timestamp / score are observation metadata and stay OUT of the hash.
  - `hash_bytes()`, `hash_payload()`, `genome_hash()` — SHA-256 in the canonical `sha256:<hex>` form. Matches `Genome.compute_content_hash()` exactly.
  - `ContentStore` — sharded `objects/<aa>/<rest>.json` layout, atomic writes via tmp-file + `os.replace`, idempotent `put`, `has` / `get` / `iter_hashes` / `count`.
- **`GenomeManifest.supersedes: list[str]`** — content-hash references to Genomes this one replaces. Walkable in both directions. The v2 lineage edge.
- **`AgentDrive`** now provisions a `ContentStore` next to its registry.
  - `ingest()` writes to both — the registry (legacy path) and the content store (new path).
  - Ingest-log entries gain `content_hash` and `deduped` fields.
  - New methods: `has_content(hash)`, `get_content(hash)`, `content_count()`.
- **`tests/test_content_store.py`** — 18 tests covering determinism, dedup, sharded layout, Drive integration, and the new `supersedes` round-trip.

### Verification

- pytest: 125/125 passing (was 107; +18 new).
- `scripts/test_healing_loop.py` → ✓
- `scripts/test_federation.py` → ✓ (quarantine gate held)
- `scripts/test_failure_modes.py` → 15/15 probes passed
- Manual dedup smoke: two Genomes with same content / different ids → one object on disk.

### Not included (next milestones)

- Reads still go through the registry's `<id>/<version>/` layout. Switching reads to content-addressed lookup is deferred until Milestone 2 collapses the per-sub-agent directory layout.
- Migration of existing v1 Drives. Not needed yet — the content store is additive; existing data keeps working untouched.

## [Unreleased] — v2 Milestone 2: three-tier topology + DNA inheritance + lineage grants + snapshot backup

Lands the full Milestone 2 series from `docs/AGENTDRIVE-V2-INHERITANCE.md`.
Four sub-cuts, each shippable on its own, all on one branch.

### M2a — shared swarm Drive (sibling learning)

- `get_swarm_drive_path(swarm_id, subagent_id=None)` is now subagent-agnostic. All sub-agents in the same swarm share one Drive at `<swarms>/<swarm_id>/drive/`. `subagent_id` accepted for backwards compatibility but ignored for routing.
- `SwarmDriveManager.get_or_create_pool` rewritten:
  - Cache key is `swarm_id` only — siblings get the SAME `AgentDrive` instance.
  - **Bug fixed:** v1 constructed `AgentDrive()` without `drive_path`, so every "isolated" sub-agent silently landed on the default Drive. The shared-Drive design now puts everyone on the swarm path on purpose.
  - Sub-agent membership tracked separately in `_active_swarms`.
- `SwarmDrivePolicy` default flipped: `isolation_level="swarm"`, `sibling_sharing="read"`. The `"subagent"` mode remains opt-in for adversarial/air-gapped children.
- `AgentDrive.ingest()` accepts a `subagent_id` parameter that auto-stamps the Genome's author list with `id="sub:<id>"` (idempotent — re-ingests don't double-tag).
- New `AgentDrive.writers()` and `AgentDrive.genomes_by_subagent(sid)` for sibling attribution queries.
- `examples/03_swarm.py` rewritten to demonstrate the shared-Drive sibling-learning flow end-to-end.

### M2b — DNA Drive forward-only with ancestry closure table

- New `agentdrive.dna` module: `Ancestry`, `DNADrive`, `InheritedGenome`.
- **`Ancestry`** — SQLite-backed closure table at `<home>/dna/_ancestry.db` with schema `(ancestor_id, descendant_id, min_depth)`. Cycles forbidden by construction (timestamp invariant: child's `created_at` must exceed parents'). Diamond inheritance (two parents sharing a grandparent) records the shortest path to the shared ancestor exactly once.
- **`DNADrive`** — per-agent ancestral memory at `<home>/dna/<agent_id>/drive/`. Reuses the Milestone-1 content store so a Genome promoted from a swarm Drive to its author's DNA Drive doesn't duplicate bytes.
- `publish()` writes own Genomes; `pull_inherited()` walks the parent chain and returns ancestors' Genomes sorted by depth (closest first). Includes a `min_eval` gate for opt-in safety; defaults to 0.0 (trust direct-line ancestors).
- **No decay** — once a Genome is in the lineage, descendants always have access. Matches the Avatar mental model (continuous connection to ancestral experience).

### M2c — lineage_share grants (sideways flow)

- New `agentdrive.dna.grants` module: `LineageShareGrant`, `GrantScope`, `GrantStore`, `pull_via_grant`.
- Ed25519-signed grants (`cryptography` library, already a transitive dep). Per-agent keypairs auto-generated on first use and persisted in the same SQLite store.
- Grants carry: issuer, grantee, scope (topics / min_eval / content-hash whitelist), reducer hint (`append` / `overwrite` / `prefer-higher-eval`), TTL, signature.
- **Quota defense** (default 50 active grants per issuer) — Sybil flood mitigation.
- **Signature verification, expiry check, revocation check** — all enforced by `GrantStore.verify()`. Tampering any signed field fails the check.
- **TTL gates new issuance, not data already received.** Once a grantee pulls a Genome through a grant, it's theirs forever (no decay) — matches the design doc.
- Cross-source pulls are marked with `depth=-1` to distinguish them from forward-line ancestral pulls in consumer code.

### M2d — Snapshot Backup + localhost UI

- New `agentdrive.backup` module: `SnapshotManager`, `SnapshotEntry`, `serve()`.
- **Point-in-time snapshots, 6h cadence by default** (`DEFAULT_CADENCE_SECONDS = 6 * 60 * 60`). `snapshot_if_due()` respects the window; back-to-back calls are no-ops.
- **Pointer-only** — manifests reference content-store hashes; no bytes are duplicated. A snapshot of an unchanged Drive costs ~one manifest write.
- Restore is read-only — returns hashes; caller decides what to rebuild. Detects missing underlying objects and raises rather than half-restoring.
- **Pin / unpin / delete** — pinned snapshots refuse deletion until unpinned.
- **Localhost UI at `http://127.0.0.1:8420/`** — stdlib-only `ThreadingHTTPServer`, no Flask/FastAPI dep. Routes: `GET /` (dashboard), `GET /api/snapshots`, `POST /api/snapshots` (on-demand), `POST /api/restore`, `POST /api/pin`, `DELETE /api/snapshots`, `GET /api/health`. Loopback-only by default; operators can override the bind interface explicitly.

### Verification

- pytest: **186/186 passing** (was 137 after M2a; +16 M2b + +16 M2c + +17 M2d = 49 new).
- Deep functional: `scripts/test_healing_loop.py`, `test_federation.py`, `test_failure_modes.py` — all green.
- Examples: `01_hello_drive.py`, `02_dedup.py`, `03_swarm.py` — all run live against the default Drive.
- M2a end-to-end: `examples/03_swarm.py` demonstrates two sub-agents writing to one shared Drive, attributing each other's work via `genomes_by_subagent()`.
- M2d end-to-end: snapshot cycle works via UI (`POST /api/snapshots` → list → pin → delete) with a real HTTP server in tests.

## [Unreleased] — v2 Milestone 3 (part 1): capability URIs as universal access primitive

The "AgentDrive moment" identified in `docs/AGENTDRIVE-PROGRESS.md` —
the cohesion artifact every component verifies access through. This
cut lands the core primitive + the single arbiter; wiring it into the
existing Drive surfaces (M3 part 2) is a follow-up commit on the same
branch.

### Added

- **`agentdrive.cap.uri`** — `Capability` dataclass, `parse_uri`, and the
  `is_narrower_than` ordering that's the spine of subset minting +
  derivation. URI grammar: `<scheme>:<action>:<resource_kind>:<id>[:k=v...]`.
  Schemes: `drive` / `dna` / `backup`. Actions: `read` / `write` / `exec` /
  `pull` with `write` covering `read` and `exec` covering everything.
  Resource selectors: `swarm`, `agent`, `object`, `lineage`, `peer`,
  `default`. Attenuations like `max_hops`, `min_eval`, `expires`, `sub`,
  `topic` — each with its own coverage rule (lower max_hops is narrower,
  higher min_eval is narrower, equal-only for string keys).

- **`agentdrive.cap.store.CapStore`** — SQLite-backed mint + derive +
  verify. Ed25519 signatures (reuses the keypair pattern from
  `dna.grants`). Subset minting: parent-cap-id required for non-root
  caps; minted cap must be narrower than parent or `CapDerivationError`.
  Trust roots: external agents' pubkeys can be registered via
  `trust_root()`; caps from unregistered issuers refuse to verify.

- **The 30-line cap resolver** lives in `CapStore.verify_request()`.
  Every Drive boundary calls it; valid+covering caps pass, invalid or
  insufficient ones raise `CapInvalidError` / `InsufficientCapability`.

- **`tests/test_capabilities.py`** — 26 tests covering URI parsing
  round-trips (including content-hash resources like `sha256:abcd`),
  narrowness ordering (write→read, exec→all, lower max_hops, higher
  min_eval), subset-mint enforcement, signature/revocation/expiry
  detection, and the verify_request arbiter behavior.

### Verification

- pytest: **212/212 passing** (was 186; +26 new).
- Deep functional (healing-loop, federation, failure-modes): all green.

### Not in this cut (M3 part 2 — same branch)

- Wiring `verify_request` into `AgentDrive.ingest()`, `query()`,
  `get_content()`, `DNADrive.pull_inherited()`, and the snapshot UI
  endpoints. Will land as the next commit on this branch so the
  primitive can be reviewed independently of the integration.
