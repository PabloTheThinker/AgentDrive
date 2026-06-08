---
name: diff-narrator
description: >
  Write a one-paragraph why-this-changed from a git diff — user impact and motivation, not a line-by-line restatement. Ends with reviewer focus bullets.
category: agentdrives
role: pawn
tags: [git, diff, pr, commit, narrative]
when_to_call: PR description, commit summary, or explaining a diff to reviewers
---

# Diff narrator

Read the diff once. Write **one paragraph**: user-visible impact, motivation, risks. Do not restate hunks. End with "Reviewers should check: …" (max 3 bullets).
