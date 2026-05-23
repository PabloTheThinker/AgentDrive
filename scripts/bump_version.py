#!/usr/bin/env python3
"""
Simple version bumper for Savant.

Usage:
    python scripts/bump_version.py patch   # 0.1.0 -> 0.1.1
    python scripts/bump_version.py minor   # 0.1.0 -> 0.2.0
    python scripts/bump_version.py major   # 0.1.0 -> 1.0.0

Then commit and tag:
    git add pyproject.toml
    git commit -m "chore: bump version to X.Y.Z"
    git tag vX.Y.Z
    git push origin main --tags
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PYPROJECT = ROOT / "pyproject.toml"

def get_current_version() -> str:
    content = PYPROJECT.read_text()
    match = re.search(r'version\s*=\s*"([^"]+)"', content)
    if not match:
        raise RuntimeError("Could not find version in pyproject.toml")
    return match.group(1)

def bump_version(current: str, part: str) -> str:
    major, minor, patch = map(int, current.split("."))
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "patch":
        patch += 1
    else:
        raise ValueError("part must be major, minor, or patch")
    return f"{major}.{minor}.{patch}"

def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("major", "minor", "patch"):
        print("Usage: python scripts/bump_version.py [major|minor|patch]")
        sys.exit(1)

    part = sys.argv[1]
    current = get_current_version()
    new = bump_version(current, part)

    content = PYPROJECT.read_text()
    new_content = re.sub(
        r'(version\s*=\s*")([^"]+)(")',
        rf'\g<1>{new}\g<3>',
        content
    )
    PYPROJECT.write_text(new_content)

    print(f"Bumped version: {current} → {new}")
    print(f"Run: git add pyproject.toml && git commit -m 'chore: bump version to {new}'")
    print(f"Then: git tag v{new} && git push origin main --tags")

if __name__ == "__main__":
    main()