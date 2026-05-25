# AgentDrive — Progress Audit & OSS Adapt Plan

> **Date:** 2026-05-24
> **Scope:** where we are *right now* (post-rebrand, post-Milestone-1) + what to lift from Supabase and ProtonDrive (both open source) to make AgentDrive credible as an OSS project an outside contributor would actually take seriously.
>
> Companion docs: [`AGENTDRIVE-V2.md`](AGENTDRIVE-V2.md) (the v2 architecture proposal), [`AGENTDRIVE-V2-RESEARCH.md`](AGENTDRIVE-V2-RESEARCH.md) (cloud-drive cross-cutting study).

---

## 1. Where we are

| Metric | Count | Notes |
|---|---|---|
| Source LOC (`src/agentdrive/`) | 21,932 | clean fanout: `drive/`, `harness/`, `adapters/`, `reasoning/`, `scanners/`, `quarantine`, `peers`, `inheritance`, `confidence`, `reconciliation` |
| Test LOC | 3,671 | pytest only; no integration harness |
| Doc LOC | 2,257 | growing; some filenames still legacy (`POOL.md`, `POOL-EVOLUTION.md`) |
| Tests | 126 passing | + 3 deep functional scripts (healing-loop, federation, failure-modes) |
| TODO / FIXME density | 3 across 22k LOC | genuinely low — debt is not the problem |
| Public Python API | `Harness`, `AgentDrive`, `DriveQuery`, `DriveSettings`, `Genome`, `GenomeRegistry`, `Quarantine`, `PeerRegistry` | + new `ContentStore` + content-addressing helpers from Milestone 1 |

**What's solid.** The engine works end-to-end. The rebrand is coherent across code, CLI, docs, and the website install endpoint. Content-addressing is live and dogfooded — I (ILO) stored real session reasoning patterns in my own Drive and queried them back, with dedup verified on the way through. The federation/quarantine spine has been hardened by the adversarial test pass that landed before the rebrand and still holds.

**What's weak.** The repo is shaped like a *project*, not like an *open-source product*. The gaps below are concrete and fixable in a single afternoon — none of them require new architecture.

---

## 2. OSS-readiness gaps, ranked

### Critical — blocks credibility for any new contributor

1. **CI runs only CodeQL.** There is no workflow that runs `pytest` on PRs. A red branch can merge green. **Fix:** add `.github/workflows/ci.yml` running pytest + ruff + mypy on every push/PR.
2. **`examples/` is broken.** `rich_agent_with_savant_pool.py`, `savant_pool_demo.py`, `savant_swarm_dna_demo.py` all import old names. First-time visitor runs them, hits `ModuleNotFoundError`, leaves. **Fix:** rewrite as `agentdrive_dogfood.py`, `swarm_drive_demo.py`, `dedup_demo.py` using the new API.
3. **Landing site (`site/index.html`)** still reads "Savant — The Living DNA Pool for AI Agent Swarms" with the old GitHub link. Public-facing rebrand miss. **Fix:** rewrite around the AgentDrive narrative; mirror the README hero.
4. **Stale `src/savant.egg-info/`** alongside `src/agentdrive.egg-info/` — leftover from the package rename. Pollutes `pip show`, `find`, mental model. **Fix:** trash it; add both `*.egg-info/` to `.gitignore` if not already.

### Important — what makes a repo feel like a real OSS project

5. **`.github/ISSUE_TEMPLATE/` exists but is empty.** Add `bug_report.md` + `feature_request.md`. Force a "swarm topology" field in bug reports (the failure mode of agent-memory systems is interaction-dependent).
6. **No `.github/pull_request_template.md`.** Adopt Supabase's "Problem / Solution / Test plan" sections — Supabase closes PRs without these.
7. **No `CODE_OF_CONDUCT.md`.** Standard OSS expectation; one-file copy from the Contributor Covenant.
8. **`CONTRIBUTING.md` is pre-v2.** Update for the new module shape; gate feature PRs behind a GitHub Discussion (steal verbatim from Supabase's pattern — it works because Discussions become the lightweight RFC surface without ceremony).
9. **No `DEVELOPERS.md`.** Anyone hacking on the engine needs a one-command bring-up: `make dev` should boot a default Drive + a 2-sub-agent swarm + a simulated peer. Today contributors have to read source to figure out what to run.
10. **No `AGENTS.md` / `.github/copilot-instructions.md`.** AgentDrive is an agent-native product; if AI contributors can't onboard cleanly, that's dissonant with the mission. Supabase ships these and they're table stakes now.
11. **Empty top-level dirs (`agents/`, `frameworks/`).** Either populate with a starter or remove.
12. **Doc filenames still say `POOL.md` / `POOL-EVOLUTION.md`.** Content was updated; the filenames are stale and will rot grep-ability. **Fix:** `git mv POOL.md DRIVE.md` + update references.

### Strategic — what unblocks the next 100 contributors

13. **No PyPI release.** `pip install agentdrive` doesn't work. Manual install via `git+https://…` only. **Plan:** add `.github/workflows/release.yml` that publishes on tag push. Cut `v0.1.0` once Milestones 1-3 are in.
14. **No `docker/` directory.** Supabase's whole "you own your data" claim is concretized in one `docker compose up`. AgentDrive needs an equivalent — a compose file that boots 1 default Drive + 2 sub-agent Drives + a peer over a virtual network. This is the demo that sells the system in 90 seconds.
15. **No architecture SVG in README.** Mermaid is fine; an SVG that visualizes Genome → Drive → Swarm → Peer → Federation is fine. Pick one. Supabase's success here is real — a picture lands faster than the architecture doc.
16. **No "AgentDrive moment" artifact.** See §5 below.

---

## 3. What to lift from Supabase

Supabase is the right model for *how to shape a multi-service OSS product*. Findings from the deep dive (full report in `AGENTDRIVE-V2-RESEARCH.md` — actually no, that's the cloud-drive doc; this is a fresh research pass and the synthesis is below):

### Repo topology

Supabase is **not** a monorepo of services. It's:

- One **meta-repo** (`supabase/supabase`) holding the website, docs, Studio dashboard, design system, examples, and a single `docker/` directory that boots the whole stack.
- Per-service repos in their native languages: `supabase/auth` (Go), `supabase/storage` (TypeScript), `supabase/realtime` (Elixir), `supabase/postgres-meta` (TypeScript), `supabase/cli` (Go).
- Per-language client SDKs as separate repos: `supabase-js`, `supabase-py`, `supabase-flutter`, `supabase-swift`.
- `postgrest/postgrest` is third-party; Supabase sponsors but doesn't own.

**Adapt for AgentDrive:** stay single-repo until we have a second service. When the cap resolver / federation daemon / SDK split makes sense, mirror Supabase exactly — meta-repo for docs + `docker/` + examples, per-service repos for engines, per-language SDKs as separate repos. Do **not** start with a Turborepo monorepo of mixed-language services; Supabase deliberately stopped at that line.

### The "Supabase moment"

It's editorial as much as technical: **one shared JWT verified at every service boundary, with Postgres row-level security as the universal authorization layer.** Every service trusts the same token; RLS does the rest. They didn't write a new access-control system; they let Postgres be it.

**Adapt for AgentDrive:** replace JWT+RLS with **capability URI + key-derivation tree**. Every service (local Drive, swarm Drive, peer federation, eventual web view) verifies the same cap URI the same way. This is Milestone 2 + 3 from `AGENTDRIVE-V2.md`. The deliverable that makes this *feel* cohesive — Supabase's analog — is a **30-line cap resolver** an outside contributor can read end-to-end and instantly understand the access model.

### Self-host story

The entire offer is `docker/docker-compose.yml` with five swappable variants (`caddy`, `envoy`, `nginx`, `pg17`, `rustfs`, `s3`) and image tags pinned by date to avoid "self-host drifts from cloud." `setup.sh` / `run.sh` / `reset.sh` / `.env.example` / `CONFIG.md` / `versions.md` all sit alongside.

**Adapt for AgentDrive:** ship `docker/docker-compose.yml` that boots 1 default Drive + 2 sub-agent Drives + a peer over a virtual network. Pin image tags. Versions file declares which Genome schema version + cap URI version each release ships. This is the artifact that makes "local-first, you own it" concrete instead of marketing.

### Contribution surface

`CONTRIBUTING.md` is short (~40 lines) and defers heavy lifting to `DEVELOPERS.md`. **Feature PRs are gated behind a GitHub Discussion.** No formal RFC process; Discussions are the lightweight RFC surface. `.github/copilot-instructions.md` + `AGENTS.md` are shipped for AI contributors.

**Adapt for AgentDrive:** copy the structure verbatim. The "feature PRs go through Discussions first" rule especially — it scales without process overhead.

---

## 4. What to lift from ProtonDrive (open clients only)

### Crypto library boundary — gopenpgp is reusable

`ProtonMail/gopenpgp` is **MIT-licensed**, Go module `github.com/ProtonMail/gopenpgp/v3`, RFC 9580 + RFC 4880 (legacy) support, and the public API is fully Proton-decoupled — no Proton API references in the public types. Builder API: `crypto.PGP()` → `Encryption()` / `Decryption()` / `Sign()` / `Verify()` / `KeyGeneration()` / `Session()`.

**Adopt for AgentDrive Milestone 3 (encryption at rest):** use gopenpgp directly. Wrap it behind an `agentdrive::crypto::Provider` trait so the rest of the codebase never imports it — this preserves the option to swap for `age` or `noise` later if the encryption story evolves.

**Caveat from the research:** Proton's *web* clients use `@protontech/crypto` (a TS/WASM package on a private registry), not gopenpgp. If AgentDrive ever ships a browser client, that path needs separate evaluation. Server-side (where our crypto actually has to live) → gopenpgp is the answer.

### Code patterns worth stealing

- **4 MB chunk size + verify-on-encrypt loop** (`packages/shared/lib/drive/constants.ts` line 8: `export const FILE_CHUNK_SIZE = 4 * MB;`). Constants `MAX_ENCRYPTED_BLOCKS=15`, `MAX_UPLOADING_BLOCKS=10`, `MAX_UPLOAD_JOBS=5` — bounded concurrency that survives real traffic. Even though our chunks are JSON Genomes not arbitrary files, the bounded-parallelism pattern is the right shape for our future sync layer.
- **Generator-based async encrypted-block stream** (`packages/drive-store/store/_uploads/worker/encryption.ts`, function `generateEncryptedBlocks`). Streams encrypted chunks while uploading earlier ones — the right shape for Milestone 5 (cross-device sync).
- **Detached signature with critical `signatureContext` tag for cross-actor attribution.** Every share-related action signs with a tagged signature context (`DRIVE_SIGNATURE_CONTEXT.SHARE_MEMBER_INVITER` etc.) so a leaked signature can't be replayed in a different context. **Direct map for AgentDrive:** sign every Genome with a sub-agent's key under a context tag like `agentdrive:swarm-publish:v1`. Cross-context replay attacks become impossible at the crypto layer instead of the application layer.

### Sharing flow — the part to copy and the part to skip

Code-level flow from `packages/drive-store/store/_shares/useShareActions.ts`:

1. Generate a fresh keypair for the share itself.
2. Wrap the resource's session keys under the new share key (`getEncryptedSessionKey()`).
3. To invite a user: wrap the **share session key** under the invitee's public key + sign with a detached, context-tagged signature.

**Direct map for AgentDrive:** swarm-to-swarm sharing wraps the swarm's Drive key under the receiving swarm's key. Peer federation already routes through quarantine; adding the wrap step formalizes the cryptographic side.

**The part to skip:** ProtonDrive does **not** re-encrypt on member removal. Revocation is server-side ACL only; anyone who held a key can keep decrypting cached blocks. This is the known E2EE-vs-revocation tension. For AgentDrive we have to be honest about the same limit, or we have to bite the re-encryption cost. The right call for v2 is to make it explicit in `SECURITY.md`: "revocation is cryptographic for new objects only; existing cached blocks remain readable to former members until next rotation." That's the same posture as Proton — the difference is we name it.

---

## 5. The "AgentDrive moment"

Every cohesive OSS product has one. Supabase's is shared JWT + RLS. ProtonDrive's is the wrapped-session-key share model. AgentDrive's should be:

> **The capability URI is the single access primitive across local store, swarm, peer federation, and any future surface. Every component verifies the same cap the same way. A 30-line reference resolver is shipped in the docs.**

That artifact — a short, readable, end-to-end cap resolver — is the thing that makes the project feel like a *system* instead of a *folder of tools*. Build it as part of Milestone 3 from `AGENTDRIVE-V2.md`.

---

## 6. Concrete fix list — what to ship next

In order. Each item is small enough to be a single PR.

| # | Item | Effort | Unblocks |
|---|---|---|---|
| 1 | Add `.github/workflows/ci.yml` running pytest + ruff + mypy | 30 min | every future PR being trustworthy |
| 2 | Trash `src/savant.egg-info/`, add `*.egg-info/` to `.gitignore` | 5 min | cleanliness |
| 3 | Rewrite `examples/` for AgentDrive API + add dedup demo | 1 hr | first impression for visitors |
| 4 | Rewrite `site/index.html` around AgentDrive | 1 hr | public-facing rebrand |
| 5 | Add `.github/ISSUE_TEMPLATE/{bug,feature}.md` + `pull_request_template.md` | 30 min | contribution discipline |
| 6 | Add `CODE_OF_CONDUCT.md`, update `CONTRIBUTING.md` for v2 | 30 min | OSS table stakes |
| 7 | Add `DEVELOPERS.md` with `make dev` one-command bring-up | 1 hr | new contributor onboarding |
| 8 | `git mv POOL.md DRIVE.md` + update internal links | 15 min | doc hygiene |
| 9 | Add architecture SVG to README | 1 hr | first-glance comprehension |
| 10 | Build the Milestone 2 PR (shared swarm Drive + sibling-learning default) | 1 day | actual product progress |
| 11 | Build the Milestone 3 PR (capability URIs + key-derivation tree + 30-line cap resolver) | 2-3 days | the AgentDrive moment |
| 12 | `docker/docker-compose.yml` booting 1 default + 2 sub-agents + 1 peer | 1 day | self-host story |
| 13 | Cut `v0.1.0` PyPI release + tag-based release workflow | 1 day | install-ability |

Items 1-9 are pure hygiene; doing them clears the runway for everything after. Items 10-13 are the actual v2 build sequence from the architecture doc, with Supabase/ProtonDrive lessons baked in.
