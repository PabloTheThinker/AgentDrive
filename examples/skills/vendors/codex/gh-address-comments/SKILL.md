---
name: codex-gh-address-comments
description: "Address PR review comments systematically from Codex."
category: vendors
harness: codex
requires: "OpenAI Codex CLI and curated plugins"
role: shared
tags: [codex, vendor, harness]
backup_of: gh-address-comments
backup_path: /home/pablothethinker/.codex/plugins/cache/openai-curated/github/3f0def1b/skills/gh-address-comments/SKILL.md
when_to_call: when running on the codex harness with its native tools; use universal/* via MCP otherwise
---

# codex-gh-address-comments (codex harness)

> **Harness:** codex · **Requires:** OpenAI Codex CLI and curated plugins
>
> Prefer the **universal/** counterpart when using AgentDrive MCP with any model.
> This copy preserves the native codex workflow and tool assumptions.

---

# GitHub PR Comment Handler

Use this skill when the user wants to work through requested changes on a GitHub pull request. Use the GitHub app from this plugin for PR metadata and patch context, but treat thread-aware review data as a `gh api graphql` problem because the connector comment surface is flat and does not preserve full review-thread state.

Run all `gh` commands with elevated network access. If CLI auth is required, confirm `gh auth status` first and ask the user to authenticate with `gh auth login` if it fails.

## Workflow

1. Resolve the PR.
   - If the user provides a repository and PR number or URL, use that directly.
   - If the request is about the current branch PR, use local git context plus `gh auth status` and `gh pr view --json number,url` to resolve it.
2. Inspect review context with thread-aware reads.
   - Use the GitHub app from this plugin to fetch PR metadata and patch context when the repo and PR are known.
   - Use the bundled `scripts/fetch_comments.py` workflow whenever the task depends on unresolved review threads, inline review locations, or resolution state. That script fetches `reviewThreads`, `isResolved`, `isOutdated`, and file and line anchors that the connector comment surface does not preserve.
   - Use connector-only comment reads only for lightweight top-level PR comment summaries.
3. Cluster actionable review threads.
   - Group comments by file or behavior area.
   - Separate actionable change requests from informational comments, approvals, already-resolved threads, and duplicates.
4. Confirm scope before editing.
   - Present numbered actionable threads with a one-line summary of the required change.
   - If the user did not ask to fix everything, ask which threads to address.
   - If the user asks to fix everything, interpret that as all unresolved actionable threads and call out anything ambiguous.
5. Implement the selected fixes locally.
   - Keep each code change traceable back to the thread or feedback cluster it addresses.
   - If a comment calls for explanation rather than code, draft the response rather than forcing a code change.
6. Summarize the result.
   - List which threads were addressed, which were intentionally left open, and what tests or checks support the change.

## Write Safety

- Do not reply on GitHub, resolve review threads, or submit a review unless the user explicitly asks for that write action.
- If review comments conflict with each other or would cause a behavioral regression, surface the tradeoff before making changes.
- If a comment is ambiguous, ask for clarification or draft a proposed response instead of guessing.
- Do not treat flat PR comments from the connector as a complete representation of review-thread state.
- If `gh` hits auth or rate-limit issues mid-run, ask the user to re-authenticate and retry.

## Fallback

If neither the connector nor `gh` can resolve the PR cleanly, tell the user whether the blocker is missing repository scope, missing PR context, or CLI authentication, then ask for the missing repo or PR identifier or for a refreshed `gh` login.
