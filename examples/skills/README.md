# Bundled AgentDrive skills bench

Shipped with the `agentdrive` package under `examples/skills/`. User skills in `~/.agentdrive/skills/` override on name collision.

## Categories

- **core/** — runnable ops (`think`, `pool-query`, `doctor`, …)
- **hive/** — Arisen + pawn + inheritance playbooks
- **agentdrives/** — narrow prodigy skills (regex, SQL, diff, …)
- **backup/grok/** — Grok harness mirrors for swarm pawns
- **backup/hermes/** — Hermes kanban/debug patterns adapted for AgentDrive

Full catalog: `docs/SKILLS-LIBRARY.md`

## Sync Grok backups

```bash
python scripts/sync_grok_skills_backup.py
```