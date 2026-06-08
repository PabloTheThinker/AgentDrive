#!/usr/bin/env python3
"""Generate docs/SKILLS-CATALOG.md from examples/skills/catalog.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "examples" / "skills" / "catalog.yaml"
OUT = REPO / "docs" / "SKILLS-CATALOG.md"

SECTION_TITLES = {
    "core": "Core — runnable AgentDrive operations",
    "hive": "Hive — Arisen, pawns, and inheritance",
    "agentdrives": "Agentdrives — narrow prodigy specialists",
    "backup_hermes": "Hermes-adapted — swarm and debugging playbooks",
    "backup_grok": "Grok backup — harness mirrors for the hive bench",
}


def _one_line(desc: str) -> str:
    return " ".join(desc.strip().split())


def main() -> int:
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    lines = [
        "# AgentDrive Skills Catalog",
        "",
        "**Generated from** `examples/skills/catalog.yaml` — run `python scripts/generate_skills_catalog_doc.py` after edits.",
        "",
        "**Total:** 40 bundled skills · invoke via `/skill <name>` or `agentdrive skills run <name>`",
        "",
        "See also: [SKILLS-LIBRARY.md](SKILLS-LIBRARY.md) (layout + metaphor), [ASSESSMENT.md](ASSESSMENT.md) (product status).",
        "",
    ]

    for section, title in SECTION_TITLES.items():
        entries = data.get(section, {})
        if not entries:
            continue
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| Skill | Role | Runnable | Description |")
        lines.append("|-------|------|----------|-------------|")
        for name, meta in entries.items():
            role = meta.get("role", "—")
            op = meta.get("operation", "—")
            desc = _one_line(str(meta.get("description", "")))
            lines.append(f"| `{name}` | {role} | `{op}` | {desc} |")
        lines.append("")

        lines.append("### When to call")
        lines.append("")
        for name, meta in entries.items():
            when = meta.get("when_to_call", "")
            if when:
                lines.append(f"- **`{name}`** — {when}")
        lines.append("")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())