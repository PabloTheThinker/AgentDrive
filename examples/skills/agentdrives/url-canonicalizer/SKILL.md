---
name: url-canonicalizer
description: >
  Canonicalize URLs, strip trackers, explain query parameters, and flag suspicious patterns (open
  redirect, homoglyph, IP literals).
category: agentdrives
role: pawn
tags: [url, security, parsing, tracking]
when_to_call: clean, compare, or security-audit URLs
harness: agentdrive
---

# URL canonicalizer

Output: canonical form, stripped trackers, param glossary, suspicion flags (open redirect, homoglyph, IP literal).
