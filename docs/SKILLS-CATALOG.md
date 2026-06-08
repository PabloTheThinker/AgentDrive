# AgentDrive Skills Catalog

**Model-agnostic bench** — no vendor-specific (Grok/Hermes) bundles. Any connected LLM can load these.

**Total:** 36 bundled skills · `/skill <name>` · `agentdrive skills list`

Source: `examples/skills/catalog.yaml`

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

## Universal — model-agnostic basics (any LLM)

| Skill | Role | Runnable | Description |
|-------|------|----------|-------------|
| `changelog` | shared | `—` | Maintain CHANGELOG.md after code or config changes — dated sections, Added/Changed/Fixed/Removed, verification hints. Works with any model or editor. |
| `verify-work` | shared | `—` | Before handoff — review your diff, run relevant tests, fix failures, confirm the task is actually done. Model-agnostic self-check, not vendor-specific tooling. |
| `skill-authoring` | shared | `—` | Author a SKILL.md — frontmatter (name, description, when_to_call), concise body, one worked example. Use agentdrive skills init to scaffold on disk. |
| `systematic-debugging` | shared | `—` | Four-phase debugging — investigate, compare patterns, hypothesize, fix root cause. No fixes before understanding WHY. Stop after three failed fixes. |
| `swarm-orchestrator` | arisen | `—` | Decompose multi-step work into pawn-sized tasks, dispatch specialists, collect handoffs. Do not implement pawn work yourself. |
| `swarm-worker` | pawn | `—` | Execute one assigned task with structured handoff — summary, files, tests, gaps. Retry discipline and scope limits for any subagent runtime. |
| `frontend-design` | shared | `—` | Build distinctive, production-grade UI — typography, spacing, motion, accessibility. Avoid generic templates; commit to a clear aesthetic before coding. |
| `design-system` | shared | `—` | Extract or define design tokens (color, type, spacing, components) as a living contract so all UI generations stay consistent. |
| `web-artifact` | shared | `—` | Self-contained interactive web artifact — HTML/CSS/JS or component framework, responsive, accessible, previewable in a browser. |
| `document-docx` | shared | `—` | Create or edit Word documents — reports, memos, letters, templates with headings and tables. Deliverable is a .docx file. |
| `document-xlsx` | shared | `—` | Read, clean, or create spreadsheets — formulas, charts, tabular data. Deliverable is xlsx/csv/tsv. |
| `document-pptx` | shared | `—` | Create or edit slide decks — structure, speaker notes, consistent layout. Deliverable is a .pptx file. |
| `parallel-attempts` | arisen | `—` | Try multiple approaches to the same problem, compare outcomes objectively, keep the best. Works with any runtime that can spawn isolated attempts. |

### When to call

- **`changelog`** — end of implementation, session wrap-up, or user asks what changed
- **`verify-work`** — check work, verify changes, or before marking a task complete
- **`skill-authoring`** — create a new skill, document a repeatable workflow
- **`systematic-debugging`** — bug, test failure, unexpected behavior, production incident
- **`swarm-orchestrator`** — project needs breakdown and delegated execution
- **`swarm-worker`** — dispatched worker on a scoped implementation or research task
- **`frontend-design`** — web pages, components, dashboards, or landing pages
- **`design-system`** — brand consistency, DESIGN.md, or token extraction from code/CSS
- **`web-artifact`** — prototype, demo, dashboard, or handoff-ready UI artifact
- **`document-docx`** — Word document, report, memo, or letter as deliverable
- **`document-xlsx`** — spreadsheet is primary input or output
- **`document-pptx`** — presentation, deck, or slides as deliverable
- **`parallel-attempts`** — uncertain best approach, compare implementations, or explore alternatives

## Personal skill overlays

Vendor-specific skills (Grok harness, Cursor, etc.) belong in `~/.agentdrive/skills/` on your machine — not in the bundled repo. They override bundled names on collision.

