# AgentDrive Skills Catalog

**Generated from** `examples/skills/catalog.yaml` — run `python scripts/generate_skills_catalog_doc.py` after edits.

**Total:** 40 bundled skills · invoke via `/skill <name>` or `agentdrive skills run <name>`

See also: [SKILLS-LIBRARY.md](SKILLS-LIBRARY.md) (layout + metaphor), [ASSESSMENT.md](ASSESSMENT.md) (product status).

## Core — runnable AgentDrive operations

| Skill | Role | Runnable | Description |
|-------|------|----------|-------------|
| `think` | arisen | `think` | Cited synthesis from your AgentDrive pool with mandatory gap analysis. Use before delegating to pawns or when you need grounded answers from DNA + learnings. |
| `golden-path-verify` | shared | `golden_path_verify` | Verify the seven-step first-run loop (install, doctor, MCP, think, learnings, query) without mutating state. Reports which steps pass or fail. |
| `learnings-log` | shared | `learnings_log` | Record one operational learning (key + insight) into the shared hive so future sessions and pawns inherit the note. |
| `learnings-list` | shared | `learnings_list` | List operational learnings already recorded for this project — the hive's short-term shared memory. |
| `pool-query` | shared | `pool_query` | Semantic search over the AgentDrive pool — find genomes and DNA relevant to a task. How pawns pull knowledge from the hive before acting. |
| `doctor` | shared | `doctor` | Run AgentDrive health checks — install, config, MCP bridge, pool, and environment sanity. First diagnostic when something feels broken. |

### When to call

- **`think`** — user needs a cited answer from the pool, gap analysis, or pre-delegation research
- **`golden-path-verify`** — before or after first run, CI smoke, or when onboarding health is uncertain
- **`learnings-log`** — durable decision, runbook note, or pawn handoff worth remembering
- **`learnings-list`** — user asks what we already learned, decided, or recorded
- **`pool-query`** — search the pool, find matching genomes, or orient before implementation
- **`doctor`** — errors, broken MCP, empty pool, or before golden-path run

## Hive — Arisen, pawns, and inheritance

| Skill | Role | Runnable | Description |
|-------|------|----------|-------------|
| `arisen-orchestrator` | arisen | `—` | The Arisen playbook — decompose user quests, spawn pawns, curate hive learnings, and synthesize outcomes. Command; do not grind. |
| `pawn-worker` | pawn | `—` | Headless pawn executing one scoped quest — pull DNA first, finish or block with a specific reason, return structured inheritance to the Arisen. |
| `pawn-scout` | pawn | `—` | Exploration pawn — map codebase or docs, list risks, recommend next pawn or skill. Read and report; do not ship code unless asked. |
| `pawn-specialist` | pawn | `—` | Narrow-domain pawn — follow one agentdrive skill literally (regex, SQL, diff, etc.). Returns specialist artifact plus one hive learning line. |
| `hive-inheritance` | shared | `—` | Package pawn outcomes for parent ingest — summary, genomes used, new patterns, learnings key, and self-score for the shared pool. |

### When to call

- **`arisen-orchestrator`** — multi-step work, swarm coordination, or deciding what the hive should learn
- **`pawn-worker`** — spawned as subagent to implement, fix, or complete a single assigned task
- **`pawn-scout`** — orientation, audit, reconnaissance before a worker pawn acts
- **`pawn-specialist`** — task clearly matches a bundled agentdrive (regex, cron, errors, tests)
- **`hive-inheritance`** — pawn completing a task and returning knowledge to the Arisen or pool

## Agentdrives — narrow prodigy specialists

| Skill | Role | Runnable | Description |
|-------|------|----------|-------------|
| `regex-architect` | pawn | `—` | Build and audit regular expressions sample-first — positives, negatives, commented form, and rejection-set proof. Never ship regex without examples. |
| `sql-explain` | pawn | `—` | Explain a SQL query in plain English — intent, tables, indexes, join strategy, cost class, and risks (full scan, implicit cast, N+1). |
| `cron-translator` | pawn | `—` | Translate between cron expressions, plain English, and next fire times. Flags day-of-month vs day-of-week conflicts. |
| `diff-narrator` | pawn | `—` | Write a one-paragraph why-this-changed from a git diff — user impact and motivation, not a line-by-line restatement. Ends with reviewer focus bullets. |
| `release-notes` | pawn | `—` | Turn a commit range into release notes — Added, Changed, Fixed, Security — framed by user impact, not implementation detail. |
| `error-translator` | pawn | `—` | Translate a stack trace to one-sentence root cause plus minimal fix. States missing evidence instead of guessing when uncertain. |
| `api-versioning-advisor` | pawn | `—` | Classify API changes as patch, minor, or major; enumerate breaking consumers and migration notes. Defaults conservative. |
| `migration-planner` | pawn | `—` | Plan forward migration and rollback with pre-flight checks and at-scale failure modes (locks, downtime, backfill duration). |
| `url-canonicalizer` | pawn | `—` | Canonicalize URLs, strip trackers, explain query parameters, and flag suspicious patterns (open redirect, homoglyph, IP literals). |
| `color-system-builder` | pawn | `—` | Expand one brand primary into a full UI palette with WCAG contrast pairings for bg, surface, accent, ok, warn, and error roles. |
| `prompt-distiller` | pawn | `—` | Distill a verbose prompt to minimum tokens while preserving constraints, output format, and success criteria. Shows before/after cuts. |
| `test-gap-finder` | pawn | `—` | Compare a function to its tests and list uncovered cases ranked by risk. Finds gaps first; does not write tests unless asked. |

### When to call

- **`regex-architect`** — write, read, audit, or debug a regular expression
- **`sql-explain`** — user pastes SQL and wants execution analysis without being a DBA
- **`cron-translator`** — cron schedule confusion, authoring schedules, or ops timing questions
- **`diff-narrator`** — PR description, commit summary, or explaining a diff to reviewers
- **`release-notes`** — release notes, changelog from commits, or version announcement draft
- **`error-translator`** — user pastes an error, exception, or failing test output
- **`api-versioning-advisor`** — API surface changed and semver or migration guidance is needed
- **`migration-planner`** — schema change, data migration, or production cutover planning
- **`url-canonicalizer`** — clean, compare, or security-audit URLs
- **`color-system-builder`** — status panels, TUI themes, or UI tokens from a single brand color
- **`prompt-distiller`** — prompt too long, cost review, or tightening system instructions
- **`test-gap-finder`** — are tests sufficient, what's missing, or pre-refactor risk check

## Hermes-adapted — swarm and debugging playbooks

| Skill | Role | Runnable | Description |
|-------|------|----------|-------------|
| `systematic-debugging` | shared | `—` | Four-phase root-cause debugging — investigate, pattern-match, hypothesize, fix. No fixes before understanding WHY. Stop after three failed fixes and question architecture. |
| `swarm-orchestrator` | arisen | `—` | Hermes kanban-orchestrator adapted for AgentDrive — decompose quests, dispatch pawns, collect inheritance. Anti-rule: do not implement pawn work yourself. |
| `swarm-worker` | pawn | `—` | Hermes kanban-worker adapted for pawns — structured handoffs, retry discipline, scope limits, and review-required blocking patterns. |

### When to call

- **`systematic-debugging`** — bug, test failure, unexpected behavior, or production incident
- **`swarm-orchestrator`** — multi-step project needs decomposition and pawn dispatch
- **`swarm-worker`** — dispatched worker pawn on a scoped implementation or research task

## Grok backup — harness mirrors for the hive bench

| Skill | Role | Runnable | Description |
|-------|------|----------|-------------|
| `grok-changelog` | shared | `—` | Maintain CHANGELOG.md after code or config changes — dated sections, Added/Changed/Fixed, verification hints. Hive copy of Grok changelog skill for pawns. |
| `grok-check-work` | shared | `—` | Self-verification via verifier subagent — review diffs, run tests, fix until pass. Hive copy for pawns finishing implementation work. |
| `grok-create-skill` | shared | `—` | Interactively scaffold a new SKILL.md with frontmatter, triggers, and body. Hive copy; use agentdrive skills init for AgentDrive-native skills. |
| `grok-help` | shared | `—` | Grok harness documentation and setup help — MCP, auth, skills, slash commands. Hive copy for pawns answering operator setup questions. |
| `grok-frontend-design` | shared | `—` | Production-grade frontend UI with distinctive aesthetics — typography, motion, spatial detail. Avoid generic AI slop. Hive copy for UI pawn work. |
| `grok-design-system` | shared | `—` | Ingest or generate DESIGN.md tokens from code, CSS, or screenshots — living design contract for consistent UI generations. Hive copy. |
| `grok-artifacts-builder` | shared | `—` | Build self-contained web artifacts (HTML/Tailwind or React) — prototypes, dashboards, interactive UIs with accessibility and dark mode. Hive copy. |
| `grok-best-of-n` | arisen | `—` | Implement a task N ways in parallel, evaluate candidates, apply the winner. Hive copy for Arisen-level parallel implementation tournaments. |
| `grok-docx` | shared | `—` | Create, read, and edit Word documents — reports, memos, templates, tracked changes. Hive copy for document pawn deliverables. |
| `grok-xlsx` | shared | `—` | Open, edit, or create spreadsheets — formulas, charts, messy data cleanup. Deliverable must be xlsx/csv/tsv. Hive copy. |
| `grok-pptx` | shared | `—` | Create or edit PowerPoint decks — slides, layouts, speaker notes, templates. Hive copy for presentation pawn work. |
| `grok-imagine` | shared | `—` | Image generation workflow — when to code vs generate, prompt craft, reference handling, factual grounding, asset consistency. Hive copy. |
| `grok-universal-brush` | shared | `—` | Universal Brush design studio — conversational visual work with live canvas preview for prototypes, decks, and marketing. Hive copy. |
| `grok-ren` | arisen | `—` | Ren Interest Brand Operator — autonomous brand loops, persona contract, Polsia-style persistent operator. Project-specific; hive copy for brand operator pawns. |

### When to call

- **`grok-changelog`** — end of implementation, session log, or user asks what changed
- **`grok-check-work`** — check work, verify changes, self-verify before handoff
- **`grok-create-skill`** — user wants to create or scaffold a new skill
- **`grok-help`** — setup, configuration, MCP, or harness feature questions
- **`grok-frontend-design`** — build web components, pages, landing pages, or React/Tailwind UI
- **`grok-design-system`** — brand tokens, design system, or consistent UI generation
- **`grok-artifacts-builder`** — interactive prototype, dashboard, or live-preview web artifact
- **`grok-best-of-n`** — best of n, try multiple approaches, parallel implementations
- **`grok-docx`** — Word doc, docx file, report, memo, or letter deliverable
- **`grok-xlsx`** — spreadsheet file as primary input or output
- **`grok-pptx`** — deck, slides, presentation, or pptx file
- **`grok-imagine`** — generate or edit images, visual assets, or image tool decisions
- **`grok-universal-brush`** — visual prototypes, slides, or marketing designs with live preview
- **`grok-ren`** — Ren persona, interest brand operator, or brand embodiment tasks

