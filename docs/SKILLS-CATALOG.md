# AgentDrive Skills Catalog

## Organization

| Tier | Folder | Who uses it |
|------|--------|-------------|
| **1–3** | `core/`, `hive/`, `agentdrives/` | Any model via **AgentDrive MCP** |
| **4** | `universal/` | Any model — no vendor tools required |
| **5** | `vendors/grok|claude|codex/` | Only when that **harness** is active |

**Rule:** On MCP with Ollama/Claude/Grok-as-MCP → use tiers 1–4. Use tier 5 only when native harness tools exist. Set `AGENTDRIVE_HARNESS=grok` to inject vendor skills into the system prompt.

**Counts:** 37 bundled + 24 vendor (claude 6, codex 4, grok 14)

## Tier 1 — AgentDrive core (runnable MCP operations)

| Skill | Harness | Role | Runnable | Description |
|-------|---------|------|----------|-------------|
| `think` | agentdrive | arisen | `think` | Cited synthesis from your AgentDrive pool with mandatory gap analysis. Use before delegating to pawns or when you need grounded answers from DNA + learnings. |
| `golden-path-verify` | agentdrive | shared | `golden_path_verify` | Verify the seven-step first-run loop (install, doctor, MCP, think, learnings, query) without mutating state. Reports which steps pass or fail. |
| `learnings-log` | agentdrive | shared | `learnings_log` | Record one operational learning (key + insight) into the shared hive so future sessions and pawns inherit the note. |
| `learnings-list` | agentdrive | shared | `learnings_list` | List operational learnings already recorded for this project — the hive's short-term shared memory. |
| `pool-query` | agentdrive | shared | `pool_query` | Semantic search over the AgentDrive pool — find genomes and DNA relevant to a task. How pawns pull knowledge from the hive before acting. |
| `doctor` | agentdrive | shared | `doctor` | Run AgentDrive health checks — install, config, MCP bridge, pool, and environment sanity. First diagnostic when something feels broken. |

## Tier 2 — Hive (Arisen, pawns, inheritance)

| Skill | Harness | Role | Runnable | Description |
|-------|---------|------|----------|-------------|
| `arisen-orchestrator` | agentdrive | arisen | `—` | The Arisen playbook — decompose user quests, spawn pawns, curate hive learnings, and synthesize outcomes. Command; do not grind. |
| `pawn-worker` | agentdrive | pawn | `—` | Headless pawn executing one scoped quest — pull DNA first, finish or block with a specific reason, return structured inheritance to the Arisen. |
| `pawn-scout` | agentdrive | pawn | `—` | Exploration pawn — map codebase or docs, list risks, recommend next pawn or skill. Read and report; do not ship code unless asked. |
| `pawn-specialist` | agentdrive | pawn | `—` | Narrow-domain pawn — follow one agentdrive skill literally (regex, SQL, diff, etc.). Returns specialist artifact plus one hive learning line. |
| `hive-inheritance` | agentdrive | shared | `—` | Package pawn outcomes for parent ingest — summary, genomes used, new patterns, learnings key, and self-score for the shared pool. |

## Tier 3 — Agentdrives (narrow specialists)

| Skill | Harness | Role | Runnable | Description |
|-------|---------|------|----------|-------------|
| `regex-architect` | agentdrive | pawn | `—` | Build and audit regular expressions sample-first — positives, negatives, commented form, and rejection-set proof. Never ship regex without examples. |
| `sql-explain` | agentdrive | pawn | `—` | Explain a SQL query in plain English — intent, tables, indexes, join strategy, cost class, and risks (full scan, implicit cast, N+1). |
| `cron-translator` | agentdrive | pawn | `—` | Translate between cron expressions, plain English, and next fire times. Flags day-of-month vs day-of-week conflicts. |
| `diff-narrator` | agentdrive | pawn | `—` | Write a one-paragraph why-this-changed from a git diff — user impact and motivation, not a line-by-line restatement. Ends with reviewer focus bullets. |
| `release-notes` | agentdrive | pawn | `—` | Turn a commit range into release notes — Added, Changed, Fixed, Security — framed by user impact, not implementation detail. |
| `error-translator` | agentdrive | pawn | `—` | Translate a stack trace to one-sentence root cause plus minimal fix. States missing evidence instead of guessing when uncertain. |
| `api-versioning-advisor` | agentdrive | pawn | `—` | Classify API changes as patch, minor, or major; enumerate breaking consumers and migration notes. Defaults conservative. |
| `migration-planner` | agentdrive | pawn | `—` | Plan forward migration and rollback with pre-flight checks and at-scale failure modes (locks, downtime, backfill duration). |
| `url-canonicalizer` | agentdrive | pawn | `—` | Canonicalize URLs, strip trackers, explain query parameters, and flag suspicious patterns (open redirect, homoglyph, IP literals). |
| `color-system-builder` | agentdrive | pawn | `—` | Expand one brand primary into a full UI palette with WCAG contrast pairings for bg, surface, accent, ok, warn, and error roles. |
| `prompt-distiller` | agentdrive | pawn | `—` | Distill a verbose prompt to minimum tokens while preserving constraints, output format, and success criteria. Shows before/after cuts. |
| `test-gap-finder` | agentdrive | pawn | `—` | Compare a function to its tests and list uncovered cases ranked by risk. Finds gaps first; does not write tests unless asked. |

## Tier 4 — Universal (any model; use when not on a vendor harness)

| Skill | Harness | Role | Runnable | Description |
|-------|---------|------|----------|-------------|
| `changelog` | universal | shared | `—` | Maintain CHANGELOG.md after code or config changes — dated sections, Added/Changed/Fixed/Removed, verification hints. Works with any model or editor. |
| `verify-work` | universal | shared | `—` | Before handoff — review your diff, run relevant tests, fix failures, confirm the task is actually done. Model-agnostic self-check, not vendor-specific tooling. |
| `skill-authoring` | universal | shared | `—` | Author a SKILL.md — frontmatter (name, description, when_to_call), concise body, one worked example. Use agentdrive skills init to scaffold on disk. |
| `systematic-debugging` | universal | shared | `—` | Four-phase debugging — investigate, compare patterns, hypothesize, fix root cause. No fixes before understanding WHY. Stop after three failed fixes. |
| `swarm-orchestrator` | universal | arisen | `—` | Decompose multi-step work into pawn-sized tasks, dispatch specialists, collect handoffs. Do not implement pawn work yourself. |
| `swarm-worker` | universal | pawn | `—` | Execute one assigned task with structured handoff — summary, files, tests, gaps. Retry discipline and scope limits for any subagent runtime. |
| `frontend-design` | universal | shared | `—` | Build distinctive, production-grade UI — typography, spacing, motion, accessibility. Avoid generic templates; commit to a clear aesthetic before coding. |
| `design-system` | universal | shared | `—` | Extract or define design tokens (color, type, spacing, components) as a living contract so all UI generations stay consistent. |
| `web-artifact` | universal | shared | `—` | Self-contained interactive web artifact — HTML/CSS/JS or component framework, responsive, accessible, previewable in a browser. |
| `document-docx` | universal | shared | `—` | Create or edit Word documents — reports, memos, letters, templates with headings and tables. Deliverable is a .docx file. |
| `document-xlsx` | universal | shared | `—` | Read, clean, or create spreadsheets — formulas, charts, tabular data. Deliverable is xlsx/csv/tsv. |
| `document-pptx` | universal | shared | `—` | Create or edit slide decks — structure, speaker notes, consistent layout. Deliverable is a .pptx file. |
| `parallel-attempts` | universal | arisen | `—` | Try multiple approaches to the same problem, compare outcomes objectively, keep the best. Works with any runtime that can spawn isolated attempts. |
| `mcp-agentdrive` | universal | shared | `—` | Use AgentDrive MCP tools from any connected model — think, pool query, learnings, golden-path verify. Prefer this over vendor-specific harness skills when on MCP. |

## Tier 5a — Grok harness (native Grok CLI tools)

**Requires:** Grok CLI harness (task tool, image_gen, etc.)

| Skill | Description |
|-------|-------------|
| *(14 skills)* | Synced from `~/.grok/skills` — see `vendors/grok/` |
| `grok-changelog`, `grok-check-work`, `grok-imagine`, … | Native Grok tool paths; use `changelog` / `verify-work` universal when on MCP only |

## Tier 5b — Claude Code harness

**Requires:** Claude Code plugin runtime

| Skill | Description |
|-------|-------------|
| `claude-mcp-integration` | Integrate MCP servers into Claude Code plugins — stdio, SSE, HTTP, .mcp.json bundling. |
| `claude-skill-creator` | Author Claude Code skills — frontmatter, validation, packaging in plugins. |
| `claude-frontend-design` | Claude Code frontend design — distinctive UI before code; plugin-native workflow. |
| `claude-session-report` | Summarize a Claude Code session into a structured report for handoff. |
| `claude-claude-md-improver` | Improve CLAUDE.md project instructions for Claude Code sessions. |
| `claude-plugin-structure` | Claude Code plugin layout — commands, agents, skills, hooks, MCP wiring. |

## Tier 5c — Codex CLI harness

**Requires:** OpenAI Codex CLI and curated plugins

| Skill | Description |
|-------|-------------|
| `codex-github` | Codex GitHub triage — repos, PRs, issues via connector; route to specialist workflows. |
| `codex-gh-fix-ci` | Diagnose and fix failing GitHub Actions CI from Codex. |
| `codex-gh-address-comments` | Address PR review comments systematically from Codex. |
| `codex-yeet` | Fast branch-and-PR publish flow from Codex when changes are ready to ship. |

## Refresh vendor overlays

```bash
python scripts/sync_vendor_skills.py
python scripts/apply_skills_catalog.py
python scripts/generate_skills_catalog_doc.py
```

