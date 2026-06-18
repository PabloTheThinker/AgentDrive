# AgentDrive Skills Library

**Status:** shipped (2026-06-08)  
**Principle:** **Tiered and model-agnostic** — tiers 1–4 work with any LLM via AgentDrive MCP. Tier 5 vendor skills activate only when that harness is running.

---

## Organization

```
examples/skills/
  catalog.yaml              # tiers 1–4 canonical descriptions
  vendor-manifest.yaml      # Grok / Claude / Codex sync sources
  think/                    # tier 1 (core)
  golden-path-verify/
  core/                     # tier 1 — runnable MCP ops
  hive/                     # tier 2 — Arisen + pawns
  agentdrives/              # tier 3 — narrow specialists
  universal/                # tier 4 — any model, no vendor tools
  vendors/
    grok/                   # tier 5a — Grok CLI native tools
    claude/                 # tier 5b — Claude Code plugins
    codex/                  # tier 5c — Codex CLI plugins

~/.agentdrive/skills/       # personal overlays — wins on name collision
```

| Tier | Folder | Harness | Who uses it |
|------|--------|---------|-------------|
| **1** | `core/`, `think/`, `golden-path-verify/` | `agentdrive` | Any model on **AgentDrive MCP** |
| **2** | `hive/` | `agentdrive` | Arisen/pawn coordination |
| **3** | `agentdrives/` | `agentdrive` | Narrow prodigy pawns |
| **4** | `universal/` | `universal` | Any model — changelog, debugging, documents, UI |
| **5a** | `vendors/grok/` | `grok` | Grok CLI (`task`, `image_gen`, Universal Brush, …) |
| **5b** | `vendors/claude/` | `claude` | Claude Code plugin runtime |
| **5c** | `vendors/codex/` | `codex` | OpenAI Codex CLI plugins |

**Rule:** Connected via AgentDrive MCP → use tiers **1–4**. Prefer `changelog` / `verify-work` / `mcp-agentdrive` over `grok-changelog` when you only have MCP.

Set `AGENTDRIVE_HARNESS=grok|claude|codex` to inject tier-5 skills into the system prompt and match them on each turn.

---

## Metaphor — Arisen, pawns, and the hive

| Role | Who | AgentDrive mapping |
|------|-----|-------------------|
| **Arisen** | Commands, does not grind | Main agent / `arisen-orchestrator` |
| **Pawn** | One quest, returns knowledge | Subagents; `pawn-worker`, `pawn-scout`, … |
| **Hive** | Shared memory | DNA pool + learnings + session events |
| **Inheritance** | Pawn → pool | `hive-inheritance`, `learnings-log` |

---

## Counts (after sync)

| Group | Count | Notes |
|-------|-------|-------|
| Bundled (tiers 1–4) | 37 | From `catalog.yaml` |
| Grok vendor | 14 | Synced from `~/.grok/skills` |
| Claude vendor | 6 | Curated plugin skills |
| Codex vendor | 4 | Curated plugin skills |
| **Total** | **61** | Full catalog: [SKILLS-CATALOG.md](SKILLS-CATALOG.md) |

---

## Surfaces

| Surface | Command |
|---------|---------|
| CLI | `agentdrive skills list [--harness grok]` · `show` · `run` · `review` · `promote` · `prune` · `dna` · `init` |
| Chat | `/skills list`, `/skill <name>` |
| System prompt | Auto catalog (tiers 1–4 always; tier 5 when `AGENTDRIVE_HARNESS` set) + matched skills per turn |

---

## Refresh workflow

```bash
python scripts/sync_vendor_skills.py      # tier 5 from vendor-manifest.yaml
python scripts/apply_skills_catalog.py    # tiers 1–4 from catalog.yaml
python scripts/generate_skills_catalog_doc.py
```

Author a new bundled skill:

```bash
agentdrive skills init my-skill --description "What it does"
# then add entry to catalog.yaml and re-run apply + generate
```

See also: [ASSESSMENT.md](ASSESSMENT.md), [SKILLS-SPEC.md](SKILLS-SPEC.md).

---

## Automatic learning (MCP / CLI)

Every successful `run_operation` call (MCP tools + CLI) runs the auto-learning hook when `AGENTDRIVE_AUTO_LEARN=1` (default):

1. **Session tracking** — context pack / think ops mark the session grounded.
2. **Auto reasoning** — high-signal mutating ops get a lightweight fabric trace if you did not call `experience_graph_record_reasoning`.
3. **Skill distillation** — playbooks install under `~/.agentdrive/skills/inherited/<swarm>/mcp-auto-learning/`.
4. **DNA ingest** — high-signal skills (external/multiverse parent, think, record_outcome) promote + ingest when `AGENTDRIVE_AUTO_ASSIMILATE_SKILLS=1`.
5. **Born skills (fusion)** — when a session merges **experience + skills + patterns** (≥2 axes), AgentDrive births a completely new `fused-*` skill — not a copy of any parent, but a synthesis of the session's lived work. Check `auto_learning.fused_skill` on results. Explicit: `synthesize_fused_skill` MCP op.

Results include `auto_learning` when something was absorbed. Sub-agent `agentdrive-skill` handoffs still merge through the same inherited path.

Disable: `AGENTDRIVE_AUTO_LEARN=0`, or finer `AGENTDRIVE_AUTO_RECORD_REASONING` / `AGENTDRIVE_AUTO_DISTILL_SKILLS` / `AGENTDRIVE_AUTO_FUSE_SKILLS`.

## Inherited skill curation

Sub-agent handoff skills land under `~/.agentdrive/skills/inherited/...`.
AgentDrive records matches and explicit run outcomes in
`~/.agentdrive/skills/usage.json`, then uses that evidence to curate the parent
bench:

Successful `SubagentDone` auto-absorption also records a success outcome with
an `inheritance:<swarm>:<subagent>` source, giving inherited skills immediate
but bounded evidence from the child task that produced them.
If the skill now satisfies the review threshold, the successful child outcome
also triggers a scoped auto-assimilation pass: the skill is promoted and
ingested as DNA, while weak candidates remain in watch mode and pruning stays
manual. Disable this with `AGENTDRIVE_AUTO_ASSIMILATE_SKILLS=0`.

```bash
agentdrive skills review
agentdrive skills assimilate
agentdrive skills promote <inherited-skill-name>
agentdrive skills prune <inherited-skill-name> --reason "superseded"
agentdrive skills dna <inherited-skill-name>
```

The same loop is available over MCP for models and local clients:
`agentdrive_review_inherited_skills`, `agentdrive_assimilate_inherited_skills`,
`agentdrive_promote_inherited_skill`, `agentdrive_prune_inherited_skill`, and
`agentdrive_ingest_skill_dna`.

`assimilate` promotes only candidates that already meet the review threshold and
ingests them as DNA by default; pruning is opt-in with `--prune`. `promote`
marks the skill frontmatter as `category: promoted`; `prune` marks it
`disabled: true` so it leaves discovery without deleting the file. `dna` turns
a promoted or inherited skill into a normal AgentDrive Genome and ingests it
into the current Drive so future DNA retrieval can use the learned playbook.
