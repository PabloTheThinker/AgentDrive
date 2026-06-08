---
name: grok-changelog
description: "Maintain CHANGELOG.md after code, config, or project changes. Use when finishing any implementation task, setup, refactor, or fix; when the user asks for a changelog or session log; or proactively at end of work that modified files. Applies to all projects per ~/.grok/AGENTS.md. Triggers: changelog, change log, session log, what did you do, document changes."
category: vendors
harness: grok
requires: "Grok CLI harness (task tool, image_gen, etc.)"
role: shared
tags: [grok, vendor, harness]
backup_of: changelog
backup_path: /home/pablothethinker/.grok/skills/changelog/SKILL.md
when_to_call: when running on the grok harness with its native tools; use universal/* via MCP otherwise
---

# grok-changelog (grok harness)

> **Harness:** grok · **Requires:** Grok CLI harness (task tool, image_gen, etc.)
>
> Prefer the **universal/** counterpart when using AgentDrive MCP with any model.
> This copy preserves the native grok workflow and tool assumptions.

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
