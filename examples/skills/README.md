# Bundled AgentDrive skills bench

**61 skills** across five tiers — invoke with `/skill <name>` or `agentdrive skills run <name>`.

| Tier | Folder | Harness | Examples |
|------|--------|---------|----------|
| 1–3 | `core/`, `hive/`, `agentdrives/`, `think/` | `agentdrive` | `think`, `pawn-worker`, `regex-architect` |
| 4 | `universal/` | `universal` | `changelog`, `mcp-agentdrive`, `systematic-debugging` |
| 5 | `vendors/grok|claude|codex/` | vendor | `grok-imagine`, `claude-skill-creator`, `codex-github` |

- **Catalog (tiers 1–4):** `catalog.yaml` → `docs/SKILLS-CATALOG.md`
- **Vendor sync:** `vendor-manifest.yaml` → `scripts/sync_vendor_skills.py`
- **Personal overlays:** `~/.agentdrive/skills/` (any vendor; wins on name collision)

On MCP with any model → tiers 1–4. Tier 5 only when native harness tools exist (`AGENTDRIVE_HARNESS`).