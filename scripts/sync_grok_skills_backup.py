#!/usr/bin/env python3
"""Copy ~/.grok/skills into AgentDrive bundled backup library."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GROK_SKILLS = Path.home() / ".grok" / "skills"
DEST_ROOT = REPO_ROOT / "examples" / "skills" / "backup" / "grok"

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def _wrap_skill(name: str, body: str) -> str:
    return f"""---
name: grok-{name}
description: "Backup of Grok harness skill `{name}` for swarm pawns and hive bench."
source: grok-backup
role: shared
category: backup
tags: [grok, backup, hive, pawn]
backup_of: {name}
backup_path: ~/.grok/skills/{name}/SKILL.md
when_to_call: when a pawn or connected agent needs the same workflow Grok uses for {name}
---

# Grok backup — {name}

This skill mirrors the operator's Grok harness skill so **pawn subagents** and other
AgentDrive-connected agents can load the same playbook from the shared hive bench.

**Original path:** `~/.grok/skills/{name}/SKILL.md`

---

{body.strip()}
"""


def main() -> int:
    if not GROK_SKILLS.is_dir():
        print(f"No Grok skills at {GROK_SKILLS}")
        return 1

    DEST_ROOT.mkdir(parents=True, exist_ok=True)
    copied = 0
    for skill_dir in sorted(GROK_SKILLS.iterdir()):
        if not skill_dir.is_dir():
            continue
        src = skill_dir / "SKILL.md"
        if not src.is_file():
            continue
        text = src.read_text(encoding="utf-8")
        match = _FRONTMATTER.match(text)
        body = match.group(2) if match else text
        dest_dir = DEST_ROOT / skill_dir.name
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / "SKILL.md").write_text(_wrap_skill(skill_dir.name, body), encoding="utf-8")
        copied += 1
        print(f"  synced grok-{skill_dir.name}")

    print(f"Synced {copied} Grok skills → {DEST_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())