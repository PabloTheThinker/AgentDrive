#!/usr/bin/env python3
"""Sync vendor harness skills into examples/skills/vendors/{grok,claude,codex}/."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "examples" / "skills" / "vendor-manifest.yaml"
DEST = REPO / "examples" / "skills" / "vendors"

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def _expand(path: str) -> Path:
    return Path(path.replace("~", str(Path.home())))


def _extract_description(meta: dict, body: str) -> str:
    desc = meta.get("description", "")
    if isinstance(desc, str):
        return " ".join(desc.strip().split())[:500]
    return ""


def _wrap(
    *,
    name: str,
    harness: str,
    requires: str,
    description: str,
    body: str,
    backup_of: str,
    backup_path: str,
) -> str:
    desc_esc = description.replace('"', '\\"')
    return f"""---
name: {name}
description: "{desc_esc}"
category: vendors
harness: {harness}
requires: "{requires.replace('"', "'")}"
role: shared
tags: [{harness}, vendor, harness]
backup_of: {backup_of}
backup_path: {backup_path}
when_to_call: when running on the {harness} harness with its native tools; use universal/* via MCP otherwise
---

# {name} ({harness} harness)

> **Harness:** {harness} · **Requires:** {requires}
>
> Prefer the **universal/** counterpart when using AgentDrive MCP with any model.
> This copy preserves the native {harness} workflow and tool assumptions.

---

{body.strip()}
"""


def _sync_grok(cfg: dict) -> int:
    src_root = _expand(cfg["source_dir"])
    prefix = cfg.get("name_prefix", "grok-")
    harness = cfg["harness"]
    requires = cfg["requires"]
    dest_root = DEST / harness
    dest_root.mkdir(parents=True, exist_ok=True)
    count = 0
    if not src_root.is_dir():
        print(f"  SKIP grok — missing {src_root}")
        return 0
    for skill_dir in sorted(src_root.iterdir()):
        if not skill_dir.is_dir():
            continue
        src = skill_dir / "SKILL.md"
        if not src.is_file():
            continue
        text = src.read_text(encoding="utf-8")
        m = _FRONTMATTER.match(text)
        meta = yaml.safe_load(m.group(1)) if m else {}
        body = m.group(2) if m else text
        if not isinstance(meta, dict):
            meta = {}
        slug = skill_dir.name
        name = f"{prefix}{slug}" if not slug.startswith(prefix) else slug
        desc = _extract_description(meta, body) or f"{harness} harness skill: {slug}"
        out = dest_root / slug / "SKILL.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            _wrap(
                name=name,
                harness=harness,
                requires=requires,
                description=desc,
                body=body,
                backup_of=slug,
                backup_path=str(src),
            ),
            encoding="utf-8",
        )
        count += 1
        print(f"  grok/{slug} → {name}")
    return count


def _sync_mapped(vendor: str, cfg: dict) -> int:
    prefix = cfg.get("name_prefix", f"{vendor}-")
    harness = cfg["harness"]
    requires = cfg["requires"]
    dest_root = DEST / harness
    dest_root.mkdir(parents=True, exist_ok=True)
    count = 0
    for slug, spec in (cfg.get("skills") or {}).items():
        if isinstance(spec, str):
            src = _expand(spec)
            desc = f"{harness} harness skill: {slug}"
        else:
            src = _expand(spec["path"])
            desc = spec.get("description") or f"{harness} harness skill: {slug}"
        if not src.is_file():
            print(f"  SKIP {vendor}/{slug} — missing {src}")
            continue
        text = src.read_text(encoding="utf-8")
        m = _FRONTMATTER.match(text)
        body = m.group(2) if m else text
        name = f"{prefix}{slug}"
        out = dest_root / slug / "SKILL.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            _wrap(
                name=name,
                harness=harness,
                requires=requires,
                description=desc,
                body=body,
                backup_of=slug,
                backup_path=str(src),
            ),
            encoding="utf-8",
        )
        count += 1
        print(f"  {vendor}/{slug} → {name}")
    return count


def main() -> int:
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    total = 0
    if "grok" in data:
        total += _sync_grok(data["grok"])
    if "claude" in data:
        total += _sync_mapped("claude", data["claude"])
    if "codex" in data:
        total += _sync_mapped("codex", data["codex"])
    print(f"Synced {total} vendor skills → {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())