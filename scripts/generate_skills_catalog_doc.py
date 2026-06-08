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
    "universal": "Universal — model-agnostic basics (any LLM)",
}


def _one_line(desc: str) -> str:
    return " ".join(desc.strip().split())


def main() -> int:
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    total = sum(len(v) for v in data.values() if isinstance(v, dict))
    lines = [
        "# AgentDrive Skills Catalog",
        "",
        "**Model-agnostic bench** — no vendor-specific (Grok/Hermes) bundles. Any connected LLM can load these.",
        "",
        f"**Total:** {total} bundled skills · `/skill <name>` · `agentdrive skills list`",
        "",
        "Source: `examples/skills/catalog.yaml`",
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

    lines.append("## Personal skill overlays")
    lines.append("")
    lines.append(
        "Vendor-specific skills (Grok harness, Cursor, etc.) belong in "
        "`~/.agentdrive/skills/` on your machine — not in the bundled repo. "
        "They override bundled names on collision."
    )
    lines.append("")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({total} skills)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())