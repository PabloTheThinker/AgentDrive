#!/usr/bin/env python3
"""Apply canonical descriptions from examples/skills/catalog.yaml to SKILL.md files."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "examples" / "skills" / "catalog.yaml"
SKILLS_ROOT = REPO / "examples" / "skills"

# Map catalog section → directory relative to SKILLS_ROOT
SECTION_DIRS = {
    "core": ["core", "."],
    "hive": ["hive"],
    "agentdrives": ["agentdrives"],
    "backup_hermes": ["backup/hermes"],
    "backup_grok": ["backup/grok"],
}

NAME_OVERRIDES = {
    "think": ["think"],
    "golden-path-verify": ["golden-path-verify"],
}


def _find_skill_md(name: str, dirs: list[str]) -> Path | None:
    if name in NAME_OVERRIDES:
        for sub in NAME_OVERRIDES[name]:
            p = SKILLS_ROOT / sub / "SKILL.md"
            if p.exists():
                return p
    for d in dirs:
        # grok skills live in backup/grok/<backup_of>/SKILL.md
        if name.startswith("grok-"):
            stem = name.removeprefix("grok-")
            p = SKILLS_ROOT / d / stem / "SKILL.md"
            if p.exists():
                return p
        p = SKILLS_ROOT / d / name / "SKILL.md"
        if p.exists():
            return p
    return None


def _quote_yaml(value: str) -> str:
    text = value.strip().replace("\n", " ").replace('"', '\\"')
    if ":" in text or text.startswith("#"):
        return f'"{text}"'
    return text


def _patch_frontmatter(path: Path, meta: dict) -> None:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if not match:
        raise ValueError(f"No frontmatter: {path}")

    existing = yaml.safe_load(match.group(1)) or {}
    if not isinstance(existing, dict):
        existing = {}

    for key in (
        "description",
        "role",
        "when_to_call",
        "tags",
        "source",
        "backup_of",
        "agentdrive_operation",
        "argument",
        "category",
    ):
        if key in meta and meta[key] is not None:
            existing[key] = meta[key]

    if "operation" in meta:
        existing["agentdrive_operation"] = meta["operation"]

    # Rebuild frontmatter (stable field order)
    order = [
        "name",
        "description",
        "agentdrive_operation",
        "argument",
        "category",
        "role",
        "source",
        "backup_of",
        "backup_path",
        "tags",
        "when_to_call",
        "related_skills",
    ]
    lines = ["---"]
    for key in order:
        if key not in existing or existing[key] in (None, "", []):
            continue
        val = existing[key]
        if key == "description":
            desc = str(val).strip()
            if "\n" in desc or len(desc) > 120:
                lines.append("description: >")
                for part in desc.replace("\n", " ").split():
                    if lines[-1].endswith(">"):
                        lines.append(f"  {part}")
                    else:
                        lines[-1] += f" {part}"
            else:
                lines.append(f"description: {_quote_yaml(desc)}")
        elif key == "tags" and isinstance(val, list):
            lines.append(f"tags: [{', '.join(str(t) for t in val)}]")
        else:
            lines.append(f"{key}: {val}")
    # Any remaining keys
    for key, val in existing.items():
        if key in order or val in (None, "", []):
            continue
        lines.append(f"{key}: {val}")
    lines.append("---")
    path.write_text("\n".join(lines) + "\n\n" + match.group(2).strip() + "\n", encoding="utf-8")


def main() -> int:
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    updated = 0
    for section, entries in data.items():
        if section.startswith("#") or not isinstance(entries, dict):
            continue
        dirs = SECTION_DIRS.get(section, [])
        category = section.replace("backup_", "backup/").replace("_", "/")
        if section == "core":
            category = "core"
        elif section == "hive":
            category = "hive"
        elif section == "agentdrives":
            category = "agentdrives"
        elif section == "backup_hermes":
            category = "backup"
        elif section == "backup_grok":
            category = "backup"

        for name, meta in entries.items():
            path = _find_skill_md(name, dirs)
            if path is None:
                print(f"  SKIP missing: {name}")
                continue
            patch = dict(meta)
            patch["name"] = name
            patch.setdefault("category", category)
            if section == "backup_grok":
                stem = name.removeprefix("grok-")
                patch.setdefault("source", "grok-backup")
                patch.setdefault("backup_of", stem)
                patch.setdefault("backup_path", f"~/.grok/skills/{stem}/SKILL.md")
            if section == "backup_hermes":
                patch.setdefault("source", "hermes-adapted")
            _patch_frontmatter(path, patch)
            updated += 1
            print(f"  updated {name} → {path.relative_to(REPO)}")

    print(f"Applied catalog to {updated} skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())