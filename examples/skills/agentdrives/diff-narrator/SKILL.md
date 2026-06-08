---
name: diff-narrator
description: "One-paragraph why-this-changed from a git diff — not a line-by-line restatement."
category: agentdrives
role: pawn
tags: [git, diff, pr, review]
when_to_call: user shares a diff or asks for PR/commit narrative
---

# Diff narrator

Read the diff once. Write **one paragraph**: user-visible impact, motivation, risks. Do not restate hunks. End with "Reviewers should check: …" (max 3 bullets).