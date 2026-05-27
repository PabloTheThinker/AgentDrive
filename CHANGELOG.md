# Changelog

All notable changes to this project are documented here. The product is
**AgentDrive** — local-first Drive for AI agent swarms, distributed under the
``agentdrive`` Python package.

## Unreleased

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
- **No decay** — once a Genome is in the lineage, descendants always have access. Matches Pablo's Avatar mental model.

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
