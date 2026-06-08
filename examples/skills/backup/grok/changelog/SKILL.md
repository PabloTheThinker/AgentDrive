---
name: grok-changelog
description: "Backup of Grok harness skill `changelog` for swarm pawns and hive bench."
source: grok-backup
role: shared
category: backup
tags: [grok, backup, hive, pawn]
backup_of: changelog
backup_path: ~/.grok/skills/changelog/SKILL.md
when_to_call: when a pawn or connected agent needs the same workflow Grok uses for changelog
---

# Grok backup — changelog

This skill mirrors the operator's Grok harness skill so **pawn subagents** and other
AgentDrive-connected agents can load the same playbook from the shared hive bench.

**Original path:** `~/.grok/skills/changelog/SKILL.md`

---

# Changelog maintenance

Follow `~/.grok/AGENTS.md` (global changelog rule). This skill is the detailed checklist.

## Before you finish

1. Identify the correct `CHANGELOG.md` (repo root, app subfolder, or create one).
2. Add a **new dated section at the top** (below any header/policy block).
3. List **Added / Changed / Removed / Fixed / Accomplished** as applicable.
4. Include verification hints: `npm run dev`, ports, env vars, URLs.
5. If you created the project's first changelog, add a README pointer in the same edit pass when a README exists.

## Create if missing

Use this header for new files:

```markdown
# Changelog

Notable changes to this project. Newest entries first.

---
```

## Do not

- Rely on chat history alone — write the file.
- Dump raw tool logs — summarize outcomes.
- Duplicate release-version changelogs (e.g. keep semver releases in `CHANGELOG.md` and add dated session sections above `[Unreleased]` or after the title).

## Template

See `references/entry-template.md` in this skill directory.
