#!/usr/bin/env python3
"""Generate docs/SKILLS-CATALOG.md from catalog.yaml + vendor-manifest.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "examples" / "skills" / "catalog.yaml"
VENDORS = REPO / "examples" / "skills" / "vendor-manifest.yaml"
OUT = REPO / "docs" / "SKILLS-CATALOG.md"

SECTION_TITLES = {
    "core": "Tier 1 — AgentDrive core (runnable MCP operations)",
    "hive": "Tier 2 — Hive (Arisen, pawns, inheritance)",
    "agentdrives": "Tier 3 — Agentdrives (narrow specialists)",
    "universal": "Tier 4 — Universal (any model; use when not on a vendor harness)",
}

VENDOR_TITLES = {
    "grok": "Tier 5a — Grok harness (native Grok CLI tools)",
    "claude": "Tier 5b — Claude Code harness",
    "codex": "Tier 5c — Codex CLI harness",
}


def _one_line(desc: str) -> str:
    return " ".join(str(desc).strip().split())


def main() -> int:
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    vdata = yaml.safe_load(VENDORS.read_text(encoding="utf-8")) if VENDORS.exists() else {}
    bundled = sum(len(v) for v in data.values() if isinstance(v, dict))
    vendors_root = REPO / "examples" / "skills" / "vendors"
    vendor_counts: dict[str, int] = {}
    if vendors_root.is_dir():
        for sub in sorted(vendors_root.iterdir()):
            if sub.is_dir():
                vendor_counts[sub.name] = len(list(sub.glob("*/SKILL.md")))
    vendor_count = sum(vendor_counts.values())

    lines = [
        "# AgentDrive Skills Catalog",
        "",
        "## Organization",
        "",
        "| Tier | Folder | Who uses it |",
        "|------|--------|-------------|",
        "| **1–3** | `core/`, `hive/`, `agentdrives/` | Any model via **AgentDrive MCP** |",
        "| **4** | `universal/` | Any model — no vendor tools required |",
        "| **5** | `vendors/grok|claude|codex/` | Only when that **harness** is active |",
        "",
        "**Rule:** On MCP with Ollama/Claude/Grok-as-MCP → use tiers 1–4. "
        "Use tier 5 only when native harness tools exist. Set `AGENTDRIVE_HARNESS=grok` "
        "to inject vendor skills into the system prompt.",
        "",
        f"**Counts:** {bundled} bundled + {vendor_count} vendor "
        f"({', '.join(f'{k} {v}' for k, v in vendor_counts.items()) or 'run sync_vendor_skills.py'})",
        "",
    ]

    for section, title in SECTION_TITLES.items():
        entries = data.get(section, {})
        if not entries:
            continue
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| Skill | Harness | Role | Runnable | Description |")
        lines.append("|-------|---------|------|----------|-------------|")
        harness = "agentdrive" if section in ("core", "hive", "agentdrives") else "universal"
        for name, meta in entries.items():
            role = meta.get("role", "—")
            op = meta.get("operation", "—")
            desc = _one_line(meta.get("description", ""))
            lines.append(f"| `{name}` | {harness} | {role} | `{op}` | {desc} |")
        lines.append("")

    for vendor, title in VENDOR_TITLES.items():
        cfg = vdata.get(vendor, {})
        requires = cfg.get("requires", f"{vendor} harness")
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"**Requires:** {requires}")
        lines.append("")
        lines.append("| Skill | Description |")
        lines.append("|-------|-------------|")
        if vendor == "grok":
            n = vendor_counts.get("grok", 0)
            lines.append(f"| *({n} skills)* | Synced from `~/.grok/skills` — see `vendors/grok/` |")
            lines.append(
                "| `grok-changelog`, `grok-check-work`, `grok-imagine`, … | Native Grok tool paths; use `changelog` / `verify-work` universal when on MCP only |"
            )
        else:
            for slug, spec in (cfg.get("skills") or {}).items():
                prefix = cfg.get("name_prefix", f"{vendor}-")
                desc = spec.get("description", "") if isinstance(spec, dict) else ""
                lines.append(f"| `{prefix}{slug}` | {_one_line(desc)} |")
        lines.append("")

    lines.append("## Refresh vendor overlays")
    lines.append("")
    lines.append("```bash")
    lines.append("python scripts/sync_vendor_skills.py")
    lines.append("python scripts/apply_skills_catalog.py")
    lines.append("python scripts/generate_skills_catalog_doc.py")
    lines.append("```")
    lines.append("")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
