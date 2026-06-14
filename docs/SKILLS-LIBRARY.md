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
| CLI | `agentdrive skills list [--harness grok]` · `show` · `run` · `review` · `promote` · `prune` · `init` |
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

## Inherited skill curation

Sub-agent handoff skills land under `~/.agentdrive/skills/inherited/...`.
AgentDrive records matches and explicit run outcomes in
`~/.agentdrive/skills/usage.json`, then uses that evidence to curate the parent
bench:

```bash
agentdrive skills review
agentdrive skills promote <inherited-skill-name>
agentdrive skills prune <inherited-skill-name> --reason "superseded"
```

`promote` marks the skill frontmatter as `category: promoted`; `prune` marks it
`disabled: true` so it leaves discovery without deleting the file.
