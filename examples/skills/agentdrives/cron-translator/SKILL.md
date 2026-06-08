---
name: cron-translator
description: "Translate cron ↔ plain English ↔ next N fire times."
category: agentdrives
role: pawn
tags: [cron, ops, scheduling]
when_to_call: user has a cron expression or wants a schedule in cron form
---

# Cron translator

1. Parse or compose the cron expression.
2. Plain-English description (timezone explicit).
3. Next 5 fire times.
4. Common mistakes check (day-of-month vs day-of-week conflict).