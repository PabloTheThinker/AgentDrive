#!/usr/bin/env python3
"""Apply canonical descriptions from examples/skills/catalog.yaml to SKILL.md files."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "examples" / "skills" / "catalog.yaml"
SKILLS_ROOT = REPO / "examples" / "skills"

SECTION_DIRS = {
    "core": ["core", "."],
    "hive": ["hive"],
    "agentdrives": ["agentdrives"],
    "universal": ["universal"],
}

NAME_OVERRIDES = {
    "think": ["think"],
    "golden-path-verify": ["golden-path-verify"],
}

BODY_STUBS = {
    "changelog": "# Changelog\n\nUpdate CHANGELOG.md at project root — newest first, user-impact bullets, verification hints.",
    "verify-work": "# Verify work\n\n1. Review diff 2. Run tests 3. Fix failures 4. Confirm acceptance criteria.",
    "skill-authoring": "# Skill authoring\n\nFrontmatter + when_to_call + steps. Scaffold: `agentdrive skills init <name>`.",
    "systematic-debugging": "# Systematic debugging\n\nInvestigate → pattern → hypothesis → fix. No fixes before root cause.",
    "swarm-orchestrator": "# Swarm orchestrator\n\nDecompose, dispatch pawns, collect handoffs. Do not implement pawn tasks.",
    "swarm-worker": "# Swarm worker\n\nOne task, structured return: summary, files, tests, gaps.",
    "frontend-design": "# Frontend design\n\nPick aesthetic, typography, spacing, motion. Then implement.",
    "design-system": "# Design system\n\nTokens for color, type, spacing, components — single source of truth.",
    "web-artifact": "# Web artifact\n\nSelf-contained HTML or components; responsive and accessible.",
    "document-docx": "# Word document\n\nDeliver .docx with clear structure and formatting.",
    "document-xlsx": "# Spreadsheet\n\nDeliver xlsx/csv with correct formulas and clean data.",
    "document-pptx": "# Presentation\n\nDeliver .pptx with consistent slides and notes.",
    "parallel-attempts": "# Parallel attempts\n\nTry N approaches, score objectively, keep the best.",
}


def _find_skill_md(name: str, dirs: list[str]) -> Path | None:
    if name in NAME_OVERRIDES:
        for sub in NAME_OVERRIDES[name]:
            p = SKILLS_ROOT / sub / "SKILL.md"
            if p.exists():
                return p
    for d in dirs:
        p = SKILLS_ROOT / d / name / "SKILL.md"
        if p.exists():
            return p
    return None


def _ensure_skill_md(name: str, dirs: list[str]) -> Path:
    existing = _find_skill_md(name, dirs)
    if existing:
        return existing
    d = dirs[0]
    path = SKILLS_ROOT / d / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    stub = BODY_STUBS.get(name, f"# {name}\n")
    path.write_text(f"---\nname: {name}\n---\n\n{stub}\n", encoding="utf-8")
    return path


def _patch_frontmatter(path: Path, meta: dict) -> None:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    body = match.group(2).strip() if match else text.strip()
    if not match:
        body = BODY_STUBS.get(meta.get("name", ""), body)

    existing: dict = {}
    if match:
        loaded = yaml.safe_load(match.group(1)) or {}
        if isinstance(loaded, dict):
            existing = loaded

    for key in (
        "description",
        "role",
        "when_to_call",
        "tags",
        "agentdrive_operation",
        "argument",
        "category",
    ):
        if key in meta and meta[key] is not None:
            existing[key] = meta[key]
    if "operation" in meta:
        existing["agentdrive_operation"] = meta["operation"]
    existing["name"] = meta["name"]

    order = [
        "name",
        "description",
        "agentdrive_operation",
        "argument",
        "category",
        "role",
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
            if len(desc) > 100:
                lines.append("description: >")
                words = desc.replace("\n", " ").split()
                chunk: list[str] = []
                for w in words:
                    chunk.append(w)
                    if len(" ".join(chunk)) > 90:
                        lines.append("  " + " ".join(chunk))
                        chunk = []
                if chunk:
                    lines.append("  " + " ".join(chunk))
            else:
                lines.append(f'description: "{desc}"' if ":" in desc else f"description: {desc}")
        elif key == "tags" and isinstance(val, list):
            lines.append(f"tags: [{', '.join(str(t) for t in val)}]")
        else:
            lines.append(f"{key}: {val}")
    lines.append("---")
    path.write_text("\n".join(lines) + "\n\n" + body + "\n", encoding="utf-8")


def main() -> int:
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    updated = 0
    for section, entries in data.items():
        if not isinstance(entries, dict):
            continue
        dirs = SECTION_DIRS.get(section, [section])
        category = section

        for name, meta in entries.items():
            path = _ensure_skill_md(name, dirs)
            patch = dict(meta)
            patch["name"] = name
            patch.setdefault("category", category)
            _patch_frontmatter(path, patch)
            updated += 1
            print(f"  updated {name}")

    print(f"Applied catalog to {updated} skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())