# AgentDrive Skills Library

**Status:** shipped (2026-06-08)  
**Pattern:** Hermes-style `SKILL.md` + YAML frontmatter; AgentDrive `agentdrive_operation` for runnable ops.

---

## Metaphor — Arisen, pawns, and the hive

Inspired by **Dragon's Dogma** and Hermes multi-agent patterns:

| Role | Who | AgentDrive mapping |
|------|-----|-------------------|
| **Arisen** | Player — commands, does not grind | Main `AgentDriveAgent` / orchestrator chat |
| **Pawn** | Hired specialist — one quest, returns | Subagents (`subagent_id` on harness); `role: pawn` skills |
| **Hive** | Shared memory all pawns pull from | DNA pool + learnings + `events.jsonl` session stream |
| **Inheritance** | Pawn knowledge returning to the Arisen | `hive-inheritance`, pool ingest, learnings-log |

Spawn a pawn → assign `pawn-worker` + a specialist (`regex-architect`, etc.) → pawn pulls DNA → returns handoff → Arisen logs to hive.

---

## On-disk layout

```
examples/skills/                    # Bundled bench (shipped with repo)
  think/                            # core — cited synthesis
  golden-path-verify/
  core/                             # runnable ops skills
  hive/                             # arisen + pawn + inheritance
  agentdrives/                      # 12 narrow prodigies (SKILLS-SPEC seed)
  backup/
    grok/                           # mirror of ~/.grok/skills (14 skills)
    hermes/                         # Hermes-adapted swarm/debug playbooks

~/.agentdrive/skills/               # User overrides (wins on name collision)
```

Discovery: `discover_skills()` walks `**/*.SKILL.md` under user + bundled roots.

---

## Frontmatter fields

| Field | Purpose |
|-------|---------|
| `name` | Unique skill id (`/skill <name>`) |
| `description` | One line for catalog + matching |
| `agentdrive_operation` | Maps to `run_operation()` when set |
| `argument` | Kwarg name for CLI/slash args |
| `role` | `arisen` \| `pawn` \| `shared` |
| `category` | `core` \| `hive` \| `agentdrives` \| `backup` |
| `tags` | Matching + filter |
| `source` | `grok-backup`, `hermes-adapted`, etc. |
| `when_to_call` | Auto-compose hint |

---

## Catalog (bundled)

### Core (runnable)

| Skill | Operation |
|-------|-----------|
| `think` | `think` |
| `golden-path-verify` | verify walkthrough |
| `learnings-log` | `learnings_log` |
| `learnings-list` | `learnings_list` |
| `pool-query` | `pool_query` |
| `doctor` | `doctor` |

### Hive (prompt playbooks)

| Skill | Role |
|-------|------|
| `arisen-orchestrator` | arisen |
| `pawn-worker` | pawn |
| `pawn-scout` | pawn |
| `pawn-specialist` | pawn |
| `hive-inheritance` | shared |

### Agentdrives (12 narrow prodigies)

`regex-architect`, `sql-explain`, `cron-translator`, `diff-narrator`, `release-notes`, `error-translator`, `api-versioning-advisor`, `migration-planner`, `url-canonicalizer`, `color-system-builder`, `prompt-distiller`, `test-gap-finder`

### Backup — Grok harness (14)

Synced from `~/.grok/skills` via `scripts/sync_grok_skills_backup.py`:

`grok-changelog`, `grok-check-work`, `grok-create-skill`, `grok-help`, `grok-frontend-design`, … (prefix `grok-`)

### Backup — Hermes-adapted (3)

`systematic-debugging`, `swarm-orchestrator`, `swarm-worker`

---

## Surfaces

| Surface | Command |
|---------|---------|
| CLI | `agentdrive skills list\|show\|run\|init` |
| Chat | `/skills list`, `/skill <name>`, `/skills init <name>` |
| System prompt | Auto catalog + top-2 matched skills per turn (`compose_skills_block`) |
| Pawn spawn | Subagents get `role=pawn` matching boost |

---

## Refresh Grok backup

When Grok harness skills change:

```bash
python scripts/sync_grok_skills_backup.py
```

Commit updated `examples/skills/backup/grok/` so swarm pawns ship with the same playbooks.

---

## Authoring

```bash
agentdrive skills init my-skill --description "What it does"
```

Or copy a template from `hive/pawn-worker` or `agentdrives/error-translator`.

**Promote to Genome** when a skill earns tracked outcomes — use existing genome scan/promotion (future: `skills promote`).

See also: `docs/SKILLS-SPEC.md` (design brainstorm), `docs/ASSESSMENT.md` (product assessment).