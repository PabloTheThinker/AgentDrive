# AgentDrive Skills Library

**Status:** shipped (2026-06-08)  
**Principle:** **Model-agnostic** — bundled skills work with any LLM (Ollama, Grok, Claude, Cursor, etc.). No vendor-specific mirrors in the repo.

---

## Why not Grok/Hermes backups?

Earlier versions copied `~/.grok/skills` into the bundle. That was wrong for a product bench:

- Grok skills assume Grok tools (`task`, `image_gen`, Universal Brush)
- Names like `grok-changelog` confuse operators on other models
- The repo should ship **universal playbooks**, not harness backups

**Vendor-specific skills** belong in `~/.agentdrive/skills/` on your machine (personal overlay). The bundled library is for everyone.

---

## Metaphor — Arisen, pawns, and the hive

| Role | Who | AgentDrive mapping |
|------|-----|-------------------|
| **Arisen** | Commands, does not grind | Main agent / `arisen-orchestrator` |
| **Pawn** | One quest, returns knowledge | Subagents; `pawn-worker`, `pawn-scout`, … |
| **Hive** | Shared memory | DNA pool + learnings + session events |
| **Inheritance** | Pawn → pool | `hive-inheritance`, `learnings-log` |

---

## On-disk layout

```
examples/skills/
  think/                 # core
  golden-path-verify/
  core/                  # runnable ops (doctor, pool-query, …)
  hive/                  # arisen + pawn playbooks
  agentdrives/           # 12 narrow prodigies
  universal/             # model-agnostic basics (changelog, verify-work, …)

~/.agentdrive/skills/    # YOUR overlays — any vendor, wins on name collision
```

**36 bundled skills** — full descriptions: [SKILLS-CATALOG.md](SKILLS-CATALOG.md)

---

## Tiers

| Tier | Count | Purpose |
|------|-------|---------|
| **core** | 6 | Runnable AgentDrive ops (`think`, `doctor`, …) |
| **hive** | 5 | Arisen/pawn coordination |
| **agentdrives** | 12 | Narrow specialists (regex, SQL, diff, …) |
| **universal** | 13 | Any-model basics (changelog, debugging, documents, UI) |

---

## Surfaces

| Surface | Command |
|---------|---------|
| CLI | `agentdrive skills list\|show\|run\|init` |
| Chat | `/skills list`, `/skill <name>` |
| System prompt | Auto catalog + matched skills per turn |

---

## Authoring

```bash
agentdrive skills init my-skill --description "What it does"
```

Edit `examples/skills/catalog.yaml`, then:

```bash
python scripts/apply_skills_catalog.py
python scripts/generate_skills_catalog_doc.py
```

See also: [ASSESSMENT.md](ASSESSMENT.md), [SKILLS-SPEC.md](SKILLS-SPEC.md).