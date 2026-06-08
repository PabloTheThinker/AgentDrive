# Bundled AgentDrive skills bench

**36 model-agnostic skills** — any LLM can load these via `/skill <name>`.

| Tier | Folder | Examples |
|------|--------|----------|
| Core ops | `core/`, `think/` | `think`, `doctor`, `pool-query` |
| Hive | `hive/` | `pawn-worker`, `arisen-orchestrator` |
| Specialists | `agentdrives/` | `regex-architect`, `error-translator` |
| Universal | `universal/` | `changelog`, `verify-work`, `systematic-debugging` |

Catalog: `docs/SKILLS-CATALOG.md` · Source: `catalog.yaml`

**Personal / vendor skills** (Grok, Cursor, etc.) → `~/.agentdrive/skills/` only, not this folder.