# Agent Drive Skills — design + first 12 skill brainstorm

**Status:** draft for review. Nothing built yet.
**Premise:** A agentdrive is someone with exceptional, narrow-domain prodigy. The product should embrace that literally — each skill is a *agentdrive*: a small, focused, world-class capability in one specific thing. The agent doesn't try to be good at everything; it consults the right agentdrive for the task.

This is the the reference CLI Phase-3 move (Jan→Feb 2026 in their arc): the moment the product stops being "an agent" and becomes "a thing you extend."

---

## How skills relate to existing pieces

Agent Drive already has **Genomes** — full reusable capability units with manifests, scanners, evaluation scores. A Genome is a `species`-level capability ("incident postmortem author", "SOC2 evidence tracer"). Heavy. Versioned. Promoted to "production-grade" via the promotion mechanic.

Skills are **lighter**: a directory of `SKILL.md` files with YAML frontmatter + a single prompt-fragment body. No manifest, no version, no evaluation pipeline. They compose into the active genome at runtime — the agent picks the most-relevant 1-3 skills for the task and appends them to its system prompt.

**Rule of thumb:**
- If it deserves outcome tracking + promotion + reuse across teams → Genome.
- If it's a focused way of thinking about one narrow problem → Skill.

A skill can be **promoted into a Genome** once it earns enough outcomes (the promotion mechanic already handles that).

---

## On-disk shape

```
~/.agentdrive/skills/
  regex-architect/
    SKILL.md
    examples/
      capture-email.md
      reject-sql-injection.md
  sql-explain/
    SKILL.md
  cron-translator/
    SKILL.md
  ...
```

A `SKILL.md` (mirrors the the reference CLI shape since it works):

```markdown
---
name: regex-architect
description: Builds, audits, and explains regular expressions for a specific
  intent. Asks for sample input/output before writing. Always provides a
  rejection-set proof.
tags: [regex, parsing, text, validation]
domains: [code]
intent: narrow-domain text-pattern reasoning
when_to_call: user wants to write/read/audit a regex, or the model is about
  to ship a regex without sample inputs
---

## How this agentdrive thinks

Always start with examples, never the pattern. For any non-trivial regex,
the agentdrive asks for at least three positive samples and at least two
negative samples (cases that MUST not match). The output is always:

1. The pattern in its simplest correct form.
2. The same pattern with `(?x)` whitespace + inline comments.
3. A worked trace against each provided sample.
4. The exact rejection set: every kind of input that will fail.
...
```

---

## Surfaces the skill touches

- **Discovery**: `agentdrive skills list` / `agentdrive skills info <name>` / `/skills` in chat.
- **Composition**: at the start of each turn, after `pull_relevant_dna` matches genomes, a second pass matches skills by tag + intent + when_to_call against the user message + the active genome's domains. Top 1-3 skill fragments get injected into the system prompt.
- **Invocation**: `/skill <name>` forces a specific skill onto the next turn.
- **Suggestion**: the LLM is told which skills exist; the model can suggest "this might be a job for the `regex-architect` skill."
- **Ribbon**: new event `SkillInvoked(skill_name, reason)` — fires a thin ribbon during chat like the existing pool events. Lets the user see *which agentdrive the agent is consulting*.
- **Authorship**: `agentdrive skills new <name>` scaffolds a SKILL.md with frontmatter template.

---

## First 12 skills to ship (the seed agentdrive library)

Picked for **narrow + universally useful**. Each is something the model is already capable of but does inconsistently. The skill enforces the consistent way.

| Skill | The narrow prodigy | Why it earns its slot |
|---|---|---|
| **regex-architect** | Builds regexes from examples first; always ships rejection-set proof | Most regex output in the wild is wrong; sample-first is the fix |
| **sql-explain** | Reads a SQL query and reports its execution intent, indexes touched, likely cost class | Decodes opaque queries for non-DBA readers |
| **cron-translator** | Cron expressions ↔ plain-English ↔ next-N-fire-times | One of the most error-prone tiny domains in ops |
| **diff-narrator** | Reads a `git diff` and writes a one-paragraph "why this changed" without restating the diff | Replaces 90% of bad PR descriptions |
| **release-notes** | Aggregates a commit range into changelog buckets (Added / Changed / Fixed / Security) with user-impact framing | Already a the reference CLI pattern, ships almost free |
| **error-translator** | Takes a raw stack trace + the surrounding code and writes the one-sentence root cause + the minimal fix | Replaces the "paste error → wall of advice" antipattern |
| **api-versioning-advisor** | Given an API change, classifies it as patch/minor/major and lists the breaking surface | Lives in the same lane as semver but with reasoning |
| **migration-planner** | Given a schema/code change, produces a forward-migration + rollback + a "what could go wrong at scale" list | Inherits the spirit of the existing security-incident-postmortem genome |
| **url-canonicalizer** | Normalizes URLs, strips trackers, detects suspicious patterns, explains what each query param does | Small, sharp, surprisingly common ask |
| **color-system-builder** | Given a primary brand color + role list, produces a full palette with WCAG contrast pairings | Pays for itself the first time someone designs a status panel |
| **prompt-distiller** | Takes a verbose prompt and produces the minimum-tokens version that preserves intent | Useful for cost work AND for prompt review |
| **test-gap-finder** | Reads a function + its existing tests and lists the cases NOT covered, ranked by risk | Higher-leverage than asking the model to "write more tests" |

These are deliberately *not* deep-domain (no "lawyer", no "doctor" — those need domain genomes with real evidence pipelines). They're the kind of small, universal agentdrives every operator wants on call.

---

## Build order

1. **Loader + registry** (~half day). `agentdrive.skills` module: load `~/.agentdrive/skills/*/SKILL.md`, parse YAML frontmatter, expose `list_skills() / get_skill(name) / search_skills(query)`.
2. **Composition into system prompt** (~half day). Hook in `agent.send` after `pull_relevant_dna`. Rank top 3 by tag/intent/keyword match. Inject as a `## Skills available for this turn` block.
3. **Slash + CLI + events** (~half day). `/skills`, `/skill <name>`, `/skill ?` for help. `agentdrive skills list/info/new`. `SkillInvoked` event + chat ribbon. Genome-side: shared code path so CLI and slash route through one function (the same pattern Pattern 5 established for genomes).
4. **Ship the first 12 skills** (~half day per ~3 skills, so ~2 days). Each one gets its own `SKILL.md` with at least one worked example in `examples/`.
5. **Promotion path** (~quarter day). Add a `agentdrive skills promote <name>` that converts a high-outcome skill into a real Genome scaffold. Doesn't auto-ingest; produces a directory the user can review and `agentdrive scan` into the registry.

**Total: ~4–5 dev-days.** Demoable after step 2.

---

## Open questions for the project maintainer

1. **Naming.** "Skill" is what the reference CLI calls it and what most agents call it. Want to keep "Skill" (clear, conventional) or rename to something Agent Drive-native like "agentdrive" (each skill literally IS a agentdrive)? My instinct: keep "Skill" in the *code* but in user-facing copy treat them as agentdrives — `/skills` lists "the agentdrives on your bench". Costs nothing, embraces the metaphor.
2. **Are the 12 above the right first set?** Anything obvious I missed, anything you'd cut?
3. **Auto-compose vs explicit only.** Should the agent automatically inject the top-matched skills, or only when the user invokes `/skill <name>`? Auto-compose is more "magic"; explicit-only is more predictable. Recommendation: ship explicit-only first, add auto-compose behind a config flag once we see what users actually want.
4. **Where does promotion fit?** Skills → Genomes is a natural ladder. Want me to wire the `agentdrive skills promote` path in this round, or defer until skills have proven themselves with real use?
